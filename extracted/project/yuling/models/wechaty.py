"""微信消息模型。"""

from typing import Literal

from pydantic import BaseModel


class WechatyMessage(BaseModel):
    """微信消息。"""

    id: str = ""
    text: str = ""
    type: Literal["text", "image", "voice", "video", "file"] = "text"
    from_id: str = ""
    from_name: str = ""
    room_id: str | None = None
    timestamp: int = 0
    mention_self: bool = False
