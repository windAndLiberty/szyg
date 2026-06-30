"""
「域灵」数字员工系统 - 集成客户端 __init__ 测试

测试各集成客户端的初始化逻辑，不依赖外部服务。
"""

import pytest

from szyg.integrations.whisper_client import WhisperClient
from szyg.integrations.comfyui_client import ComfyUIClient
from szyg.integrations.ffmpeg_client import FFmpegClient
from szyg.integrations.ollama_client import OllamaClient
from szyg.integrations.litellm_client import LiteLLMClient
from szyg.integrations.base_client import BaseClient


class TestBaseClient:
    """测试 BaseClient 抽象基类。"""

    def test_init_stores_params(self):
        """初始化应存储 base_url 和 timeout。"""
        client = BaseClient("http://example.com", timeout=60.0)
        assert client.base_url == "http://example.com"
        assert client.timeout == 60.0

    def test_init_strips_trailing_slash(self):
        """base_url 尾部斜杠应被移除。"""
        client = BaseClient("http://example.com/api/")
        assert client.base_url == "http://example.com/api"

    def test_client_property_creates_httpx(self):
        """client 属性应返回 httpx.AsyncClient。"""
        import httpx
        client = BaseClient("http://test.local")
        c = client.client
        assert isinstance(c, httpx.AsyncClient)


class TestWhisperClientInit:
    """测试 WhisperClient 初始化。"""

    def test_default_init(self):
        client = WhisperClient()
        assert client.api_url == "http://localhost:9000"
        assert client.default_model == "medium"
        assert client.default_language == "zh"
        assert client.timeout == 300

    def test_custom_init(self):
        client = WhisperClient(
            api_url="http://custom:8080",
            default_model="large",
            default_language="en",
            timeout=120,
        )
        assert client.api_url == "http://custom:8080"
        assert client.default_model == "large"
        assert client.default_language == "en"
        assert client.timeout == 120


class TestComfyUIClientInit:
    """测试 ComfyUIClient 初始化。"""

    def test_default_init(self):
        client = ComfyUIClient()
        assert client.api_url == "http://localhost:8188"
        assert str(client.output_dir).replace("\\", "/") == "data/comfyui_output"
        assert client.checkpoint == "sd21.safetensors"
        assert client.timeout == 300

    def test_custom_init(self, tmp_path):
        output_dir = str(tmp_path / "comfy_output")
        client = ComfyUIClient(
            api_url="http://gpu:8188",
            output_dir=output_dir,
            checkpoint="sd_xl.safetensors",
            timeout=600,
        )
        assert client.api_url == "http://gpu:8188"
        assert str(client.output_dir) == output_dir
        assert client.checkpoint == "sd_xl.safetensors"
        assert client.timeout == 600


class TestFFmpegClientInit:
    """测试 FFmpegClient 初始化。"""

    def test_default_init(self):
        client = FFmpegClient()
        assert client.ffmpeg_path == "ffmpeg"
        assert client.ffprobe_path == "ffprobe"
        assert client.templates_dir == "./data/ffmpeg_templates"
        assert client.threads == 4

    def test_custom_init(self):
        client = FFmpegClient(
            ffmpeg_path="/usr/local/bin/ffmpeg",
            ffprobe_path="/usr/local/bin/ffprobe",
            templates_dir="/custom/templates",
            threads=8,
        )
        assert client.ffmpeg_path == "/usr/local/bin/ffmpeg"
        assert client.ffprobe_path == "/usr/local/bin/ffprobe"
        assert client.templates_dir == "/custom/templates"
        assert client.threads == 8


class TestOllamaClientInit:
    """测试 OllamaClient 初始化。"""

    def test_default_init(self):
        client = OllamaClient()
        assert client.base_url == "http://localhost:11434"
        assert client.default_model == "qwen3:0.6B"
        assert client.timeout == 120.0

    def test_custom_init(self):
        client = OllamaClient(
            base_url="http://gpu-server:11434",
            default_model="llama3",
            timeout=120,
        )
        assert client.base_url == "http://gpu-server:11434"
        assert client.default_model == "llama3"
        assert client.timeout == 120


class TestLiteLLMClientInit:
    """测试 LiteLLMClient 初始化。"""

    def test_default_init(self):
        client = LiteLLMClient()
        assert client.base_url == "http://localhost:4000"
        assert client.api_key is None
        assert client.default_model == "gpt-4"
        assert client.timeout == 60.0

    def test_custom_init(self):
        client = LiteLLMClient(
            base_url="https://api.openai.com/v1",
            api_key="sk-test-key",
            default_model="gpt-4o",
            timeout=120.0,
        )
        assert client.base_url == "https://api.openai.com/v1"
        assert client.api_key == "sk-test-key"
        assert client.default_model == "gpt-4o"
        assert client.timeout == 120.0
