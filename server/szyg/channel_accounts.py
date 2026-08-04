"""Channel account registry for account-level publishing."""

from __future__ import annotations

import re
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path

from szyg.atomic_file import atomic_read, atomic_write
from szyg.data_path import DATA_DIR

ACCOUNTS_FILE = DATA_DIR / "channel_accounts.json"
PROFILES_FILE = DATA_DIR / "publishing_profiles.json"
SESSIONS_DIR = DATA_DIR / "sessions"
ACCOUNT_SESSIONS_DIR = SESSIONS_DIR / "accounts"
SAU_COOKIES_DIR = DATA_DIR / "social_auto_upload" / "cookies"

MAX_ACCOUNTS_PER_PLATFORM = 10
MAX_TOTAL_ACCOUNTS = 50
MAX_PUBLISH_TARGETS = 20

PLATFORM_LABELS = {
    "douyin": "抖音",
    "xhs": "小红书",
    "kuaishou": "快手",
    "tencent": "视频号",
    "bilibili": "B站",
    "youtube": "YouTube",
    "weibo": "微博",
    "wechat_mp": "公众号",
}

_lock = threading.RLock()


def now_iso() -> str:
    return datetime.now().isoformat()


def normalize_platform(platform: str) -> str:
    aliases = {
        "xiaohongshu": "xhs",
        "redbook": "xhs",
        "little-red-book": "xhs",
        "wechat_video": "tencent",
        "shipinhao": "tencent",
    }
    key = (platform or "").strip().lower()
    return aliases.get(key, key)


def safe_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    return token.strip("_")[:48] or "account"


def account_session_path(platform: str, account_id: str) -> Path:
    return ACCOUNT_SESSIONS_DIR / normalize_platform(platform) / safe_token(account_id) / "storage_state.json"


def legacy_session_path(platform: str) -> Path:
    return SESSIONS_DIR / f"storage_state_{normalize_platform(platform)}.json"


def _session_info(path: str) -> dict:
    p = Path(path)
    exists = p.exists()
    size = p.stat().st_size if exists else 0
    saved_at = datetime.fromtimestamp(p.stat().st_mtime).isoformat() if exists else ""
    return {
        "has_session": exists,
        "valid": bool(exists and size > 100),
        "cookie_count": 0,
        "saved_at": saved_at,
        "cookie_expiry": None,
        "path": str(p),
    }


def _sau_account_file(platform: str, account: dict) -> Path:
    sau_name = account.get("sau_account_name") or safe_token(account.get("id", ""))
    return SAU_COOKIES_DIR / f"{normalize_platform(platform)}_{sau_name}.json"


def _effective_session_info(account: dict) -> dict:
    session = _session_info(account.get("session_path", ""))
    platform = normalize_platform(account.get("platform", ""))
    if platform == "wechat_mp":
        calibration = DATA_DIR / "wechat_desktop_calibration.json"
        desktop_session = _session_info(str(calibration))
        desktop_session["kind"] = "desktop_calibration"
        return desktop_session
    if platform == "bilibili" and not session["valid"]:
        external = _session_info(str(_sau_account_file(platform, account)))
        if external["valid"]:
            external["kind"] = "biliup"
            return external
    if platform == "weibo" and account.get("status") == "connected":
        profile_key = account.get("desktop_profile_key") or f"weibo_{safe_token(account.get('id', 'weibo_default'))}"
        profile_dir = DATA_DIR / "browser_profiles" / profile_key
        return {
            "has_session": profile_dir.exists(),
            "valid": True,
            "cookie_count": 0,
            "saved_at": datetime.fromtimestamp(profile_dir.stat().st_mtime).isoformat() if profile_dir.exists() else account.get("updated_at", ""),
            "cookie_expiry": None,
            "path": str(profile_dir),
            "kind": "desktop_browser",
        }
    session["kind"] = "playwright"
    return session


