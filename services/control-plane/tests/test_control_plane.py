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


def test_admin_can_create_a_ready_to_login_account():
    with TestClient(app) as client:
        admin = login_admin(client)
        created = client.post("/api/v1/admin/users", headers=auth(admin["access_token"]), json={
            "email": "direct-user@example.com",
            "display_name": "直接开通用户",
            "password": "direct-user-password-123",
            "organization_name": "直接开通企业",
            "entitlement_days": 45,
            "device_limit": 2,
        })
        assert created.status_code == 200, created.text

        logged_in = client.post("/api/v1/auth/login", json={
            "email": "direct-user@example.com",
            "password": "direct-user-password-123",
            "device": device("direct-user-device-0001"),
        })
        assert logged_in.status_code == 200, logged_in.text
        assert logged_in.json()["user"]["display_name"] == "直接开通用户"


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


def test_device_is_blacklisted_after_ten_failed_logins_and_admin_can_unblock():
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "locked-device@example.com")
        locked_device = {
            "installation_id": "locked-device-0001",
            "name": "待锁定电脑",
            "fingerprint": "stable-locked-device-fingerprint",
            "app_version": "1.0.2-test",
        }

        for attempt in range(1, 10):
            failed = client.post("/api/v1/auth/login", json={
                "email": "locked-device@example.com",
                "password": "wrong-password-value",
                "device": locked_device,
            })
            assert failed.status_code == 401
            assert f"还可尝试 {10 - attempt} 次" in failed.text

        locked = client.post("/api/v1/auth/login", json={
            "email": "locked-device@example.com",
            "password": "wrong-password-value",
            "device": locked_device,
        })
        assert locked.status_code == 423
        assert "设备已锁定" in locked.text

        correct_password_cannot_bypass = client.post("/api/v1/auth/login", json={
            "email": "locked-device@example.com",
            "password": "user-password-123",
            "device": locked_device,
        })
        assert correct_password_cannot_bypass.status_code == 423

        blocks = client.get("/api/v1/admin/login-blocks", headers=auth(admin["access_token"]))
        assert blocks.status_code == 200
        block = next(item for item in blocks.json()["items"] if item["attempted_account"] == "locked-device@example.com")
        assert block["failed_attempts"] == 10
        assert block["device_name"] == "待锁定电脑"

        removed = client.delete(
            f"/api/v1/admin/login-blocks/{block['id']}",
            headers=auth(admin["access_token"]),
        )
        assert removed.status_code == 200

        login_after_unblock = client.post("/api/v1/auth/login", json={
            "email": "locked-device@example.com",
            "password": "user-password-123",
            "device": locked_device,
        })
        assert login_after_unblock.status_code == 200
        assert login_after_unblock.json()["user"]["id"] == user["user"]["id"]


def test_blacklisting_an_existing_device_revokes_its_sessions():
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "session-lock@example.com")
        existing_device = device("user-device-0001")

        for _ in range(10):
            client.post("/api/v1/auth/login", json={
                "email": "session-lock@example.com",
                "password": "wrong-password-value",
                "device": existing_device,
            })

        assert client.get("/api/v1/auth/me", headers=auth(user["access_token"])).status_code == 403
        assert client.post("/api/v1/auth/refresh", json={"refresh_token": user["refresh_token"]}).status_code in {401, 403}


def test_user_can_change_password_only_once_per_beijing_day():
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "password-change@example.com")
        changed = client.put("/api/v1/auth/password", headers=auth(user["access_token"]), json={
            "current_password": "user-password-123",
            "new_password": "new-user-password-456",
        })
        assert changed.status_code == 200, changed.text
        assert changed.json()["next_change_at"]

        second_change = client.put("/api/v1/auth/password", headers=auth(user["access_token"]), json={
            "current_password": "new-user-password-456",
            "new_password": "another-password-789",
        })
        assert second_change.status_code == 429
        assert "明天再试" in second_change.text

        old_password = client.post("/api/v1/auth/login", json={
            "email": "password-change@example.com",
            "password": "user-password-123",
            "device": device("password-change-device-0002"),
        })
        assert old_password.status_code == 401
        new_password = client.post("/api/v1/auth/login", json={
            "email": "password-change@example.com",
            "password": "new-user-password-456",
            "device": device("password-change-device-0002"),
        })
        assert new_password.status_code == 200


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
        client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json={"credits": 100},
        )
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
        from app.database import ModelRoute, SessionLocal
        with SessionLocal.begin() as db:
            route = db.get(ModelRoute, "text.fast")
            route.provider_model = "test-model"
            route.enabled = True
        funded = client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json={
                "credits": 10000,
                "payment_amount_micros": 100_000_000,
                "note": "内测充值",
                "reference_id": "beta-order-0001",
            },
        )
        assert funded.status_code == 200, funded.text

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


