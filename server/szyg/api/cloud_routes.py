from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from szyg.cloud_auth import CloudAuthError, cloud_auth


router = APIRouter(prefix="/api/cloud", tags=["cloud-account"])


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str
    totp_code: str = ""


class ActivateBody(BaseModel):
    invitation_code: str
    display_name: str
    password: str = Field(min_length=10)


class FeedbackBody(BaseModel):
    category: str = "general"
    message: str
    request_id: str = ""


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except CloudAuthError as exc:
        raise HTTPException(401 if str(exc) == "请先登录" else 400, str(exc)) from exc


@router.get("/config")
def config():
    cfg = cloud_auth.config
    return {"enabled": cfg["enabled"], "configured": bool(cfg["control_url"])}


@router.get("/session")
def session():
    return cloud_auth.session()


@router.post("/login")
def login(body: LoginBody):
    return call(cloud_auth.login, body.email, body.password, body.totp_code)


@router.post("/activate")
def activate(body: ActivateBody):
    return call(cloud_auth.activate, body.invitation_code, body.display_name, body.password)


@router.post("/logout")
def logout():
    cloud_auth.logout()
    return {"ok": True}


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


@router.post("/feedback")
def feedback(body: FeedbackBody):
    return call(cloud_auth.proxy, "POST", "/api/v1/feedback", body.model_dump())