def _read_accounts() -> list[dict]:
    return atomic_read(ACCOUNTS_FILE)


def _write_accounts(rows: list[dict]) -> None:
    atomic_write(ACCOUNTS_FILE, rows)


def _read_profiles() -> list[dict]:
    return atomic_read(PROFILES_FILE)


def _write_profiles(rows: list[dict]) -> None:
    atomic_write(PROFILES_FILE, rows)


def default_account(platform: str) -> dict | None:
    platform = normalize_platform(platform)
    path = legacy_session_path(platform)
    if not path.exists():
        return None
    label = f"{PLATFORM_LABELS.get(platform, platform)}默认账号"
    updated = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    return {
        "id": f"{platform}_default",
        "platform": platform,
        "label": label,
        "nickname": label,
        "status": "connected",
        "session_path": str(path),
        "sau_account_name": safe_token(f"{platform}_default"),
        "created_at": updated,
        "updated_at": updated,
        "last_login_at": updated,
        "last_publish_at": "",
        "enabled": True,
        "is_default": True,
    }


def enrich_account(account: dict) -> dict:
    item = dict(account)
    item["platform"] = normalize_platform(item.get("platform", ""))
    if not item.get("session_path"):
        item["session_path"] = str(account_session_path(item["platform"], item.get("id", "")))
    if not item.get("sau_account_name"):
        item["sau_account_name"] = safe_token(item.get("id", ""))
    session = _effective_session_info(item)
    item["session"] = session
    explicit_status = item.get("status") or ""
    if item["platform"] in {"tencent", "weibo"} and explicit_status in {"connected", "manual_ready"}:
        item["status"] = "connected"
    else:
        item["status"] = "connected" if session["valid"] and explicit_status != "needs_login" else explicit_status or "needs_login"
    if not session["valid"] and item["status"] == "connected" and item["platform"] not in {"tencent", "weibo"}:
        item["status"] = "needs_login"
    item["platform_label"] = PLATFORM_LABELS.get(item["platform"], item["platform"])
    return item


def list_accounts(platform: str = "", include_defaults: bool = True) -> list[dict]:
    platform = normalize_platform(platform) if platform else ""
    with _lock:
        rows = _read_accounts()
        if platform:
            rows = [item for item in rows if normalize_platform(item.get("platform", "")) == platform]
        if include_defaults:
            default_platforms = [platform] if platform else sorted(set(PLATFORM_LABELS) | {normalize_platform(item.get("platform", "")) for item in rows})
            existing_ids = {item.get("id") for item in rows}
            for pid in default_platforms:
                item = default_account(pid)
                if item and item["id"] not in existing_ids:
                    rows.append(item)
        enriched = [enrich_account(item) for item in rows]
        enriched.sort(key=lambda item: (item.get("platform", ""), item.get("created_at", "")))
        return enriched


def get_account(account_id: str) -> dict | None:
    for account in list_accounts(include_defaults=True):
        if account.get("id") == account_id:
            return account
    return None