def test_admin_recharge_endpoint_grants_credits_and_switches_to_unified_billing():
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "recharge-api@example.com")

        # 普通用户从激活起即进入预付 Credits 模式，不再回退到免费配额。
        entitlements = client.get("/api/v1/entitlements", headers=auth(user["access_token"]))
        assert entitlements.json()["billing"]["mode"] == "credits"
        assert entitlements.json()["billing"]["balance"] == 0

        # 管理员充值 500 credits
        recharged = client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json={"credits": 500, "note": "内测充值"},
        )
        assert recharged.status_code == 200, recharged.text
        body = recharged.json()
        assert body["credits"] == 500
        assert body["balance"] == 500
        assert body["reference_id"]

        # 充值后进入统一计费（credits）模式
        entitlements = client.get("/api/v1/entitlements", headers=auth(user["access_token"]))
        assert entitlements.json()["billing"]["mode"] == "credits"
        assert entitlements.json()["billing"]["balance"] == 500

        billing = client.get("/api/v1/billing/summary", headers=auth(user["access_token"]))
        assert billing.json()["credited_credits"] == 500
        assert billing.json()["recharges"][0]["note"] == "内测充值"

        users = client.get("/api/v1/admin/users", headers=auth(admin["access_token"])).json()["items"]
        row = next(item for item in users if item["id"] == user["user"]["id"])
        assert row["credits"]["credited"] == 500


def test_recharge_reference_is_idempotent_in_the_new_ledger():
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "idempotent-credit@example.com")
        request = {"credits": 500, "reference_id": "operator-grant-0001"}
        first = client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json=request,
        )
        second = client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json=request,
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["balance"] == second.json()["balance"] == 500
        assert first.json()["idempotent"] is False
        assert second.json()["idempotent"] is True

        from app.database import CreditLedgerEntry, SessionLocal
        from sqlalchemy import func, select
        with SessionLocal() as db:
            count = db.scalar(select(func.count(CreditLedgerEntry.id)).where(
                CreditLedgerEntry.user_id == user["user"]["id"],
                CreditLedgerEntry.reference_id == "operator-grant-0001",
            ))
            assert count == 1


def test_same_email_and_wallets_are_isolated_between_products():
    from datetime import timedelta
    from app.database import Entitlement, Organization, Product, SessionLocal, User, utcnow
    from app.security import hash_password
    from app.wallets import ensure_wallet

    with TestClient(app) as client:
        with SessionLocal.begin() as db:
            public_product = db.get(Product, "xiaoyu_public")
            assert public_product is not None
            org = Organization(product_id="xiaoyu_public", name="小妤公域测试")
            db.add(org)
            db.flush()
            public_user = User(
                product_id="xiaoyu_public",
                organization_id=org.id,
                email="admin@example.com",
                display_name="公域同邮箱用户",
                password_hash=hash_password("public-user-password-123"),
            )
            db.add(public_user)
            db.flush()
            ensure_wallet(db, public_user)
            db.add(Entitlement(
                user_id=public_user.id,
                valid_until=utcnow() + timedelta(days=3650),
                device_limit=2,
                features={"billing_mode": "credits"},
                quotas={},
            ))
            public_user_id = public_user.id

        private_login = login_admin(client)
        public_login = client.post("/api/v1/auth/login", json={
            "product_id": "xiaoyu_public",
            "email": "admin@example.com",
            "password": "public-user-password-123",
            "device": device("public-device-0001"),
        })
        assert public_login.status_code == 200, public_login.text
        assert private_login["user"]["product_id"] == "szyg_private"
        assert public_login.json()["user"]["product_id"] == "xiaoyu_public"

        cross_product_grant = client.post(
            f"/api/v1/admin/users/{public_user_id}/credits",
            headers=auth(private_login["access_token"]),
            json={"credits": 100},
        )
        assert cross_product_grant.status_code == 404


