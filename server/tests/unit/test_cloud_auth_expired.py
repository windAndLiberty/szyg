from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def manager(tmp_path, monkeypatch):
    import szyg.cloud_auth as cloud_auth_module

    monkeypatch.setattr(cloud_auth_module, "_dpapi", lambda value, decrypt=False: value)
    monkeypatch.setenv("SZYG_CLOUD_ENABLED", "true")
    monkeypatch.setenv("SZYG_CONTROL_URL", "https://ctrl.test")
    m = cloud_auth_module.CloudAuthManager()
    m._root = tmp_path
    m._session_file = tmp_path / "session.json"
    m._device_file = tmp_path / "device.json"
    monkeypatch.setattr(cloud_auth_module, "cloud_auth", m)
    return m


def test_note_auth_error_records_only_authorization_messages(manager):
    manager.note_auth_error("服务授权已到期，请联系管理员")
    assert manager._auth_error == "服务授权已到期，请联系管理员"
    manager.note_auth_error("设备已被移除")
    assert manager._auth_error == "服务授权已到期，请联系管理员"  # not overwritten
    manager.note_auth_error("账户暂不可用")
    assert manager._auth_error == "账户暂不可用"


def test_clear_auth_error(manager):
    manager.note_auth_error("服务授权已到期")
    manager.clear_auth_error()
    assert manager._auth_error == ""


def test_session_includes_authorization_error_when_set(manager, monkeypatch):
    manager._auth_error = "服务授权已到期"

    def fake_access_token(*, force_refresh: bool = False) -> str:
        return "access-1"

    def fake_request(method, path, *, token="", json_body=None):
        return {"user": {"id": "u1", "email": "e@e.com"}, "device": {"id": "d1", "name": "PC"}}

    monkeypatch.setattr(manager, "access_token", fake_access_token)
    monkeypatch.setattr(manager, "_request", fake_request)

    result = manager.session()
    assert result["authenticated"] is True
    assert result["authorization_error"] == "服务授权已到期"


def test_session_does_not_set_authorization_error_when_clean(manager, monkeypatch):
    def fake_access_token(*, force_refresh: bool = False) -> str:
        return "access-1"

    def fake_request(method, path, *, token="", json_body=None):
        return {"user": {"id": "u1"}, "device": {"id": "d1"}}

    monkeypatch.setattr(manager, "access_token", fake_access_token)
    monkeypatch.setattr(manager, "_request", fake_request)
    result = manager.session()
    assert result["authenticated"] is True
    assert "authorization_error" not in result


def test_session_records_auth_error_on_403_exc(manager, monkeypatch):
    import szyg.cloud_auth as cloud_auth_module

    def fake_access_token(*, force_refresh: bool = False) -> str:
        raise cloud_auth_module.CloudAuthError("服务授权已到期")

    monkeypatch.setattr(manager, "access_token", fake_access_token)
    result = manager.session()
    assert manager._auth_error == "服务授权已到期"
    # 401 (请先登录) 路径不应触发授权标记
    assert result["authenticated"] is False


def test_accept_session_clears_auth_error(manager):
    manager._auth_error = "服务授权已到期"
    manager._accept_session({
        "access_token": "a",
        "refresh_token": "r",
        "user": {"id": "u"},
        "device": {"id": "d"},
    })
    assert manager._auth_error == ""


def test_refresh_status_returns_expired_when_entitlement_inactive(manager, monkeypatch):
    import szyg.cloud_auth as cloud_auth_module

    calls = {"access_token": 0, "proxy": []}

    def fake_access_token(*, force_refresh: bool = False) -> str:
        calls["access_token"] += 1
        return "access"

    def fake_proxy(method, path, body=None):
        calls["proxy"].append((method, path))
        return {
            "status": "expired",
            "valid_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        }

    monkeypatch.setattr(manager, "access_token", fake_access_token)
    monkeypatch.setattr(manager, "proxy", fake_proxy)

    result = manager.refresh_status()
    assert result["expired"] is True
    assert result["authorization_error"]
    assert manager._auth_error  # 记录以便下次 session() 透出
    assert calls["access_token"] == 1
    assert calls["proxy"] == [("GET", "/api/v1/entitlements")]


def test_refresh_status_clears_auth_error_when_active(manager, monkeypatch):
    manager._auth_error = "服务授权已到期"

    def fake_access_token(*, force_refresh: bool = False) -> str:
        return "access"

    def fake_proxy(method, path, body=None):
        return {
            "status": "active",
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

    monkeypatch.setattr(manager, "access_token", fake_access_token)
    monkeypatch.setattr(manager, "proxy", fake_proxy)

    result = manager.refresh_status()
    assert result["expired"] is False
    assert manager._auth_error == ""


def test_refresh_status_handles_403_from_control_plane(manager, monkeypatch):
    import szyg.cloud_auth as cloud_auth_module

    def fake_access_token(*, force_refresh: bool = False) -> str:
        raise cloud_auth_module.CloudAuthError("服务授权已到期")

    monkeypatch.setattr(manager, "access_token", fake_access_token)
    result = manager.refresh_status()
    assert result["expired"] is True
    assert result["authorization_error"] == "服务授权已到期"
