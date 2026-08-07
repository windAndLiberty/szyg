from __future__ import annotations

import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .database import (
    AdminAuditLog,
    CreditTransaction,
    Device,
    Entitlement,
    Feedback,
    Invitation,
    LoginDeviceBlock,
    ModelRoute,
    Organization,
    ProviderBillingDaily,
    RefreshSession,
    SessionLocal,
    UsageEvent,
    User,
    VideoTask,
    as_utc,
    create_schema,
    utcnow,
)
from .dependencies import Principal, current_admin, current_principal, get_db
from .provider import ProviderError, ProviderGateway
from .schemas import (
    ActivateRequest,
    AdminCreditRechargeRequest,
    AdminUserCreateRequest,
    ChangePasswordRequest,
    EntitlementUpdate,
    FeedbackRequest,
    InferenceRequest,
    InviteRequest,
    LoginRequest,
    LogoutRequest,
    ModelRouteUpdate,
    RefreshRequest,
    UserStatusUpdate,
)
from .security import (
    create_access_token,
    create_offline_license,
    offline_license_public_key,
    hash_password,
    random_token,
    token_hash,
    verify_password,
    verify_totp,
)
from .usage_accounting import estimate_credits_micros, settle_usage

settings = get_settings()
app = FastAPI(title="SZYG Control", version="1.0.0", docs_url=None if settings.environment == "production" else "/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-App-Version"],
)

DEFAULT_QUOTAS = {
    "text_tokens": 1_000_000,
    "image_count": 200,
    "video_seconds": 600,
    "speech_characters": 200_000,
    "embedding_tokens": 1_000_000,
}

CAPABILITY_UNITS = {
    "text.fast": "text_tokens",
    "text.vision": "text_tokens",
    "text.reasoning": "text_tokens",
    "image.standard": "image_count",
    "video.standard": "video_seconds",
    "speech.tts": "speech_characters",
    "embedding.standard": "embedding_tokens",
}

def _credits(value: int | None) -> float:
    return round(int(value or 0) / 1_000_000, 6)


def _credit_balance(db: Session, user_id: str) -> int:
    """统一计费余额（micros）：总充值 − 已成功消费。"""
    credited = db.scalar(select(func.coalesce(func.sum(CreditTransaction.credits_micros), 0)).where(
        CreditTransaction.user_id == user_id,
    )) or 0
    spent = db.scalar(select(func.coalesce(func.sum(UsageEvent.credits_charged_micros), 0)).where(
        UsageEvent.user_id == user_id,
        UsageEvent.status == "succeeded",
    )) or 0
    return int(credited) - int(spent)


def _month_start() -> datetime:
    now = utcnow()
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def _day_window(timezone_name: str = "Asia/Shanghai") -> tuple[datetime, datetime]:
    try:
        zone = ZoneInfo(timezone_name)
    except Exception:
        zone = ZoneInfo("Asia/Shanghai")
    now = datetime.now(zone)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def _user_json(user: User) -> dict:
    return {
        "id": user.id,
        "organization_id": user.organization_id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "password_changed_at": user.password_changed_at,
    }


def _device_json(device: Device) -> dict:
    return {
        "id": device.id,
        "name": device.name,
        "installation_id": device.installation_id,
        "app_version": device.app_version,
        "status": device.status,
        "created_at": device.created_at,
        "last_seen_at": device.last_seen_at,
    }


def _login_identity(device_input) -> tuple[str, str]:
    fingerprint_hash = _fingerprint(device_input.fingerprint)
    if fingerprint_hash:
        return f"fingerprint:{fingerprint_hash}", fingerprint_hash
    installation_hash = hashlib.sha256(device_input.installation_id.encode("utf-8")).hexdigest()
    return f"installation:{installation_hash}", ""


def _login_guard(db: Session, device_input) -> LoginDeviceBlock | None:
    identity_key, _ = _login_identity(device_input)
    return db.scalar(select(LoginDeviceBlock).where(LoginDeviceBlock.identity_key == identity_key).with_for_update())


def _block_matching_devices(db: Session, guard: LoginDeviceBlock) -> None:
    rows = db.scalars(select(Device).where(Device.installation_id == guard.installation_id)).all()
    if guard.fingerprint_hash:
        fingerprint_rows = db.scalars(select(Device).where(Device.fingerprint_hash == guard.fingerprint_hash)).all()
        rows = list({item.id: item for item in [*rows, *fingerprint_rows]}.values())
    now = utcnow()
    for device in rows:
        if device.status != "revoked":
            device.status = "blocked"
        for session in db.scalars(select(RefreshSession).where(
            RefreshSession.device_id == device.id,
            RefreshSession.revoked_at.is_(None),
        )):
            session.revoked_at = now


def _record_login_failure(db: Session, req: LoginRequest) -> LoginDeviceBlock:
    identity_key, fingerprint_hash = _login_identity(req.device)
    guard = _login_guard(db, req.device)
    now = utcnow()
    if guard is None:
        candidate = LoginDeviceBlock(
            identity_key=identity_key,
            installation_id=req.device.installation_id,
            fingerprint_hash=fingerprint_hash,
            device_name=req.device.name,
            app_version=req.device.app_version,
            attempted_account=req.email.lower().strip(),
            failed_attempts=0,
            first_failure_at=now,
            last_failure_at=now,
        )
        try:
            with db.begin_nested():
                db.add(candidate)
                db.flush()
            guard = candidate
        except IntegrityError:
            guard = _login_guard(db, req.device)
            if guard is None:
                raise
    guard.installation_id = req.device.installation_id
    guard.device_name = req.device.name
    guard.app_version = req.device.app_version
    guard.attempted_account = req.email.lower().strip()
    guard.failed_attempts += 1
    guard.last_failure_at = now
    if guard.failed_attempts >= 10:
        guard.status = "blocked"
        guard.blocked_at = guard.blocked_at or now
        _block_matching_devices(db, guard)
    db.commit()
    return guard