def test_failed_provider_call_releases_wallet_reservation(monkeypatch):
    async def failing_chat(self, model, payload):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("app.provider.ProviderGateway.chat", failing_chat)
    with TestClient(app, raise_server_exceptions=False) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "release-hold@example.com")
        client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json={"credits": 100},
        )
        from app.database import CreditWallet, ModelRoute, SessionLocal
        from sqlalchemy import select
        with SessionLocal.begin() as db:
            route = db.get(ModelRoute, "text.fast")
            route.provider_model = "test-model"
            route.enabled = True
        failed = client.post("/api/v1/inference/chat", headers=auth(user["access_token"]), json={
            "capability": "text.fast",
            "payload": {"messages": [{"role": "user", "content": "hello"}]},
            "idempotency_key": "failed-provider-0001",
        })
        assert failed.status_code == 500
        with SessionLocal() as db:
            wallet = db.scalar(select(CreditWallet).where(CreditWallet.user_id == user["user"]["id"]))
            assert wallet.balance_micros == 100_000_000
            assert wallet.reserved_micros == 0


def test_alipay_notification_is_verified_and_credited_once(monkeypatch, tmp_path):
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from app.alipay import _canonical
    from app.main import settings

    merchant_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    alipay_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    merchant_path = tmp_path / "merchant.pem"
    alipay_public_path = tmp_path / "alipay-public.pem"
    merchant_path.write_bytes(merchant_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    alipay_public_path.write_bytes(alipay_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    monkeypatch.setattr(settings, "alipay_app_id", "2026000000000001")
    monkeypatch.setattr(settings, "alipay_merchant_private_key_file", str(merchant_path))
    monkeypatch.setattr(settings, "alipay_public_key_file", str(alipay_public_path))
    monkeypatch.setattr(settings, "alipay_seller_id", "2088000000000001")

    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "alipay-user@example.com")
        config = client.get("/api/v1/payments/config", headers=auth(user["access_token"]))
        assert config.json()["alipay_enabled"] is True
        created = client.post("/api/v1/payments/orders", headers=auth(user["access_token"]), json={
            "amount_cny": "12.34",
            "idempotency_key": "alipay-create-0001",
        })
        assert created.status_code == 200, created.text
        order = created.json()
        assert order["credits"] == 1234
        assert order["merchant_order_no"].startswith("SZY")
        assert order["payment_url"].startswith("https://openapi.alipay.com/gateway.do?")

        notification = {
            "app_id": settings.alipay_app_id,
            "seller_id": settings.alipay_seller_id,
            "out_trade_no": order["merchant_order_no"],
            "trade_no": "2026090922000000000001",
            "trade_status": "TRADE_SUCCESS",
            "total_amount": "12.34",
            "sign_type": "RSA2",
        }
        rejected = client.post("/api/v1/payments/alipay/notify", data=notification)
        assert rejected.status_code == 400
        before_payment = client.get("/api/v1/billing/summary", headers=auth(user["access_token"])).json()
        assert before_payment["balance_credits"] == 0
        signature = alipay_key.sign(
            _canonical(notification).encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        notification["sign"] = base64.b64encode(signature).decode("ascii")
        first = client.post("/api/v1/payments/alipay/notify", data=notification)
        second = client.post("/api/v1/payments/alipay/notify", data=notification)
        assert first.text == second.text == "success"

        status = client.get(f"/api/v1/payments/orders/{order['id']}", headers=auth(user["access_token"])).json()
        assert status["status"] == "paid"
        assert status["credited_at"]
        returned = client.get(
            "/api/v1/payments/alipay/return",
            params={"out_trade_no": order["merchant_order_no"]},
        )
        assert "支付成功" in returned.text
        assert "数字员工账户充值 1234.0 Credits" in returned.text
        billing = client.get("/api/v1/billing/summary", headers=auth(user["access_token"])).json()
        assert billing["balance_credits"] == 1234

        from app.database import CreditLedgerEntry, SessionLocal
        from sqlalchemy import func, select
        with SessionLocal() as db:
            count = db.scalar(select(func.count(CreditLedgerEntry.id)).where(
                CreditLedgerEntry.payment_order_id == order["id"],
            ))
            assert count == 1


def test_payment_branding_distinguishes_private_and_public_products():
    from app.main import _payment_product_brand

    assert _payment_product_brand("szyg_private") == ("SZY", "数字员工")
    assert _payment_product_brand("xiaoyu_public") == ("XY", "小妤数字员工")


def test_regular_user_without_credits_cannot_call_cloud_models():
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "prepaid-only@example.com")
        from app.database import ModelRoute, SessionLocal
        with SessionLocal.begin() as db:
            route = db.get(ModelRoute, "text.fast")
            route.provider_model = "deepseek-v4-flash-ga-260731"
            route.enabled = True

        response = client.post(
            "/api/v1/inference/chat",
            headers=auth(user["access_token"]),
            json={
                "capability": "text.fast",
                "payload": {"messages": [{"role": "user", "content": "hello"}]},
                "idempotency_key": "no-credit-request-0001",
                "app_version": "1.0.0-test",
            },
        )
        assert response.status_code == 429
        assert "余额不足" in response.text


def test_inflight_video_reservation_prevents_credit_overspend(monkeypatch):
    calls = 0

    async def fake_create_video(self, model, payload):
        nonlocal calls
        calls += 1
        return {"id": f"provider-video-{calls}"}, f"provider-request-{calls}"

    monkeypatch.setattr("app.provider.ProviderGateway.create_video", fake_create_video)
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "video-hold@example.com")
        client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json={"credits": 1000},
        )
        from app.database import ModelRoute, SessionLocal
        with SessionLocal.begin() as db:
            route = db.get(ModelRoute, "video.standard")
            route.provider_model = "doubao-seedance-2.0"
            route.enabled = True

        payload = {
            "capability": "video.standard",
            "payload": {"duration": 4, "resolution": "720p"},
            "idempotency_key": "video-hold-request-0001",
            "app_version": "1.0.0-test",
        }
        first = client.post("/api/v1/inference/video/tasks", headers=auth(user["access_token"]), json=payload)
        assert first.status_code == 200, first.text

        payload["idempotency_key"] = "video-hold-request-0002"
        second = client.post("/api/v1/inference/video/tasks", headers=auth(user["access_token"]), json=payload)
        assert second.status_code == 429
        assert "余额不足" in second.text
        assert calls == 1


