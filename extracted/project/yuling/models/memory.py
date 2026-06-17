"""记忆相关模型。"""

from pydantic import BaseModel


class MemoryEntry(BaseModel):
    """记忆条目。"""

    id: int | None = None
    content: str
    metadata: dict = {}
    created_at: str = ""
    updated_at: str = ""
    relevance_score: float | None = None


class MemorySearchResult(BaseModel):
    """记忆搜索结果。"""

    entries: list[MemoryEntry]
    total: int
    query: str
