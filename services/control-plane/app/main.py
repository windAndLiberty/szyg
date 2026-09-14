from __future__ import annotations

import hashlib
import hmac
import json
import logging
import mimetypes
import asyncio
import math
import secrets
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session

from .config import get_settings
from .database import (
    AdminAuditLog,
    CreditLedgerEntry,
    CreditWallet,
    Device,
    EmailVerificationChallenge,
    Entitlement,
    Feedback,
    Invitation,
    LoginDeviceBlock,
    ModelRoute,
    Organization,
    PaymentOrder,
    PRIVATE_PRODUCT_ID,
    Product,
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
    PaymentOrderCreateRequest,
    PublicRegisterRequest,
    PublicRegisterCodeRequest,
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
from .usage_accounting import CREDITS_PER_CNY, estimate_credits_micros, settle_usage
from .alipay import AlipayGateway
from .ses import SesDeliveryError, TencentSesSender
from .wallets import (
    credit as credit_wallet,
    ensure_wallet,
    release as release_wallet_reservation,
    reserve as reserve_wallet,
    settle as settle_wallet,
)

settings = get_settings()
app = FastAPI(title="SZYG Control", version="1.0.0", docs_url=None if settings.environment == "production" else "/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-App-Version"],
)


def _reference_root() -> Path:
    root = Path(settings.reference_temp_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _reference_signature(reference_id: str, expires_at: int) -> str:
    message = f"{reference_id}:{expires_at}".encode("utf-8")
    return hmac.new(settings.jwt_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _cleanup_reference_uploads() -> None:
    now = int(time.time())
    root = _reference_root()
    for metadata_path in root.glob("*.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if int(metadata.get("expires_at") or 0) > now:
                continue
            (root / str(metadata.get("stored_name") or "")).unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            continue


@app.post("/api/v1/inference/references")
async def upload_inference_reference(
    file: UploadFile = File(...),
    principal: Principal = Depends(current_principal),
):
    del principal
    _cleanup_reference_uploads()
    suffix = Path(file.filename or "reference.bin").suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".mp3", ".wav"}
    if suffix not in allowed:
        raise HTTPException(400, "参考素材格式暂不支持")
    reference_id = secrets.token_hex(24)
    stored_name = f"{reference_id}{suffix}"
    target = _reference_root() / stored_name
    limit = settings.reference_max_mb * 1024 * 1024
    size = 0
    try:
        with target.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"单个参考素材不能超过 {settings.reference_max_mb}MB")
                handle.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    if not size:
        target.unlink(missing_ok=True)
        raise HTTPException(400, "参考素材为空")
    expires_at = int(time.time()) + settings.reference_ttl_hours * 3600
    content_type = file.content_type or mimetypes.guess_type(stored_name)[0] or "application/octet-stream"
    metadata = {"stored_name": stored_name, "content_type": content_type, "expires_at": expires_at}
    (_reference_root() / f"{reference_id}.json").write_text(json.dumps(metadata), encoding="utf-8")
    signature = _reference_signature(reference_id, expires_at)
    base = settings.public_base_url.rstrip("/")
    return {
        "url": f"{base}/api/v1/inference/references/{reference_id}?expires={expires_at}&signature={signature}",
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc),
        "size": size,
    }


@app.get("/api/v1/inference/references/{reference_id}")
def read_inference_reference(reference_id: str, expires: int, signature: str):
    if expires <= int(time.time()) or not hmac.compare_digest(signature, _reference_signature(reference_id, expires)):
        raise HTTPException(404, "参考素材已过期")
    metadata_path = _reference_root() / f"{reference_id}.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(404, "参考素材不存在")
    if int(metadata.get("expires_at") or 0) != expires:
        raise HTTPException(404, "参考素材不存在")
    target = _reference_root() / str(metadata.get("stored_name") or "")
    if not target.is_file() or target.parent != _reference_root():
        raise HTTPException(404, "参考素材不存在")
    return FileResponse(target, media_type=str(metadata.get("content_type") or "application/octet-stream"))

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
    "video.presenter": "video_seconds",
    "video.omnihuman": "video_seconds",
    "video.subject_detection": "image_count",
    "speech.tts": "speech_characters",
    "speech.asr": "asr_seconds",
    "embedding.standard": "embedding_tokens",
    "geo.search.doubao": "text_tokens",
    "geo.search.openai": "text_tokens",
    "geo.search.perplexity": "text_tokens",
    "geo.search.gemini": "text_tokens",
}

DEFAULT_QUOTAS = {
    "text_tokens": 1_000_000,
    "image_count": 200,
    "video_seconds": 600,
    "speech_characters": 200_000,
    "asr_seconds": 72000,  # 默认 20 小时
    "embedding_tokens": 1_000_000,
}

def _credits(value: int | None) -> float:
    return round(int(value or 0) / 1_000_000, 6)


def _payment_json(order: PaymentOrder, *, payment_url: str = "") -> dict:
    return {
        "id": order.id,
        "channel": order.channel,
        "merchant_order_no": order.merchant_order_no,
        "status": order.status,
        "amount_cny": round(order.amount_micros / 1_000_000, 2),
        "credits": _credits(order.credits_micros),
        "currency": order.currency,
        "payment_url": payment_url,
        "expires_at": order.expires_at,
        "paid_at": order.paid_at,
        "credited_at": order.credited_at,
        "created_at": order.created_at,
    }


def _payment_product_brand(product_id: str) -> tuple[str, str]:
    if product_id == "xiaoyu_public":
        return "XY", "小妤AI"
    return "SZY", "数字员工"


def _credit_balance(db: Session, user_id: str) -> int:
    """The materialized wallet is the only source of truth after cutover."""
    wallet = db.scalar(select(CreditWallet).where(CreditWallet.user_id == user_id))
    return int(wallet.balance_micros) if wallet else 0


def _available_credit_balance(db: Session, user_id: str) -> int:
    wallet = db.scalar(select(CreditWallet).where(CreditWallet.user_id == user_id))
    return int(wallet.balance_micros) - int(wallet.reserved_micros) if wallet else 0


def _billing_mode(user: User, entitlement: Entitlement) -> str:
    configured = str((entitlement.features or {}).get("billing_mode") or "").strip().lower()
    if configured in {"credits", "internal"}:
        return configured
    return "internal" if user.role == "admin" else "credits"


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
        "product_id": user.product_id,
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


