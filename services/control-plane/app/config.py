from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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
    # 火山视觉 CV 平台（OmniHuman1.5 / 主体检测 / 视频理解 等）。
    # 必须使用 cn-north-1 + Service=cv 的 V4 签名。
    provider_cv_access_key: str = ""
    provider_cv_secret_key: str = ""
    provider_cv_base_url: str = "https://visual.volcengineapi.com"
    provider_cv_region: str = "cn-north-1"
    # 火山大模型录音文件识别（ASR）。新版控制台使用 X-Api-Key + X-Api-Resource-Id 鉴权。
    provider_asr_app_key: str = ""
    provider_asr_resource_id: str = "volc.seedasr.auc"
    provider_asr_base_url: str = "https://openspeech.bytedance.com"
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
    alipay_app_id: str = ""
    alipay_merchant_private_key_file: str = ""
    alipay_public_key_file: str = ""
    alipay_seller_id: str = ""
    alipay_gateway_url: str = "https://openapi.alipay.com/gateway.do"
    alipay_notify_url: str = ""
    alipay_return_url: str = ""
    ses_region: str = "ap-hongkong"
    ses_secret_id: str = ""
    ses_secret_key: str = ""
    ses_secret_id_file: str = ""
    ses_secret_key_file: str = ""
    ses_from_email: str = ""
    ses_template_id: int = 0
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
    # Used by private clients that predate the explicit product selector.
    # Public clients must send xiaoyu_public in login/registration requests.
    product_id: str = "szyg_private"
    @property
    def provider_billing_enabled(self) -> bool:
        return bool(self.provider_billing_access_key and self.provider_billing_secret_key)

    @property
    def alipay_enabled(self) -> bool:
        return bool(
            self.alipay_app_id
            and self.alipay_merchant_private_key_file
            and self.alipay_public_key_file
        )

    @staticmethod
    def _secret_value(value: str, file_name: str) -> str:
        if value:
            return value.strip()
        if file_name:
            try:
                return Path(file_name).read_text(encoding="utf-8").strip()
            except OSError:
                return ""
        return ""

    @property
    def ses_secret_id_value(self) -> str:
        return self._secret_value(self.ses_secret_id, self.ses_secret_id_file)

    @property
    def ses_secret_key_value(self) -> str:
        return self._secret_value(self.ses_secret_key, self.ses_secret_key_file)

    @property
    def ses_enabled(self) -> bool:
        return bool(
            self.ses_region
            and self.ses_secret_id_value
            and self.ses_secret_key_value
            and self.ses_from_email
            and self.ses_template_id
        )

    model_text_fast: str = Field(default="", validation_alias="MODEL_TEXT_FAST")
    model_text_vision: str = Field(default="", validation_alias="MODEL_TEXT_VISION")
    model_text_reasoning: str = Field(default="", validation_alias="MODEL_TEXT_REASONING")
    model_image_standard: str = Field(default="", validation_alias="MODEL_IMAGE_STANDARD")
    model_video_standard: str = Field(default="", validation_alias="MODEL_VIDEO_STANDARD")
    # OmniHuman1.5 走火山视觉 CV 平台，model 字段固定为 jimeng_realman_avatar_picture_omni_v15
    # （由 req_key 标识，不由 Ark 端点解释）。
    model_video_presenter: str = Field(default="", validation_alias="MODEL_VIDEO_PRESENTER")
    model_video_omnihuman: str = Field(default="jimeng_realman_avatar_picture_omni_v15", validation_alias="MODEL_VIDEO_OMNIHUMAN")
    # 主体检测（OmniHuman 多主体场景，用于 mask_url）
    model_subject_detection: str = Field(default="jimeng_realman_avatar_object_detection", validation_alias="MODEL_SUBJECT_DETECTION")
    model_speech_tts: str = Field(default="", validation_alias="MODEL_SPEECH_TTS")
    # ASR 使用固定资源 ID（来自开通 ASR 服务时控制台分配）。
    model_speech_asr: str = Field(default="volc.seedasr.auc", validation_alias="MODEL_SPEECH_ASR")
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
            "video.omnihuman": self.model_video_omnihuman if self.provider_cv_access_key and self.provider_cv_secret_key else "",
            "video.subject_detection": self.model_subject_detection if self.provider_cv_access_key else "",
            "speech.tts": self.model_speech_tts,
            "speech.asr": self.model_speech_asr if self.provider_asr_app_key else "",
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
        if self.product_id not in {"szyg_private", "xiaoyu_public"}:
            raise RuntimeError("CONTROL_PRODUCT_ID must be szyg_private or xiaoyu_public")
        if self.environment == "production":
            if len(self.jwt_secret) < 32:
                raise RuntimeError("CONTROL_JWT_SECRET must contain at least 32 characters")
            if not self.provider_api_key:
                raise RuntimeError("CONTROL_PROVIDER_API_KEY is required in production")
            if self.model_speech_tts and not self.provider_speech_api_key:
                raise RuntimeError("CONTROL_PROVIDER_SPEECH_API_KEY is required when MODEL_SPEECH_TTS is configured")
            if self.model_video_omnihuman and not (self.provider_cv_access_key and self.provider_cv_secret_key):
                raise RuntimeError(
                    "CV access and secret keys are required when MODEL_VIDEO_OMNIHUMAN is configured"
                )
            if self.model_speech_asr and not self.provider_asr_app_key:
                raise RuntimeError(
                    "CONTROL_PROVIDER_ASR_APP_KEY is required when MODEL_SPEECH_ASR is configured"
                )
            if not self.offline_license_private_key_file or not self.offline_license_public_key_file:
                raise RuntimeError("Offline license signing keys are required in production")
            if self.bootstrap_admin_password in {"", "replace-before-start", "admin123"}:
                raise RuntimeError("A secure bootstrap administrator password is required")


@lru_cache
def get_settings() -> Settings:
    return Settings()