def _clear_login_failures(db: Session, device_input) -> None:
    guard = _login_guard(db, device_input)
    if guard and guard.status != "blocked":
        db.delete(guard)


def _audit(db: Session, admin_id: str, action: str, target_type: str = "", target_id: str = "", detail: dict | None = None) -> None:
    db.add(AdminAuditLog(
        admin_user_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail or {},
    ))


def _ensure_device(db: Session, user: User, device_input, entitlement: Entitlement) -> Device:
    device = db.scalar(select(Device).where(
        Device.user_id == user.id,
        Device.installation_id == device_input.installation_id,
    ))
    if device:
        if device.status == "blocked":
            raise HTTPException(423, "当前设备已锁定，请联系管理员")
        if device.status != "active":
            raise HTTPException(403, "当前设备已被移除，请联系管理员")
        device.name = device_input.name
        device.app_version = device_input.app_version
        device.last_seen_at = utcnow()
        return device
    active_count = db.scalar(select(func.count(Device.id)).where(
        Device.user_id == user.id,
        Device.status == "active",
    )) or 0
    if active_count >= entitlement.device_limit:
        raise HTTPException(403, f"设备数量已达上限（{entitlement.device_limit}台）")
    device = Device(
        user_id=user.id,
        installation_id=device_input.installation_id,
        name=device_input.name,
        fingerprint_hash=_fingerprint(device_input.fingerprint),
        app_version=device_input.app_version,
    )
    db.add(device)
    db.flush()
    return device


def _issue_session(db: Session, user: User, device: Device) -> dict:
    access_token, access_expires = create_access_token(user.id, user.organization_id, user.role, device.id)
    refresh_token = random_token(48)
    refresh_expires = utcnow() + timedelta(days=settings.refresh_token_days)
    db.add(RefreshSession(
        user_id=user.id,
        device_id=device.id,
        token_hash=token_hash(refresh_token),
        expires_at=refresh_expires,
    ))
    return {
        "access_token": access_token,
        "access_expires_at": access_expires,
        "refresh_token": refresh_token,
        "refresh_expires_at": refresh_expires,
        "token_type": "bearer",
        "user": _user_json(user),
        "device": _device_json(device),
    }


def _license_payload(user: User, device: Device, entitlement: Entitlement) -> dict:
    license_token, expires = create_offline_license(
        user.id,
        user.organization_id,
        device.id,
        entitlement.valid_until,
        entitlement.features,
    )
    return {
        "license_token": license_token,
        "offline_valid_until": expires,
        "entitlement_valid_until": entitlement.valid_until,
        "features": entitlement.features,
    }


