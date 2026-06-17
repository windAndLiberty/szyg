"""
「域灵」数字员工系统 - 数据模型真单元测试

直接导入 yuling.models.* 中的 Pydantic 模型，
测试序列化/反序列化、验证规则、默认值。
"""

import pytest
from pydantic import ValidationError

from yuling.models.api import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelInfo,
    ModelListResponse,
)
from yuling.models.common import ErrorResponse
from yuling.models.integration import (
    BatchResult,
    ChatResponse,
    CompletionResponse,
    GenerateResponse,
    GenerationResult,
    TranscriptionResult,
)
from yuling.models.mcp import MCPServerConfig, Tool, ToolResult
from yuling.models.memory import MemoryEntry
from yuling.models.skill import Skill, SkillParameter, SkillResult
from yuling.models.task import TaskPlan, TaskStep
from yuling.models.wechaty import WechatyMessage


# ============================================================================
# API Models
# ============================================================================


class TestChatCompletionRequest:
    def test_defaults(self):
        req = ChatCompletionRequest()
        assert req.model == "qwen2.5"
        assert req.messages == []
        assert req.stream is False
        assert req.temperature == 0.7
        assert req.max_tokens == 4096

    def test_custom_values(self):
        req = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True,
            temperature=0.3,
            max_tokens=200,
        )
        assert req.model == "gpt-4"
        assert len(req.messages) == 1
        assert req.stream is True
        assert req.temperature == 0.3
        assert req.max_tokens == 200

    def test_json_roundtrip(self):
        req = ChatCompletionRequest(
            model="qwen2.5",
            messages=[{"role": "user", "content": "你好"}],
        )
        json_str = req.model_dump_json()
        restored = ChatCompletionRequest.model_validate_json(json_str)
        assert restored.model == "qwen2.5"
        assert restored.messages[0]["content"] == "你好"


class TestChatCompletionResponse:
    def test_defaults(self):
        resp = ChatCompletionResponse()
        assert resp.id == ""
        assert resp.object == "chat.completion"
        assert resp.model == ""
        assert resp.choices == []
        assert resp.usage == {}

    def test_custom(self):
        resp = ChatCompletionResponse(
            id="chatcmpl-123",
            model="qwen2.5",
            choices=[
                {"index": 0, "message": {"role": "assistant", "content": "Hi!"}, "finish_reason": "stop"}
            ],
            usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        )
        assert resp.id == "chatcmpl-123"
        assert len(resp.choices) == 1


class TestModelInfo:
    def test_construction(self):
        info = ModelInfo(id="qwen2.5", created=1677610602)
        assert info.id == "qwen2.5"
        assert info.object == "model"


class TestModelListResponse:
    def test_construction(self):
        resp = ModelListResponse(
            data=[ModelInfo(id="qwen2.5"), ModelInfo(id="llama3")]
        )
        assert resp.object == "list"
        assert len(resp.data) == 2
        assert resp.data[0].id == "qwen2.5"


# ============================================================================
# Memory Model
# ============================================================================


