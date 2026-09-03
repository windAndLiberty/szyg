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
    provider_speech_base_url: str = "https://openspeech.bytedance.com/api/v3/tts/create"
    provider_billing_access_key: str = ""
    provider_billing_secret_key: str = ""
    provider_billing_region: str = "cn-beijing"
    provider_billing_project: str = ""
    geo_openai_api_key: str = ""
    geo_perplexity_api_key: str = ""
    geo_gemini_api_key: str = ""
    geo_openai_base_url: str = "https://api.openai.com/v1"
    geo_perplexity_base_url: str = "https://api.perplexity.ai"
    geo_gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    cors_origins: str = ""
    public_base_url: str = "http://127.0.0.1:18080"
    reference_temp_dir: str = "./data/reference_uploads"
    reference_ttl_hours: int = 24
    reference_max_mb: int = 200
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
    model_video_presenter: str = Field(default="doubao-seedance-2-5-260628", validation_alias="MODEL_VIDEO_PRESENTER")
    model_speech_tts: str = Field(default="", validation_alias="MODEL_SPEECH_TTS")
    model_embedding_standard: str = Field(default="", validation_alias="MODEL_EMBEDDING_STANDARD")
    model_geo_doubao: str = Field(default="", validation_alias="MODEL_GEO_DOUBAO")
    model_geo_openai: str = Field(default="gpt-5-mini", validation_alias="MODEL_GEO_OPENAI")
    model_geo_perplexity: str = Field(default="sonar", validation_alias="MODEL_GEO_PERPLEXITY")
    model_geo_gemini: str = Field(default="gemini-2.5-flash", validation_alias="MODEL_GEO_GEMINI")

    @property
    def capability_models(self) -> dict[str, str]:
        return {
            "text.fast": self.model_text_fast,
            "text.vision": self.model_text_vision,
            "text.reasoning": self.model_text_reasoning,
            "image.standard": self.model_image_standard,
            "video.standard": self.model_video_standard,
            "video.presenter": self.model_video_presenter,
            "speech.tts": self.model_speech_tts,
            "embedding.standard": self.model_embedding_standard,
            "geo.search.doubao": (self.model_geo_doubao or self.model_text_fast) if self.provider_api_key else "",
            "geo.search.openai": self.model_geo_openai if self.geo_openai_api_key else "",
            "geo.search.perplexity": self.model_geo_perplexity if self.geo_perplexity_api_key else "",
            "geo.search.gemini": self.model_geo_gemini if self.geo_gemini_api_key else "",
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
            if self.model_speech_tts and not self.provider_speech_api_key:
                raise RuntimeError("CONTROL_PROVIDER_SPEECH_API_KEY is required when MODEL_SPEECH_TTS is configured")
            if not self.offline_license_private_key_file or not self.offline_license_public_key_file:
                raise RuntimeError("Offline license signing keys are required in production")
            if self.bootstrap_admin_password in {"", "replace-before-start", "admin123"}:
                raise RuntimeError("A secure bootstrap administrator password is required")


@lru_cache
def get_settings() -> Settings:
    return Settings()
