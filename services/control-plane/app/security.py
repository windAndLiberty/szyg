from __future__ import annotations

import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from .config import get_settings

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("密码至少需要10个字符")
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hasher.verify(encoded, password)
    except (VerifyMismatchError, ValueError):
        return False


def random_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, organization_id: str, role: str, device_id: str) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": user_id,
        "org": organization_id,
        "role": role,
        "device": device_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": random_token(12),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), expires_at


def create_offline_license(
    user_id: str,
    organization_id: str,
    device_id: str,
    valid_until: datetime,
    features: dict,
) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    normalized_until = valid_until.replace(tzinfo=timezone.utc) if valid_until.tzinfo is None else valid_until
    expires_at = min(normalized_until, now + timedelta(days=settings.offline_license_days))
    payload = {
        "sub": user_id,
        "org": organization_id,
        "device": device_id,
        "features": features,
        "type": "offline_license",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": random_token(12),
    }
    if settings.offline_license_private_key_file:
        key = Path(settings.offline_license_private_key_file).read_text(encoding="utf-8")
        return jwt.encode(payload, key, algorithm="RS256"), expires_at
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), expires_at


def offline_license_public_key() -> str:
    settings = get_settings()
    if not settings.offline_license_public_key_file:
        return ""
    return Path(settings.offline_license_public_key_file).read_text(encoding="utf-8")


def decode_access_token(value: str) -> dict:
    settings = get_settings()
    try:
        claims = jwt.decode(value, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("invalid token") from exc
    if claims.get("type") != "access":
        raise ValueError("invalid token type")
    return claims


def verify_totp(secret: str, code: str) -> bool:
    if not secret:
        return True
    return bool(code and pyotp.TOTP(secret).verify(code, valid_window=1))
