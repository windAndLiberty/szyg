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
import stat
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
        self._auth_error = ""
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
        app_version = os.environ.get("SZYG_APP_VERSION", str(section.get("app_version", "1.1.3"))).strip()
        product_id = os.environ.get("SZYG_PRODUCT_ID", str(section.get("product_id", "szyg_private"))).strip()
        if product_id != "szyg_private":
            product_id = "szyg_private"
        return {
            "enabled": enabled and bool(url),
            "control_url": url,
            "app_version": app_version,
            "product_id": product_id,
        }

    def device(self, *, force_rotate: bool = False) -> dict[str, str]:
        """本机设备身份。指纹基于硬件信息保持不变,installation id 可旋转。

        force_rotate 用于"设备被移除"冲突后的自动重备案——复用物理指纹,
        仅更换安装序号,保证同一台机器可自动重新绑定,而不是把用户拦住。
        """
        if not force_rotate and self._device_file.exists():
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

    @staticmethod
    def _is_device_conflict(exc: CloudAuthError) -> bool:
        """动态安全策略:设备被云端移除/解绑时,自动换新设备身份后重试绑定,
        而不是直接报错拦住用户。仅当且仅当错误明确指向本机设备记录无效。"""
        message = str(exc).lower()
        return any(marker in message for marker in (
            "设备已移除", "设备已被移除", "设备已删除", "设备已注销", "设备不存在",
            "device has been removed", "device was removed", "device removed",
            "device no longer", "device revoked", "device was revoked", "not bound",
            "device not found", "已被移除", "已解绑",
        ))

    def _bind_with_rotation(self, fn) -> dict:
        """先按当前设备尝试;若服务端判定该设备已被移除,自动更换设备记录重试一次。"""
        try:
            return fn()
        except CloudAuthError as exc:
            if self._is_device_conflict(exc):
                self.device(force_rotate=True)
                return fn()
            raise

    # 授权到期标记:云端返回"服务授权已到期"时记录,前端据此展示重新登录/刷新入口。
    # /auth/me 不校验授权有效期,只有真正发起推理调用才会触发 403,因此必须由
    # 推理客户端显式上报,且只在授权类消息时记录(设备被移除等场景不触发)。
    _AUTH_ERROR_MARKERS = ("服务授权已到期", "授权已到期", "账户暂不可用")

    def note_auth_error(self, message: str) -> None:
        text = str(message or "")
        if text and any(marker in text for marker in self._AUTH_ERROR_MARKERS):
            with self._lock:
                self._auth_error = text

    def clear_auth_error(self) -> None:
        with self._lock:
            self._auth_error = ""

    def _with_auth_error(self, payload: dict) -> dict:
        with self._lock:
            if self._auth_error:
                return {**payload, "authorization_error": self._auth_error}
            return payload

    def _cached_session_data(self) -> dict[str, Any]:
        try:
            data = json.loads(self._session_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_refresh(
        self,
        refresh_token: str,
        license_data: dict | None = None,
        public_key: str | None = None,
    ) -> None:
        """Persist a rotated token before any optional follow-up request.

        Refresh tokens are single-use. Losing the replacement token because a
        later license-key request timed out leaves an otherwise valid desktop
        installation unable to use cloud features until the user signs in
        again. Preserve the cached offline license and write the replacement
        token atomically first.
        """
        cached = self._cached_session_data()
        if not refresh_token:
            raise CloudAuthError("登录状态已失效，请重新登录")
        encrypted = base64.b64encode(_dpapi(refresh_token.encode("utf-8"))).decode("ascii")
        temp = self._session_file.with_suffix(".tmp")
        temp.write_text(json.dumps({
            "refresh_token": encrypted,
            "license": license_data if isinstance(license_data, dict) else cached.get("license", {}),
            "public_key": public_key if public_key is not None else str(cached.get("public_key") or ""),
            "profile": self._profile,
        }), encoding="utf-8")
        # POSIX development builds do not have DPAPI, so the refresh token is
        # protected by owner-only file permissions in addition to staying out
        # of version control. Windows still encrypts the token with DPAPI.
        try:
            temp.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        os.replace(temp, self._session_file)

    def _load_refresh(self) -> str:
        try:
            cached = json.loads(self._session_file.read_text(encoding="utf-8"))
            profile_product = str(((cached.get("profile") or {}).get("user") or {}).get("product_id") or "szyg_private")
            if profile_product != self.config["product_id"]:
                return ""
            raw = cached["refresh_token"]
            return _dpapi(base64.b64decode(raw), decrypt=True).decode("utf-8")
        except Exception:
            return ""

    def _cached_profile(self) -> dict[str, Any] | None:
        """设备绑定策略:登录过即视为本机已认证,离线/云端抖动时沿用本地档案。"""
        try:
            profile = json.loads(self._session_file.read_text(encoding="utf-8")).get("profile")
            return profile if isinstance(profile, dict) else None
        except Exception:
            return None

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
            error = CloudAuthError(str(detail or "请求未完成"))
            error.status_code = response.status_code
            raise error
        return response.json() if response.content else {}

    def _accept_session(self, data: dict) -> dict:
        self._access_token = str(data.get("access_token", ""))
        self._profile = {"user": data.get("user", {}), "device": data.get("device", {})}
        # 重新登录/续期成功 → 清掉上一次的授权到期标记
        self.clear_auth_error()
        refresh_token = str(data.get("refresh_token", ""))
        license_data = data.get("license") if isinstance(data.get("license"), dict) else None

        # The replacement refresh token must be durable before any secondary
        # network request. The public key is useful for offline mode, but it is
        # not required for the active online session.
        self._save_refresh(
            refresh_token,
            license_data,
        )
        try:
            key_data = self._request("GET", "/api/v1/auth/license-key")
            self._save_refresh(refresh_token, license_data, str(key_data.get("public_key", "")))
        except CloudAuthError:
            pass
        return {"configured": True, "authenticated": True, **self._profile}

    def _offline_session(self) -> dict | None:
        try:
            cached = json.loads(self._session_file.read_text(encoding="utf-8"))
            license_data = cached.get("license") or {}
            token = str(license_data.get("license_token") or "")
            public_key = str(cached.get("public_key") or "")
            claims = jwt.decode(token, public_key, algorithms=["RS256"])
            profile = cached.get("profile") or {}
            if (
                claims.get("type") != "offline_license"
                or claims.get("device") != (profile.get("device") or {}).get("id")
                or claims.get("product") != self.config["product_id"]
            ):
                return None
            return {"configured": True, "authenticated": True, "offline": True, **profile}
        except (OSError, ValueError, JWTError, KeyError):
            return None

    def login(self, email: str, password: str) -> dict:
        with self._lock:
            def attempt() -> dict:
                data = self._request("POST", "/api/v1/auth/login", json_body={
                    "product_id": self.config["product_id"],
                    "email": email,
                    "password": password,
                    "device": self.device(),
                })
                return self._accept_session(data)
            return self._bind_with_rotation(attempt)

    def activate(self, invitation_code: str, display_name: str, password: str) -> dict:
        with self._lock:
            def attempt() -> dict:
                data = self._request("POST", "/api/v1/auth/activate", json_body={
                    "invitation_code": invitation_code,
                    "display_name": display_name,
                    "password": password,
                    "device": self.device(),
                })
                return self._accept_session(data)
            return self._bind_with_rotation(attempt)

    def request_registration_code(self, email: str) -> dict:
        with self._lock:
            if self.config["product_id"] == "szyg_private":
                raise CloudAuthError("当前产品未开放自助注册")
            return self._request("POST", "/api/v1/auth/register/code", json_body={
                "product_id": self.config["product_id"],
                "email": email,
                "device": self.device(),
            })

    def register(
        self,
        email: str,
        display_name: str,
        password: str,
        verification_id: str,
        verification_code: str,
    ) -> dict:
        with self._lock:
            if self.config["product_id"] == "szyg_private":
                raise CloudAuthError("当前产品未开放自助注册")

            def attempt() -> dict:
                data = self._request("POST", "/api/v1/auth/register", json_body={
                    "product_id": self.config["product_id"],
                    "email": email,
                    "display_name": display_name,
                    "password": password,
                    "device": self.device(),
                    "verification_id": verification_id,
                    "verification_code": verification_code,
                })
                return self._accept_session(data)
            return self._bind_with_rotation(attempt)

    def access_token(self, *, force_refresh: bool = False) -> str:
        with self._lock:
            if self._access_token and not force_refresh:
                return self._access_token
            if force_refresh:
                self._access_token = ""
            refresh_token = self._load_refresh()
            if not refresh_token:
                raise CloudAuthError("请先登录")

            def refresh_once() -> dict:
                return self._request("POST", "/api/v1/auth/refresh", json_body={"refresh_token": refresh_token})

            data = self._bind_with_rotation(refresh_once)
            self._accept_session(data)
            return self._access_token

    def session(self) -> dict:
        if not self.config["enabled"]:
            return self._with_auth_error({"configured": False, "authenticated": False})
        try:
            token = self.access_token()
            profile = self._request("GET", "/api/v1/auth/me", token=token)
            self._profile = profile
            return self._with_auth_error({"configured": True, "authenticated": True, **profile})
        except CloudAuthError as exc:
            self._access_token = ""
            # 任何授权类错误必须显式记录,避免"账号不存在/被禁用"被静默吞成离线可用
            self.note_auth_error(str(exc))
            # 设备绑定策略:一旦本机登录过,云端校验失败(换 IP/超时/网络抖动)
            # 一律视为离线可用,不因云端状态变化要求用户重新登录。
            if str(exc) == "请先登录":
                return self._with_auth_error({"configured": True, "authenticated": False})
            offline = self._offline_session()
            if offline:
                return self._with_auth_error(offline)
            cached = self._cached_profile()
            if cached:
                return self._with_auth_error({"configured": True, "authenticated": True, "offline": True, **cached})
            return self._with_auth_error({"configured": True, "authenticated": False, "message": str(exc)})

    def refresh_status(self) -> dict:
        """强制刷新 access token 并探测授权状态。用于前端「刷新授权状态」按钮:
        若授权已被续期则清掉授权到期标记,否则返回过期信息。"""
        if not self.config["enabled"]:
            return {"configured": False, "expired": True, "message": "云账户服务尚未配置"}
        try:
            self.access_token(force_refresh=True)
        except CloudAuthError as exc:
            self.note_auth_error(str(exc))
            return {
                "configured": True,
                "expired": True,
                "authorization_error": self._auth_error or str(exc),
            }
        try:
            ent = self.proxy("GET", "/api/v1/entitlements")
        except CloudAuthError as exc:
            self.note_auth_error(str(exc))
            return {
                "configured": True,
                "expired": True,
                "authorization_error": self._auth_error or str(exc),
            }
        from datetime import datetime, timezone as _tz
        valid_until_raw = str(ent.get("valid_until") or "")
        expired = (str(ent.get("status") or "").strip().lower() != "active")
        if not expired and valid_until_raw:
            try:
                dt = datetime.fromisoformat(valid_until_raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_tz.utc)
                if dt <= datetime.now(_tz.utc):
                    expired = True
            except ValueError:
                expired = True
        if expired:
            self.note_auth_error("服务授权已到期，请联系管理员")
        else:
            self.clear_auth_error()
        return {
            "configured": True,
            "expired": expired,
            "status": str(ent.get("status") or ""),
            "valid_until": valid_until_raw,
            "authorization_error": self._auth_error,
        }

    def proxy(self, method: str, path: str, body: dict | None = None) -> dict:
        token = self.access_token()
        try:
            return self._request(method, path, json_body=body, token=token)
        except CloudAuthError as exc:
            # Access tokens are intentionally short-lived. A request may race
            # their expiry even though the encrypted refresh token is valid.
            # Refresh once and retry the same idempotent/proxied request before
            # surfacing a login error to the desktop UI.
            if getattr(exc, "status_code", None) != 401:
                raise
            return self._request(
                method,
                path,
                json_body=body,
                token=self.access_token(force_refresh=True),
            )

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
