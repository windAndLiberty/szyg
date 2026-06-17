"""
「域灵」数字员工系统 - 共享pytest fixtures

本文件提供所有测试模块共享的fixtures，包括：
- 异步事件循环
- 临时目录和内存数据库
- Mock HTTP服务（Ollama/ComfyUI/LiteLLM）
- 各Client实例
- FastAPI TestClient
- Agent Core组件实例
"""

import asyncio
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import respx
from httpx import ASGITransport, AsyncClient, Response

# =============================================================================
# 事件循环和基础 Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """提供session级别的事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """提供临时目录。"""
    return tmp_path


# =============================================================================
# Config Fixture
# =============================================================================


@pytest.fixture
def config(temp_dir: Path) -> MagicMock:
    """提供测试配置实例。"""
    mock_config = MagicMock()
    mock_config.model = MagicMock()
    mock_config.model.ollama = MagicMock()
    mock_config.model.ollama.host = "http://localhost:11434"
    mock_config.model.ollama.default_model = "qwen2.5"
    mock_config.model.litellm = MagicMock()
    mock_config.model.litellm.api_base = "http://localhost:4000"
    mock_config.model.litellm.api_key = "sk-test-key"
    mock_config.model.litellm.default_model = "gpt-4"
    mock_config.model.primary_backend = "ollama"
    mock_config.model.fallback_backend = "litellm"

    mock_config.memory = MagicMock()
    mock_config.memory.type = "sqlite"
    mock_config.memory.sqlite = MagicMock()
    mock_config.memory.sqlite.path = str(temp_dir / "memory.db")
    mock_config.memory.vector_dimension = 768

    mock_config.mcp = MagicMock()
    mock_config.mcp.servers = []

    mock_config.api = MagicMock()
    mock_config.api.host = "0.0.0.0"
    mock_config.api.port = 8000
    mock_config.api.auth_token = None

    mock_config.whisper = MagicMock()
    mock_config.whisper.host = "http://localhost:9000"

    mock_config.comfyui = MagicMock()
    mock_config.comfyui.host = "http://localhost:8188"

    mock_config.ffmpeg = MagicMock()
    mock_config.ffmpeg.binary = "ffmpeg"

    mock_config.wechaty = MagicMock()
    mock_config.wechaty.puppet_token = "test-token"

    return mock_config


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def memory_db(temp_dir: Path) -> sqlite3.Connection:
    """提供内存SQLite数据库（带FTS5支持）。"""
    db_path = temp_dir / "test_memory.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # 创建主表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建FTS5虚拟表用于全文搜索
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content,
            metadata,
            content='memories',
            content_rowid='id'
        )
    """)

    # 创建触发器保持FTS索引同步
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, metadata)
            VALUES (new.id, new.content, new.metadata);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, metadata)
            VALUES ('delete', old.id, old.content, old.metadata);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, metadata)
            VALUES ('delete', old.id, old.content, old.metadata);
            INSERT INTO memories_fts(rowid, content, metadata)
            VALUES (new.id, new.content, new.metadata);
        END
    """)

    conn.commit()
    yield conn
    conn.close()


# =============================================================================
# Mock HTTP Server Fixtures (使用 respx)
# =============================================================================


@pytest.fixture
def mock_ollama_server() -> Generator[respx.MockRouter, None, None]:
    """提供mock Ollama HTTP服务。"""
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as router:
        # Chat endpoint
        route_chat = router.post("http://localhost:11434/api/chat").mock(
            return_value=Response(
                200,
                json={
                    "model": "qwen2.5",
                    "message": {"role": "assistant", "content": "Hello from Ollama!"},
                    "done": True,
                },
            )
        )
        route_chat._name = "ollama_chat"

        # Generate endpoint
        route_gen = router.post("http://localhost:11434/api/generate").mock(
            return_value=Response(
                200,
                json={
                    "model": "qwen2.5",
                    "response": "Generated text from Ollama",
                    "done": True,
                },
            )
        )
        route_gen._name = "ollama_generate"

        # Tags/list models endpoint
        route_tags = router.get("http://localhost:11434/api/tags").mock(
            return_value=Response(
                200,
                json={
                    "models": [
                        {"name": "qwen2.5:latest", "modified_at": "2024-01-01"},
                        {"name": "llama3:latest", "modified_at": "2024-01-01"},
                    ]
                },
            )
        )
        route_tags._name = "ollama_tags"

        yield router