def get_default_account_for_platform(platform: str) -> dict | None:
    platform = normalize_platform(platform)
    accounts = [item for item in list_accounts(platform, include_defaults=True) if item.get("enabled", True)]
    connected = [item for item in accounts if item.get("session", {}).get("valid")]
    if connected:
        return connected[0]
    if accounts:
        return accounts[0]
    label = f"{PLATFORM_LABELS.get(platform, platform)}默认账号"
    return enrich_account({
        "id": f"{platform}_default",
        "platform": platform,
        "label": label,
        "nickname": label,
        "status": "needs_login",
        "session_path": str(legacy_session_path(platform)),
        "sau_account_name": safe_token(f"{platform}_default"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "last_login_at": "",
        "last_publish_at": "",
        "enabled": True,
        "is_default": True,
    })


def create_account(platform: str, label: str = "") -> dict:
    platform = normalize_platform(platform)
    if not platform:
        raise ValueError("平台不能为空")
    with _lock:
        accounts = _read_accounts()
        total_count = len(list_accounts(include_defaults=True))
        platform_count = len(list_accounts(platform, include_defaults=True))
        if total_count >= MAX_TOTAL_ACCOUNTS:
            raise ValueError("最多50个账号")
        if platform_count >= MAX_ACCOUNTS_PER_PLATFORM:
            raise ValueError("单个平台最多10个账号")
        account_id = f"acct_{platform}_{uuid.uuid4().hex[:8]}"
        label = (label or f"{PLATFORM_LABELS.get(platform, platform)}账号{platform_count + 1}").strip()
        created = now_iso()
        account = {
            "id": account_id,
            "platform": platform,
            "label": label,
            "nickname": label,
            "status": "needs_login",
            "session_path": str(account_session_path(platform, account_id)),
            "sau_account_name": safe_token(account_id),
            "created_at": created,
            "updated_at": created,
            "last_login_at": "",
            "last_publish_at": "",
            "enabled": True,
            "is_default": False,
        }
        accounts.append(account)
        _write_accounts(accounts)
        return enrich_account(account)


def patch_account(account_id: str, **updates) -> dict:
    with _lock:
        rows = _read_accounts()
        for index, item in enumerate(rows):
            if item.get("id") == account_id:
                item.update({key: value for key, value in updates.items() if value is not None})
                item["updated_at"] = now_iso()
                rows[index] = item
                _write_accounts(rows)
                return enrich_account(item)
    default = get_account(account_id)
    if default and default.get("is_default"):
        with _lock:
            rows = _read_accounts()
            item = dict(default)
            item.update({key: value for key, value in updates.items() if value is not None})
            item["updated_at"] = now_iso()
            rows.append(item)
            _write_accounts(rows)
            return enrich_account(item)
    raise KeyError(account_id)


def mark_account_login(account_id: str, success: bool, message: str = "") -> dict:
    status = "connected" if success else "needs_login"
    updates = {"status": status}
    if success:
        updates["last_login_at"] = now_iso()
    if message:
        updates["last_message"] = message[:300]
    return patch_account(account_id, **updates)


def _remove_path(path: Path) -> None:
    try:
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    except FileNotFoundError:
        pass


def _remove_account_files(account: dict) -> None:
    session_path = Path(account.get("session_path", ""))
    if session_path.exists():
        _remove_path(session_path)

    try:
        if session_path.parent != SESSIONS_DIR and ACCOUNT_SESSIONS_DIR in session_path.parents:
            _remove_path(session_path.parent)
    except Exception:
        pass

    platform = normalize_platform(account.get("platform", ""))
    sau_name = account.get("sau_account_name") or safe_token(account.get("id", ""))
    _remove_path(SAU_COOKIES_DIR / f"{platform}_{sau_name}.json")
    if account.get("is_default"):
        cfg_dir = {
            "douyin": "douyin_uploader",
            "xhs": "xiaohongshu_uploader",
            "kuaishou": "ks_uploader",
            "tencent": "tencent_uploader",
            "youtube": "youtube_uploader",
            "bilibili": "bilibili_uploader",
        }.get(platform)
        if cfg_dir:
            _remove_path(SAU_COOKIES_DIR / cfg_dir / "account.json")


def _remove_account_from_profiles(account_id: str) -> None:
    rows = _read_profiles()
    changed = False
    next_rows = []
    for profile in rows:
        account_ids = [item for item in profile.get("account_ids", []) if item != account_id]
        if account_ids != profile.get("account_ids", []):
            changed = True
            profile = {**profile, "account_ids": account_ids, "updated_at": now_iso()}
        next_rows.append(profile)
    if changed:
        _write_profiles(next_rows)


def delete_account_session(account_id: str) -> dict:
    account = get_account(account_id)
    if not account:
        raise KeyError(account_id)
    _remove_account_files(account)
    deleted_account = {
        **account,
        "status": "needs_login",
        "nickname": account.get("label", ""),
        "avatar_url": "",
        "profile_url": "",
        "platform_user_id": "",
        "followers": 0,
        "following": 0,
        "works_count": 0,
        "likes_count": 0,
        "sync_status": "",
        "sync_message": "",
        "last_profile_sync_at": "",
        "last_login_at": "",
        "last_message": "登录态已移除",
    }
    with _lock:
        rows = [item for item in _read_accounts() if item.get("id") != account_id]
        _write_accounts(rows)
        _remove_account_from_profiles(account_id)
    return enrich_account(deleted_account)


def list_profiles() -> list[dict]:
    accounts = {item["id"]: item for item in list_accounts(include_defaults=True)}
    rows = _read_profiles()
    result = []
    for profile in rows:
        item = dict(profile)
        item["accounts"] = [accounts[aid] for aid in item.get("account_ids", []) if aid in accounts]
        result.append(item)
    result.sort(key=lambda item: item.get("updated_at", item.get("created_at", "")), reverse=True)
    return result


def get_profile(profile_id: str) -> dict | None:
    for profile in list_profiles():
        if profile.get("id") == profile_id:
            return profile
    return None


def save_profile(name: str, account_ids: list[str], profile_id: str = "", description: str = "") -> dict:
    if not name.strip():
        raise ValueError("配置档案名称不能为空")
    existing_accounts = {item["id"] for item in list_accounts(include_defaults=True)}
    account_ids = [item for item in dict.fromkeys(account_ids) if item in existing_accounts]
    if not account_ids:
        raise ValueError("请选择至少一个账号")
    now = now_iso()
    with _lock:
        rows = _read_profiles()
        if profile_id:
            for index, item in enumerate(rows):
                if item.get("id") == profile_id:
                    item.update({
                        "name": name.strip(),
                        "description": description.strip(),
                        "account_ids": account_ids,
                        "updated_at": now,
                    })
                    rows[index] = item
                    _write_profiles(rows)
                    return get_profile(profile_id) or item
            raise KeyError(profile_id)
        profile = {
            "id": f"profile_{uuid.uuid4().hex[:8]}",
            "name": name.strip(),
            "description": description.strip(),
            "account_ids": account_ids,
            "created_at": now,
            "updated_at": now,
        }
        rows.append(profile)
        _write_profiles(rows)
        return get_profile(profile["id"]) or profile


def delete_profile(profile_id: str) -> None:
    with _lock:
        rows = _read_profiles()
        next_rows = [item for item in rows if item.get("id") != profile_id]
        if len(next_rows) == len(rows):
            raise KeyError(profile_id)
        _write_profiles(next_rows)


def resolve_publish_targets(platform: str, account_id: str = "", target_account_ids: list[str] | None = None, profile_id: str = "") -> list[dict]:
    ids: list[str] = []
    profile_ids: set[str] = set()
    if profile_id:
        profile = get_profile(profile_id)
        if not profile:
            raise ValueError("发布配置档案不存在")
        profile_ids = set(profile.get("account_ids", []))
        ids.extend(profile_ids)
    if target_account_ids:
        ids.extend(target_account_ids)
    if account_id:
        ids.append(account_id)
    ids = [item for item in dict.fromkeys(ids) if item]
    if not ids:
        default = get_default_account_for_platform(platform)
        return [default] if default else []
    if len(ids) > MAX_PUBLISH_TARGETS:
        raise ValueError("单次发布最多选择20个账号")
    accounts = []
    for aid in ids:
        account = get_account(aid)
        if not account:
            raise ValueError(f"账号不存在: {aid}")
        if platform and normalize_platform(account.get("platform", "")) != normalize_platform(platform):
            if aid in profile_ids:
                continue
            raise ValueError("所选账号与发布平台不一致")
        accounts.append(account)
    if not accounts and profile_id:
        raise ValueError("发布配置档案中没有当前平台账号")
    return accounts
