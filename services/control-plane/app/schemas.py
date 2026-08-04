from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class DeviceInput(BaseModel):
    installation_id: str = Field(min_length=8, max_length=160)
    name: str = Field(default="Windows PC", max_length=160)
    fingerprint: str = Field(default="", max_length=500)
    app_version: str = Field(default="", max_length=40)


class ActivateRequest(BaseModel):
    invitation_code: str
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=200)
    device: DeviceInput


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str
    device: DeviceInput
    totp_code: str = ""


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=200)


class FeedbackRequest(BaseModel):
    category: str = Field(default="general", max_length=48)
    message: str = Field(min_length=1, max_length=5000)
    request_id: str = Field(default="", max_length=160)


class InviteRequest(BaseModel):
    email: EmailStr
    organization_name: str = Field(default="", max_length=120)
    role: str = Field(default="user", pattern="^(user|admin)$")
    entitlement_days: int = Field(default=30, ge=1, le=3650)
    device_limit: int = Field(default=2, ge=1, le=10)
    quotas: dict[str, int] = Field(default_factory=dict)


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=200)
    organization_name: str = Field(default="", max_length=120)
    entitlement_days: int = Field(default=30, ge=1, le=3650)
    device_limit: int = Field(default=2, ge=1, le=10)
    quotas: dict[str, int] = Field(default_factory=dict)


class EntitlementUpdate(BaseModel):
    valid_days_from_now: int | None = Field(default=None, ge=1, le=3650)
    device_limit: int | None = Field(default=None, ge=1, le=10)
    quotas: dict[str, int] | None = None


class UserStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|suspended|expired)$")


class ModelRouteUpdate(BaseModel):
    provider_model: str = Field(max_length=180)
    enabled: bool = True
    rollout_percent: int = Field(default=100, ge=0, le=100)
    config: dict[str, Any] = Field(default_factory=dict)


class InferenceRequest(BaseModel):
    capability: str
    payload: dict[str, Any]
    idempotency_key: str = Field(min_length=8, max_length=160)
    app_version: str = Field(default="", max_length=40)