@pytest.fixture
def mock_comfyui_server() -> Generator[respx.MockRouter, None, None]:
    """提供mock ComfyUI HTTP服务。"""
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as router:
        # Prompt/queue endpoint
        route_prompt = router.post("http://localhost:8188/prompt").mock(
            return_value=Response(200, json={"prompt_id": "test-prompt-123"})
        )
        route_prompt._name = "comfyui_prompt"

        # History endpoint
        route_history = router.get("http://localhost:8188/history/test-prompt-123").mock(
            return_value=Response(
                200,
                json={
                    "test-prompt-123": {
                        "outputs": {
                            "9": {"images": [{"filename": "test.png", "subfolder": ""}]}
                        }
                    }
                },
            )
        )
        route_history._name = "comfyui_history"

        # View image endpoint
        route_view = router.get("http://localhost:8188/view").mock(
            return_value=Response(200, content=b"\x89PNG\r\n\x1a\nfake_image_data")
        )
        route_view._name = "comfyui_view"

        yield router


@pytest.fixture
def mock_litellm_server() -> Generator[respx.MockRouter, None, None]:
    """提供mock LiteLLM HTTP服务。"""
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as router:
        # Chat completions endpoint
        route_chat = router.post("http://localhost:4000/v1/chat/completions").mock(
            return_value=Response(
                200,
                json={
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "gpt-4",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "Hello from LiteLLM!"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                },
            )
        )
        route_chat._name = "litellm_chat"

        # Models endpoint
        route_models = router.get("http://localhost:4000/v1/models").mock(
            return_value=Response(
                200,
                json={
                    "object": "list",
                    "data": [
                        {"id": "gpt-4", "object": "model", "created": 1677610602},
                        {"id": "gpt-3.5-turbo", "object": "model", "created": 1677649963},
                    ],
                },
            )
        )
        route_models._name = "litellm_models"

        yield router


@pytest.fixture
def mock_whisper_server() -> Generator[respx.MockRouter, None, None]:
    """提供mock Whisper HTTP服务。"""
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as router:
        # Transcribe endpoint
        route_transcribe = router.post("http://localhost:9000/transcribe").mock(
            return_value=Response(
                200,
                json={"text": "Hello world, this is a test transcription"},
            )
        )
        route_transcribe._name = "whisper_transcribe"

        yield router


# =============================================================================
# Integration Client Fixtures
# =============================================================================


@pytest.fixture
def client_whisper(config: MagicMock) -> AsyncMock:
    """提供WhisperClient实例（mock）。"""
    mock_client = AsyncMock()
    mock_client.transcribe = AsyncMock(return_value=" transcribed text from audio ")
    mock_client.close = AsyncMock()
    return mock_client


@pytest.fixture
def client_comfyui(config: MagicMock) -> AsyncMock:
    """提供ComfyUIClient实例（mock）。"""
    mock_client = AsyncMock()
    mock_client.generate_cover = AsyncMock(return_value=b"\x89PNG\r\n\x1a\ngenerated_image")
    mock_client.queue_workflow = AsyncMock(return_value="test-prompt-123")
    mock_client.get_result = AsyncMock(
        return_value={"outputs": {"9": {"images": [{"filename": "test.png"}]}}}
    )
    mock_client.close = AsyncMock()
    return mock_client


@pytest.fixture
def client_ffmpeg(config: MagicMock) -> MagicMock:
    """提供FFmpegClient实例（mock）。"""
    mock_client = MagicMock()
    mock_client.batch_edit = MagicMock(return_value="/output/edited_video.mp4")
    mock_client.extract_audio = MagicMock(return_value="/output/audio.mp3")
    mock_client.run_command = MagicMock(return_value=(0, "stdout", ""))
    return mock_client


@pytest.fixture
def client_ollama(config: MagicMock) -> AsyncMock:
    """提供OllamaClient实例（mock）。"""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(
        return_value={"message": {"role": "assistant", "content": "Hello from Ollama!"}}
    )
    mock_client.generate = AsyncMock(
        return_value={"response": "Generated text from Ollama"}
    )
    mock_client.list_models = AsyncMock(
        return_value={"models": [{"name": "qwen2.5:latest"}]}
    )
    mock_client.close = AsyncMock()
    return mock_client


