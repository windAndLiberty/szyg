"""
「域灵」数字员工系统 - 长期记忆管理模块

基于 SQLite FTS5 的全文检索 + 向量存储。
"""

import json
import logging
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from szyg.models.common import MemoryError
from szyg.models.memory import MemoryEntry

logger = logging.getLogger(__name__)


class Memory:
    """长期记忆管理 - SQLite FTS5 全文检索 + 向量存储。

    提供存储、检索、搜索、更新、删除记忆条目的功能。
    使用 FTS5 虚拟表实现高效全文搜索。
    """

    def __init__(self, db_path: str = "./data/memory.db"):
        """初始化记忆管理器。

        Args:
            db_path: SQLite 数据库文件路径。支持 ":memory:" 内存数据库。
        """
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._ensure_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接。

        对于内存数据库，使用持久连接。
        对于文件数据库，每次创建新连接。
        """
        if self.db_path == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(self.db_path)
            return self._conn
        return sqlite3.connect(self.db_path)

    def _ensure_db(self) -> None:
        """确保数据库和表结构存在。"""
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_connection()
        try:
            # 主表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            # FTS5 虚拟表
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    content, metadata,
                    content='memories', content_rowid='id'
                )
            """
            )
            # 触发器 - 插入
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memories_fts(rowid, content, metadata)
                    VALUES (new.id, new.content, new.metadata);
                END
            """
            )
            # 触发器 - 删除
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content, metadata)
                    VALUES ('delete', old.id, old.content, old.metadata);
                END
            """
            )
            # 触发器 - 更新
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content, metadata)
                    VALUES ('delete', old.id, old.content, old.metadata);
                    INSERT INTO memories_fts(rowid, content, metadata)
                    VALUES (new.id, new.content, new.metadata);
                END
            """
            )
            conn.commit()
        except Exception as e:
            logger.info("FTS5 not available, full-text search will use LIKE fallback: %s", e)

    def store(self, content: str, metadata: dict | None = None) -> MemoryEntry:
        """存储记忆。

        Args:
            content: 记忆内容
            metadata: 记忆元数据字典

        Returns:
            存储后的记忆条目

        Raises:
            MemoryError: 存储失败时抛出
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO memories (content, metadata) VALUES (?, ?)",
                (content, json.dumps(metadata or {})),
            )
            entry_id = cursor.lastrowid
            conn.commit()
            row = conn.execute(
                "SELECT id, content, metadata, created_at, updated_at FROM memories WHERE id = ?",
                (entry_id,),
            ).fetchone()
            return MemoryEntry(
                id=row[0],
                content=row[1],
                metadata=json.loads(row[2]),
                created_at=row[3],
                updated_at=row[4],
            )
        except sqlite3.Error as e:
            raise MemoryError(f"Failed to store memory: {e}")

    def retrieve(self, entry_id: int) -> MemoryEntry | None:
        """按 ID 检索记忆。

        Args:
            entry_id: 记忆条目 ID

        Returns:
            记忆条目，未找到则返回 None
        """
        conn = self._get_connection()
        row = conn.execute(
            "SELECT id, content, metadata, created_at, updated_at FROM memories WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if row is None:
            return None
        return MemoryEntry(
            id=row[0],
            content=row[1],
            metadata=json.loads(row[2]),
            created_at=row[3],
            updated_at=row[4],
        )

    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """FTS5 全文搜索记忆。FTS5 无结果时自动回退 LIKE。

        Args:
            query: 搜索查询
            limit: 返回结果数量上限

        Returns:
            匹配的记忆条目列表
        """
        conn = self._get_connection()
        rows = []
        try:
            rows = conn.execute(
                """
                SELECT m.id, m.content, m.metadata, m.created_at, m.updated_at,
                       rank
                FROM memories_fts f
                JOIN memories m ON m.id = f.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """,
                (query, limit),
            ).fetchall()
        except sqlite3.Error as e:
            logger.debug("FTS5 search failed, falling back to LIKE: %s", e)

        # FTS5 无结果时回退到 LIKE（处理 CJK 等无分词语言）
        if not rows:
            rows = conn.execute(
                "SELECT id, content, metadata, created_at, updated_at "
                "FROM memories WHERE content LIKE ? OR metadata LIKE ? LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
            results = []
            for r in rows:
                entry = MemoryEntry(
                    id=r[0], content=r[1],
                    metadata=json.loads(r[2]) if isinstance(r[2], str) else (r[2] or {}),
                    created_at=r[3], updated_at=r[4],
                )
                results.append(entry)
            return results

        results = []
        for row in rows:
            entry = MemoryEntry(
                id=row[0],
                content=row[1],
                metadata=json.loads(row[2]),
                created_at=row[3],
                updated_at=row[4],
                relevance_score=row[5],
            )
            results.append(entry)
        return results

    def search_by_metadata(self, key: str, value: Any, limit: int = 5) -> list[MemoryEntry]:
        """按元数据搜索。

        Args:
            key: 元数据键
            value: 元数据值
            limit: 返回结果数量上限

        Returns:
            匹配的记忆条目列表
        """
        conn = self._get_connection()
        pattern = f'%"{key}": "{value}"%'
        rows = conn.execute(
            """SELECT id, content, metadata, created_at, updated_at 
               FROM memories WHERE metadata LIKE ? LIMIT ?""",
            (pattern, limit),
        ).fetchall()
        return [
            MemoryEntry(
                id=r[0],
                content=r[1],
                metadata=json.loads(r[2]),
                created_at=r[3],
                updated_at=r[4],
            )
            for r in rows
        ]

    def update(
        self,
        entry_id: int,
        content: str | None = None,
        metadata: dict | None = None,
    ) -> MemoryEntry | None:
        """更新记忆。

        Args:
            entry_id: 记忆条目 ID
            content: 新内容（None 表示不更新）
            metadata: 新元数据（None 表示不更新）

        Returns:
            更新后的记忆条目，未找到则返回 None
        """
        conn = self._get_connection()
        existing = conn.execute(
            "SELECT content, metadata FROM memories WHERE id = ?", (entry_id,)
        ).fetchone()
        if existing is None:
            return None
        new_content = content if content is not None else existing[0]
        new_metadata = json.dumps(metadata) if metadata is not None else existing[1]
        conn.execute(
            "UPDATE memories SET content = ?, metadata = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_content, new_metadata, entry_id),
        )
        conn.commit()
        return self.retrieve(entry_id)

    def delete(self, entry_id: int) -> bool:
        """删除记忆。

        Args:
            entry_id: 记忆条目 ID

        Returns:
            是否成功删除
        """
        conn = self._get_connection()
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (entry_id,))
        conn.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        """关闭资源。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Memory":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
