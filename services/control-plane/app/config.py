from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CONTROL_", extra="ignore")

    database_url: str = "sqlite:///./data/control.db"
    jwt_secret: str = ""
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_totp_secret: str = ""
    provider_api_key: str = ""
    provider_speech_api_key: str = ""
    provider_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    provider_billing_access_key: str = ""
    provider_billing_secret_key: str = ""
    provider_billing_region: str = "cn-beijing"
    cors_origins: str = ""
    public_base_url: str = "http://127.0.0.1:18080"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    offline_license_days: int = 7
    offline_license_private_key_file: str = ""
    offline_license_public_key_file: str = ""
    default_device_limit: int = 2
    default_entitlement_days: int = 30
    log_prompt_content: bool = False
    environment: str = "development"
    # 统一计费下每位用户开通 credits 时的默认赠送额度（credits 数，0 表示不赠送）
    default_credits: float = 0

    @property
    def default_credit_micros(self) -> int:
        return int((Decimal(str(self.default_credits)) * Decimal("1000000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @property
    def provider_billing_enabled(self) -> bool:
        return bool(self.provider_billing_access_key and self.provider_billing_secret_key)

    model_text_fast: str = Field(default="", validation_alias="MODEL_TEXT_FAST")
    model_text_vision: str = Field(default="", validation_alias="MODEL_TEXT_VISION")
    model_text_reasoning: str = Field(default="", validation_alias="MODEL_TEXT_REASONING")
    model_image_standard: str = Field(default="", validation_alias="MODEL_IMAGE_STANDARD")
    model_video_standard: str = Field(default="", validation_alias="MODEL_VIDEO_STANDARD")
    model_speech_tts: str = Field(default="", validation_alias="MODEL_SPEECH_TTS")
    model_embedding_standard: str = Field(default="", validation_alias="MODEL_EMBEDDING_STANDARD")

    @property
    def capability_models(self) -> dict[str, str]:
        return {
            "text.fast": self.model_text_fast,
            "text.vision": self.model_text_vision,
            "text.reasoning": self.model_text_reasoning,
            "image.standard": self.model_image_standard,
            "video.standard": self.model_video_standard,
            "speech.tts": self.model_speech_tts,
            "embedding.standard": self.model_embedding_standard,
        }

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    def validate_production(self) -> None:
        if self.environment == "production":
            if len(self.jwt_secret) < 32:
                raise RuntimeError("CONTROL_JWT_SECRET must contain at least 32 characters")
            if not self.provider_api_key:
                raise RuntimeError("CONTROL_PROVIDER_API_KEY is required in production")
            if not self.offline_license_private_key_file or not self.offline_license_public_key_file:
                raise RuntimeError("Offline license signing keys are required in production")
            if self.bootstrap_admin_password in {"", "replace-before-start", "admin123"}:
                raise RuntimeError("A secure bootstrap administrator password is required")


@lru_cache
def get_settings() -> Settings:
    return Settings()