def test_presenter_video_uses_separate_route_and_reference_upload(monkeypatch):
    """数字人视频现在走专用端点：OmniHuman1.5 走 /omni-human/tasks + CV 平台，
    不再复用 video.standard 路径。这条测试验证端点分流。
    """
    calls = []
    async def fake_duration(url):
        return 4
    monkeypatch.setattr("app.main._uploaded_audio_seconds", fake_duration)
    async def fake_omni_submit(self, model, payload):
        calls.append((model, payload))
        return {"task_id": "provider-presenter-1", "model": model}, "provider-request-presenter"

    monkeypatch.setattr("app.provider.ProviderGateway.omni_human_submit", fake_omni_submit)
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "presenter@example.com")
        client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json={"credits": 1000},
        )
        uploaded = client.post(
            "/api/v1/inference/references",
            headers=auth(user["access_token"]),
            files={"file": ("avatar.png", b"virtual-avatar", "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        from urllib.parse import urlsplit
        ref = urlsplit(uploaded.json()["url"])
        fetched = client.get(f"{ref.path}?{ref.query}")
        assert fetched.status_code == 200
        assert fetched.content == b"virtual-avatar"

        # 启用 video.omnihuman 路由（默认 disabled，因为测试环境无 CV 凭据）
        from app.database import ModelRoute, SessionLocal
        with SessionLocal.begin() as db:
            route = db.get(ModelRoute, "video.omnihuman")
            route.provider_model = "jimeng_realman_avatar_picture_omni_v15"
            route.enabled = True

        created = client.post(
            "/api/v1/inference/omni-human/tasks",
            headers=auth(user["access_token"]),
            json={
                "capability": "video.omnihuman",
                "payload": {
                    "image_url": "https://example.com/avatar.png",
                    "audio_url": "https://example.com/speech.mp3",
                    "duration": 4,
                    "output_resolution": 720,
                },
                "idempotency_key": "presenter-video-request-0001",
                "app_version": "1.1.3-test",
            },
        )
        assert calls, f"Mock not called; got {created.status_code} {created.text}"
        assert created.status_code == 200, created.text
        from app.database import SessionLocal, VideoTask
        with SessionLocal() as db:
            task = db.get(VideoTask, created.json()["task_id"])
            assert task.model_alias == "video.omnihuman"

        async def fake_done(self, task_id, **kwargs):
            return {"status": "done", "video_url": "https://media.test/result.mp4"}, "omni-query"
        monkeypatch.setattr("app.provider.ProviderGateway.omni_human_get", fake_done)
        result_url = "/api/v1/inference/omni-human/tasks/" + created.json()["task_id"]
        assert client.get(result_url, headers=auth(user["access_token"])).json()["status"] == "done"
        from app.database import UsageEvent
        with SessionLocal() as db:
            event = db.get(UsageEvent, created.json()["request_id"])
            assert event.status == "succeeded"
            assert event.provider_cost_micros == 4_000_000
            charged = event.credits_charged_micros
        async def fake_expired(self, task_id, **kwargs):
            return {"status": "expired", "video_url": ""}, "omni-query-later"
        monkeypatch.setattr("app.provider.ProviderGateway.omni_human_get", fake_expired)
        client.get(result_url, headers=auth(user["access_token"]))
        with SessionLocal() as db:
            event = db.get(UsageEvent, created.json()["request_id"])
            assert event.status == "succeeded"
            assert event.credits_charged_micros == charged


def test_asr_success_persists_settlement(monkeypatch):
    async def fake_asr(self, model, payload):
        return {"text": "识别结果", "duration_ms": 6312}, "asr-smoke"
    monkeypatch.setattr("app.provider.ProviderGateway.asr_transcribe", fake_asr)
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "asr-settlement@example.com")
        client.post(f"/api/v1/admin/users/{user['user']['id']}/credits", headers=auth(admin["access_token"]), json={"credits": 10})
        from app.database import ModelRoute, SessionLocal, UsageEvent
        with SessionLocal.begin() as db:
            route = db.get(ModelRoute, "speech.asr")
            route.provider_model = "volc.seedasr.auc"
            route.enabled = True
        res = client.post("/api/v1/inference/asr", headers=auth(user["access_token"]), json={"capability": "speech.asr", "payload": {"audio_url": "https://media.test/a.wav"}, "idempotency_key": "asr-settlement-check"})
        assert res.status_code == 200, res.text
        with SessionLocal() as db:
            event = db.get(UsageEvent, res.json()["request_id"])
            assert event.status == "succeeded"
            assert event.provider_cost_micros == 1403
            assert event.credits_charged_micros > 0


def test_admin_recharge_endpoint_validates_inputs():
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "recharge-validate@example.com")

        missing = client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json={"credits": 0},
        )
        assert missing.status_code == 422

        unknown_user = client.post(
            "/api/v1/admin/users/does-not-exist/credits",
            headers=auth(admin["access_token"]),
            json={"credits": 10},
        )
        assert unknown_user.status_code == 404