def _estimate_units(capability: str, payload: dict) -> int:
    if capability.startswith("text."):
        return max(1, len(json.dumps(payload, ensure_ascii=False)) // 2)
    if capability == "image.standard":
        return max(1, int(payload.get("n") or 1))
    if capability == "video.standard":
        return max(1, int(payload.get("duration") or 5))
    if capability == "speech.tts":
        return max(1, len(str(payload.get("input") or payload.get("text") or "")))
    if capability == "embedding.standard":
        return max(1, len(json.dumps(payload.get("input") or "", ensure_ascii=False)) // 2)
    return 1


def _reserve_usage(db: Session, principal: Principal, req: InferenceRequest) -> tuple[UsageEvent, bool]:
    existing = db.scalar(select(UsageEvent).where(
        UsageEvent.user_id == principal.user.id,
        UsageEvent.idempotency_key == req.idempotency_key,
    ))
    if existing:
        return existing, False
    entitlement = db.scalar(
        select(Entitlement).where(Entitlement.user_id == principal.user.id).with_for_update()
    )
    if not entitlement or entitlement.status != "active" or as_utc(entitlement.valid_until) <= utcnow():
        raise HTTPException(403, "服务授权已到期")
    unit_type = CAPABILITY_UNITS.get(req.capability)
    if not unit_type:
        raise HTTPException(400, "未知的智能能力")
    estimate = _estimate_units(req.capability, req.payload)
    credited = db.scalar(select(func.coalesce(func.sum(CreditTransaction.credits_micros), 0)).where(
        CreditTransaction.user_id == principal.user.id,
    )) or 0
    if int(credited) > 0:
        # 统一计费（方案B）：credits 为唯一拦截额度，text/图片/视频统一从一个池子扣
        balance = _credit_balance(db, principal.user.id)
        route = db.get(ModelRoute, req.capability)
        estimate_credits = estimate_credits_micros(req.capability, req.payload, route.config if route else {})
        if max(0, balance) - estimate_credits < 0:
            raise HTTPException(429, "credits 余额不足，请先充值后再使用")
    else:
        # 尚未开通 credits 计费：回退到分类型月度配额（兼容存量用户）
        used = db.scalar(select(func.coalesce(func.sum(UsageEvent.units), 0)).where(
            UsageEvent.user_id == principal.user.id,
            UsageEvent.unit_type == unit_type,
            UsageEvent.status.in_(["reserved", "succeeded"]),
            UsageEvent.created_at >= _month_start(),
        )) or 0
        limit = int((entitlement.quotas or {}).get(unit_type, 0))
        if limit > 0 and used + estimate > limit:
            raise HTTPException(429, f"本月{unit_type}额度已用完")
    event = UsageEvent(
        organization_id=principal.user.organization_id,
        user_id=principal.user.id,
        device_id=principal.device.id,
        idempotency_key=req.idempotency_key,
        capability=req.capability,
        status="reserved",
        units=estimate,
        unit_type=unit_type,
        app_version=req.app_version or principal.device.app_version,
    )
    db.add(event)
    db.flush()
    return event, True


def _complete_usage(
    event: UsageEvent,
    data: dict,
    latency_ms: int,
    request_id: str,
    payload: dict,
    route_config: dict | None,
) -> None:
    usage, provider_cost_micros, credits_micros, pricing_version = settle_usage(
        event.capability,
        data,
        payload,
        route_config,
    )
    if event.unit_type in {"text_tokens", "embedding_tokens"}:
        event.units = int(usage.get("total_tokens") or usage.get("input_tokens") or event.units)
    event.status = "succeeded"
    event.latency_ms = latency_ms
    event.provider_usage = usage
    event.provider_cost_micros = provider_cost_micros
    event.credits_charged_micros = credits_micros
    event.pricing_version = pricing_version
    event.estimated_cost = provider_cost_micros / 1_000_000
    event.provider_request_id = request_id
    event.completed_at = utcnow()


def _fail_usage(event: UsageEvent, exc: Exception, latency_ms: int) -> None:
    event.status = "failed"
    event.units = 0
    event.latency_ms = latency_ms
    event.error_code = getattr(exc, "code", "request_failed")[:80]
    event.error_message = "智能服务暂时不可用"
    event.provider_request_id = getattr(exc, "request_id", "")[:160]
    event.completed_at = utcnow()


@app.on_event("startup")
def startup() -> None:
    settings.validate_production()
    create_schema()
    with SessionLocal.begin() as db:
        for alias, model in settings.capability_models.items():
            route = db.get(ModelRoute, alias)
            if not route:
                db.add(ModelRoute(alias=alias, provider_model=model, enabled=bool(model)))
            elif not route.provider_model and model:
                route.provider_model = model
                route.enabled = True
        if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
            email = settings.bootstrap_admin_email.lower().strip()
            if not db.scalar(select(User).where(User.email == email)):
                org = Organization(name="SZYG 内测管理")
                db.add(org)
                db.flush()
                admin = User(
                    organization_id=org.id,
                    email=email,
                    display_name="管理员",
                    password_hash=hash_password(settings.bootstrap_admin_password),
                    role="admin",
                    status="active",
                    totp_secret=settings.bootstrap_admin_totp_secret,
                )
                db.add(admin)
                db.flush()
                db.add(Entitlement(
                    user_id=admin.id,
                    valid_until=utcnow() + timedelta(days=3650),
                    device_limit=10,
                    features={"admin": True},
                    quotas={key: 0 for key in DEFAULT_QUOTAS},
                ))
        # 统一计费（方案B）：为存量已授权用户一次性赠送默认 credits（CONTROL_DEFAULT_CREDITS）
        default_credit_micros = settings.default_credit_micros
        if default_credit_micros > 0:
            for user, _ent in db.execute(
                select(User, Entitlement).join(Entitlement, Entitlement.user_id == User.id)
            ).all():
                has_credit = db.scalar(select(func.count(CreditTransaction.id)).where(
                    CreditTransaction.user_id == user.id,
                )) or 0
                if not has_credit:
                    db.add(CreditTransaction(
                        organization_id=user.organization_id,
                        user_id=user.id,
                        kind="grant",
                        credits_micros=default_credit_micros,
                        note="统一计费上线赠送额度",
                        created_by=user.id,
                    ))


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "service": "szyg-control", "version": "1.0.0"}


@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(Path(__file__).parent / "static" / "admin.html")


@app.post("/api/v1/auth/activate")
def activate(req: ActivateRequest, db: Session = Depends(get_db)):
    invitation = db.scalar(select(Invitation).where(Invitation.code_hash == token_hash(req.invitation_code)).with_for_update())
    if not invitation or invitation.status != "pending" or as_utc(invitation.expires_at) <= utcnow():
        raise HTTPException(400, "邀请码无效或已过期")
    if db.scalar(select(User).where(User.email == invitation.email)):
        raise HTTPException(409, "该账户已经激活")
    user = User(
        organization_id=invitation.organization_id,
        email=invitation.email,
        display_name=req.display_name.strip(),
        password_hash=hash_password(req.password),
        role=invitation.role,
    )
    db.add(user)
    db.flush()
    entitlement = Entitlement(
        user_id=user.id,
        valid_until=utcnow() + timedelta(days=invitation.entitlement_days),
        device_limit=invitation.device_limit,
        features={"cloud_models": True},
        quotas={**DEFAULT_QUOTAS, **(invitation.quotas or {})},
    )
    db.add(entitlement)
    db.flush()
    device = _ensure_device(db, user, req.device, entitlement)
    invitation.status = "activated"
    invitation.activated_at = utcnow()
    result = _issue_session(db, user, device)
    result["license"] = _license_payload(user, device, entitlement)
    db.commit()
    return result


@app.get("/api/v1/auth/license-key")
def license_key():
    public_key = offline_license_public_key()
    return {"algorithm": "RS256" if public_key else "HS256", "public_key": public_key}


@app.post("/api/v1/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    guard = _login_guard(db, req.device)
    if guard and guard.status == "blocked":
        raise HTTPException(423, "当前设备已锁定，请联系管理员解除")
    user = db.scalar(select(User).where(User.email == req.email.lower().strip()))
    if not user or not verify_password(req.password, user.password_hash):
        guard = _record_login_failure(db, req)
        if guard.status == "blocked":
            raise HTTPException(423, "密码错误次数已达上限，当前设备已锁定")
        remaining = 10 - guard.failed_attempts
        raise HTTPException(401, f"账号或密码错误，还可尝试 {remaining} 次")
    if user.status != "active":
        raise HTTPException(403, "账户暂不可用")
    if not verify_totp(user.totp_secret, req.totp_code):
        guard = _record_login_failure(db, req)
        if guard.status == "blocked":
            raise HTTPException(423, "验证失败次数已达上限，当前设备已锁定")
        remaining = 10 - guard.failed_attempts
        raise HTTPException(401, f"验证未通过，还可尝试 {remaining} 次")
    entitlement = db.scalar(select(Entitlement).where(Entitlement.user_id == user.id))
    if not entitlement or as_utc(entitlement.valid_until) <= utcnow():
        raise HTTPException(403, "服务授权已到期")
    device = _ensure_device(db, user, req.device, entitlement)
    _clear_login_failures(db, req.device)
    user.last_login_at = utcnow()
    result = _issue_session(db, user, device)
    result["license"] = _license_payload(user, device, entitlement)
    db.commit()
    return result


@app.post("/api/v1/auth/refresh")
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == token_hash(req.refresh_token)).with_for_update())
    if not session or session.revoked_at or as_utc(session.expires_at) <= utcnow():
        raise HTTPException(401, "登录状态已失效")
    user, device = db.get(User, session.user_id), db.get(Device, session.device_id)
    if not user or user.status != "active" or not device or device.status != "active":
        raise HTTPException(403, "账户或设备授权已失效")
    session.revoked_at = utcnow()
    result = _issue_session(db, user, device)
    entitlement = db.scalar(select(Entitlement).where(Entitlement.user_id == user.id))
    if entitlement:
        result["license"] = _license_payload(user, device, entitlement)
    replacement = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == token_hash(result["refresh_token"])))
    session.replaced_by = replacement.id if replacement else ""
    db.commit()
    return result


