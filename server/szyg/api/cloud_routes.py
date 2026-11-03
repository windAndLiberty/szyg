from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from szyg.cloud_auth import CloudAuthError, cloud_auth


router = APIRouter(prefix="/api/cloud", tags=["cloud-account"])


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str


class ActivateBody(BaseModel):
    invitation_code: str
    display_name: str
    password: str = Field(min_length=10)


class RegisterBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=200)
    verification_id: str = Field(min_length=8, max_length=80)
    verification_code: str = Field(pattern="^[0-9]{6}$")


class RegisterCodeBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasswordResetCodeBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class DeviceReplacementCodeBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str


class DeviceReplacementBody(DeviceReplacementCodeBody):
    verification_id: str = Field(min_length=8, max_length=80)
    verification_code: str = Field(pattern="^[0-9]{6}$")
    revoke_device_id: str = Field(min_length=8, max_length=80)


class FeedbackBody(BaseModel):
    category: str = "general"
    message: str
    request_id: str = ""


class ChangePasswordBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    new_password: str = Field(min_length=10, max_length=200)
    verification_id: str = Field(min_length=8, max_length=80)
    verification_code: str = Field(pattern="^[0-9]{6}$")


class PaymentOrderBody(BaseModel):
    amount_cny: float = Field(ge=0.01, le=100000)
    idempotency_key: str = Field(min_length=8, max_length=160)


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except CloudAuthError as exc:
        status_code = int(getattr(exc, "status_code", 0) or (401 if str(exc) == "请先登录" else 400))
        detail = getattr(exc, "detail", None)
        raise HTTPException(status_code, detail if isinstance(detail, dict) else str(exc)) from exc


@router.get("/config")
def config():
    cfg = cloud_auth.config
    return {"enabled": cfg["enabled"], "configured": bool(cfg["control_url"])}


@router.get("/session")
def session():
    return cloud_auth.session()


@router.post("/session/refresh")
def session_refresh():
    return cloud_auth.refresh_status()


@router.post("/login")
def login(body: LoginBody):
    return call(cloud_auth.login, body.email, body.password)


@router.post("/activate")
def activate(body: ActivateBody):
    return call(cloud_auth.activate, body.invitation_code, body.display_name, body.password)


@router.post("/register")
def register(body: RegisterBody):
    return call(
        cloud_auth.register,
        body.email,
        body.display_name,
        body.password,
        body.verification_id,
        body.verification_code,
    )


@router.post("/register/code")
def register_code(body: RegisterCodeBody):
    return call(cloud_auth.request_registration_code, body.email)


@router.post("/password/code")
def password_reset_code(body: PasswordResetCodeBody):
    return call(cloud_auth.request_password_reset_code, body.email)


@router.post("/device-replacement/code")
def device_replacement_code(body: DeviceReplacementCodeBody):
    return call(cloud_auth.request_device_replacement_code, body.email, body.password)


@router.post("/device-replacement")
def device_replacement(body: DeviceReplacementBody):
    return call(
        cloud_auth.replace_device,
        body.email,
        body.password,
        body.verification_id,
        body.verification_code,
        body.revoke_device_id,
    )


@router.post("/logout")
def logout():
    cloud_auth.logout()
    return {"ok": True}


@router.put("/password")
def change_password(body: ChangePasswordBody):
    return call(
        cloud_auth.reset_password,
        body.email,
        body.new_password,
        body.verification_id,
        body.verification_code,
    )


@router.get("/devices")
def devices():
    return call(cloud_auth.proxy, "GET", "/api/v1/devices")


@router.delete("/devices/{device_id}")
def revoke_device(device_id: str):
    return call(cloud_auth.proxy, "DELETE", f"/api/v1/devices/{device_id}")


@router.get("/entitlements")
def entitlements():
    return call(cloud_auth.proxy, "GET", "/api/v1/entitlements")


@router.get("/usage")
def usage():
    return call(cloud_auth.proxy, "GET", "/api/v1/usage/summary")


@router.get("/billing")
def billing():
    return call(cloud_auth.proxy, "GET", "/api/v1/billing/summary")


@router.get("/payments/config")
def payment_config():
    return call(cloud_auth.proxy, "GET", "/api/v1/payments/config")


@router.post("/payments/orders")
def create_payment_order(body: PaymentOrderBody):
    return call(cloud_auth.proxy, "POST", "/api/v1/payments/orders", body.model_dump())


@router.get("/payments/orders/{order_id}")
def payment_order(order_id: str):
    return call(cloud_auth.proxy, "GET", f"/api/v1/payments/orders/{order_id}")


@router.post("/feedback")
def feedback(body: FeedbackBody):
    return call(cloud_auth.proxy, "POST", "/api/v1/feedback", body.model_dump())
