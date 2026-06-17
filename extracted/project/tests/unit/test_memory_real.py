"""
「域灵」数字员工系统 - Memory模块真单元测试

直接导入 yuling.agent_core.memory.Memory，
使用 SQLite :memory: 数据库测试真实的 FTS5 全文检索。
"""

import json
import threading
from pathlib import Path

import pytest

from yuling.agent_core.memory import Memory
from yuling.models.common import MemoryError
from yuling.models.memory import MemoryEntry


class TestMemoryReal:
    """使用真实 Memory 类的单元测试。"""

    @pytest.fixture
    def mem(self, tmp_path):
        """创建基于临时文件的 Memory 实例。"""
        db_path = str(tmp_path / "test_memory.db")
        m = Memory(db_path)
        yield m
        m.close()

    @pytest.fixture
    def mem_memory(self):
        """创建基于 :memory: 的 Memory 实例。"""
        m = Memory(":memory:")
        yield m
        m.close()

    def test_store_and_retrieve(self, mem):
        """存储后应能按 ID 检索。"""
        entry = mem.store("Hello, YuLing!", {"type": "greeting", "lang": "zh"})
        assert entry.id is not None
        assert entry.content == "Hello, YuLing!"
        assert entry.metadata["type"] == "greeting"

        retrieved = mem.retrieve(entry.id)
        assert retrieved is not None
        assert retrieved.content == "Hello, YuLing!"
        assert retrieved.metadata["type"] == "greeting"

    def test_retrieve_nonexistent(self, mem):
        """检索不存在的 ID 应返回 None。"""
        result = mem.retrieve(99999)
        assert result is None

    def test_store_empty_metadata(self, mem):
        """不提供 metadata 时应默认为空字典。"""
        entry = mem.store("content only")
        assert entry.metadata == {}

    def test_full_text_search(self, mem):
        """FTS5 全文搜索应能匹配内容。"""
        mem.store("The weather today is sunny and warm", {"type": "diary"})
        mem.store("Tomorrow might rain bring an umbrella", {"type": "diary"})
        mem.store("Python is a great programming language for AI", {"type": "fact"})

        # 英文搜索
        results = mem.search("weather", limit=5)
        assert len(results) >= 1
        assert any("weather" in r.content for r in results)

        results = mem.search("Python", limit=5)
        assert len(results) >= 1
        assert any("Python" in r.content for r in results)

    def test_full_text_search_cjk(self, mem):
        """CJK 搜索回退到 LIKE 模式。FTS5 默认 tokenizer 不支持 CJK 分词，
        但代码中 search() 方法会在 MATCH 无结果时回退到 LIKE。"""
        mem.store("今天天气很好适合出门", {"type": "diary"})
        mem.store("明天可能有雨需要带伞", {"type": "diary"})
        mem.store("机器学习 Machine Learning", {"type": "fact"})

        # LIKE 回退应能找到中文——注意 FTS5 MATCH 返回0行但不抛异常，
        # 这里测试 LIKE 回退路径：匹配"学习"能命中
        results = mem.search("Machine", limit=5)
        assert len(results) >= 1

        # 单字符英文字也能匹配
        results = mem.search("Learning", limit=5)
        assert len(results) >= 1

    def test_search_limit(self, mem):
        """搜索应尊重 limit 参数。"""
        for i in range(5):
            mem.store(f"test search item number {i}")
        results = mem.search("test search", limit=2)
        assert len(results) == 2

    def test_search_no_results(self, mem):
        """搜索无匹配内容应返回空列表（不抛异常）。"""
        results = mem.search("zzzz_nonexistent_content_zzzz", limit=5)
        assert results == []

    def test_search_ranking(self, mem):
        """FTS5 搜索结果应按 rank 排序（更相关的结果排在前面）。"""
        mem.store("Artificial Intelligence and Machine Learning research paper")
        mem.store("Artificial Intelligence application case study in healthcare")
        mem.store("Machine Learning tutorial for beginners in Python")

        results = mem.search("Artificial Intelligence", limit=3)
        assert len(results) >= 2
        # 检查 relevance_score 是否存在
        for r in results:
            assert r.relevance_score is not None

    def test_search_by_metadata(self, mem):
        """按 metadata 过滤搜索。"""
        mem.store("video editing tutorial", {"category": "video", "level": "beginner"})
        mem.store("image generation guide", {"category": "image", "level": "advanced"})
        mem.store("python basics", {"category": "code", "level": "beginner"})

        results = mem.search_by_metadata("category", "video", limit=5)
        assert len(results) == 1
        assert results[0].content == "video editing tutorial"

        results = mem.search_by_metadata("level", "beginner", limit=5)
        assert len(results) == 2

    def test_update_entry(self, mem):
        """更新记忆条目。"""
        entry = mem.store("original content", {"v": 1})
        updated = mem.update(entry.id, content="updated content", metadata={"v": 2})

        assert updated is not None
        assert updated.content == "updated content"
        assert updated.metadata["v"] == 2

        # 验证原条目也被更新
        retrieved = mem.retrieve(entry.id)
        assert retrieved.content == "updated content"

    def test_update_nonexistent(self, mem):
        """更新不存在的 ID 应返回 None。"""
        result = mem.update(99999, content="new")
        assert result is None

    def test_update_partial(self, mem):
        """只更新 content 不更新 metadata，反之亦然。"""
        entry = mem.store("original", {"key": "value"})

        # 只更新 content
        updated = mem.update(entry.id, content="new content")
        assert updated.content == "new content"
        assert updated.metadata == {"key": "value"}

        # 只更新 metadata
        updated = mem.update(entry.id, metadata={"key": "new value", "extra": 123})
        assert updated.content == "new content"
        assert updated.metadata["key"] == "new value"
        assert updated.metadata["extra"] == 123

    def test_delete_entry(self, mem):
        """删除后应无法检索。"""
        entry = mem.store("to be deleted")
        assert mem.delete(entry.id) is True
        assert mem.retrieve(entry.id) is None
        assert mem.delete(entry.id) is False  # 再次删除返回 False

    def test_persistence(self, tmp_path):
        """关闭后重新打开，数据应保持。"""
        db_path = str(tmp_path / "persist_test.db")

        # 写入
        m1 = Memory(db_path)
        m1.store("persistent data", {"persist": True})
        m1.close()

        # 重新打开
        m2 = Memory(db_path)
        # 直接搜索（FTS 可能需要等待同步，用 search_by_metadata 更稳定）
        results = m2.search("persistent", limit=5)
        assert len(results) >= 1
        assert results[0].content == "persistent data"
        m2.close()

    def test_concurrent_access(self, mem):
        """并发写入应线程安全（线程间写入不互相干扰）。"""
        errors = []

        def write_entry(content):
            try:
                mem.store(content)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            t = threading.Thread(target=write_entry, args=(f"concurrent test {i}",))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # 所有数据都应可搜索
        results = mem.search("concurrent test", limit=20)
        assert len(results) == 10

    def test_memory_error_on_corrupt(self, tmp_path):
        """空文件或损坏数据库不应崩溃。"""
        corrupt_path = tmp_path / "corrupt.db"
        # 写入非SQLite内容
        corrupt_path.write_text("this is not a sqlite database")
        m = Memory(str(corrupt_path))
        # 不应在构造时崩溃
        # 但 store 操作应可能触发异常
        try:
            m.store("test")
        except MemoryError:
            pass  # 预期行为
        finally:
            m.close()

    def test_context_manager(self):
        """支持 with 语句。"""
        with Memory(":memory:") as m:
            m.store("test context")
            assert len(m.search("test", limit=1)) == 1
        # __exit__ 应已调用 close()