def test_unified_credits_gating_returns_429_when_balance_insufficient(monkeypatch):
    async def fake_chat(self, model, payload):
        return {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"total_tokens": 25},
        }, "provider-request-low-credit"

    monkeypatch.setattr("app.provider.ProviderGateway.chat", fake_chat)
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "low-credit@example.com")

        # 开通 credits 但余额极低（0.000001 → 1 micro），远不足以完成一次估算
        funded = client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json={"credits": 0.000001},
        )
        assert funded.status_code == 200

        from app.database import ModelRoute, SessionLocal
        with SessionLocal.begin() as db:
            route = db.get(ModelRoute, "text.fast")
            route.provider_model = "test-model"
            route.enabled = True

        response = client.post(
            "/api/v1/inference/chat",
            headers=auth(user["access_token"]),
            json={
                "capability": "text.fast",
                "payload": {"messages": [{"role": "user", "content": "hello"}]},
                "idempotency_key": "low-credit-0001",
                "app_version": "1.0.0-test",
            },
        )
        assert response.status_code == 429
        assert "余额不足" in response.text


def test_unified_credits_are_deducted_after_successful_inference(monkeypatch):
    async def fake_chat(self, model, payload):
        return {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"input_tokens": 1000, "output_tokens": 100},
        }, "provider-request-credits"

    monkeypatch.setattr("app.provider.ProviderGateway.chat", fake_chat)
    with TestClient(app) as client:
        admin = login_admin(client)
        user = invite_and_activate(client, admin["access_token"], "spend-credit@example.com")

        client.post(
            f"/api/v1/admin/users/{user['user']['id']}/credits",
            headers=auth(admin["access_token"]),
            json={"credits": 1000},
        )

        from app.database import ModelRoute, SessionLocal
        with SessionLocal.begin() as db:
            route = db.get(ModelRoute, "text.fast")
            route.provider_model = "test-model"
            route.enabled = True

        inference = client.post(
            "/api/v1/inference/chat",
            headers=auth(user["access_token"]),
            json={
                "capability": "text.fast",
                "payload": {"messages": [{"role": "user", "content": "hello"}]},
                "idempotency_key": "spend-credit-0001",
                "app_version": "1.0.0-test",
            },
        )
        assert inference.status_code == 200, inference.text

        entitlements = client.get("/api/v1/entitlements", headers=auth(user["access_token"]))
        balance = entitlements.json()["billing"]["balance"]
        assert entitlements.json()["billing"]["mode"] == "credits"
        assert balance < 1000
        assert balance == 1000 - settle_credits_for_payload()


