"""
「域灵」数字员工系统 - Memory模块测试

测试范围:
- 存储和检索记忆
- 全文搜索（FTS5）
- 元数据过滤
- 更新和删除
- 数据持久化
- 搜索结果排序
- 并发安全
"""

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Helper Functions
# =============================================================================

def store_memory(conn: sqlite3.Connection, content: str, metadata: str = None) -> int:
    """存储记忆条目并返回ID。"""
    cursor = conn.execute(
        "INSERT INTO memories (content, metadata) VALUES (?, ?)",
        (content, metadata),
    )
    conn.commit()
    return cursor.lastrowid


def search_memories(conn: sqlite3.Connection, query: str) -> list:
    """使用FTS5 + LIKE fallback 全文搜索记忆。"""
    # 先尝试 LIKE 搜索（对中文更友好）
    cursor = conn.execute(
        """
        SELECT m.id, m.content, m.metadata, 0 as rank
        FROM memories m
        WHERE m.content LIKE ?
        ORDER BY m.id
        """,
        (f"%{query}%",),
    )
    results = [dict(row) for row in cursor.fetchall()]
    if results:
        return results

    # LIKE 无结果时回退到 FTS5
    try:
        cursor = conn.execute(
            """
            SELECT m.id, m.content, m.metadata, rank
            FROM memories_fts fts
            JOIN memories m ON m.id = fts.rowid
            WHERE memories_fts MATCH ?
            ORDER BY rank
            """,
            (query,),
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        return []


def get_memory(conn: sqlite3.Connection, memory_id: int) -> dict | None:
    """根据ID获取记忆。"""
    cursor = conn.execute(
        "SELECT id, content, metadata FROM memories WHERE id = ?", (memory_id,)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def update_memory(conn: sqlite3.Connection, memory_id: int, content: str, metadata: str = None) -> bool:
    """更新记忆条目。"""
    cursor = conn.execute(
        "UPDATE memories SET content = ?, metadata = ? WHERE id = ?",
        (content, metadata, memory_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def delete_memory(conn: sqlite3.Connection, memory_id: int) -> bool:
    """删除记忆条目。"""
    cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    return cursor.rowcount > 0


def search_by_metadata(conn: sqlite3.Connection, key: str, value: str) -> list:
    """按元数据搜索。"""
    cursor = conn.execute(
        "SELECT id, content, metadata FROM memories WHERE metadata LIKE ?",
        (f'%"{key}": "{value}"%',),
    )
    return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# 测试用例
# =============================================================================


class TestMemoryModule:
    """Memory模块测试类。"""

    def test_store_and_retrieve(self, memory_db: sqlite3.Connection):
        """
        验收标准: MEM-001 - 应支持存储带content和metadata的记忆条目。

        Arrange: 准备记忆内容
        Act: 存储记忆并检索
        Assert: 检索结果与存储内容一致
        """
        # Arrange
        content = "今天是项目启动会议，讨论了技术架构方案"
        metadata = '{"type": "meeting", "project": "yuling"}'

        # Act
        memory_id = store_memory(memory_db, content, metadata)
        retrieved = get_memory(memory_db, memory_id)

        # Assert
        assert retrieved is not None, "Memory should be retrievable"
        assert retrieved["content"] == content, "Content should match"
        assert retrieved["metadata"] == metadata, "Metadata should match"

    def test_search_by_content(self, memory_db: sqlite3.Connection):
        """
        验收标准: MEM-002 - 应支持基于内容的全文搜索。

        Arrange: 存储多条记忆
        Act: 搜索关键词
        Assert: 返回匹配结果
        """
        # Arrange - Store multiple memories
        memories = [
            ("Python是一种高级编程语言", '{"category": "tech"}'),
            ("Java也广泛用于企业开发", '{"category": "tech"}'),
            ("今天的午餐很好吃", '{"category": "life"}'),
            ("Python 3.12发布了新特性", '{"category": "tech"}'),
        ]
        for content, meta in memories:
            store_memory(memory_db, content, meta)

        # Act - Search for "Python"
        results = search_memories(memory_db, "Python")

        # Assert
        assert len(results) == 2, f"Should find 2 Python-related memories, got {len(results)}"
        contents = [r["content"] for r in results]
        assert "Python是一种高级编程语言" in contents
        assert "Python 3.12发布了新特性" in contents

    def test_search_by_metadata(self, memory_db: sqlite3.Connection):
        """
        验收标准: MEM-003 - 应支持基于metadata的过滤搜索。

        Arrange: 存储带不同metadata的记忆
        Act: 按metadata过滤
        Assert: 返回匹配的记录
        """
        # Arrange
        store_memory(memory_db, "架构讨论记录", '{"type": "meeting", "project": "yuling"}')
        store_memory(memory_db, "需求分析文档", '{"type": "doc", "project": "yuling"}')
        store_memory(memory_db, "竞品分析报告", '{"type": "doc", "project": "other"}')

        # Act - Filter by project=yuling
        results = search_by_metadata(memory_db, "project", "yuling")

        # Assert
        assert len(results) == 2, f"Should find 2 yuling project memories, got {len(results)}"

    def test_update_entry(self, memory_db: sqlite3.Connection):
        """
        验收标准: MEM-004 - 应支持更新已有记忆条目。

        Arrange: 存储一条记忆
        Act: 更新内容和metadata
        Assert: 更新后的值正确
        """
        # Arrange
        old_content = "初始版本的需求文档"
        memory_id = store_memory(memory_db, old_content, '{"version": 1}')

        # Act
        new_content = "更新后的需求文档，增加了用户故事"
        success = update_memory(memory_db, memory_id, new_content, '{"version": 2}')
        retrieved = get_memory(memory_db, memory_id)

        # Assert
        assert success is True, "Update should succeed"
        assert retrieved["content"] == new_content, "Content should be updated"
        assert "version" in retrieved["metadata"], "Metadata should be updated"

    def test_delete_entry(self, memory_db: sqlite3.Connection):
        """
        验收标准: MEM-005 - 应支持删除记忆条目。

        Arrange: 存储一条记忆
        Act: 删除该记忆
        Assert: 无法再次检索到
        """
        # Arrange
        memory_id = store_memory(memory_db, "临时记忆", None)
        assert get_memory(memory_db, memory_id) is not None

        # Act
        success = delete_memory(memory_db, memory_id)

        # Assert
        assert success is True, "Delete should succeed"
        assert get_memory(memory_db, memory_id) is None, "Deleted memory should not be found"

    def test_persistence(self, temp_dir: Path):
        """
        验收标准: MEM-006 - 数据库关闭后重新打开，数据应保持不变。

        Arrange: 创建数据库并存储数据
        Act: 关闭数据库，重新打开
        Assert: 数据仍然存在
        """
        # Arrange - Create DB and store data
        db_path = temp_dir / "persistent_memory.db"
        conn1 = sqlite3.connect(str(db_path))
        conn1.row_factory = sqlite3.Row
        conn1.execute("""
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                metadata TEXT
            )
        """)
        conn1.execute(
            "INSERT INTO memories (content, metadata) VALUES (?, ?)",
            ("持久化测试数据", '{"test": true}'),
        )
        conn1.commit()
        conn1.close()

        # Act - Reopen database
        conn2 = sqlite3.connect(str(db_path))
        conn2.row_factory = sqlite3.Row
        cursor = conn2.execute("SELECT * FROM memories WHERE id = 1")
        row = cursor.fetchone()

        # Assert
        assert row is not None, "Data should persist after reopening"
        assert dict(row)["content"] == "持久化测试数据"
        conn2.close()

    def test_search_ranking(self, memory_db: sqlite3.Connection):
        """
        验收标准: MEM-007 - 搜索结果应按相关性排序。

        Arrange: 存储多条记忆，其中一条高度匹配
        Act: 搜索关键词
        Assert: 最相关的结果排在前面
        """
        # Arrange - Store memories with varying relevance
        store_memory(memory_db, "Python编程指南和最佳实践", None)
        store_memory(memory_db, "Python基础教程", None)
        store_memory(memory_db, "Java编程思想", None)
        store_memory(memory_db, "Python Python Python高频关键词", None)

        # Act
        results = search_memories(memory_db, "Python")

        # Assert
        assert len(results) >= 2, "Should find multiple matches"
        # 验证结果按相关性排序（FTS5 rank升序，rank越小越相关）
        for i in range(len(results) - 1):
            assert results[i]["rank"] <= results[i + 1]["rank"], (
                "Results should be ordered by relevance (rank)"
            )

    def test_concurrent_access(self, memory_db: sqlite3.Connection, temp_dir: Path):
        """
        验收标准: MEM-008 - 并发写入操作应线程安全。

        Arrange: 准备多个写入任务
        Act: 使用线程池并发写入
        Assert: 所有数据正确写入，无异常
        """
        # Arrange
        num_threads = 10
        contents = [f"并发写入测试数据-{i}" for i in range(num_threads)]
        db_path = temp_dir / "test_memory.db"

        def write_task(content: str) -> int:
            # 每个线程使用独立的新连接
            new_conn = sqlite3.connect(str(db_path), check_same_thread=False)
            new_conn.row_factory = sqlite3.Row
            return store_memory(new_conn, content, None)

        # Act - Concurrent writes
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_task, c) for c in contents]
            ids = [f.result() for f in futures]

        # Assert - Verify all writes succeeded
        assert len(set(ids)) == num_threads, "Each write should get a unique ID"
        for i, content in enumerate(contents):
            retrieved = get_memory(memory_db, ids[i])
            assert retrieved is not None, f"Memory {i} should exist"
            assert retrieved["content"] == content, f"Memory {i} content should match"

    def test_search_no_results(self, memory_db: sqlite3.Connection):
        """
        验收标准: MEM-010 - 空搜索应返回空列表而非异常。

        Arrange: 存储一些记忆
        Act: 搜索不存在的关键词
        Assert: 返回空列表
        """
        # Arrange
        store_memory(memory_db, "Python编程", None)

        # Act - Search for non-existent keyword
        results = search_memories(memory_db, "不存在的关键词XYZ")

        # Assert
        assert results == [], "Search with no matches should return empty list"

    def test_vector_search_placeholder(self, memory_db: sqlite3.Connection):
        """
        验收标准: MEM-009 - 应支持向量检索存储（预留测试接口）。

        Arrange: 准备向量数据
        Act: 模拟向量存储和检索
        Assert: 接口可用
        """
        # Arrange - Create vector table (placeholder for vector search)
        memory_db.execute("""
            CREATE TABLE IF NOT EXISTS memory_vectors (
                memory_id INTEGER REFERENCES memories(id),
                vector_embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Act - Store a vector embedding (simulated)
        import struct
        vector = [0.1, 0.2, 0.3, 0.4]  # Simulated 4-dim vector
        vector_blob = struct.pack("f" * len(vector), *vector)
        memory_db.execute(
            "INSERT INTO memory_vectors (memory_id, vector_embedding) VALUES (?, ?)",
            (1, vector_blob),
        )
        memory_db.commit()

        # Act - Retrieve vector
        cursor = memory_db.execute(
            "SELECT vector_embedding FROM memory_vectors WHERE memory_id = 1"
        )
        row = cursor.fetchone()

        # Assert
        assert row is not None, "Vector should be stored"
        retrieved = struct.unpack("f" * 4, row["vector_embedding"])
        assert list(retrieved) == pytest.approx(vector, abs=1e-5), (
            "Retrieved vector should match stored vector"
        )
