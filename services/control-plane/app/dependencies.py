from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import Device, SessionLocal, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@dataclass
class Principal:
    user: User
    device: Device


def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Principal:
    if not credentials:
        raise HTTPException(401, "请先登录")
    try:
        claims = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(401, "登录状态已失效")
    user = db.get(User, claims.get("sub"))
    device = db.get(Device, claims.get("device"))
    if not user or user.status != "active":
        raise HTTPException(403, "账户暂不可用")
    if not device or device.user_id != user.id or device.status != "active":
        raise HTTPException(403, "当前设备授权已失效")
    return Principal(user=user, device=device)


def current_admin(principal: Principal = Depends(current_principal)) -> Principal:
    if principal.user.role != "admin":
        raise HTTPException(403, "仅管理员可操作")
    return principal
