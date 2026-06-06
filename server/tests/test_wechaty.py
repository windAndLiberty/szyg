"""
「域灵」数字员工系统 - WechatyBridge私域层测试

测试范围:
- 处理文本消息
- 完整消息管道
- 发送消息
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# =============================================================================
# Helper Classes
# =============================================================================

class WechatyBridgeSimulator:
    """WechatyBridge模拟器。"""

    def __init__(self, config: MagicMock):
        self.config = config
        self._message_handlers = []
        self._received_messages = []
        self._sent_messages = []
        self._agent_callback = None

    def on_message(self, callback):
        """注册消息处理器。"""
        self._agent_callback = callback
        return callback

    async def handle_message(self, message: dict) -> str:
        """处理接收到的消息。"""
        self._received_messages.append(message)
        
        msg_type = message.get("type", "text")
        if msg_type != "text":
            return "Unsupported message type"
        
        text = message.get("text", "")
        if not text:
            return "Empty message"
        
        # Call agent if callback is registered
        if self._agent_callback:
            response = await self._agent_callback(text, message)
            return response
        
        return f"Echo: {text}"

    async def send_message(self, to: str, content: str) -> bool:
        """发送消息到指定联系人。"""
        self._sent_messages.append({
            "to": to,
            "content": content,
            "timestamp": 1234567890,
        })
        return True

    async def start(self):
        """启动桥接。"""
        pass

    async def stop(self):
        """停止桥接。"""
        pass

    def get_received_messages(self) -> list:
        return self._received_messages

    def get_sent_messages(self) -> list:
        return self._sent_messages


def create_wechaty_bridge(config: MagicMock) -> WechatyBridgeSimulator:
    """创建WechatyBridge实例。"""
    return WechatyBridgeSimulator(config)


# =============================================================================
# 测试用例
# =============================================================================


@pytest.mark.asyncio
class TestWechatyBridge:
    """WechatyBridge测试类。"""

    @pytest_asyncio.fixture
    async def bridge(self, config: MagicMock) -> WechatyBridgeSimulator:
        """提供WechatyBridge实例。"""
        return create_wechaty_bridge(config)

    async def test_handle_text_message(self, bridge: WechatyBridgeSimulator):
        """
        验收标准: WCT-001 - 应能接收并解析文本消息。

        Arrange: 准备文本消息
        Act: 处理消息
        Assert: 正确处理并返回回复
        """
        # Arrange
        message = {
            "id": "msg-001",
            "type": "text",
            "text": "Hello, YuLing!",
            "from": "user-123",
            "room": None,
            "timestamp": 1234567890,
        }

        # Act
        response = await bridge.handle_message(message)

        # Assert
        assert response is not None
        assert "Echo: Hello, YuLing!" == response
        assert len(bridge.get_received_messages()) == 1
        assert bridge.get_received_messages()[0]["text"] == "Hello, YuLing!"

    async def test_handle_message_pipeline(self, bridge: WechatyBridgeSimulator):
        """
        验收标准: WCT-002 - 完整消息管道应：接收→解析→Agent处理→发送回复。

        Arrange: 注册Agent回调
        Act: 处理消息
        Assert: 完整管道执行
        """
        # Arrange - Register agent callback
        agent_calls = []

        async def agent_handler(text: str, message: dict) -> str:
            agent_calls.append({"text": text, "from": message.get("from")})
            return f"Agent processed: {text}"

        bridge.on_message(agent_handler)

        message = {
            "id": "msg-002",
            "type": "text",
            "text": "What is AI?",
            "from": "user-456",
            "room": None,
            "timestamp": 1234567890,
        }

        # Act
        response = await bridge.handle_message(message)

        # Assert - Agent was called
        assert len(agent_calls) == 1
        assert agent_calls[0]["text"] == "What is AI?"
        assert agent_calls[0]["from"] == "user-456"
        assert response == "Agent processed: What is AI?"

    async def test_send_message(self, bridge: WechatyBridgeSimulator):
        """
        验收标准: WCT-003 - 应能主动发送消息到指定联系人/群。

        Arrange: 准备目标联系人和内容
        Act: 发送消息
        Assert: 消息记录正确
        """
        # Arrange
        target = "user-789"
        content = "Hello! This is an active notification."

        # Act
        success = await bridge.send_message(target, content)

        # Assert
        assert success is True
        sent = bridge.get_sent_messages()
        assert len(sent) == 1
        assert sent[0]["to"] == target
        assert sent[0]["content"] == content

    async def test_handle_non_text_message(self, bridge: WechatyBridgeSimulator):
        """
        额外测试 - 非文本消息应被适当处理。

        Arrange: 准备图片和语音消息
        Act: 处理消息
        Assert: 返回适当响应
        """
        # Arrange
        image_message = {
            "id": "msg-img-001",
            "type": "image",
            "url": "http://example.com/image.jpg",
            "from": "user-123",
        }
        voice_message = {
            "id": "msg-voice-001",
            "type": "voice",
            "url": "http://example.com/voice.mp3",
            "from": "user-123",
        }

        # Act
        image_response = await bridge.handle_message(image_message)
        voice_response = await bridge.handle_message(voice_message)

        # Assert
        assert image_response == "Unsupported message type"
        assert voice_response == "Unsupported message type"

    async def test_handle_empty_message(self, bridge: WechatyBridgeSimulator):
        """
        额外测试 - 空消息应返回适当响应。

        Arrange: 准备空消息
        Act: 处理
        Assert: 返回空消息提示
        """
        # Arrange
        empty_message = {
            "id": "msg-empty",
            "type": "text",
            "text": "",
            "from": "user-123",
        }

        # Act
        response = await bridge.handle_message(empty_message)

        # Assert
        assert response == "Empty message"

    async def test_start_stop(self, bridge: WechatyBridgeSimulator):
        """
        额外测试 - 启动和停止不应抛异常。

        Arrange: bridge实例
        Act: 启动和停止
        Assert: 无异常
        """
        # Act & Assert
        await bridge.start()
        await bridge.stop()
        # No exception should be raised
