import asyncio
from yuling.models.wechaty import WechatyMessage
from yuling.wechaty.bridge import WechatyBridge


class MessagePipeline:
    """微信消息处理管道"""

    def __init__(self, bridge: WechatyBridge | None = None):
        self.bridge = bridge or WechatyBridge()

    async def process(self, raw_message: dict) -> str:
        """处理原始消息（接收→解析→路由→回复）"""
        # 1. 解析消息
        message = self._parse_message(raw_message)

        # 2. 路由到桥接处理
        response = await self.bridge.handle_message(message)

        # 3. 返回回复
        return response

    def _parse_message(self, raw: dict) -> WechatyMessage:
        """解析原始消息为WechatyMessage"""
        return WechatyMessage(
            id=raw.get("id", ""),
            text=raw.get("text", raw.get("content", "")),
            type=raw.get("type", "text"),
            from_id=raw.get("from_id", raw.get("from", "")),
            from_name=raw.get("from_name", ""),
            room_id=raw.get("room_id"),
            timestamp=raw.get("timestamp", 0),
            mention_self=raw.get("mention_self", False),
        )
