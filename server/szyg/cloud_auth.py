"""Local broker for SZYG cloud authentication.

The renderer never receives the cloud refresh token. On Windows it is encrypted
with DPAPI and only the short-lived access token is kept in process memory.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import platform
import socket
import threading
import uuid
from ctypes import wintypes
from pathlib import Path
from typing import Any

import httpx
from jose import JWTError, jwt

from szyg.config.loader import load_config


class CloudAuthError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi(value: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        return value
    source = ctypes.create_string_buffer(value)
    source_blob = _DataBlob(len(value), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    target_blob = _DataBlob()
    fn = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if decrypt:
        ok = fn(ctypes.byref(source_blob), None, None, None, None, 0, ctypes.byref(target_blob))
    else:
        ok = fn(ctypes.byref(source_blob), "SZYG cloud session", None, None, None, 0, ctypes.byref(target_blob))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target_blob.pbData, target_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(target_blob.pbData)


class CloudAuthManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._access_token = ""
        self._profile: dict[str, Any] = {}
        self._root = Path(os.environ.get("SZYG_DATA_DIR", "data")) / "cloud"
        self._root.mkdir(parents=True, exist_ok=True)
        self._session_file = self._root / "session.json"
        self._device_file = self._root / "device.json"

    @property
    def config(self) -> dict[str, Any]:
        try:
            section = load_config().get("cloud", {})
        except Exception:
            section = {}
        url = os.environ.get("SZYG_CONTROL_URL", str(section.get("control_url", ""))).strip().rstrip("/")
        enabled_value = os.environ.get("SZYG_CLOUD_ENABLED", section.get("enabled", bool(url)))
        enabled = str(enabled_value).lower() in {"1", "true", "yes", "on"}
        return {"enabled": enabled and bool(url), "control_url": url, "app_version": str(section.get("app_version", "1.0.2"))}

    def device(self) -> dict[str, str]:
        if self._device_file.exists():
            try:
                return json.loads(self._device_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        installation_id = str(uuid.uuid4())
        identity = "|".join([platform.node(), platform.machine(), platform.processor(), str(uuid.getnode())])
        item = {
            "installation_id": installation_id,
            "name": socket.gethostname() or "Windows PC",
            "fingerprint": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
            "app_version": self.config["app_version"],
        }
        self._device_file.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        return item

    def _save_refresh(self, refresh_token: str, license_data: dict | None = None, public_key: str = "") -> None:
        encrypted = base64.b64encode(_dpapi(refresh_token.encode("utf-8"))).decode("ascii")
        temp = self._session_file.with_suffix(".tmp")
        temp.write_text(json.dumps({
            "refresh_token": encrypted,
            "license": license_data or {},
            "public_key": public_key,
            "profile": self._profile,
        }), encoding="utf-8")
        os.replace(temp, self._session_file)

    def _load_refresh(self) -> str:
        try:
            raw = json.loads(self._session_file.read_text(encoding="utf-8"))["refresh_token"]
            return _dpapi(base64.b64decode(raw), decrypt=True).decode("utf-8")
        except Exception:
            return ""

    def _request(self, method: str, path: str, *, json_body: dict | None = None, token: str = "") -> dict:
        cfg = self.config
        if not cfg["enabled"]:
            raise CloudAuthError("云账户服务尚未配置")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            with httpx.Client(timeout=30, trust_env=False) as client:
                response = client.request(method, cfg["control_url"] + path, json=json_body, headers=headers)
        except httpx.HTTPError as exc:
            raise CloudAuthError("云账户服务暂时不可用") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", "")
                if isinstance(detail, dict):
                    detail = detail.get("message", "")
            except Exception:
                detail = ""
            raise CloudAuthError(str(detail or "请求未完成"))
        return response.json() if response.content else {}

    def _accept_session(self, data: dict) -> dict:
        self._access_token = str(data.get("access_token", ""))
        self._profile = {"user": data.get("user", {}), "device": data.get("device", {})}
        key_data = self._request("GET", "/api/v1/auth/license-key")
        self._save_refresh(
            str(data.get("refresh_token", "")),
            data.get("license") if isinstance(data.get("license"), dict) else {},
            str(key_data.get("public_key", "")),
        )
        return self.session()

    def _offline_session(self) -> dict | None:
        try:
            cached = json.loads(self._session_file.read_text(encoding="utf-8"))
            license_data = cached.get("license") or {}
            token = str(license_data.get("license_token") or "")
            public_key = str(cached.get("public_key") or "")
            claims = jwt.decode(token, public_key, algorithms=["RS256"])
            profile = cached.get("profile") or {}
            if claims.get("type") != "offline_license" or claims.get("device") != (profile.get("device") or {}).get("id"):
                return None
            return {"configured": True, "authenticated": True, "offline": True, **profile}
        except (OSError, ValueError, JWTError, KeyError):
            return None

    def login(self, email: str, password: str, totp_code: str = "") -> dict:
        with self._lock:
            data = self._request("POST", "/api/v1/auth/login", json_body={
                "email": email, "password": password, "totp_code": totp_code, "device": self.device(),
            })
            return self._accept_session(data)

    def activate(self, invitation_code: str, display_name: str, password: str) -> dict:
        with self._lock:
            data = self._request("POST", "/api/v1/auth/activate", json_body={
                "invitation_code": invitation_code,
                "display_name": display_name,
                "password": password,
                "device": self.device(),
            })
            return self._accept_session(data)

    def access_token(self) -> str:
        with self._lock:
            if self._access_token:
                return self._access_token
            refresh_token = self._load_refresh()
            if not refresh_token:
                raise CloudAuthError("请先登录")
            data = self._request("POST", "/api/v1/auth/refresh", json_body={"refresh_token": refresh_token})
            self._accept_session(data)
            return self._access_token

    def session(self) -> dict:
        if not self.config["enabled"]:
            return {"configured": False, "authenticated": False}
        try:
            token = self.access_token()
            profile = self._request("GET", "/api/v1/auth/me", token=token)
            self._profile = profile
            return {"configured": True, "authenticated": True, **profile}
        except CloudAuthError as exc:
            self._access_token = ""
            offline = self._offline_session()
            if offline:
                return offline
            return {"configured": True, "authenticated": False, "message": str(exc)}

    def proxy(self, method: str, path: str, body: dict | None = None) -> dict:
        return self._request(method, path, json_body=body, token=self.access_token())

    def logout(self) -> None:
        with self._lock:
            refresh = self._load_refresh()
            if refresh:
                try:
                    self._request("POST", "/api/v1/auth/logout", json_body={"refresh_token": refresh})
                except CloudAuthError:
                    pass
            self._access_token = ""
            self._profile = {}
            self._session_file.unlink(missing_ok=True)


cloud_auth = CloudAuthManager()
