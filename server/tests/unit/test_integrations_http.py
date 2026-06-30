"""
「域灵」数字员工系统 - 集成客户端 HTTP 方法测试

使用 respx mock HTTP 测试实际客户端的网络方法。
"""

import pytest
import respx
from httpx import Response

from szyg.integrations.base_client import BaseClient
from szyg.integrations.ollama_client import OllamaClient
from szyg.integrations.litellm_client import LiteLLMClient
from szyg.models.common import IntegrationError


class TestBaseClientHttp:
    """测试 BaseClient 的 _post / _get / close 方法。"""

    @pytest.fixture
    def client(self):
        return BaseClient("http://test-service.local", timeout=5.0)

    async def test_post_success(self, client):
        """_post 成功请求。"""
        with respx.mock:
            respx.post("http://test-service.local/test").mock(
                return_value=Response(200, json={"ok": True})
            )
            resp = await client._post("/test", json={"key": "val"})
            assert resp.status_code == 200
            assert resp.json() == {"ok": True}

    async def test_get_success(self, client):
        """_get 成功请求。"""
        with respx.mock:
            respx.get("http://test-service.local/data").mock(
                return_value=Response(200, json={"data": [1, 2, 3]})
            )
            resp = await client._get("/data")
            assert resp.status_code == 200

    async def test_post_http_error(self, client):
        """_post HTTP 错误应抛出 IntegrationError。"""
        with respx.mock:
            respx.post("http://test-service.local/bad").mock(
                return_value=Response(500, text="Server Error")
            )
            with pytest.raises(IntegrationError):
                await client._post("/bad")

    async def test_get_http_error(self, client):
        """_get HTTP 错误应抛出 IntegrationError。"""
        with respx.mock:
            respx.get("http://test-service.local/bad").mock(
                return_value=Response(500, text="Error")
            )
            with pytest.raises(IntegrationError):
                await client._get("/bad")

    async def test_get_timeout_error(self, client):
        """_get 超时应抛出 IntegrationError。"""
        with respx.mock:
            respx.get("http://test-service.local/slow").mock(
                side_effect=Exception("timeout")
            )
            with pytest.raises(IntegrationError):
                await client._get("/slow")

    async def test_close(self, client):
        """close 应关闭 HTTP 客户端。"""
        await client.close()
        assert client._client is None or client._client.is_closed


class TestOllamaClientReal:
    """测试 OllamaClient 的 chat / generate / list_models。"""

    @pytest.fixture
    def client(self):
        return OllamaClient(base_url="http://localhost:11434", timeout=10.0)

    async def test_chat_success(self, client):
        """chat 应正确调用 Ollama API。"""
        with respx.mock:
            respx.post("http://localhost:11434/api/chat").mock(
                return_value=Response(
                    200,
                    json={
                        "model": "qwen2.5",
                        "message": {"role": "assistant", "content": "Hello!"},
                        "done": True,
                    },
                )
            )
            resp = await client.chat(messages=[{"role": "user", "content": "Hi"}])
            assert resp["message"]["content"] == "Hello!"
            assert resp["done"] is True

    async def test_generate_success(self, client):
        """generate 应正确调用 Ollama API。"""
        with respx.mock:
            respx.post("http://localhost:11434/api/generate").mock(
                return_value=Response(
                    200,
                    json={"model": "qwen2.5", "response": "Generated!", "done": True},
                )
            )
            resp = await client.generate(prompt="Test prompt")
            assert resp["response"] == "Generated!"

    async def test_list_models(self, client):
        """list_models 应返回模型列表。"""
        with respx.mock:
            respx.get("http://localhost:11434/api/tags").mock(
                return_value=Response(
                    200,
                    json={"models": [{"name": "qwen2.5:latest"}, {"name": "llama3:latest"}]},
                )
            )
            models = await client.list_models()
            assert "models" in models
            assert len(models["models"]) == 2

    async def test_chat_with_custom_model(self, client):
        """使用自定义 model 参数。"""
        with respx.mock:
            respx.post("http://localhost:11434/api/chat").mock(
                return_value=Response(200, json={"message": {"content": "ok"}, "done": True})
            )
            resp = await client.chat(
                model="llama3",
                messages=[{"role": "user", "content": "Hi"}],
            )
            assert resp["done"] is True

    async def test_close(self, client):
        """close 应清理客户端。"""
        with respx.mock:
            respx.post("http://localhost:11434/api/chat").mock(
                return_value=Response(200, json={"message": {"content": "ok"}, "done": True})
            )
            await client.chat(messages=[{"role": "user", "content": "x"}])
        await client.close()


class TestWhisperClientReal:
    """测试 WhisperClient 的 transcribe 方法。"""

    @pytest.fixture
    def client(self):
        from szyg.integrations.whisper_client import WhisperClient
        return WhisperClient(api_url="http://localhost:9000", timeout=10.0)

    async def test_transcribe_success(self, client, tmp_path):
        """transcribe 应发送音频文件并返回文本。"""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF fake wav data")

        with respx.mock:
            respx.post("http://localhost:9000/transcribe").mock(
                return_value=Response(200, json={"text": "Hello world from whisper"})
            )
            result = await client.transcribe(str(audio_file))
            assert result.text == "Hello world from whisper"


class TestLiteLLMClientReal:
    """测试 LiteLLMClient 的 completion。"""

    @pytest.fixture
    def client(self):
        return LiteLLMClient(base_url="http://localhost:4000", timeout=10.0)

    async def test_completion_success(self, client):
        """completion 应正确调用 LiteLLM API。"""
        with respx.mock:
            respx.post("http://localhost:4000/v1/chat/completions").mock(
                return_value=Response(
                    200,
                    json={
                        "choices": [{"message": {"content": "Hello from LLM!"}}],
                        "model": "gpt-4",
                        "usage": {"total_tokens": 10},
                    },
                )
            )
            resp = await client.completion(
                messages=[{"role": "user", "content": "Hi"}]
            )
            assert resp["choices"][0]["message"]["content"] == "Hello from LLM!"

    async def test_completion_auth_error(self, client):
        """认证错误应抛出 HTTPStatusError。"""
        client.api_key = "invalid-key"
        with respx.mock:
            respx.post("http://localhost:4000/v1/chat/completions").mock(
                return_value=Response(401, json={"error": "Invalid API key"})
            )
            with pytest.raises(Exception):  # httpx.HTTPStatusError
                await client.completion(messages=[{"role": "user", "content": "Hi"}])

    async def test_list_models(self, client):
        """list_models 应返回模型列表并缓存。"""
        with respx.mock:
            respx.get("http://localhost:4000/v1/models").mock(
                return_value=Response(
                    200,
                    json={
                        "object": "list",
                        "data": [
                            {"id": "gpt-4", "object": "model"},
                            {"id": "gpt-3.5-turbo", "object": "model"},
                        ],
                    },
                )
            )
            data = await client.list_models()
            assert data["object"] == "list"
            assert len(data["data"]) == 2
            assert "gpt-4" in client.available_models