class TestMemoryEntry:
    def test_construction(self):
        entry = MemoryEntry(
            id=1,
            content="test memory",
            metadata={"key": "value"},
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        assert entry.id == 1
        assert entry.content == "test memory"
        assert entry.metadata["key"] == "value"

    def test_defaults(self):
        entry = MemoryEntry(
            id=1,
            content="test",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        assert entry.metadata == {}

    def test_json_roundtrip(self):
        entry = MemoryEntry(
            id=42,
            content="round trip",
            metadata={"source": "unit_test"},
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            relevance_score=0.95,
        )
        json_str = entry.model_dump_json()
        restored = MemoryEntry.model_validate_json(json_str)
        assert restored.id == 42
        assert restored.relevance_score == 0.95


# ============================================================================
# Task Models
# ============================================================================


class TestTaskStep:
    def test_defaults(self):
        step = TaskStep(id=1, description="test step")
        assert step.id == 1
        assert step.tool_name is None
        assert step.parameters == {}
        assert step.dependencies == []
        assert step.status == "pending"

    def test_with_deps(self):
        step = TaskStep(
            id=2,
            description="step 2",
            tool_name="ffmpeg",
            parameters={"input": "/tmp/v.mp4"},
            dependencies=[1],
        )
        assert step.tool_name == "ffmpeg"
        assert step.dependencies == [1]

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            TaskStep(id=1, description="x", status="invalid")


class TestTaskPlan:
    def test_construction(self):
        plan = TaskPlan(
            instruction="do something",
            steps=[
                TaskStep(id=1, description="step 1"),
                TaskStep(id=2, description="step 2"),
            ],
        )
        assert plan.instruction == "do something"
        assert len(plan.steps) == 2
        assert plan.status == "pending"


# ============================================================================
# MCP Models
# ============================================================================


class TestMCPServerConfig:
    def test_defaults(self):
        cfg = MCPServerConfig(name="test-server", command="python")
        assert cfg.args == []
        assert cfg.env == {}
        assert cfg.enabled is True
        assert cfg.auto_start is True
        assert cfg.timeout == 30

    def test_full(self):
        cfg = MCPServerConfig(
            name="browser",
            command="npx",
            args=["-y", "server-browser-use"],
            env={"NODE_ENV": "production"},
            timeout=60,
        )
        assert cfg.command == "npx"
        assert len(cfg.args) == 2


class TestTool:
    def test_defaults(self):
        tool = Tool(name="read_file")
        assert tool.description == ""
        assert tool.parameters == {}


class TestToolResult:
    def test_success(self):
        result = ToolResult(success=True, data="file content", execution_time=0.15)
        assert result.success is True
        assert result.data == "file content"
        assert result.error is None

    def test_failure(self):
        result = ToolResult(success=False, error="Connection refused", execution_time=5.0)
        assert result.success is False
        assert result.error == "Connection refused"


# ============================================================================
# Skill Models
# ============================================================================


class TestSkillParameterModel:
    def test_defaults(self):
        p = SkillParameter(name="input_file")
        assert p.type == "string"
        assert p.description == ""
        assert p.required is True
        assert p.default is None

    def test_optional(self):
        p = SkillParameter(name="quality", required=False, default="high")
        assert p.required is False
        assert p.default == "high"


class TestSkill:
    def test_minimal(self):
        skill = Skill(name="test", description="A test skill")
        assert skill.parameters == []
        assert skill.handler is None  # excluded, so not in dump

    def test_with_params(self):
        skill = Skill(
            name="ffmpeg_extract",
            description="Extract audio from video",
            parameters=[SkillParameter(name="video_path")],
        )
        assert len(skill.parameters) == 1

    def test_handler_excluded(self):
        """handler 字段应在序列化时排除。"""
        def my_handler():
            pass
        skill = Skill(name="t", description="d", handler=my_handler)
        d = skill.model_dump()
        assert "handler" not in d


class TestSkillResult:
    def test_success(self):
        result = SkillResult(success=True, data="/output.mp4", execution_time=0.25)
        assert result.success is True
        assert result.data == "/output.mp4"

    def test_failure(self):
        result = SkillResult(success=False, error="File not found")
        assert result.error == "File not found"


# ============================================================================
# Integration Models
# ============================================================================


class TestTranscriptionResult:
    def test_defaults(self):
        result = TranscriptionResult(text="Hello world")
        assert result.language == "zh"
        assert result.confidence == 1.0
        assert result.segments == []

    def test_with_segments(self):
        result = TranscriptionResult(
            text="你好世界",
            language="zh",
            confidence=0.95,
            segments=[{"start": 0.0, "end": 1.5, "text": "你好世界"}],
        )
        assert result.segments[0]["text"] == "你好世界"


class TestGenerationResult:
    def test_success(self):
        result = GenerationResult(success=True, prompt_id="pid-123", image_url="/out/img.png")
        assert result.success is True
        assert result.prompt_id == "pid-123"
        assert result.error is None

    def test_failure(self):
        result = GenerationResult(success=False, error="GPU OOM")
        assert result.success is False
        assert result.error == "GPU OOM"


class TestBatchResult:
    def test_defaults(self):
        result = BatchResult(success=True)
        assert result.output_files == []
        assert result.errors == []
        assert result.total == 0
        assert result.completed == 0

    def test_partial(self):
        result = BatchResult(
            success=False,
            output_files=["/a.mp4"],
            errors=["timeout on b.mp4"],
            total=2,
            completed=1,
        )
        assert result.total == 2
        assert result.completed == 1
        assert len(result.errors) == 1


class TestChatResponseModel:
    def test_defaults(self):
        resp = ChatResponse()
        assert resp.message == {}
        assert resp.model == ""
        assert resp.done is True


class TestGenerateResponseModel:
    def test_defaults(self):
        resp = GenerateResponse()
        assert resp.response == ""
        assert resp.done is True


class TestCompletionResponseModel:
    def test_defaults(self):
        resp = CompletionResponse()
        assert resp.choices == []
        assert resp.usage == {}


# ============================================================================
# Wechaty Model
# ============================================================================


class TestWechatyMessage:
    def test_defaults(self):
        msg = WechatyMessage()
        assert msg.id == ""
        assert msg.text == ""
        assert msg.type == "text"
        assert msg.from_id == ""
        assert msg.mention_self is False

    def test_text_message(self):
        msg = WechatyMessage(
            id="msg-001",
            text="你好域灵",
            type="text",
            from_id="wx_user_123",
            from_name="张三",
        )
        assert msg.type == "text"
        assert msg.from_name == "张三"

    def test_image_message(self):
        msg = WechatyMessage(type="image", from_id="wx_456")
        assert msg.type == "image"

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            WechatyMessage(type="sticker")


# ============================================================================
# Common Error Model
# ============================================================================


class TestErrorResponse:
    def test_basic(self):
        err = ErrorResponse(detail="Something went wrong")
        assert err.detail == "Something went wrong"
        assert err.error_code is None

    def test_with_code(self):
        err = ErrorResponse(detail="Auth failed", error_code="AUTH_401")
        assert err.error_code == "AUTH_401"