@app.post("/api/v1/auth/logout")
def logout(req: LogoutRequest, db: Session = Depends(get_db)):
    session = db.scalar(select(RefreshSession).where(RefreshSession.token_hash == token_hash(req.refresh_token)))
    if session and not session.revoked_at:
        session.revoked_at = utcnow()
        db.commit()
    return {"ok": True}


@app.put("/api/v1/auth/password")
def change_password(req: ChangePasswordRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.id == principal.user.id).with_for_update())
    if not user or not verify_password(req.current_password, user.password_hash):
        raise HTTPException(400, "当前密码不正确")
    if verify_password(req.new_password, user.password_hash):
        raise HTTPException(400, "新密码不能与当前密码相同")
    day_start, day_end = _day_window()
    if user.password_changed_at and day_start <= as_utc(user.password_changed_at) < day_end:
        raise HTTPException(429, "今天已经修改过密码，请明天再试")
    user.password_hash = hash_password(req.new_password)
    user.must_change_password = False
    now = utcnow()
    user.password_changed_at = now
    for session in db.scalars(select(RefreshSession).where(
        RefreshSession.user_id == user.id,
        RefreshSession.device_id != principal.device.id,
        RefreshSession.revoked_at.is_(None),
    )):
        session.revoked_at = now
    db.commit()
    return {"ok": True, "password_changed_at": now, "next_change_at": day_end}


@app.get("/api/v1/auth/me")
def me(principal: Principal = Depends(current_principal)):
    return {"user": _user_json(principal.user), "device": _device_json(principal.device)}


