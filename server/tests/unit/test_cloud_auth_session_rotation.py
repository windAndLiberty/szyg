import json
import os
import stat


def test_rotated_refresh_token_survives_optional_key_lookup_failure(tmp_path, monkeypatch):
    import szyg.cloud_auth as cloud_auth_module

    monkeypatch.setattr(cloud_auth_module, "_dpapi", lambda value, decrypt=False: value)
    manager = cloud_auth_module.CloudAuthManager()
    manager._root = tmp_path
    manager._session_file = tmp_path / "session.json"
    manager._device_file = tmp_path / "device.json"

    def fail_key_lookup(*args, **kwargs):
        raise cloud_auth_module.CloudAuthError("temporary network failure")

    monkeypatch.setattr(manager, "_request", fail_key_lookup)
    result = manager._accept_session({
        "access_token": "access-new",
        "refresh_token": "refresh-new",
        "user": {"id": "user-1", "email": "tester@example.com"},
        "device": {"id": "device-1", "name": "Test PC"},
        "license": {"license_token": "offline-license"},
    })

    assert result["authenticated"] is True
    assert manager._load_refresh() == "refresh-new"
    cached = json.loads(manager._session_file.read_text(encoding="utf-8"))
    assert cached["license"]["license_token"] == "offline-license"
    if os.name != "nt":
        assert stat.S_IMODE(manager._session_file.stat().st_mode) == 0o600


def test_refresh_save_preserves_cached_offline_license(tmp_path, monkeypatch):
    import szyg.cloud_auth as cloud_auth_module

    monkeypatch.setattr(cloud_auth_module, "_dpapi", lambda value, decrypt=False: value)
    manager = cloud_auth_module.CloudAuthManager()
    manager._root = tmp_path
    manager._session_file = tmp_path / "session.json"
    manager._device_file = tmp_path / "device.json"
    manager._profile = {"user": {"id": "user-1"}, "device": {"id": "device-1"}}
    manager._save_refresh("refresh-old", {"license_token": "keep-me"}, "public-key")
    manager._save_refresh("refresh-new")

    cached = json.loads(manager._session_file.read_text(encoding="utf-8"))
    assert manager._load_refresh() == "refresh-new"
    assert cached["license"]["license_token"] == "keep-me"
    assert cached["public_key"] == "public-key"