@pytest.fixture
def client_litellm(config: MagicMock) -> AsyncMock:
    """提供LiteLLMClient实例（mock）。"""
    mock_client = AsyncMock()
    mock_client.completion = AsyncMock(
        return_value={
            "choices": [{"message": {"content": "Hello from LiteLLM!"}}]
        }
    )
    mock_client.acompletion = AsyncMock(
        return_value={
            "choices": [{"message": {"content": "Async hello from LiteLLM!"}}]
        }
    )
    mock_client.close = AsyncMock()
    return mock_client


# =============================================================================
# FastAPI TestClient
# =============================================================================


@pytest_asyncio.fixture
async def test_app(config: MagicMock) -> AsyncGenerator[AsyncClient, None]:
    """提供FastAPI异步TestClient。"""
    # 延迟导入以避免在模块级别加载FastAPI
    try:
        from fastapi import FastAPI
        from fastapi.responses import StreamingResponse

        app = FastAPI(title="Yuling Test API")

        @app.get("/health")
        async def health_check():
            return {"status": "ok", "version": "0.1.0"}

        @app.get("/v1/models")
        async def list_models():
            return {
                "object": "list",
                "data": [
                    {"id": "qwen2.5", "object": "model"},
                    {"id": "gpt-4", "object": "model"},
                ],
            }

        @app.post("/v1/chat/completions")
        async def chat_completion(request_data: dict):
            """OpenAI兼容的chat completions端点。"""
            stream = request_data.get("stream", False)
            model = request_data.get("model", "qwen2.5")
            messages = request_data.get("messages", [])

            if not messages:
                from fastapi import HTTPException
                raise HTTPException(status_code=422, detail="messages is required")

            if stream:
                async def event_stream():
                    chunks = ["Hello", ", ", "streaming", "!"]
                    for chunk in chunks:
                        data = {
                            "choices": [{"delta": {"content": chunk}}],
                            "model": model,
                        }
                        yield f"data: {json.dumps(data)}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    event_stream(), media_type="text/event-stream"
                )

            return {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello from API!"},
                        "finish_reason": "stop",
                    }
                ],
            }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    except ImportError:
        pytest.skip("FastAPI not installed")


# =============================================================================
# Agent Core Fixtures
# =============================================================================


@pytest.fixture
def skill_registry() -> MagicMock:
    """提供空的SkillRegistry实例。"""
    registry = MagicMock()
    registry._skills = {}

    def register(name: str, description: str, handler) -> None:
        registry._skills[name] = {
            "name": name,
            "description": description,
            "handler": handler,
        }

    def list_skills() -> list:
        return [
            {"name": k, "description": v["description"]}
            for k, v in registry._skills.items()
        ]

    def execute(name: str, **kwargs):
        if name not in registry._skills:
            raise KeyError(f"Skill not found: {name}")
        return registry._skills[name]["handler"](**kwargs)

    def unregister(name: str) -> None:
        if name in registry._skills:
            del registry._skills[name]

    registry.register = MagicMock(side_effect=register)
    registry.list_skills = MagicMock(side_effect=list_skills)
    registry.execute = MagicMock(side_effect=execute)
    registry.unregister = MagicMock(side_effect=unregister)
    return registry


@pytest.fixture
def model_router(config: MagicMock, client_ollama: AsyncMock, client_litellm: AsyncMock) -> MagicMock:
    """提供配置的ModelRouter实例。"""
    router = MagicMock()
    router._backends = {
        "ollama": client_ollama,
        "litellm": client_litellm,
    }
    router._primary = config.model.primary_backend
    router._fallback = config.model.fallback_backend

    async def route(model: str, messages: list, stream: bool = False, **kwargs):
        backend = router._backends.get(router._primary)
        try:
            if stream:
                async def stream_gen():
                    chunks = ["Hello", ", ", "world", "!"]
                    for chunk in chunks:
                        yield {"choices": [{"delta": {"content": chunk}}]}
                return stream_gen()
            return await backend.chat(model=model, messages=messages)
        except Exception:
            fallback = router._backends.get(router._fallback)
            return await fallback.chat(model=model, messages=messages)

    async def get_available_models() -> list:
        ollama_models = await client_ollama.list_models()
        return [m["name"] for m in ollama_models.get("models", [])]

    router.route = AsyncMock(side_effect=route)
    router.get_available_models = AsyncMock(side_effect=get_available_models)
    return router