def _login_guard(db: Session, product_id: str, device_input) -> LoginDeviceBlock | None:
    identity_key, _ = _login_identity(device_input)
    return db.scalar(select(LoginDeviceBlock).where(
        LoginDeviceBlock.product_id == product_id,
        LoginDeviceBlock.identity_key == identity_key,
    ).with_for_update())


def _block_matching_devices(db: Session, guard: LoginDeviceBlock) -> None:
    rows = db.scalars(select(Device).join(User, User.id == Device.user_id).where(
        User.product_id == guard.product_id,
        Device.installation_id == guard.installation_id,
    )).all()
    if guard.fingerprint_hash:
        fingerprint_rows = db.scalars(select(Device).join(User, User.id == Device.user_id).where(
            User.product_id == guard.product_id,
            Device.fingerprint_hash == guard.fingerprint_hash,
        )).all()
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
    guard = _login_guard(db, req.product_id, req.device)
    now = utcnow()
    if guard is None:
        candidate = LoginDeviceBlock(
            product_id=req.product_id,
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
            guard = _login_guard(db, req.product_id, req.device)
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


def _clear_login_failures(db: Session, product_id: str, device_input) -> None:
    guard = _login_guard(db, product_id, device_input)
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
    access_token, access_expires = create_access_token(
        user.id, user.organization_id, user.product_id, user.role, device.id
    )
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
        user.product_id,
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
    if capability.startswith("text.") or capability.startswith("geo.search."):
        return max(1, len(json.dumps(payload, ensure_ascii=False)) // 2)
    if capability == "image.standard":
        return max(1, int(payload.get("n") or 1))
    if capability == "video.subject_detection":
        return 1
    if capability in {"video.standard", "video.presenter", "video.omnihuman"}:
        return max(1, int(payload.get("duration") or 5))
    if capability == "speech.tts":
        return max(1, len(str(payload.get("input") or payload.get("text") or "")))
    if capability == "speech.asr":
        # 提交时无法精确知道音频时长；按 30 秒保守预估，
        # 实际结算以 provider 返回的 audio_info.duration 为准。
        return max(1, int(payload.get("estimated_seconds") or 30))
    if capability == "embedding.standard":
        return max(1, len(json.dumps(payload.get("input") or "", ensure_ascii=False)) // 2)
    return 1


def _ensure_active_entitlement(db: Session, user: User) -> Entitlement:
    """授权到期机制已取消：授权永不过期。

    缺失、停用或已到期的授权会被自动补发为长期有效（10 年），
    不再拦截登录与推理请求。设备限制、计费模式与配额逻辑保持不变。
    """
    entitlement = db.scalar(
        select(Entitlement).where(Entitlement.user_id == user.id).with_for_update()
    )
    if entitlement is None:
        entitlement = Entitlement(
            user_id=user.id,
            valid_until=utcnow() + timedelta(days=3650),
            device_limit=settings.default_device_limit,
            features={"cloud_models": True},
            quotas=dict(DEFAULT_QUOTAS),
        )
        db.add(entitlement)
        db.flush()
        return entitlement
    if entitlement.status != "active" or as_utc(entitlement.valid_until) <= utcnow():
        entitlement.status = "active"
        entitlement.valid_until = utcnow() + timedelta(days=3650)
        db.flush()
    return entitlement


def _reserve_usage(db: Session, principal: Principal, req: InferenceRequest) -> tuple[UsageEvent, bool]:
    existing = db.scalar(select(UsageEvent).where(
        UsageEvent.user_id == principal.user.id,
        UsageEvent.idempotency_key == req.idempotency_key,
    ))
    if existing:
        return existing, False
    entitlement = _ensure_active_entitlement(db, principal.user)
    unit_type = CAPABILITY_UNITS.get(req.capability)
    if not unit_type:
        raise HTTPException(400, "未知的智能能力")
    estimate = _estimate_units(req.capability, req.payload)
    billing_mode = _billing_mode(principal.user, entitlement)
    if billing_mode == "credits":
        # 普通用户始终使用预付 Credits。没有充值记录也不能回退到免费月度配额。
        balance = _available_credit_balance(db, principal.user.id)
        route = db.get(ModelRoute, req.capability)
        estimate_credits = estimate_credits_micros(
            req.capability,
            req.payload,
            route.config if route else {},
            route.provider_model if route else "",
        )
        if max(0, balance) - estimate_credits < 0:
            raise HTTPException(429, "Credits 余额不足，请联系管理员调整额度")
    route = db.get(ModelRoute, req.capability)
    event = UsageEvent(
        product_id=principal.user.product_id,
        organization_id=principal.user.organization_id,
        user_id=principal.user.id,
        device_id=principal.device.id,
        idempotency_key=req.idempotency_key,
        capability=req.capability,
        status="reserved",
        units=estimate,
        unit_type=unit_type,
        provider_model=route.provider_model if route else "",
        credits_charged_micros=estimate_credits if billing_mode == "credits" else 0,
        reserved_credits_micros=estimate_credits if billing_mode == "credits" else 0,
        app_version=req.app_version or principal.device.app_version,
    )
    db.add(event)
    db.flush()
    if billing_mode == "credits":
        try:
            reserve_wallet(db, principal.user, event, estimate_credits)
        except ValueError as exc:
            raise HTTPException(429, str(exc)) from exc
    return event, True


def _complete_usage(
    event: UsageEvent,
    data: dict,
    latency_ms: int,
    request_id: str,
    payload: dict,
    route_config: dict | None,
    provider_model: str,
) -> None:
    resolved_provider_model = str(data.get("provider_model") or provider_model)
    usage, provider_cost_micros, credits_micros, pricing_version, pricing_snapshot = settle_usage(
        event.capability,
        data,
        payload,
        route_config,
        resolved_provider_model,
    )
    if event.unit_type in {"text_tokens", "embedding_tokens"}:
        event.units = int(usage.get("total_tokens") or usage.get("input_tokens") or event.units)
    event.status = "succeeded"
    event.latency_ms = latency_ms
    event.provider_usage = usage
    event.provider_model = resolved_provider_model
    event.provider_cost_micros = provider_cost_micros
    event.credits_charged_micros = credits_micros
    event.pricing_version = pricing_version
    event.pricing_snapshot = pricing_snapshot
    event.estimated_cost = provider_cost_micros / 1_000_000
    event.provider_request_id = request_id
    event.completed_at = utcnow()
    db = object_session(event)
    if db and event.wallet_id:
        settle_wallet(db, event, credits_micros)
    event.reserved_credits_micros = 0


def _fail_usage(event: UsageEvent, exc: Exception, latency_ms: int) -> None:
    db = object_session(event)
    if db:
        release_wallet_reservation(db, event)
    event.status = "failed"
    event.units = 0
    event.credits_charged_micros = 0
    event.latency_ms = latency_ms
    event.error_code = getattr(exc, "code", "request_failed")[:80]
    # 保留上游真实消息用于诊断（例如火山 CV 具体拒绝原因），
    # 客户端收到的 HTTP 文案仍由 502/503 统一转换为“智能服务暂时不可用”。
    event.error_message = str(exc)[:500] or exc.__class__.__name__
    event.provider_request_id = getattr(exc, "request_id", "")[:160]
    event.completed_at = utcnow()


@app.on_event("startup")
def startup() -> None:
    settings.validate_production()
    create_schema()
    with SessionLocal.begin() as db:
        private_product = db.get(Product, PRIVATE_PRODUCT_ID)
        if not private_product:
            private_product = Product(id=PRIVATE_PRODUCT_ID, name="数字员工", registration_mode="invite_only")
            db.add(private_product)
        private_product.name = "数字员工"
        private_product.registration_mode = "invite_only"
        public_product = db.get(Product, "xiaoyu_public")
        if not public_product:
            public_product = Product(id="xiaoyu_public", name="小妤AI", registration_mode="self_service")
            db.add(public_product)
        public_product.name = "小妤AI"
        public_product.registration_mode = "self_service"
        db.flush()
        for alias, model in settings.capability_models.items():
            route = db.get(ModelRoute, alias)
            if not route:
                db.add(ModelRoute(alias=alias, provider_model=model, enabled=bool(model)))
            elif not route.provider_model and model:
                route.provider_model = model
                route.enabled = True
        if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
            email = settings.bootstrap_admin_email.lower().strip()
            if not db.scalar(select(User).where(User.product_id == settings.product_id, User.email == email)):
                org = Organization(product_id=settings.product_id, name="SZYG 内测管理")
                db.add(org)
                db.flush()
                admin = User(
                    product_id=settings.product_id,
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
                    features={"admin": True, "billing_mode": "internal"},
                    quotas={key: 0 for key in DEFAULT_QUOTAS},
                ))
        # Billing mode is explicit. Regular users are prepaid; administrators are internal.
        for user, entitlement in db.execute(
            select(User, Entitlement).join(Entitlement, Entitlement.user_id == User.id)
        ).all():
            ensure_wallet(db, user)
            features = dict(entitlement.features or {})
            if "billing_mode" not in features:
                features["billing_mode"] = "internal" if user.role == "admin" else "credits"
                entitlement.features = features
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
    if db.scalar(select(User).where(
        User.product_id == invitation.product_id,
        User.email == invitation.email,
    )):
        raise HTTPException(409, "该账户已经激活")
    user = User(
        product_id=invitation.product_id,
        organization_id=invitation.organization_id,
        email=invitation.email,
        display_name=req.display_name.strip(),
        password_hash=hash_password(req.password),
        role=invitation.role,
    )
    db.add(user)
    db.flush()
    ensure_wallet(db, user)
    entitlement = Entitlement(
        user_id=user.id,
        valid_until=utcnow() + timedelta(days=invitation.entitlement_days),
        device_limit=invitation.device_limit,
        features={"cloud_models": True, "billing_mode": "credits"},
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


def _registration_hash(value: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        value.strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _masked_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


@app.post("/api/v1/auth/register/code")
def public_register_code(
    req: PublicRegisterCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    product = db.get(Product, req.product_id)
    if not product or product.status != "active" or product.registration_mode != "self_service":
        raise HTTPException(403, "当前产品未开放自助注册")
    email = req.email.lower().strip()
    if db.scalar(select(User.id).where(User.product_id == req.product_id, User.email == email)):
        raise HTTPException(409, "该邮箱已经注册，请直接登录")

    now = utcnow()
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    ip_hash = _registration_hash(request.client.host if request.client else "unknown")
    fingerprint_hash = _registration_hash(req.device.fingerprint or req.device.installation_id)
    installation_hash = _registration_hash(req.device.installation_id)
    latest = db.scalar(
        select(EmailVerificationChallenge)
        .where(
            EmailVerificationChallenge.product_id == req.product_id,
            EmailVerificationChallenge.email == email,
            EmailVerificationChallenge.status != "send_failed",
        )
        .order_by(EmailVerificationChallenge.created_at.desc())
    )
    if latest and as_utc(latest.created_at) > now - timedelta(seconds=60):
        raise HTTPException(429, "验证码发送过于频繁，请60秒后再试")

    def challenge_count(*conditions) -> int:
        return int(db.scalar(
            select(func.count(EmailVerificationChallenge.id)).where(*conditions)
        ) or 0)

    common = (
        EmailVerificationChallenge.product_id == req.product_id,
        EmailVerificationChallenge.status != "send_failed",
    )
    if challenge_count(*common, EmailVerificationChallenge.email == email, EmailVerificationChallenge.created_at >= hour_ago) >= 5:
        raise HTTPException(429, "该邮箱验证码发送次数过多，请稍后再试")
    if challenge_count(*common, EmailVerificationChallenge.ip_hash == ip_hash, EmailVerificationChallenge.created_at >= hour_ago) >= 20:
        raise HTTPException(429, "当前网络注册请求过多，请稍后再试")
    if challenge_count(*common, EmailVerificationChallenge.device_fingerprint_hash == fingerprint_hash, EmailVerificationChallenge.created_at >= day_ago) >= 10:
        raise HTTPException(429, "当前设备验证码发送次数过多，请明天再试")

    for previous in db.scalars(select(EmailVerificationChallenge).where(
        EmailVerificationChallenge.product_id == req.product_id,
        EmailVerificationChallenge.email == email,
        EmailVerificationChallenge.status == "pending",
    )):
        previous.status = "superseded"
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = EmailVerificationChallenge(
        product_id=req.product_id,
        email=email,
        code_hash=token_hash(code),
        ip_hash=ip_hash,
        device_fingerprint_hash=fingerprint_hash,
        installation_id_hash=installation_hash,
        expires_at=now + timedelta(minutes=10),
    )
    db.add(challenge)
    db.commit()
    try:
        if settings.environment != "test":
            TencentSesSender(settings).send_registration_code(email, code)
    except SesDeliveryError as exc:
        challenge.status = "send_failed"
        db.commit()
        logger.warning("Registration email delivery failed: %s", exc)
        raise HTTPException(503, "验证码邮件发送失败，请稍后再试") from exc

    result = {
        "verification_id": challenge.id,
        "email": _masked_email(email),
        "expires_in_seconds": 600,
        "retry_after_seconds": 60,
    }
    if settings.environment == "test":
        result["test_code"] = code
    return result


@app.post("/api/v1/auth/register")
def public_register(req: PublicRegisterRequest, db: Session = Depends(get_db)):
    product = db.get(Product, req.product_id)
    if not product or product.status != "active" or product.registration_mode != "self_service":
        raise HTTPException(403, "当前产品未开放自助注册")
    email = req.email.lower().strip()
    if db.scalar(select(User.id).where(User.product_id == req.product_id, User.email == email)):
        raise HTTPException(409, "该邮箱已经注册，请直接登录")

    now = utcnow()
    challenge = db.scalar(
        select(EmailVerificationChallenge)
        .where(EmailVerificationChallenge.id == req.verification_id)
        .with_for_update()
    )
    if not challenge or challenge.product_id != req.product_id or challenge.email != email:
        raise HTTPException(400, "验证码记录无效，请重新获取")
    if challenge.status != "pending":
        raise HTTPException(400, "验证码已经失效，请重新获取")
    if as_utc(challenge.expires_at) <= now:
        challenge.status = "expired"
        db.commit()
        raise HTTPException(400, "验证码已经过期，请重新获取")
    if challenge.attempts >= 5:
        challenge.status = "locked"
        db.commit()
        raise HTTPException(429, "验证码尝试次数过多，请重新获取")
    challenge.attempts += 1
    if not hmac.compare_digest(challenge.code_hash, token_hash(req.verification_code)):
        if challenge.attempts >= 5:
            challenge.status = "locked"
        db.commit()
        raise HTTPException(400, "验证码不正确")

    day_ago = now - timedelta(days=1)
    successful_from_device = int(db.scalar(
        select(func.count(EmailVerificationChallenge.id)).where(
            EmailVerificationChallenge.product_id == req.product_id,
            EmailVerificationChallenge.device_fingerprint_hash == challenge.device_fingerprint_hash,
            EmailVerificationChallenge.status == "consumed",
            EmailVerificationChallenge.consumed_at >= day_ago,
        )
    ) or 0)
    if successful_from_device >= 3:
        raise HTTPException(429, "当前设备今天注册账号数量已达上限")

    organization = Organization(
        product_id=req.product_id,
        name=f"{req.display_name.strip()}的工作空间"[:120],
    )
    db.add(organization)
    db.flush()
    user = User(
        product_id=req.product_id,
        organization_id=organization.id,
        email=email,
        display_name=req.display_name.strip(),
        password_hash=hash_password(req.password),
        role="user",
        status="active",
    )
    db.add(user)
    db.flush()
    ensure_wallet(db, user)
    entitlement = Entitlement(
        user_id=user.id,
        valid_until=utcnow() + timedelta(days=3650),
        device_limit=2,
        features={"cloud_models": True, "billing_mode": "credits"},
        quotas=dict(DEFAULT_QUOTAS),
    )
    db.add(entitlement)
    db.flush()
    device = _ensure_device(db, user, req.device, entitlement)
    challenge.status = "consumed"
    challenge.consumed_at = now
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
    guard = _login_guard(db, req.product_id, req.device)
    if guard and guard.status == "blocked":
        raise HTTPException(423, "当前设备已锁定，请联系管理员解除")
    user = db.scalar(select(User).where(
        User.product_id == req.product_id,
        User.email == req.email.lower().strip(),
    ))
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
    entitlement = _ensure_active_entitlement(db, user)
    device = _ensure_device(db, user, req.device, entitlement)
    _clear_login_failures(db, req.product_id, req.device)
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
    ent = _ensure_active_entitlement(db, principal.user)
    db.flush()
    credited = db.scalar(select(func.coalesce(func.sum(CreditLedgerEntry.credits_delta_micros), 0)).where(
        CreditLedgerEntry.user_id == principal.user.id,
        CreditLedgerEntry.credits_delta_micros > 0,
    )) or 0
    balance = _credit_balance(db, principal.user.id)
    return {
        "status": ent.status,
        "valid_until": ent.valid_until,
        "device_limit": ent.device_limit,
        "features": ent.features,
        "quotas": ent.quotas,
        "billing": {
            "mode": _billing_mode(principal.user, ent),
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
    credited_micros = db.scalar(select(func.coalesce(func.sum(CreditLedgerEntry.credits_delta_micros), 0)).where(
        CreditLedgerEntry.user_id == principal.user.id,
        CreditLedgerEntry.credits_delta_micros > 0,
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
    transactions = db.scalars(select(CreditLedgerEntry).where(
        CreditLedgerEntry.user_id == principal.user.id,
        CreditLedgerEntry.credits_delta_micros > 0,
    ).order_by(CreditLedgerEntry.created_at.desc()).limit(50)).all()
    recent_usage = db.scalars(select(UsageEvent).where(
        UsageEvent.user_id == principal.user.id,
        UsageEvent.status == "succeeded",
    ).order_by(UsageEvent.completed_at.desc()).limit(30)).all()
    return {
        "balance_credits": _credits(_credit_balance(db, principal.user.id)),
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
            "kind": item.entry_type,
            "credits": _credits(item.credits_delta_micros),
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


@app.get("/api/v1/payments/config")
def payment_config(principal: Principal = Depends(current_principal)):
    del principal
    return {
        "alipay_enabled": settings.alipay_enabled,
        "credits_per_cny": int(CREDITS_PER_CNY),
        "minimum_amount_cny": 0.01,
        "maximum_amount_cny": 100000,
    }


@app.post("/api/v1/payments/orders")
def create_payment_order(req: PaymentOrderCreateRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    gateway = AlipayGateway()
    if not gateway.enabled:
        raise HTTPException(503, "支付宝充值尚未开通")
    existing = db.scalar(select(PaymentOrder).where(
        PaymentOrder.user_id == principal.user.id,
        PaymentOrder.idempotency_key == req.idempotency_key,
    ).with_for_update())
    if existing:
        url = ""
        if existing.status == "pending" and as_utc(existing.expires_at) > utcnow():
            url = gateway.page_pay_url(
                merchant_order_no=existing.merchant_order_no,
                amount=f"{existing.amount_micros / 1_000_000:.2f}",
                subject=existing.subject,
            )
        return _payment_json(existing, payment_url=url)

    amount_micros = int((req.amount_cny * Decimal("1000000")).quantize(Decimal("1")))
    credits_micros = int((req.amount_cny * CREDITS_PER_CNY * Decimal("1000000")).quantize(Decimal("1")))
    wallet = ensure_wallet(db, principal.user, lock=True)
    order_prefix, product_name = _payment_product_brand(principal.user.product_id)
    order = PaymentOrder(
        product_id=principal.user.product_id,
        organization_id=principal.user.organization_id,
        user_id=principal.user.id,
        wallet_id=wallet.id,
        merchant_order_no=order_prefix + utcnow().strftime("%Y%m%d%H%M%S") + secrets.token_hex(8).upper(),
        idempotency_key=req.idempotency_key,
        amount_micros=amount_micros,
        credits_micros=credits_micros,
        subject=f"{product_name} Credits 充值",
        expires_at=utcnow() + timedelta(minutes=30),
    )
    db.add(order)
    db.flush()
    try:
        payment_url = gateway.page_pay_url(
            merchant_order_no=order.merchant_order_no,
            amount=f"{req.amount_cny:.2f}",
            subject=order.subject,
        )
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(503, "支付宝密钥配置不可用") from exc
    db.commit()
    return _payment_json(order, payment_url=payment_url)


@app.get("/api/v1/payments/orders/{order_id}")
def get_payment_order(order_id: str, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    order = db.get(PaymentOrder, order_id)
    if not order or order.user_id != principal.user.id or order.product_id != principal.user.product_id:
        raise HTTPException(404, "支付订单不存在")
    if order.status == "pending" and as_utc(order.expires_at) <= utcnow():
        order.status = "expired"
        db.commit()
    return _payment_json(order)


@app.post("/api/v1/payments/alipay/notify", include_in_schema=False)
async def alipay_notify(request: Request, db: Session = Depends(get_db)):
    params = {key: str(value) for key, value in (await request.form()).items()}
    gateway = AlipayGateway()
    if not gateway.enabled or not gateway.verify(params):
        return PlainTextResponse("failure", status_code=400)
    if params.get("app_id") != settings.alipay_app_id:
        return PlainTextResponse("failure", status_code=400)
    if settings.alipay_seller_id and params.get("seller_id") != settings.alipay_seller_id:
        return PlainTextResponse("failure", status_code=400)
    order = db.scalar(select(PaymentOrder).where(
        PaymentOrder.merchant_order_no == params.get("out_trade_no", ""),
    ).with_for_update())
    if not order:
        return PlainTextResponse("failure", status_code=404)
    try:
        notified_micros = int((Decimal(params.get("total_amount", "")) * Decimal("1000000")).quantize(Decimal("1")))
    except Exception:
        return PlainTextResponse("failure", status_code=400)
    if notified_micros != order.amount_micros:
        return PlainTextResponse("failure", status_code=400)

    trade_status = params.get("trade_status", "")
    if trade_status in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
        user = db.get(User, order.user_id)
        if not user or user.product_id != order.product_id:
            return PlainTextResponse("failure", status_code=400)
        order.status = "paid"
        order.provider_trade_no = params.get("trade_no", "")[:80]
        order.notification = params
        order.paid_at = order.paid_at or utcnow()
        credit_wallet(
            db,
            user,
            amount_micros=order.credits_micros,
            entry_type="alipay_recharge",
            idempotency_key=f"alipay-payment:{order.id}",
            note="支付宝充值",
            payment_amount_micros=order.amount_micros,
            currency=order.currency,
            payment_order_id=order.id,
            reference_id=order.merchant_order_no,
        )
        order.credited_at = order.credited_at or utcnow()
    elif trade_status == "TRADE_CLOSED" and order.status == "pending":
        order.status = "closed"
        order.notification = params
    db.commit()
    return PlainTextResponse("success")


@app.get("/api/v1/payments/alipay/return", include_in_schema=False)
def alipay_return(out_trade_no: str = "", db: Session = Depends(get_db)):
    order = db.scalar(select(PaymentOrder).where(PaymentOrder.merchant_order_no == out_trade_no)) if out_trade_no else None
    _, product_name = _payment_product_brand(order.product_id if order else settings.product_id)
    if order and order.status == "paid":
        heading = "支付成功"
        message = f"已为{product_name}账户充值 {_credits(order.credits_micros)} Credits，请返回应用查看余额。"
    else:
        heading = "支付结果正在确认"
        message = f"请返回{product_name}，余额会在支付宝通知确认后自动刷新。"
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'><title>支付结果</title>"
        "<div style='font:16px system-ui;padding:48px;text-align:center'>"
        f"<h1>{heading}</h1><p>{message}</p></div>"
    )


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
    configured_models = settings.capability_models
    return {"items": [{
        "alias": r.alias,
        "available": bool(
            r.enabled and r.provider_model
            and (not r.alias.startswith("geo.search.") or configured_models.get(r.alias))
        ),
    } for r in routes]}


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
        elif req.capability.startswith("geo.search."):
            provider = req.capability.rsplit(".", 1)[-1]
            data, provider_request_id = await gateway.geo_search(provider, route.provider_model, req.payload)
        elif req.capability == "speech.tts":
            data, provider_request_id = await gateway.tts(route.provider_model, req.payload)
        else:
            raise HTTPException(400, "请使用视频任务接口")
        latency = int((time.perf_counter() - started) * 1000)
        event = db.get(UsageEvent, event.id)
        _complete_usage(event, data, latency, provider_request_id, req.payload, route.config, route.provider_model)
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


@app.post("/api/v1/inference/geo/search")
async def inference_geo_search(req: InferenceRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if req.capability not in {
        "geo.search.doubao", "geo.search.openai", "geo.search.perplexity", "geo.search.gemini",
    }:
        raise HTTPException(400, "能力类型与接口不匹配")
    return await _run_inference(req, principal, db)


@app.post("/api/v1/inference/video/tasks")
async def create_video_task(req: InferenceRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if req.capability not in {"video.standard", "video.presenter"}:
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
            model_alias=req.capability,
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
            route.provider_model if route else event.provider_model,
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


# ═══════════════════════════════════════════════════════════════════════
# OmniHuman1.5 数字人视频生成（火山视觉 CV 平台）
# ═══════════════════════════════════════════════════════════════════════


def _omni_human_route(db: Session) -> ModelRoute | None:
    route = db.get(ModelRoute, "video.omnihuman")
    if not route or not route.enabled or not route.provider_model:
        return None
    return route


async def _uploaded_audio_seconds(audio_url: str) -> int:
    """Measure signed local media; client-supplied durations cannot set the bill."""
    from urllib.parse import parse_qs, urlsplit
    url = urlsplit(audio_url)
    base = urlsplit(settings.public_base_url)
    if url.netloc != base.netloc or not url.path.startswith("/api/v1/inference/references/"):
        raise HTTPException(400, "请先上传音频参考素材")
    query = parse_qs(url.query)
    try:
        expires = int(query["expires"][0])
        signature = query["signature"][0]
    except (KeyError, ValueError, IndexError):
        raise HTTPException(400, "音频参考链接无效")
    reference = read_inference_reference(url.path.rsplit("/", 1)[-1], expires, signature)
    process = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", str(reference.path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=20)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise HTTPException(400, "音频参考文件无法解析")
    try:
        seconds = float(stdout.strip())
        if process.returncode or not math.isfinite(seconds) or seconds <= 0 or seconds > 30:
            raise ValueError()
    except ValueError:
        raise HTTPException(400, "单段音频需为有效音频，时长不能超过30秒")
    return math.ceil(seconds)


@app.post("/api/v1/inference/omni-human/tasks")
async def create_omni_human_task(req: InferenceRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if req.capability != "video.omnihuman":
        raise HTTPException(400, "能力类型与接口不匹配")
    route = _omni_human_route(db)
    if not route:
        raise HTTPException(503, "OmniHuman 数字人能力暂未开放")
    payload = dict(req.payload or {})
    image_url = str(payload.get("image_url") or "").strip()
    audio_url = str(payload.get("audio_url") or "").strip()
    if not image_url or not audio_url:
        raise HTTPException(400, "image_url 和 audio_url 必填")
    payload["duration"] = await _uploaded_audio_seconds(audio_url)
    req = req.model_copy(update={"payload": payload})
    # 仅透传 OmniHuman 业务字段；mask_url 数组、prompt、output_resolution 等保持原样。
    forward_payload: dict = {
        "image_url": image_url,
        "audio_url": audio_url,
    }
    for key in ("mask_url", "prompt", "output_resolution", "pe_fast_mode", "seed"):
        if key in payload:
            forward_payload[key] = payload[key]

    event, created = _reserve_usage(db, principal, req)
    if not created:
        existing = db.scalar(select(VideoTask).where(VideoTask.usage_event_id == event.id))
        if existing:
            return {"task_id": existing.id, "status": existing.status, "request_id": event.id}
        raise HTTPException(409, "相同请求正在处理中")
    db.commit()
    started = time.perf_counter()
    try:
        data, provider_request_id = await ProviderGateway().omni_human_submit(
            route.provider_model, forward_payload,
        )
        provider_task_id = str(data.get("task_id") or "")
        if not provider_task_id:
            raise RuntimeError("OmniHuman 未返回 task_id")
        task = VideoTask(
            user_id=principal.user.id,
            device_id=principal.device.id,
            provider_task_id=provider_task_id,
            model_alias=req.capability,
            usage_event_id=event.id,
        )
        db.add(task)
        event = db.get(UsageEvent, event.id)
        event.provider_request_id = provider_request_id
        event.latency_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        return {"task_id": task.id, "status": task.status, "request_id": event.id}
    except Exception as exc:
        logger.error("omni_human_submit failed for user=%s capability=%s: %s",
                     principal.user.email, req.capability, exc, exc_info=True)
        event = db.get(UsageEvent, event.id)
        _fail_usage(event, exc, int((time.perf_counter() - started) * 1000))
        db.commit()
        raise HTTPException(502, {
            "message": f"OmniHuman 数字人服务暂时不可用（{exc}）",
            "request_id": event.id,
        })


@app.get("/api/v1/inference/omni-human/tasks/{task_id}")
async def get_omni_human_task(task_id: str, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    task = db.get(VideoTask, task_id)
    if not task or task.user_id != principal.user.id or task.model_alias != "video.omnihuman":
        raise HTTPException(404, "任务不存在")
    event = db.get(UsageEvent, task.usage_event_id)
    if event.status == "failed":
        return {"task_id": task.id, "request_id": event.id, "status": "failed", "video_url": "", "error": "数字人任务已失败"}
    data, provider_request_id = await ProviderGateway().omni_human_get(
        task.provider_task_id, model=task.model_alias and (db.get(ModelRoute, task.model_alias).provider_model if db.get(ModelRoute, task.model_alias) else "") or "jimeng_realman_avatar_picture_omni_v15",
    )
    status = str(data.get("status") or "unknown")
    task.status = status
    event = db.get(UsageEvent, task.usage_event_id)
    if status == "done" and event.status != "succeeded":
        # OmniHuman 任务 succeeded：video_url 1 小时有效，结算一次。
        # CV 平台不返回 usage.duration，用 reserve 时的 units（秒数）作为结算依据。
        route = db.get(ModelRoute, task.model_alias)
        settled_units = event.units or 1
        _complete_usage(
            event,
            {
                "model": "video.omnihuman",
                "provider_model": route.provider_model if route else task.model_alias,
                "usage": {"duration_seconds": settled_units},
            },
            event.latency_ms,
            provider_request_id or event.provider_request_id,
            {"duration": settled_units},
            route.config if route else {},
            route.provider_model if route else event.provider_model,
        )
    elif status in {"failed", "expired", "not_found"} and event.status == "reserved":
        _fail_usage(event, RuntimeError(f"omni_human_{status}"), event.latency_ms)
    db.commit()
    safe_data = {
        "status": status,
        "video_url": str(data.get("video_url") or ""),
        "aigc_meta_tagged": bool(data.get("aigc_meta_tagged", False)),
        "error": "OmniHuman 任务处理失败" if status == "failed" else "",
    }
    return {"task_id": task.id, "request_id": event.id, **safe_data}


@app.post("/api/v1/inference/omni-human/subject-detection")
async def omni_human_subject_detection(
    payload: dict,
    principal: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    """主体检测：识别图片中可作为说话人的主体，返回 mask_url 列表。
    同步调用，不产生 UsageEvent（用于 OmniHuman 多主体场景的预处理）。"""
    route = db.get(ModelRoute, "video.subject_detection")
    if not route or not route.enabled or not route.provider_model:
        raise HTTPException(503, "主体检测能力暂未开放")
    image_url = str(payload.get("image_url") or "").strip()
    if not image_url:
        raise HTTPException(400, "image_url 必填")
    data, request_id = await ProviderGateway().subject_detection(route.provider_model, image_url)
    return {"status": data.get("status"), "mask_urls": data.get("mask_urls", []), "request_id": request_id}


# ═══════════════════════════════════════════════════════════════════════
# 录音文件识别 ASR（火山大模型）
# ═══════════════════════════════════════════════════════════════════════


@app.post("/api/v1/inference/asr")
async def inference_asr(req: InferenceRequest, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if req.capability != "speech.asr":
        raise HTTPException(400, "能力类型与接口不匹配")
    route = db.get(ModelRoute, req.capability)
    if not route or not route.enabled or not route.provider_model:
        raise HTTPException(503, "录音文件识别能力暂未开放")
    event, created = _reserve_usage(db, principal, req)
    db.commit()
    started = time.perf_counter()
    try:
        data, provider_request_id = await ProviderGateway().asr_transcribe(
            route.provider_model, req.payload,
        )
        event = db.get(UsageEvent, event.id)
        # ASR 真实音频时长从 audio_info.duration（毫秒）得到，结算时按秒扣费。
        # 把 audio_info 嵌进 data 让 normalize_provider_usage 提取 asr_seconds。
        provider_response = dict(data)
        provider_response["audio_info"] = {"duration": data.get("duration_ms", 0)}
        provider_response["usage"] = {"duration_ms": data.get("duration_ms", 0)}
        _complete_usage(
            event,
            {"model": "speech.asr", "provider_model": route.provider_model, **provider_response},
            int((time.perf_counter() - started) * 1000),
            provider_request_id,
            req.payload,
            route.config if route else {},
            route.provider_model,
        )
        # 把结算后的实际秒数写回 event.units，便于前端展示
        event.units = (int(data.get("duration_ms") or 0) + 999) // 1000
        db.commit()
        return {
            "text": data.get("text", ""),
            "utterances": data.get("utterances", []),
            "duration_ms": data.get("duration_ms", 0),
            "duration_seconds": (data.get("duration_ms", 0) + 999) // 1000 if data.get("duration_ms") else 0,
            "request_id": event.id,
        }
    except Exception as exc:
        event = db.get(UsageEvent, event.id)
        _fail_usage(event, exc, int((time.perf_counter() - started) * 1000))
        db.commit()
        if isinstance(exc, ProviderError):
            raise HTTPException(502, {"message": "录音文件识别服务暂时不可用", "request_id": event.id})
        raise


@app.get("/api/v1/admin/dashboard")
def admin_dashboard(admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    product_id = admin.user.product_id
    total_users = db.scalar(select(func.count(User.id)).where(User.product_id == product_id, User.role != "admin")) or 0
    active_users = db.scalar(select(func.count(User.id)).where(User.product_id == product_id, User.role != "admin", User.status == "active")) or 0
    month_requests = db.scalar(select(func.count(UsageEvent.id)).where(UsageEvent.product_id == product_id, UsageEvent.created_at >= _month_start())) or 0
    success_requests = db.scalar(select(func.count(UsageEvent.id)).where(UsageEvent.product_id == product_id, UsageEvent.created_at >= _month_start(), UsageEvent.status == "succeeded")) or 0
    return {
        "users": {"total": total_users, "active": active_users},
        "requests": {"month": month_requests, "success": success_requests},
        "success_rate": round(success_requests / month_requests * 100, 1) if month_requests else 0,
        "open_feedback": db.scalar(select(func.count(Feedback.id)).join(
            Organization, Organization.id == Feedback.organization_id
        ).where(Organization.product_id == product_id, Feedback.status == "open")) or 0,
    }


@app.get("/api/v1/admin/users")
def admin_users(admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).where(
        User.product_id == admin.user.product_id,
    ).order_by(User.created_at.desc())).all()
    result = []
    for user in rows:
        ent = db.scalar(select(Entitlement).where(Entitlement.user_id == user.id))
        device_count = db.scalar(select(func.count(Device.id)).where(Device.user_id == user.id, Device.status == "active")) or 0
        credited_micros = db.scalar(select(func.coalesce(func.sum(CreditLedgerEntry.credits_delta_micros), 0)).where(
            CreditLedgerEntry.user_id == user.id,
            CreditLedgerEntry.credits_delta_micros > 0,
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
            "balance": _credits(_credit_balance(db, user.id)),
            "credited": _credits(credited_micros),
            "spent": _credits(spent_micros),
        }})
    return {"items": result}


@app.post("/api/v1/admin/users")
def admin_create_user(req: AdminUserCreateRequest, admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    email = req.email.lower().strip()
    if db.scalar(select(User).where(User.product_id == admin.user.product_id, User.email == email)):
        raise HTTPException(409, "该账号已开通")
    organization = Organization(
        product_id=admin.user.product_id,
        name=req.organization_name.strip() or req.display_name.strip(),
    )
    db.add(organization)
    db.flush()
    user = User(
        product_id=admin.user.product_id,
        organization_id=organization.id,
        email=email,
        display_name=req.display_name.strip(),
        password_hash=hash_password(req.password),
        role="user",
        status="active",
    )
    db.add(user)
    db.flush()
    ensure_wallet(db, user)
    entitlement = Entitlement(
        user_id=user.id,
        valid_until=utcnow() + timedelta(days=req.entitlement_days),
        device_limit=req.device_limit,
        features={"cloud_models": True, "billing_mode": "credits"},
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
    rows = db.scalars(select(LoginDeviceBlock).where(
        LoginDeviceBlock.product_id == admin.user.product_id,
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
    if not guard or guard.product_id != admin.user.product_id or guard.status != "blocked":
        raise HTTPException(404, "黑名单设备不存在")
    matching_devices = db.scalars(select(Device).join(User, User.id == Device.user_id).where(
        User.product_id == admin.user.product_id,
        Device.installation_id == guard.installation_id,
    )).all()
    if guard.fingerprint_hash:
        fingerprint_devices = db.scalars(select(Device).join(User, User.id == Device.user_id).where(
            User.product_id == admin.user.product_id,
            Device.fingerprint_hash == guard.fingerprint_hash,
        )).all()
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
    if db.scalar(select(User).where(User.product_id == admin.user.product_id, User.email == email)):
        raise HTTPException(409, "该邮箱已开通")
    organization = Organization(
        product_id=admin.user.product_id,
        name=req.organization_name.strip() or req.email.split("@", 1)[0],
    )
    db.add(organization)
    db.flush()
    code = random_token(24)
    invitation = Invitation(
        product_id=admin.user.product_id,
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
    if user.product_id != admin.user.product_id:
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
    if not user or user.role == "admin" or user.product_id != admin.user.product_id:
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
    user = db.get(User, user_id)
    if not user or user.product_id != admin.user.product_id:
        raise HTTPException(404, "用户授权不存在")
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
    """Grant prepaid Credits and append exactly one immutable ledger entry."""
    user = db.get(User, user_id)
    if not user or user.role == "admin" or user.product_id != admin.user.product_id:
        raise HTTPException(404, "用户不存在")
    if not db.scalar(select(Entitlement).where(Entitlement.user_id == user_id)):
        raise HTTPException(404, "用户授权不存在")
    credits_micros = int((Decimal(str(req.credits)) * Decimal("1000000")).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
    if credits_micros <= 0:
        raise HTTPException(400, "充值 credits 必须大于 0")
    reference = req.reference_id or f"manual-{random_token(12)}"
    wallet, ledger, created = credit_wallet(
        db,
        user,
        amount_micros=credits_micros,
        entry_type=req.kind,
        idempotency_key=f"admin-credit:{reference}",
        note=req.note or "管理员手动充值",
        payment_amount_micros=req.payment_amount_micros,
        currency=req.currency,
        reference_id=reference,
        operator_user_id=admin.user.id,
    )
    if created:
        _audit(db, admin.user.id, "recharge_credits", "user", user_id, {
            "credits": req.credits,
            "kind": req.kind,
            "reference_id": reference,
        })
    db.commit()
    return {
        "ok": True,
        "user_id": user_id,
        "credits": _credits(ledger.credits_delta_micros),
        "balance": _credits(wallet.balance_micros),
        "reference_id": reference,
        "idempotent": not created,
    }


@app.delete("/api/v1/admin/devices/{device_id}")
def admin_revoke_device(device_id: str, admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    owner = db.get(User, device.user_id) if device else None
    if not device or not owner or owner.product_id != admin.user.product_id:
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
    rows = db.scalars(select(UsageEvent).where(
        UsageEvent.product_id == admin.user.product_id,
    ).order_by(UsageEvent.created_at.desc()).limit(min(max(limit, 1), 500))).all()
    return {"items": [{
        "id": row.id,
        "user_id": row.user_id,
        "capability": row.capability,
        "status": row.status,
        "units": row.units,
        "unit_type": row.unit_type,
        "provider_usage": row.provider_usage,
        "provider_model": row.provider_model,
        "provider_cost_cny": round(row.provider_cost_micros / 1_000_000, 6),
        "credits_charged": round(row.credits_charged_micros / 1_000_000, 6),
        "pricing_version": row.pricing_version,
        "pricing_snapshot": row.pricing_snapshot,
        "latency_ms": row.latency_ms,
        "error_code": row.error_code,
        "created_at": row.created_at,
    } for row in rows]}


@app.get("/api/v1/admin/provider-billing")
def admin_provider_billing(admin: Principal = Depends(current_admin), db: Session = Depends(get_db), limit: int = 31):
    product_id = admin.user.product_id
    zone = ZoneInfo("Asia/Shanghai")
    today = datetime.now(zone).date()
    item_count = min(max(limit, 1), 366)
    actual_rows = {
        row.billing_date: row
        for row in db.scalars(select(ProviderBillingDaily).where(
            ProviderBillingDaily.billing_date >= today - timedelta(days=item_count - 1),
        )).all()
    }
    items = []
    for days_ago in range(item_count):
        billing_date = today - timedelta(days=days_ago)
        start_local = datetime.combine(billing_date, datetime.min.time(), tzinfo=zone)
        start = start_local.astimezone(timezone.utc)
        end = (start_local + timedelta(days=1)).astimezone(timezone.utc)
        settled_cost, credits_revenue = db.execute(select(
            func.coalesce(func.sum(UsageEvent.provider_cost_micros), 0),
            func.coalesce(func.sum(UsageEvent.credits_charged_micros), 0),
        ).where(
            UsageEvent.product_id == product_id,
            UsageEvent.status == "succeeded",
            UsageEvent.completed_at >= start,
            UsageEvent.completed_at < end,
        )).one()
        row = actual_rows.get(billing_date)
        actual_cost = int(row.actual_cost_micros) if row else None
        reference_cost = actual_cost if actual_cost is not None else int(settled_cost or 0)
        revenue_micros = int(Decimal(int(credits_revenue or 0)) / CREDITS_PER_CNY)
        gross_profit = revenue_micros - reference_cost
        gross_margin = (gross_profit / revenue_micros) if revenue_micros > 0 else None
        variance = (
            (actual_cost - int(settled_cost or 0)) / int(settled_cost)
            if actual_cost is not None and int(settled_cost or 0) > 0
            else None
        )
        status = "awaiting_bill"
        if actual_cost is not None:
            status = "healthy" if gross_margin is not None and gross_margin >= 0.35 and abs(variance or 0) <= 0.05 else "review"
        items.append({
            "provider": "volcengine",
            "billing_date": billing_date,
            "actual_cost_cny": round(actual_cost / 1_000_000, 6) if actual_cost is not None else None,
            "settled_cost_cny": round(int(settled_cost or 0) / 1_000_000, 6),
            "credits_revenue_cny": round(revenue_micros / 1_000_000, 6),
            "gross_profit_cny": round(gross_profit / 1_000_000, 6),
            "gross_margin_percent": round(gross_margin * 100, 2) if gross_margin is not None else None,
            "billing_variance_percent": round(variance * 100, 2) if variance is not None else None,
            "status": status,
            "currency": row.currency if row else "CNY",
            "line_count": row.line_count if row else 0,
            "synced_at": row.synced_at if row else None,
        })
    return {
        "product_id": product_id,
        "provider_billing_configured": settings.provider_billing_enabled,
        "target_provider_cost_share": 0.60,
        "items": items,
    }


@app.get("/api/v1/admin/feedback")
def admin_feedback(admin: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(Feedback).join(
        Organization, Organization.id == Feedback.organization_id
    ).where(
        Organization.product_id == admin.user.product_id,
    ).order_by(Feedback.created_at.desc()).limit(300)).all()
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