@app.get("/api/v1/devices")
def devices(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.scalars(select(Device).where(Device.user_id == principal.user.id).order_by(Device.last_seen_at.desc())).all()
    return {"items": [_device_json(item) for item in rows]}


@app.delete("/api/v1/devices/{device_id}")
def revoke_device(device_id: str, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device or device.user_id != principal.user.id:
        raise HTTPException(404, "设备不存在")
    if device.id == principal.device.id:
        raise HTTPException(400, "不能移除当前正在使用的设备")
    device.status = "revoked"
    now = utcnow()
    for session in db.scalars(select(RefreshSession).where(RefreshSession.device_id == device.id, RefreshSession.revoked_at.is_(None))):
        session.revoked_at = now
    db.commit()
    return {"ok": True}


@app.get("/api/v1/entitlements")
def entitlements(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    ent = db.scalar(select(Entitlement).where(Entitlement.user_id == principal.user.id))
    if not ent:
        raise HTTPException(404, "未找到服务授权")
    credited = db.scalar(select(func.coalesce(func.sum(CreditTransaction.credits_micros), 0)).where(
        CreditTransaction.user_id == principal.user.id,
    )) or 0
    balance = _credit_balance(db, principal.user.id)
    return {
        "status": ent.status,
        "valid_until": ent.valid_until,
        "device_limit": ent.device_limit,
        "features": ent.features,
        "quotas": ent.quotas,
        "billing": {
            "mode": "credits" if int(credited) > 0 else "quota",
            "balance": _credits(balance),
            "credited": _credits(credited),
        },
        **_license_payload(principal.user, principal.device, ent),
    }


@app.get("/api/v1/usage/summary")
def usage_summary(timezone_name: str = "Asia/Shanghai", principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    ent = db.scalar(select(Entitlement).where(Entitlement.user_id == principal.user.id))
    period_start, period_end = _day_window(timezone_name)
    rows = db.execute(select(UsageEvent.unit_type, func.sum(UsageEvent.units)).where(
        UsageEvent.user_id == principal.user.id,
        UsageEvent.status == "succeeded",
        UsageEvent.completed_at >= period_start,
        UsageEvent.completed_at < period_end,
    ).group_by(UsageEvent.unit_type)).all()
    used = {unit: int(value or 0) for unit, value in rows}
    credits_micros = db.scalar(select(func.coalesce(func.sum(UsageEvent.credits_charged_micros), 0)).where(
        UsageEvent.user_id == principal.user.id,
        UsageEvent.status == "succeeded",
        UsageEvent.completed_at >= period_start,
        UsageEvent.completed_at < period_end,
    )) or 0
    quotas = ent.quotas if ent else {}
    return {
        "period": "day",
        "timezone": timezone_name,
        "period_start": period_start,
        "period_end": period_end,
        "today_credits": round(int(credits_micros) / 1_000_000, 6),
        "used": used,
        "quotas": quotas,
        "as_of": utcnow(),
    }


@app.get("/api/v1/billing/summary")
def billing_summary(
    timezone_name: str = "Asia/Shanghai",
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    period_start, period_end = _day_window(timezone_name)
    thirty_days_start = period_start - timedelta(days=29)
    credited_micros = db.scalar(select(func.coalesce(func.sum(CreditTransaction.credits_micros), 0)).where(
        CreditTransaction.user_id == principal.user.id,
    )) or 0
    spent_micros = db.scalar(select(func.coalesce(func.sum(UsageEvent.credits_charged_micros), 0)).where(
        UsageEvent.user_id == principal.user.id,
        UsageEvent.status == "succeeded",
    )) or 0
    today_micros = db.scalar(select(func.coalesce(func.sum(UsageEvent.credits_charged_micros), 0)).where(
        UsageEvent.user_id == principal.user.id,
        UsageEvent.status == "succeeded",
        UsageEvent.completed_at >= period_start,
        UsageEvent.completed_at < period_end,
    )) or 0
    thirty_day_micros = db.scalar(select(func.coalesce(func.sum(UsageEvent.credits_charged_micros), 0)).where(
        UsageEvent.user_id == principal.user.id,
        UsageEvent.status == "succeeded",
        UsageEvent.completed_at >= thirty_days_start,
        UsageEvent.completed_at < period_end,
    )) or 0
    breakdown_rows = db.execute(select(
        UsageEvent.capability,
        func.sum(UsageEvent.credits_charged_micros),
        func.count(UsageEvent.id),
    ).where(
        UsageEvent.user_id == principal.user.id,
        UsageEvent.status == "succeeded",
        UsageEvent.completed_at >= thirty_days_start,
        UsageEvent.completed_at < period_end,
    ).group_by(UsageEvent.capability).order_by(func.sum(UsageEvent.credits_charged_micros).desc())).all()
    transactions = db.scalars(select(CreditTransaction).where(
        CreditTransaction.user_id == principal.user.id,
    ).order_by(CreditTransaction.created_at.desc()).limit(50)).all()
    recent_usage = db.scalars(select(UsageEvent).where(
        UsageEvent.user_id == principal.user.id,
        UsageEvent.status == "succeeded",
    ).order_by(UsageEvent.completed_at.desc()).limit(30)).all()
    return {
        "balance_credits": _credits(int(credited_micros) - int(spent_micros)),
        "credited_credits": _credits(credited_micros),
        "spent_credits": _credits(spent_micros),
        "today_credits": _credits(today_micros),
        "thirty_day_credits": _credits(thirty_day_micros),
        "timezone": timezone_name,
        "as_of": utcnow(),
        "breakdown": [{
            "capability": capability,
            "credits": _credits(amount),
            "requests": int(count or 0),
        } for capability, amount, count in breakdown_rows],
        "recharges": [{
            "id": item.id,
            "kind": item.kind,
            "credits": _credits(item.credits_micros),
            "payment_amount_cny": round(item.payment_amount_micros / 1_000_000, 2),
            "currency": item.currency,
            "note": item.note,
            "reference_id": item.reference_id,
            "created_at": item.created_at,
        } for item in transactions],
        "recent_usage": [{
            "id": item.id,
            "capability": item.capability,
            "credits": _credits(item.credits_charged_micros),
            "status": item.status,
            "created_at": item.completed_at or item.created_at,
        } for item in recent_usage],
    }


@app.post("/api/v1/feedback")
def create_feedback(req: FeedbackRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    item = Feedback(
        organization_id=principal.user.organization_id,
        user_id=principal.user.id,
        device_id=principal.device.id,
        category=req.category,
        message=req.message,
        request_id=req.request_id,
    )
    db.add(item)
    db.commit()
    return {"ok": True, "id": item.id}


@app.get("/api/v1/models/capabilities")
def capabilities(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    del principal
    routes = db.scalars(select(ModelRoute).order_by(ModelRoute.alias)).all()
    return {"items": [{"alias": r.alias, "available": bool(r.enabled and r.provider_model)} for r in routes]}


async def _run_inference(req: InferenceRequest, principal: Principal, db: Session) -> dict:
    route = db.get(ModelRoute, req.capability)
    if not route or not route.enabled or not route.provider_model:
        raise HTTPException(503, "当前智能能力暂未开放")
    try:
        event, created = _reserve_usage(db, principal, req)
        if not created:
            if event.status == "succeeded":
                return {"request_id": event.id, "status": "already_completed"}
            raise HTTPException(409, "相同请求正在处理中")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "相同请求正在处理中")
    gateway = ProviderGateway()
    started = time.perf_counter()
    try:
        if req.capability in {"text.fast", "text.reasoning"}:
            data, provider_request_id = await gateway.chat(route.provider_model, req.payload)
        elif req.capability == "text.vision":
            data, provider_request_id = await gateway.vision(route.provider_model, req.payload)
        elif req.capability == "image.standard":
            data, provider_request_id = await gateway.image(route.provider_model, req.payload)
        elif req.capability == "embedding.standard":
            data, provider_request_id = await gateway.embeddings(route.provider_model, req.payload)
        elif req.capability == "speech.tts":
            data, provider_request_id = await gateway.tts(route.provider_model, req.payload)
        else:
            raise HTTPException(400, "请使用视频任务接口")
        latency = int((time.perf_counter() - started) * 1000)
        event = db.get(UsageEvent, event.id)
        _complete_usage(event, data, latency, provider_request_id, req.payload, route.config)
        db.commit()
        return {"request_id": event.id, "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        latency = int((time.perf_counter() - started) * 1000)
        event = db.get(UsageEvent, event.id)
        _fail_usage(event, exc, latency)
        db.commit()
        if isinstance(exc, ProviderError):
            raise HTTPException(502, {"message": "智能服务暂时不可用", "request_id": event.id})
        raise


@app.post("/api/v1/inference/chat")
async def inference_chat(req: InferenceRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if req.capability not in {"text.fast", "text.reasoning"}:
        raise HTTPException(400, "能力类型与接口不匹配")
    return await _run_inference(req, principal, db)


@app.post("/api/v1/inference/vision")
async def inference_vision(req: InferenceRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if req.capability != "text.vision":
        raise HTTPException(400, "能力类型与接口不匹配")
    return await _run_inference(req, principal, db)


@app.post("/api/v1/inference/image")
async def inference_image(req: InferenceRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if req.capability != "image.standard":
        raise HTTPException(400, "能力类型与接口不匹配")
    return await _run_inference(req, principal, db)


@app.post("/api/v1/inference/tts")
async def inference_tts(req: InferenceRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if req.capability != "speech.tts":
        raise HTTPException(400, "能力类型与接口不匹配")
    return await _run_inference(req, principal, db)


@app.post("/api/v1/inference/embeddings")
async def inference_embeddings(req: InferenceRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if req.capability != "embedding.standard":
        raise HTTPException(400, "能力类型与接口不匹配")
    return await _run_inference(req, principal, db)


@app.post("/api/v1/inference/video/tasks")
async def create_video_task(req: InferenceRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if req.capability != "video.standard":
        raise HTTPException(400, "能力类型与接口不匹配")
    route = db.get(ModelRoute, req.capability)
    if not route or not route.enabled or not route.provider_model:
        raise HTTPException(503, "当前智能能力暂未开放")
    event, created = _reserve_usage(db, principal, req)
    if not created:
        existing = db.scalar(select(VideoTask).where(VideoTask.usage_event_id == event.id))
        if existing:
            return {"task_id": existing.id, "status": existing.status}
        raise HTTPException(409, "相同请求正在处理中")
    db.commit()
    started = time.perf_counter()
    try:
        data, provider_request_id = await ProviderGateway().create_video(route.provider_model, req.payload)
        provider_task_id = str(data.get("id") or "")
        if not provider_task_id:
            raise RuntimeError("provider returned no task id")
        task = VideoTask(
            user_id=principal.user.id,
            device_id=principal.device.id,
            provider_task_id=provider_task_id,
            usage_event_id=event.id,
        )
        db.add(task)
        event = db.get(UsageEvent, event.id)
        event.provider_request_id = provider_request_id
        event.latency_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        return {"task_id": task.id, "status": task.status, "request_id": event.id}
    except Exception as exc:
        event = db.get(UsageEvent, event.id)
        _fail_usage(event, exc, int((time.perf_counter() - started) * 1000))
        db.commit()
        raise HTTPException(502, {"message": "视频生成服务暂时不可用", "request_id": event.id})


@app.get("/api/v1/inference/video/tasks/{task_id}")
async def get_video_task(task_id: str, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    task = db.get(VideoTask, task_id)
    if not task or task.user_id != principal.user.id:
        raise HTTPException(404, "任务不存在")
    data, provider_request_id = await ProviderGateway().get_video(task.provider_task_id)
    task.status = str(data.get("status") or "unknown")
    event = db.get(UsageEvent, task.usage_event_id)
    if task.status == "succeeded" and event.status != "succeeded":
        route = db.get(ModelRoute, task.model_alias)
        _complete_usage(
            event,
            data,
            event.latency_ms,
            provider_request_id or event.provider_request_id,
            {"duration": event.units},
            route.config if route else {},
        )
    elif task.status == "failed" and event.status != "failed":
        _fail_usage(event, RuntimeError("video_failed"), event.latency_ms)
    db.commit()
    safe_data = {
        "status": task.status,
        "content": data.get("content") or {},
        "error": "视频生成未完成" if task.status == "failed" else "",
    }
    return {"task_id": task.id, "request_id": event.id, **safe_data}


@app.get("/api/v1/admin/dashboard")
def admin_dashboard(admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    del admin
    total_users = db.scalar(select(func.count(User.id)).where(User.role != "admin")) or 0
    active_users = db.scalar(select(func.count(User.id)).where(User.role != "admin", User.status == "active")) or 0
    month_requests = db.scalar(select(func.count(UsageEvent.id)).where(UsageEvent.created_at >= _month_start())) or 0
    success_requests = db.scalar(select(func.count(UsageEvent.id)).where(UsageEvent.created_at >= _month_start(), UsageEvent.status == "succeeded")) or 0
    return {
        "users": {"total": total_users, "active": active_users},
        "requests": {"month": month_requests, "success": success_requests},
        "success_rate": round(success_requests / month_requests * 100, 1) if month_requests else 0,
        "open_feedback": db.scalar(select(func.count(Feedback.id)).where(Feedback.status == "open")) or 0,
    }


@app.get("/api/v1/admin/users")
def admin_users(admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    del admin
    rows = db.scalars(select(User).order_by(User.created_at.desc())).all()
    result = []
    for user in rows:
        ent = db.scalar(select(Entitlement).where(Entitlement.user_id == user.id))
        device_count = db.scalar(select(func.count(Device.id)).where(Device.user_id == user.id, Device.status == "active")) or 0
        credited_micros = db.scalar(select(func.coalesce(func.sum(CreditTransaction.credits_micros), 0)).where(
            CreditTransaction.user_id == user.id,
        )) or 0
        spent_micros = db.scalar(select(func.coalesce(func.sum(UsageEvent.credits_charged_micros), 0)).where(
            UsageEvent.user_id == user.id,
            UsageEvent.status == "succeeded",
        )) or 0
        result.append({**_user_json(user), "device_count": device_count, "entitlement": {
            "valid_until": ent.valid_until if ent else None,
            "device_limit": ent.device_limit if ent else 0,
            "quotas": ent.quotas if ent else {},
        }, "credits": {
            "balance": _credits(int(credited_micros) - int(spent_micros)),
            "credited": _credits(credited_micros),
            "spent": _credits(spent_micros),
        }})
    return {"items": result}


@app.post("/api/v1/admin/users")
def admin_create_user(req: AdminUserCreateRequest, admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    email = req.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "该账号已开通")
    organization = Organization(name=req.organization_name.strip() or req.display_name.strip())
    db.add(organization)
    db.flush()
    user = User(
        organization_id=organization.id,
        email=email,
        display_name=req.display_name.strip(),
        password_hash=hash_password(req.password),
        role="user",
        status="active",
    )
    db.add(user)
    db.flush()
    entitlement = Entitlement(
        user_id=user.id,
        valid_until=utcnow() + timedelta(days=req.entitlement_days),
        device_limit=req.device_limit,
        features={"cloud_models": True},
        quotas={**DEFAULT_QUOTAS, **req.quotas},
    )
    db.add(entitlement)
    _audit(db, admin.user.id, "create_user", "user", user.id, {
        "email": email,
        "device_limit": req.device_limit,
        "entitlement_days": req.entitlement_days,
    })
    db.commit()
    return {
        "user": _user_json(user),
        "entitlement": {
            "valid_until": entitlement.valid_until,
            "device_limit": entitlement.device_limit,
        },
    }


@app.get("/api/v1/admin/login-blocks")
def admin_login_blocks(admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    del admin
    rows = db.scalars(select(LoginDeviceBlock).where(
        LoginDeviceBlock.status == "blocked",
    ).order_by(LoginDeviceBlock.blocked_at.desc())).all()
    return {"items": [{
        "id": item.id,
        "device_name": item.device_name,
        "installation_id": item.installation_id,
        "attempted_account": item.attempted_account,
        "failed_attempts": item.failed_attempts,
        "app_version": item.app_version,
        "blocked_at": item.blocked_at,
        "last_failure_at": item.last_failure_at,
    } for item in rows]}


@app.delete("/api/v1/admin/login-blocks/{block_id}")
def admin_remove_login_block(block_id: str, admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    guard = db.get(LoginDeviceBlock, block_id)
    if not guard or guard.status != "blocked":
        raise HTTPException(404, "黑名单设备不存在")
    matching_devices = db.scalars(select(Device).where(Device.installation_id == guard.installation_id)).all()
    if guard.fingerprint_hash:
        fingerprint_devices = db.scalars(select(Device).where(Device.fingerprint_hash == guard.fingerprint_hash)).all()
        matching_devices = list({item.id: item for item in [*matching_devices, *fingerprint_devices]}.values())
    for device in matching_devices:
        if device.status == "blocked":
            device.status = "active"
    _audit(db, admin.user.id, "remove_login_block", "login_device_block", guard.id, {
        "attempted_account": guard.attempted_account,
        "installation_id": guard.installation_id,
    })
    db.delete(guard)
    db.commit()
    return {"ok": True}


@app.post("/api/v1/admin/invitations")
def admin_invite(req: InviteRequest, admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    email = req.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "该邮箱已开通")
    organization = Organization(name=req.organization_name.strip() or req.email.split("@", 1)[0])
    db.add(organization)
    db.flush()
    code = random_token(24)
    invitation = Invitation(
        organization_id=organization.id,
        email=email,
        code_hash=token_hash(code),
        role=req.role,
        entitlement_days=req.entitlement_days,
        device_limit=req.device_limit,
        quotas={**DEFAULT_QUOTAS, **req.quotas},
        expires_at=utcnow() + timedelta(days=7),
        created_by=admin.user.id,
    )
    db.add(invitation)
    _audit(db, admin.user.id, "invite_user", "invitation", invitation.id, {"email": email})
    db.commit()
    return {
        "id": invitation.id,
        "email": email,
        "invitation_code": code,
        "activation_url": f"{settings.public_base_url.rstrip('/')}/activate?code={code}",
        "expires_at": invitation.expires_at,
        "requested_device_limit": req.device_limit,
        "requested_quotas": {**DEFAULT_QUOTAS, **req.quotas},
    }


@app.post("/api/v1/admin/users/{user_id}/reset-password")
def admin_reset_password(user_id: str, admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user or user.role == "admin":
        raise HTTPException(404, "用户不存在")
    temporary_password = secrets.token_urlsafe(14)
    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    now = utcnow()
    for session in db.scalars(select(RefreshSession).where(
        RefreshSession.user_id == user.id,
        RefreshSession.revoked_at.is_(None),
    )):
        session.revoked_at = now
    _audit(db, admin.user.id, "reset_password", "user", user.id)
    db.commit()
    return {"temporary_password": temporary_password, "must_change_password": True}


@app.put("/api/v1/admin/users/{user_id}/status")
def admin_user_status(user_id: str, req: UserStatusUpdate, admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user or user.role == "admin":
        raise HTTPException(404, "用户不存在")
    user.status = req.status
    if req.status != "active":
        now = utcnow()
        for session in db.scalars(select(RefreshSession).where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))):
            session.revoked_at = now
    _audit(db, admin.user.id, "update_user_status", "user", user.id, {"status": req.status})
    db.commit()
    return _user_json(user)


@app.put("/api/v1/admin/users/{user_id}/entitlement")
def admin_entitlement(user_id: str, req: EntitlementUpdate, admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    ent = db.scalar(select(Entitlement).where(Entitlement.user_id == user_id))
    if not ent:
        raise HTTPException(404, "用户授权不存在")
    if req.valid_days_from_now is not None:
        ent.valid_until = utcnow() + timedelta(days=req.valid_days_from_now)
    if req.device_limit is not None:
        ent.device_limit = req.device_limit
    if req.quotas is not None:
        ent.quotas = {**DEFAULT_QUOTAS, **req.quotas}
    _audit(db, admin.user.id, "update_entitlement", "user", user_id, req.model_dump(exclude_none=True))
    db.commit()
    return {"ok": True, "valid_until": ent.valid_until, "device_limit": ent.device_limit, "quotas": ent.quotas}


@app.post("/api/v1/admin/users/{user_id}/credits")
def admin_recharge(
    user_id: str,
    req: AdminCreditRechargeRequest,
    admin: Principal = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """统一计费（方案B）：管理员为用户充值 credits（写入 credit_transactions 流水）。"""
    user = db.get(User, user_id)
    if not user or user.role == "admin":
        raise HTTPException(404, "用户不存在")
    if not db.scalar(select(Entitlement).where(Entitlement.user_id == user_id)):
        raise HTTPException(404, "用户授权不存在")
    credits_micros = int((Decimal(str(req.credits)) * Decimal("1000000")).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
    if credits_micros <= 0:
        raise HTTPException(400, "充值 credits 必须大于 0")
    reference = req.reference_id or f"manual-{random_token(12)}"
    db.add(CreditTransaction(
        organization_id=user.organization_id,
        user_id=user_id,
        kind=req.kind,
        credits_micros=credits_micros,
        payment_amount_micros=req.payment_amount_micros,
        currency=req.currency,
        note=req.note or "管理员手动充值",
        reference_id=reference,
        created_by=admin.user.id,
    ))
    _audit(db, admin.user.id, "recharge_credits", "user", user_id, {
        "credits": req.credits,
        "kind": req.kind,
        "reference_id": reference,
    })
    db.commit()
    return {
        "ok": True,
        "user_id": user_id,
        "credits": _credits(credits_micros),
        "balance": _credits(_credit_balance(db, user_id)),
        "reference_id": reference,
    }


@app.delete("/api/v1/admin/devices/{device_id}")
def admin_revoke_device(device_id: str, admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "设备不存在")
    device.status = "revoked"
    now = utcnow()
    for session in db.scalars(select(RefreshSession).where(RefreshSession.device_id == device.id, RefreshSession.revoked_at.is_(None))):
        session.revoked_at = now
    _audit(db, admin.user.id, "revoke_device", "device", device.id)
    db.commit()
    return {"ok": True}


@app.get("/api/v1/admin/models")
def admin_models(admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    del admin
    rows = db.scalars(select(ModelRoute).order_by(ModelRoute.alias)).all()
    return {"items": [{
        "alias": r.alias,
        "configured": bool(r.provider_model),
        "enabled": r.enabled,
        "rollout_percent": r.rollout_percent,
        "config": r.config,
    } for r in rows]}


@app.put("/api/v1/admin/models/{alias:path}")
def admin_model_update(alias: str, req: ModelRouteUpdate, admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    if alias not in CAPABILITY_UNITS:
        raise HTTPException(404, "能力不存在")
    route = db.get(ModelRoute, alias) or ModelRoute(alias=alias)
    route.provider_model = req.provider_model
    route.enabled = req.enabled
    route.rollout_percent = req.rollout_percent
    route.config = req.config
    db.add(route)
    _audit(db, admin.user.id, "update_model_route", "model_route", alias, {
        "enabled": req.enabled,
        "rollout_percent": req.rollout_percent,
        "configured": bool(req.provider_model),
    })
    db.commit()
    return {"ok": True}


@app.get("/api/v1/admin/usage")
def admin_usage(admin: Principal = Depends(current_admin), db: Session = Depends(get_db), limit: int = 100):
    del admin
    rows = db.scalars(select(UsageEvent).order_by(UsageEvent.created_at.desc()).limit(min(max(limit, 1), 500))).all()
    return {"items": [{
        "id": row.id,
        "user_id": row.user_id,
        "capability": row.capability,
        "status": row.status,
        "units": row.units,
        "unit_type": row.unit_type,
        "provider_usage": row.provider_usage,
        "provider_cost_cny": round(row.provider_cost_micros / 1_000_000, 6),
        "credits_charged": round(row.credits_charged_micros / 1_000_000, 6),
        "latency_ms": row.latency_ms,
        "error_code": row.error_code,
        "created_at": row.created_at,
    } for row in rows]}


@app.get("/api/v1/admin/provider-billing")
def admin_provider_billing(admin: Principal = Depends(current_admin), db: Session = Depends(get_db), limit: int = 31):
    del admin
    rows = db.scalars(
        select(ProviderBillingDaily)
        .order_by(ProviderBillingDaily.billing_date.desc())
        .limit(min(max(limit, 1), 366))
    ).all()
    return {"items": [{
        "provider": row.provider,
        "billing_date": row.billing_date,
        "actual_cost_cny": round(row.actual_cost_micros / 1_000_000, 6),
        "currency": row.currency,
        "line_count": row.line_count,
        "synced_at": row.synced_at,
    } for row in rows]}


@app.get("/api/v1/admin/feedback")
def admin_feedback(admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    del admin
    rows = db.scalars(select(Feedback).order_by(Feedback.created_at.desc()).limit(300)).all()
    return {"items": [{
        "id": row.id,
        "user_id": row.user_id,
        "category": row.category,
        "message": row.message,
        "request_id": row.request_id,
        "status": row.status,
        "created_at": row.created_at,
    } for row in rows]}


@app.exception_handler(ProviderError)
async def provider_error_handler(_request: Request, exc: ProviderError):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=502, content={"detail": "智能服务暂时不可用", "code": exc.code})
