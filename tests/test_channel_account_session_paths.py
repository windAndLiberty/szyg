from pathlib import Path

from szyg import channel_accounts


def test_missing_session_path_does_not_resolve_to_working_directory(tmp_path, monkeypatch):
    expected = tmp_path / "sessions" / "storage_state_douyin.json"
    monkeypatch.setattr(channel_accounts, "legacy_session_path", lambda _platform: expected)

    resolved = channel_accounts.resolve_account_session_path({
        "id": "douyin_default", "platform": "douyin", "is_default": True,
    })

    assert resolved == expected
    assert resolved != Path(".")


def test_stale_absolute_session_path_is_repaired_to_current_data_dir(tmp_path, monkeypatch):
    expected = tmp_path / "sessions" / "accounts" / "douyin" / "account-1" / "storage_state.json"
    expected.parent.mkdir(parents=True)
    expected.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(channel_accounts, "account_session_path", lambda _platform, _account_id: expected)

    resolved = channel_accounts.resolve_account_session_path({
        "id": "account-1", "platform": "douyin", "session_path": "D:/old/data/storage_state.json",
    })

    assert resolved == expected
