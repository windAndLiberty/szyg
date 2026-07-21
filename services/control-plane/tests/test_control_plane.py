from fastapi.testclient import TestClient

from app.main import app


def device(installation_id: str):
    return {
        "installation_id": installation_id,
        "name": f"PC {installation_id[-1]}",
        "fingerprint": f"fingerprint-{installation_id}",
        "app_version": "1.0.0-test",
    }


def login_admin(client: TestClient) -> dict:
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@example.com",
        "password": "correct-horse-battery-staple",
        "device": device("admin-device-0001"),
    })
    assert response.status_code == 200, response.text
    return response.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def invite_and_activate(client: TestClient, admin_token: str, email: str = "user@example.com") -> dict:
    invitation = client.post("/api/v1/admin/invitations", headers=auth(admin_token), json={
        "email": email,
        "organization_name": "测试企业",
        "entitlement_days": 30,
        "device_limit": 2,
        "quotas": {"text_tokens": 2000},
    })
    assert invitation.status_code == 200, invitation.text
    activated = client.post("/api/v1/auth/activate", json={
        "invitation_code": invitation.json()["invitation_code"],
        "display_name": "内测用户",
        "password": "user-password-123",
        "device": device("user-device-0001"),
    })
    assert activated.status_code == 200, activated.text
    return activated.json()


def test_invitation_activation_device_limit_and_session_rotation():
    with TestClient(app) as client:
        license_key = client.get("/api/v1/auth/license-key")
        assert license_key.status_code == 200
        assert license_key.json() == {"algorithm": "HS256", "public_key": ""}
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"])
        assert user["user"]["email"] == "user@example.com"
        assert user["license"]["offline_valid_until"]

        second = client.post("/api/v1/auth/login", json={
            "email": "user@example.com",
            "password": "user-password-123",
            "device": device("user-device-0002"),
        })
        assert second.status_code == 200
        third = client.post("/api/v1/auth/login", json={
            "email": "user@example.com",
            "password": "user-password-123",
            "device": device("user-device-0003"),
        })
        assert third.status_code == 403
        assert "2台" in third.text

        refresh_token = user["refresh_token"]
        rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert rotated.status_code == 200
        replay = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert replay.status_code == 401


def test_user_isolation_suspend_and_header_spoofing():
    with TestClient(app) as client:
        admin = login_admin(client)
        first = invite_and_activate(client, admin["access_token"], "first@example.com")
        second = invite_and_activate(client, admin["access_token"], "second@example.com")

        devices = client.get(
            "/api/v1/devices",
            headers={**auth(first["access_token"]), "X-OEM-ID": second["user"]["organization_id"]},
        )
        assert devices.status_code == 200
        assert all(item["installation_id"].startswith("user-device") for item in devices.json()["items"])
        assert len(devices.json()["items"]) == 1

        suspended = client.put(
            f"/api/v1/admin/users/{first['user']['id']}/status",
            headers=auth(admin["access_token"]),
            json={"status": "suspended"},
        )
        assert suspended.status_code == 200
        assert client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
        assert client.get("/api/v1/auth/me", headers=auth(first["access_token"])).status_code == 403


def test_idempotency_prevents_duplicate_usage(monkeypatch):
    async def fake_chat(self, model, payload):
        return {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"total_tokens": 25},
        }, "provider-request-1"

    monkeypatch.setattr("app.provider.ProviderGateway.chat", fake_chat)
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "usage@example.com")
        from app.database import ModelRoute, SessionLocal
        with SessionLocal.begin() as db:
            route = db.get(ModelRoute, "text.fast")
            route.provider_model = "test-model"
            route.enabled = True

        request = {
            "capability": "text.fast",
            "payload": {"messages": [{"role": "user", "content": "hello"}]},
            "idempotency_key": "same-request-0001",
            "app_version": "1.0.0-test",
        }
        first = client.post("/api/v1/inference/chat", headers=auth(user["access_token"]), json=request)
        second = client.post("/api/v1/inference/chat", headers=auth(user["access_token"]), json=request)
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        summary = client.get("/api/v1/usage/summary", headers=auth(user["access_token"]))
        assert summary.json()["used"]["text_tokens"] == 25
        assert summary.json()["period"] == "day"
        assert summary.json()["timezone"] == "Asia/Shanghai"
        assert summary.json()["today_credits"] > 0


def test_admin_recharge_and_user_billing_summary(monkeypatch):
    async def fake_chat(self, model, payload):
        return {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"input_tokens": 1000, "output_tokens": 100},
        }, "provider-request-billing"

    monkeypatch.setattr("app.provider.ProviderGateway.chat", fake_chat)
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "billing@example.com")
        from app.database import CreditTransaction, ModelRoute, SessionLocal
        with SessionLocal.begin() as db:
            route = db.get(ModelRoute, "text.fast")
            route.provider_model = "test-model"
            route.enabled = True
            db.add(CreditTransaction(
                organization_id=user["user"]["organization_id"],
                user_id=user["user"]["id"],
                kind="recharge",
                credits_micros=10_000_000_000,
                payment_amount_micros=100_000_000,
                note="内测充值",
                reference_id="beta-order-0001",
                created_by=admin["user"]["id"],
            ))

        inference = client.post("/api/v1/inference/chat", headers=auth(user["access_token"]), json={
            "capability": "text.fast",
            "payload": {"messages": [{"role": "user", "content": "hello"}]},
            "idempotency_key": "billing-usage-0001",
            "app_version": "1.0.0-test",
        })
        assert inference.status_code == 200, inference.text

        billing = client.get("/api/v1/billing/summary", headers=auth(user["access_token"]))
        assert billing.status_code == 200, billing.text
        payload = billing.json()
        assert payload["credited_credits"] == 10000
        assert payload["today_credits"] > 0
        assert payload["balance_credits"] < 10000
        assert payload["recharges"][0]["note"] == "内测充值"
        assert payload["breakdown"][0]["capability"] == "text.fast"
        assert payload["recent_usage"][0]["credits"] > 0
        users = client.get("/api/v1/admin/users", headers=auth(admin["access_token"])).json()["items"]
        row = next(item for item in users if item["id"] == user["user"]["id"])
        assert row["credits"]["credited"] == 10000
        assert row["credits"]["balance"] == payload["balance_credits"]
