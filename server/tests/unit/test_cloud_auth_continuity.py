from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from time import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from szyg.cloud_auth import CloudAuthError, CloudAuthManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("SZYG_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SZYG_PRODUCT_ID", "xiaoyu_public")
    monkeypatch.setenv("SZYG_CLOUD_ENABLED", "true")
    monkeypatch.setenv("SZYG_CONTROL_URL", "https://accounts.example.invalid")
    return CloudAuthManager()


def session_data(number=1, *, user="u1", expires=None):
    return {
        "user": {"id": user}, "device": {"id": "d1"}, "access_token": f"{user}-access-{number}",
        "refresh_token": f"{user}-refresh-{number}",
        "access_expires_at": datetime.fromtimestamp(expires or time() + 900, timezone.utc).isoformat(),
    }


def denial(status):
    error = CloudAuthError("登录状态已失效")
    error.status_code = status
    return error


def test_racing_unauthorized_requests_share_one_rotation(manager, monkeypatch):
    first = session_data()
    manager._accept_session(first)
    calls = []

    def refresh(method, path, *, json_body):
        assert path == "/api/v1/auth/refresh"
        calls.append(json_body["refresh_token"])
        return session_data(2)

    monkeypatch.setattr(manager, "_request", refresh)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: manager.access_token(force_refresh=True, rejected_token=first["access_token"]), range(24)))
    assert results == ["u1-access-2"] * 24
    assert calls == ["u1-refresh-1"]
    manager._accept_session(session_data(user="u2"))
    with pytest.raises(CloudAuthError, match="已变更"):
        manager.access_token(force_refresh=True, rejected_token=first["access_token"])
    assert manager.active_user_id == "u2"


def test_account_status_recovers_expired_access_without_dropping_workspace(manager, monkeypatch):
    first = session_data()
    manager._accept_session(first)
    calls = []

    def request(method, path, *, token="", json_body=None):
        calls.append(path)
        if path.endswith("/refresh"):
            return session_data(2)
        if token == first["access_token"]:
            raise denial(401)
        assert token == "u1-access-2"
        return {"user": first["user"], "device": first["device"]}

    monkeypatch.setattr(manager, "_request", request)
    assert manager.session()["authenticated"]
    assert calls == ["/api/v1/auth/me", "/api/v1/auth/refresh", "/api/v1/auth/me"]


def test_active_account_keeps_renewing_across_months_and_restart(manager, monkeypatch):
    now = [time()]
    monkeypatch.setattr("szyg.cloud_auth.time.time", lambda: now[0])
    issued = [1]
    next_refresh_expires = [now[0] + 30 * 86400]

    def request(method, path, *, token="", json_body=None):
        if path.endswith("/refresh"):
            assert now[0] < next_refresh_expires[0]
            assert json_body["refresh_token"] == f"u1-refresh-{issued[0]}"
            issued[0] += 1
            next_refresh_expires[0] = now[0] + 30 * 86400
            return session_data(issued[0], expires=now[0] + 900)
        assert token == f"u1-access-{issued[0]}"
        return {"user": {"id": "u1"}, "device": {"id": "d1"}}

    manager._accept_session(session_data(expires=now[0] + 900))
    monkeypatch.setattr(manager, "_request", request)
    now[0] += 840  # User is active shortly before the access token's expiry.
    assert manager.access_token() == "u1-access-2"
    for _ in range(5):
        now[0] += 24 * 86400
        manager = CloudAuthManager()
        monkeypatch.setattr(manager, "_request", request)
        assert manager.session()["authenticated"]
    assert issued[0] == 7


@pytest.fixture
def offline_credentials(manager):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    creds = session_data()
    manager._profile = {"user": creds["user"], "device": creds["device"]}

    def issue(**overrides):
        claims = {"sub": "u1", "product": "xiaoyu_public", "device": "d1", "type": "offline_license", "exp": int(time() + 300), **overrides}
        token = jwt.encode(claims, private_key, algorithm="RS256")
        manager._save_refresh(creds["refresh_token"], {"license_token": token}, key)

    return issue


@pytest.mark.parametrize("claims,accepted", [
    ({}, True), ({"sub": "other"}, False), ({"product": "szyg_private"}, False),
    ({"device": "other"}, False), ({"exp": 1}, False),
])
def test_offline_restart_requires_matching_signed_grant(manager, monkeypatch, offline_credentials, claims, accepted):
    offline_credentials(**claims)

    def unavailable(*args, **kwargs):
        raise CloudAuthError("云账户服务暂时不可用")

    monkeypatch.setattr(manager, "_request", unavailable)
    result = manager.session()
    assert result["authenticated"] is accepted
    assert result.get("offline", False) is accepted
    assert result.get("unavailable", False) is not accepted
    assert manager._load_refresh() == "u1-refresh-1"


@pytest.mark.parametrize("status", [401, 403, 423])
def test_denied_refresh_discards_even_a_valid_offline_license(manager, monkeypatch, offline_credentials, status):
    offline_credentials()

    def revoked(*args, **kwargs):
        raise denial(status)

    monkeypatch.setattr(manager, "_request", revoked)
    assert not manager.session()["authenticated"]
    assert not manager._session_file.exists()
    assert not manager.active_user_id
    assert not manager.session()["authenticated"]


def test_explicit_logout_revokes_locally_before_remote_call(manager, monkeypatch):
    manager._accept_session(session_data())
    pending = []
    manager.logout(defer=lambda *job: pending.append(job))
    assert not manager.session()["authenticated"]
    assert not manager._session_file.exists()
    assert not manager.active_user_id
    manager._accept_session(session_data(user="u2"))
    received = []

    def request(method, path, *, json_body):
        received.append((path, json_body["refresh_token"]))

    monkeypatch.setattr(manager, "_request", request)
    revoke, old_token = pending.pop()
    revoke(old_token)
    assert received == [("/api/v1/auth/logout", "u1-refresh-1")]
    assert manager.active_user_id == "u2"


def test_unavailable_service_does_not_report_expired_entitlement_or_authorize_local_mcp(manager, monkeypatch):
    manager._accept_session(session_data(expires=time()-10))

    def unavailable(*args, **kwargs):
        raise CloudAuthError("云账户服务暂时不可用")

    monkeypatch.setattr(manager, "_request", unavailable)
    assert not manager.active_user_id
    assert manager.refresh_status() == {"configured": True, "expired": None, "message": "云账户服务暂时不可用"}
    assert manager._load_refresh() == "u1-refresh-1"
