"""
「域灵」数字员工系统 - 配置管理模块

使用 pydantic-settings 的完整配置系统。
环境变量前缀为 YL_，嵌套分隔符为 __。
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseModel):
    """Agent 行为配置。"""

    name: str = Field(default="域灵")
    max_plan_steps: int = Field(default=10, ge=1, le=50)
    planner_model: str = Field(default="qwen2.5:14b")
    executor_model: str = Field(default="qwen2.5:14b")
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=120, ge=10)
    enable_self_correction: bool = Field(default=True)


class MemoryConfig(BaseModel):
    """长期记忆配置。"""

    db_path: str = Field(default="./data/memory.db")
    enable_fts: bool = Field(default=True)
    embedding_dim: int = Field(default=768, ge=128, le=4096)
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    max_history_per_session: int = Field(default=20, ge=5)
    auto_summarize_after: int = Field(default=10, ge=5)


class MCPServerDefinition(BaseModel):
    """单个 MCP 服务器定义。"""

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict = Field(default_factory=dict)
    enabled: bool = Field(default=True)
    auto_start: bool = Field(default=True)
    timeout: int = Field(default=30, ge=5)


class MCPConfig(BaseModel):
    """MCP 服务器管理配置。"""

    servers: list[MCPServerDefinition] = Field(default_factory=list)
    default_timeout: int = Field(default=30, ge=5)
    tool_result_max_length: int = Field(default=10000, ge=1000)


class ModelBackend(BaseModel):
    """模型后端配置。"""

    name: str
    backend_type: Literal["ollama", "litellm"] = "ollama"
    base_url: str
    api_key: str | None = Field(default=None)
    default_model: str
    available_models: list[str] = Field(default_factory=list)
    timeout: int = Field(default=60, ge=10)
    max_tokens: int = Field(default=4096, ge=256)
    priority: int = Field(default=1, ge=1, le=10)
    enable_streaming: bool = Field(default=True)


class ModelsConfig(BaseModel):
    """模型管理配置。"""

    backends: list[ModelBackend] = Field(default_factory=list)
    default_backend: str = Field(default="ollama")
    fallback_enabled: bool = Field(default=True)
    fallback_order: list[str] = Field(default_factory=list)
    request_timeout: int = Field(default=120, ge=10)


class WhisperConfig(BaseModel):
    """Whisper 语音识别配置（已弃用，保留兼容）。"""

    api_url: str = Field(default="http://localhost:9000")
    default_model: str = Field(default="medium")
    default_language: str = Field(default="zh")
    timeout: int = Field(default=300, ge=10)


class ComfyUIConfig(BaseModel):
    """ComfyUI 图像生成配置（已弃用，保留兼容）。"""

    api_url: str = Field(default="http://localhost:8188")
    output_dir: str = Field(default="./data/comfyui_output")
    default_workflow: str = Field(default="default")
    timeout: int = Field(default=300, ge=10)


class FFmpegConfig(BaseModel):
    """FFmpeg 视频处理配置。"""

    ffmpeg_path: str = Field(default="ffmpeg")
    ffprobe_path: str = Field(default="ffprobe")
    default_video_codec: str = Field(default="libx264")
    default_audio_codec: str = Field(default="aac")
    threads: int = Field(default=4, ge=1, le=16)
    hwaccel: str | None = Field(default=None)
    templates_dir: str = Field(default="./data/ffmpeg_templates")


class VolcanoEngineConfig(BaseModel):
    """火山引擎配置（LLM + 图像 + 语音）。"""

    enabled: bool = Field(default=True)
    # ARK LLM
    ark_api_key: str | None = Field(default=None)
    ark_base_url: str = Field(default="https://ark.cn-beijing.volces.com/api/v3")
    ark_default_model: str = Field(default="doubao-lite-4k")
    ark_timeout: int = Field(default=120, ge=10)
    ark_max_retries: int = Field(default=3, ge=0)
    # Image
    image_model: str = Field(default="doubao-seedream")
    image_timeout: int = Field(default=120, ge=10)
    # Speech
    speech_app_id: str | None = Field(default=None)
    speech_access_token: str | None = Field(default=None)
    tts_voice: str = Field(default="zh_female_qingxinnvsheng_mars_bigtts")
    tts_encoding: str = Field(default="mp3")
    tts_speed_ratio: float = Field(default=1.0)
    speech_timeout: int = Field(default=60, ge=10)


class IntegrationsConfig(BaseModel):
    """集成配置聚合。"""

    whisper: WhisperConfig = Field(default_factory=WhisperConfig)
    comfyui: ComfyUIConfig = Field(default_factory=ComfyUIConfig)
    ffmpeg: FFmpegConfig = Field(default_factory=FFmpegConfig)
    volcano_engine: VolcanoEngineConfig = Field(default_factory=VolcanoEngineConfig)


class APIConfig(BaseModel):
    """API 服务配置。"""

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1024, le=65535)
    workers: int = Field(default=1, ge=1, le=8)
    reload: bool = Field(default=False)
    cors_origins: list[str] = Field(default_factory=list)
    api_key: str | None = Field(default=None)
    request_timeout: int = Field(default=120, ge=10)
    max_request_body_size: int = Field(default=10485760, ge=1048576)
    enable_docs: bool = Field(default=True)


class WechatyConfig(BaseModel):
    """微信机器人配置。"""

    enabled: bool = Field(default=False)
    name: str = Field(default="域灵助手")
    puppet: str = Field(default="wechaty-puppet-wechat")
    token: str | None = Field(default=None)
    endpoint: str | None = Field(default=None)
    auto_accept_friend: bool = Field(default=False)
    allowed_groups: list[str] = Field(default_factory=list)
    response_delay: tuple[float, float] = Field(default=(0.5, 2.0))


class SzygSettings(BaseSettings):
    """szyg 系统主配置类。

    支持从环境变量加载，前缀为 YL_，嵌套分隔符为 __。
    例如：YL_AGENT__NAME=自定义名称
    """

    model_config = SettingsConfigDict(
        env_prefix="YL_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    agent: AgentConfig = Field(default_factory=AgentConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    mcp_servers: MCPConfig = Field(default_factory=MCPConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    wechaty: WechatyConfig = Field(default_factory=WechatyConfig)
    debug: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    data_dir: Path = Field(default=Path("./data"))


# 全局设置实例
_settings: SzygSettings | None = None


def get_settings() -> SzygSettings:
    """获取全局设置实例（单例模式）。"""
    global _settings
    if _settings is None:
        _settings = SzygSettings()
    return _settings


def reload_settings() -> SzygSettings:
    """重新加载设置。"""
    global _settings
    _settings = SzygSettings()
    return _settings
