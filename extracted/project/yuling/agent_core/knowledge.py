"""
「域灵」知识库系统 — 文档摄入 + 上下文检索。

在 Memory (SQLite FTS5) 基础上增加:
    - 文件摄入: txt, md, json
    - 文档分块: 按段落/语义分割
    - RAG 检索: 搜索相关片段作为 LLM 上下文
    - 来源追踪: 每条知识记录来源文件

用法:
    kb = KnowledgeBase()
    await kb.ingest_file("docs/product_manual.txt")
    context = kb.query("产品价格是多少", top_k=3)
"""

from pathlib import Path
from typing import Any

from yuling.agent_core.memory import Memory


class KnowledgeBase:
    """知识库管理器 — 文档摄入、分块、检索。"""

    CHUNK_SIZE = 500   # 每块最大字符数
    CHUNK_OVERLAP = 50  # 块间重叠

    def __init__(self, db_path: str = "./data/knowledge.db"):
        self.memory = Memory(db_path)
        self._sources: dict[str, dict] = {}  # source_name → metadata

    def ingest_file(self, file_path: str, source_name: str = None) -> int:
        """摄入文件到知识库。

        支持 txt, md, json。自动分块并存储到 Memory。

        Args:
            file_path: 文件路径
            source_name: 来源名称（默认用文件名）

        Returns:
            int: 摄入的块数量
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        source = source_name or path.name
        content = path.read_text(encoding="utf-8", errors="replace")
        return self.ingest_text(content, source=source, source_type=path.suffix)

    def ingest_text(
        self, text: str, source: str = "manual", source_type: str = ".txt"
    ) -> int:
        """摄入文本到知识库，自动分块存储。

        Returns:
            int: 摄入的块数
        """
        chunks = self._chunk(text)
        count = 0
        for i, chunk in enumerate(chunks):
            self.memory.store(
                content=chunk,
                metadata={
                    "type": "knowledge",
                    "source": source,
                    "source_type": source_type,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            )
            count += 1

        self._sources[source] = {
            "chunks": len(chunks),
            "source_type": source_type,
        }
        return count

    def query(self, question: str, top_k: int = 5) -> list[dict]:
        """检索与问题最相关的知识片段。

        Returns:
            list[dict]: [{"content": "...", "source": "...", "score": float}]
        """
        results = self.memory.search(question, limit=top_k)
        return [
            {
                "content": r.content,
                "source": r.metadata.get("source", "unknown"),
                "score": r.relevance_score or 0.0,
            }
            for r in results
        ]

    def query_as_context(self, question: str, top_k: int = 5) -> str:
        """检索并格式化为 LLM 上下文。

        Returns:
            str: 格式化的上下文文本，可直接拼入 prompt
        """
        results = self.query(question, top_k)
        if not results:
            return ""

        parts = ["【知识库相关内容】"]
        for i, r in enumerate(results):
            parts.append(f"[来源: {r['source']}] {r['content']}")
        return "\n\n".join(parts)

    def _chunk(self, text: str) -> list[str]:
        """简单的段落分块：优先按段落，超长段按固定大小切分。"""
        # 按段落分
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return [text]

        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) <= self.CHUNK_SIZE:
                current = current + "\n\n" + para if current else para
            else:
                if current:
                    chunks.append(current)
                if len(para) > self.CHUNK_SIZE:
                    # 超长段按固定大小切分
                    for i in range(0, len(para), self.CHUNK_SIZE - self.CHUNK_OVERLAP):
                        chunks.append(para[i:i + self.CHUNK_SIZE])
                else:
                    current = para
        if current:
            chunks.append(current)
        return chunks

    def close(self):
        self.memory.close()
