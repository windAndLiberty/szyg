"""
「域灵」数字员工系统 - Wechaty 模块真单元测试
"""

import pytest

from yuling.wechaty.bridge import WechatyBridge
from yuling.wechaty.pipeline import MessagePipeline
from yuling.models.wechaty import WechatyMessage


class TestWechatyBridge:
    """真实 WechatyBridge 类测试。"""

    @pytest.fixture
    def bridge(self):
        return WechatyBridge()

    def test_default_init(self, bridge):
        """默认初始化参数。"""
        assert bridge.name == "域灵助手"
        assert bridge.config is None
        assert bridge._messages == []

    def test_custom_config_name(self):
        """自定义配置中的名字应生效。"""
        config = type("Config", (), {"name": "测试助手"})()
        bridge = WechatyBridge(config=config)
        assert bridge.name == "测试助手"

    async def test_handle_text_message(self, bridge):
        """处理文本消息。"""
        msg = WechatyMessage(type="text", text="你好", from_id="user1")
        response = await bridge.handle_message(msg)
        assert response == "收到消息: 你好"
        assert len(bridge._messages) == 1

    async def test_handle_dict_message(self, bridge):
        """处理字典格式的消息。"""
        msg_dict = {"type": "text", "text": "Hello!", "from_id": "user2"}
        response = await bridge.handle_message(msg_dict)
        assert response == "收到消息: Hello!"

    async def test_handle_non_text_message(self, bridge):
        """处理非文本消息应返回不支持。"""
        msg = WechatyMessage(type="image", from_id="user3")
        response = await bridge.handle_message(msg)
        assert "暂不支持" in response

    async def test_send_message(self, bridge):
        """发送消息。"""
        result = await bridge.send_message("user4", "Hello back!")
        assert result is True
        assert len(bridge._responses) == 1
        assert bridge._responses[0]["to"] == "user4"
        assert bridge._responses[0]["content"] == "Hello back!"

    async def test_start_stop(self, bridge):
        """启动和停止不应崩溃。"""
        await bridge.start()
        await bridge.stop()
        # 没有异常即为通过


class TestMessagePipeline:
    """真实 MessagePipeline 类测试。"""

    @pytest.fixture
    def pipeline(self):
        bridge = WechatyBridge()
        return MessagePipeline(bridge=bridge)

    def test_default_init(self):
        """默认初始化应创建 WechatyBridge。"""
        pipeline = MessagePipeline()
        assert pipeline.bridge is not None
        assert isinstance(pipeline.bridge, WechatyBridge)

    async def test_process_text(self, pipeline):
        """处理原始文本消息。"""
        raw = {"type": "text", "text": "测试消息", "from_id": "user_x"}
        response = await pipeline.process(raw)
        assert response == "收到消息: 测试消息"

    async def test_process_alt_field_names(self, pipeline):
        """使用 content 字段代替 text。"""
        raw = {"type": "text", "content": "备选字段", "from": "user_y"}
        response = await pipeline.process(raw)
        assert response == "收到消息: 备选字段"

    def test_parse_message(self, pipeline):
        """_parse_message 正确解析。"""
        raw = {
            "id": "msg-001",
            "text": "hello",
            "type": "text",
            "from_id": "wx_123",
            "from_name": "张三",
            "timestamp": 1234567890,
            "mention_self": True,
        }
        msg = pipeline._parse_message(raw)
        assert msg.id == "msg-001"
        assert msg.text == "hello"
        assert msg.from_id == "wx_123"
        assert msg.from_name == "张三"
        assert msg.timestamp == 1234567890
        assert msg.mention_self is True
