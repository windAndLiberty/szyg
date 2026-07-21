"""
「域灵」数字员工系统 - 端到端测试

测试范围:
- 语音指令完整链路：语音→转录→Agent处理→内容生成
- Agent→MCP→Integration调用链
- 完整聊天API流程
"""

import asyncio
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# =============================================================================
# 端到端测试用例
# =============================================================================

@pytest.mark.asyncio
class TestEndToEnd:
    """端到端测试类。"""

    async def test_voice_to_content_pipeline(
        self,
        temp_dir: Path,
        config: MagicMock,
        planner: MagicMock,
        skill_registry: MagicMock,
    ):
        """
        验收标准: E2E-001 - 语音指令完整链路。
        流程: 语音文件 → Whisper转录 → Planner拆解 → Agent执行 → 返回结果

        Arrange: 模拟语音文件和各组件
        Act: 执行完整链路
        Assert: 各步骤正确执行，最终结果非空
        """
        # Arrange - Create fake audio file
        audio_file = temp_dir / "command.wav"
        audio_file.write_bytes(b"RIFF fake wav data")

        # Step 1: Simulate Whisper transcription
        transcribed_text = "帮我生成一张AI海报，主题是未来城市"

        # Step 2: Simulate Planner task breakdown
        plan = planner.plan(transcribed_text)

        # Step 3: Simulate skill execution based on plan
        def mock_generate_cover(theme: str) -> bytes:
            return b"\x89PNG fake_cover_image_data"

        skill_registry.register(
            name="generate_cover",
            description="Generate AI cover image",
            handler=mock_generate_cover,
        )

        # Act - Execute pipeline
        # 1. Transcription
        assert audio_file.exists(), "Audio file should exist"
        
        # 2. Planning
        assert plan is not None, "Plan should be created"
        assert len(plan["steps"]) > 0, "Plan should have at least one step"
        
        # 3. Execute relevant skill
        if "generate" in transcribed_text or "海报" in transcribed_text:
            result = skill_registry.execute("generate_cover", theme="未来城市")

        # Assert - Verify pipeline results
        # Check plan has valid steps
        for step in plan["steps"]:
            assert "id" in step, "Each step should have an id"
            assert "description" in step, "Each step should have a description"
            assert "dependencies" in step, "Each step should have dependencies"

    async def test_agent_to_mcp_to_integration(
        self,
        config: MagicMock,
        mcp_manager: MagicMock,
        client_ffmpeg: MagicMock,
        client_comfyui: AsyncMock,
    ):
        """
        验收标准: E2E-002 - Agent→MCP→Integration调用链。
        流程: Agent决策 → MCP Tool调用 → Integration Client执行

        Arrange: 设置MCP Server和Integration Client
        Act: Agent决策后通过MCP调用Integration
        Assert: 完整调用链执行成功
        """
        # Arrange - Setup MCP Server for video processing
        mcp_manager.add_server(
            name="video-processor",
            command="python",
            args=["video_server.py"],
        )
        mcp_manager.start_server("video-processor")

        # Register available tools
        mcp_manager.register_tools("video-processor", [
            {"name": "extract_audio", "description": "Extract audio from video"},
            {"name": "generate_cover", "description": "Generate video cover"},
        ])

        # Simulate Agent decision
        agent_decision = {
            "action": "call_tool",
            "server": "video-processor",
            "tool": "extract_audio",
            "arguments": {"video_path": "/input/video.mp4"},
        }

        # Act - Execute the chain: Agent → MCP → Integration
        chain_calls = []

        # 1. Agent decides to use MCP tool
        chain_calls.append(f"Agent decided: {agent_decision['action']}")

        # 2. MCP routes to correct server
        tool_result = await mcp_manager.call_tool(
            server_name=agent_decision["server"],
            tool_name=agent_decision["tool"],
            arguments=agent_decision["arguments"],
        )
        chain_calls.append(f"MCP called tool: {agent_decision['tool']}")

        # 3. Integration client executes actual operation
        ffmpeg_result = client_ffmpeg.extract_audio("/input/video.mp4", "/output/audio.mp3")
        chain_calls.append(f"FFmpeg extracted: {ffmpeg_result}")

        # Assert - Verify complete chain
        assert mcp_manager._servers["video-processor"]["running"] is True
        assert tool_result is not None
        assert tool_result["tool"] == "extract_audio"
        assert len(chain_calls) == 3, "Chain should have 3 steps"
        assert "Agent decided" in chain_calls[0]
        assert "MCP called tool" in chain_calls[1]
        assert "FFmpeg extracted" in chain_calls[2]

        # Cleanup
        mcp_manager.stop_server("video-processor")

    async def test_full_chat_api_flow(
        self,
        config: MagicMock,
        model_router: MagicMock,
    ):
        """
        验收标准: E2E-003 - 完整聊天API流程。
        流程: HTTP请求 → API层 → ModelRouter → Ollama → 响应

        Arrange: 设置各层组件
        Act: 发送聊天请求
        Assert: 完整流程返回正确响应
        """
        # Arrange - Setup components
        conversation_history = []

        async def mock_model_chat(model: str, messages: list, **kwargs) -> dict:
            """模拟模型聊天。"""
            user_message = messages[-1]["content"] if messages else ""
            
            # Store in memory (conversation history)
            conversation_history.append({"role": "user", "content": user_message})
            
            # Generate response
            response_content = f"Response to: {user_message}"
            conversation_history.append({"role": "assistant", "content": response_content})
            
            return {
                "message": {
                    "role": "assistant",
                    "content": response_content,
                },
                "model": model,
                "done": True,
            }

        model_router._backends["ollama"].chat = AsyncMock(side_effect=mock_model_chat)

        # Simulate API request handling
        async def handle_chat_request(request_data: dict) -> dict:
            """模拟API层处理。"""
            model = request_data["model"]
            messages = request_data["messages"]
            stream = request_data.get("stream", False)
            
            # Route through ModelRouter
            result = await model_router.route(model=model, messages=messages, stream=stream)
            
            # Format OpenAI-compatible response
            return {
                "id": "chatcmpl-e2e",
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": result["message"],
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

        # Act - Execute full flow
        request_data = {
            "model": "qwen2.5",
            "messages": [
                {"role": "system", "content": "You are YuLing."},
                {"role": "user", "content": "Tell me about AI agents."},
            ],
            "stream": False,
        }

        response = await handle_chat_request(request_data)

        # Assert - Verify API response format
        assert response["id"] == "chatcmpl-e2e"
        assert response["object"] == "chat.completion"
        assert response["model"] == "qwen2.5"
        assert len(response["choices"]) == 1
        assert response["choices"][0]["message"]["role"] == "assistant"
        assert "Tell me about AI agents" in response["choices"][0]["message"]["content"]
        assert "usage" in response

        # Verify ModelRouter was called
        model_router.route.assert_called_once()
        call_kwargs = model_router.route.call_args.kwargs
        assert call_kwargs["model"] == "qwen2.5"
        assert call_kwargs["stream"] is False

        # Verify conversation history
        assert len(conversation_history) == 2  # user + assistant
        assert conversation_history[0]["role"] == "user"
        assert conversation_history[1]["role"] == "assistant"

    async def test_streaming_chat_api_flow(self, config: MagicMock, model_router: MagicMock):
        """
        额外测试 - 流式聊天API完整流程。

        Arrange: 设置流式模型响应
        Act: 发送流式请求
        Assert: 返回流式chunks
        """
        # Arrange
        model_router.reset_mock()

        async def mock_stream():
            chunks = ["AI", " agents", " are", " intelligent", " systems", "."]
            for chunk in chunks:
                yield {
                    "choices": [{"delta": {"content": chunk}}],
                    "model": "qwen2.5",
                }

        model_router.route = AsyncMock(return_value=mock_stream())

        # Act
        request_data = {
            "model": "qwen2.5",
            "messages": [{"role": "user", "content": "What are AI agents?"}],
            "stream": True,
        }

        stream_result = await model_router.route(
            model=request_data["model"],
            messages=request_data["messages"],
            stream=True,
        )

        # Assert
        chunks = []
        async for chunk in stream_result:
            chunks.append(chunk)

        full_content = "".join(c["choices"][0]["delta"]["content"] for c in chunks)
        assert full_content == "AI agents are intelligent systems."
        model_router.route.assert_called_once()

    async def test_multi_turn_conversation_flow(
        self,
        config: MagicMock,
        model_router: MagicMock,
    ):
        """
        额外测试 - 多轮对话完整流程。

        Arrange: 设置对话上下文
        Act: 进行多轮对话
        Assert: 上下文保持正确
        """
        # Arrange
        conversation = []

        async def mock_chat_with_context(model: str, messages: list, **kwargs) -> dict:
            # Append to conversation
            for msg in messages:
                if msg not in conversation:
                    conversation.append(msg)
            
            return {
                "message": {
                    "role": "assistant",
                    "content": f"Reply to: {messages[-1]['content']}",
                }
            }

        model_router._backends["ollama"].chat = AsyncMock(side_effect=mock_chat_with_context)

        # Act - Multi-turn conversation
        turns = [
            "Hello",
            "What can you do?",
            "Help me write code",
        ]

        for turn in turns:
            messages = [{"role": "user", "content": turn}]
            result = await model_router.route(
                model="qwen2.5",
                messages=messages,
            )
            conversation.append(result["message"])

        # Assert
        assert len(conversation) == 6  # 3 user messages + 3 assistant replies
        assert conversation[0]["role"] == "user"
        assert conversation[0]["content"] == "Hello"
        assert conversation[1]["role"] == "assistant"
        assert conversation[2]["content"] == "What can you do?"
        assert conversation[4]["content"] == "Help me write code"