def settle_credits_for_payload() -> float:
    from app.usage_accounting import settle_usage
    _, _, credits_micros, _, _ = settle_usage(
        "text.fast",
        {"usage": {"input_tokens": 1000, "output_tokens": 100}},
        {"messages": [{"role": "user", "content": "hello"}]},
        {},
    )
    return credits_micros / 1_000_000


def test_expired_entitlement_is_renewed_instead_of_blocking():
    """授权到期机制已取消：过期授权在登录时自动续期，不再返回 403。"""
    from datetime import timedelta

    from sqlalchemy import select

    from app.database import Entitlement, SessionLocal, User
    from app.main import utcnow

    with TestClient(app) as client:
        admin = login_admin(client)
        created = client.post("/api/v1/admin/users", headers=auth(admin["access_token"]), json={
            "email": "expired-user@example.com",
            "display_name": "过期续期用户",
            "password": "expired-user-password-123",
            "organization_name": "过期续期企业",
            "entitlement_days": 1,
            "device_limit": 2,
        })
        assert created.status_code == 200, created.text

        # 人为把授权改为已过期
        with SessionLocal.begin() as db:
            user = db.scalar(select(User).where(User.email == "expired-user@example.com"))
            entitlement = db.scalar(select(Entitlement).where(Entitlement.user_id == user.id))
            entitlement.valid_until = utcnow() - timedelta(days=1)

        # 登录不再因授权到期被拦截（旧逻辑返回 403 服务授权已到期）
        logged_in = client.post("/api/v1/auth/login", json={
            "email": "expired-user@example.com",
            "password": "expired-user-password-123",
            "device": device("expired-user-device-0001"),
        })
        assert logged_in.status_code == 200, logged_in.text

        # 授权被自动续期为长期有效
        view = client.get("/api/v1/entitlements", headers=auth(logged_in.json()["access_token"]))
        assert view.status_code == 200, view.text
        assert view.json()["status"] == "active"
        assert str(view.json()["valid_until"]) > str(logged_in.json()["license"]["offline_valid_until"])

def test_entitlements_endpoint_renews_expired_entitlement():
    """GET /api/v1/entitlements 也应自动续期过期授权（刷新授权状态按钮不再显示过期）。"""
    from datetime import timedelta

    from sqlalchemy import select

    from app.database import Entitlement, SessionLocal, User
    from app.main import utcnow

    with TestClient(app) as client:
        admin = login_admin(client)
        created = client.post("/api/v1/admin/users", headers=auth(admin["access_token"]), json={
            "email": "refresh-expired@example.com",
            "display_name": "刷新续期用户",
            "password": "refresh-expired-password-123",
            "organization_name": "刷新续期企业",
            "entitlement_days": 1,
            "device_limit": 2,
        })
        assert created.status_code == 200, created.text

        # 先正常登录拿 token，再把授权人为改为已过期
        logged_in = client.post("/api/v1/auth/login", json={
            "email": "refresh-expired@example.com",
            "password": "refresh-expired-password-123",
            "device": device("refresh-expired-device-0001"),
        })
        assert logged_in.status_code == 200, logged_in.text
        with SessionLocal.begin() as db:
            user = db.scalar(select(User).where(User.email == "refresh-expired@example.com"))
            entitlement = db.scalar(select(Entitlement).where(Entitlement.user_id == user.id))
            entitlement.valid_until = utcnow() - timedelta(days=1)

        # 直接查 entitlements（模拟桌面端「刷新授权状态」），应自动续期返回 200
        view = client.get("/api/v1/entitlements", headers=auth(logged_in.json()["access_token"]))
        assert view.status_code == 200, view.text
        assert view.json()["status"] == "active"
        assert str(view.json()["valid_until"]) > str(logged_in.json()["license"]["offline_valid_until"])