@pytest.fixture
def planner(config: MagicMock) -> MagicMock:
    """提供Planner实例。"""
    planner_mock = MagicMock()

    def plan(instruction: str) -> dict:
        if not instruction or not instruction.strip():
            return {"steps": [], "instruction": instruction}

        # 简单规则：根据关键词拆分
        steps = []
        if "然后" in instruction or "接着" in instruction:
            parts = instruction.replace("接着", "然后").split("然后")
            for i, part in enumerate(parts):
                part = part.strip()
                if part:
                    steps.append({
                        "id": i + 1,
                        "description": part,
                        "dependencies": [i] if i > 0 else [],
                    })
        else:
            steps.append({
                "id": 1,
                "description": instruction,
                "dependencies": [],
            })

        return {"steps": steps, "instruction": instruction}

    planner_mock.plan = MagicMock(side_effect=plan)
    return planner_mock


# =============================================================================
# MCP Fixtures
# =============================================================================


@pytest.fixture
def mcp_manager() -> MagicMock:
    """提供MCP Manager实例。"""
    manager = MagicMock()
    manager._servers = {}
    manager._tools = {}

    def add_server(name: str, config: dict = None, **kwargs) -> None:
        if config is None:
            config = kwargs
        manager._servers[name] = {"config": config, "running": False, "process": None}

    def start_server(name: str) -> None:
        if name not in manager._servers:
            raise KeyError(f"Server not found: {name}")
        manager._servers[name]["running"] = True
        manager._servers[name]["process"] = MagicMock()

    def stop_server(name: str) -> None:
        if name not in manager._servers:
            raise KeyError(f"Server not found: {name}")
        manager._servers[name]["running"] = False
        manager._servers[name]["process"] = None

    async def call_tool(server_name: str, tool_name: str, arguments: dict = None, timeout: float = 30.0):
        if server_name not in manager._servers:
            raise KeyError(f"Server not found: {server_name}")
        if not manager._servers[server_name]["running"]:
            raise RuntimeError(f"Server not running: {server_name}")
        if arguments and arguments.get("trigger_timeout"):
            raise TimeoutError(f"Tool call timed out after {timeout}s")
        return {"result": f"Executed {tool_name} on {server_name}", "tool": tool_name}

    def list_tools(server_name: str) -> list:
        if server_name not in manager._servers:
            raise KeyError(f"Server not found: {server_name}")
        return manager._tools.get(server_name, [])

    manager.add_server = MagicMock(side_effect=add_server)
    manager.start_server = MagicMock(side_effect=start_server)
    manager.stop_server = MagicMock(side_effect=stop_server)
    manager.call_tool = AsyncMock(side_effect=call_tool)
    manager.list_tools = MagicMock(side_effect=list_tools)
    return manager


# =============================================================================
# Wechaty Fixtures
# =============================================================================


@pytest.fixture
def wechaty_bridge(config: MagicMock) -> AsyncMock:
    """提供WechatyBridge实例（mock）。"""
    bridge = AsyncMock()
    bridge._messages = []
    bridge._responses = []

    async def handle_message(message: dict) -> str:
        bridge._messages.append(message)
        msg_type = message.get("type", "text")
        if msg_type == "text":
            text = message.get("text", "")
            response = f"Processed: {text}"
            bridge._responses.append(response)
            return response
        return "Unsupported message type"

    async def send_message(to: str, content: str) -> bool:
        bridge._responses.append({"to": to, "content": content})
        return True

    bridge.handle_message = AsyncMock(side_effect=handle_message)
    bridge.send_message = AsyncMock(side_effect=send_message)
    bridge.start = AsyncMock()
    bridge.stop = AsyncMock()
    return bridge


# =============================================================================
# 辅助 Fixtures
# =============================================================================


@pytest.fixture
def sample_audio_file(temp_dir: Path) -> Path:
    """提供示例音频文件路径。"""
    audio_path = temp_dir / "sample.wav"
    audio_path.write_bytes(b"RIFF\x26\x00\x00\x00WAVEfmt " + b"\x00" * 38)
    return audio_path


@pytest.fixture
def sample_video_file(temp_dir: Path) -> Path:
    """提供示例视频文件路径。"""
    video_path = temp_dir / "sample.mp4"
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)
    return video_path


@pytest.fixture
def sample_workflow() -> dict:
    """提供示例ComfyUI工作流。"""
    return {
        "1": {"inputs": {"text": "a beautiful landscape"}, "class_type": "CLIPTextEncode"},
        "3": {"inputs": {"seed": 42, "steps": 20}, "class_type": "KSampler"},
    }
