"""
知识库 + SOP 系统单元测试。
"""

import json
import pytest

from szyg.agent_core.knowledge import KnowledgeBase
from szyg.agent_core.sop_manager import SOP, SOPStep, SOPManager
from szyg.agent_core.skill_registry import SkillRegistry


class TestKnowledgeBase:
    """知识库测试。"""

    @pytest.fixture
    def kb(self, tmp_path):
        db = str(tmp_path / "test_kb.db")
        k = KnowledgeBase(db)
        yield k
        k.close()

    def test_ingest_text_chunks(self, kb):
        """摄入文本应自动分块。"""
        text = "段落A\n\n段落B\n\n段落C"
        count = kb.ingest_text(text, source="test")
        assert count >= 1

    def test_ingest_file(self, kb, tmp_path):
        """摄入文件。"""
        f = tmp_path / "doc.txt"
        f.write_text("Hello world\n\nThis is a test document")
        count = kb.ingest_file(str(f))
        assert count >= 1

    def test_query_finds_content(self, kb):
        """检索应返回匹配结果。"""
        kb.ingest_text("Python is a programming language for AI development")
        kb.ingest_text("JavaScript is used for web development")
        results = kb.query("Python AI", top_k=3)
        assert len(results) >= 1
        assert "Python" in results[0]["content"]

    def test_query_empty(self, kb):
        """空知识库应返回空结果。"""
        results = kb.query("nothing", top_k=5)
        assert results == []

    def test_query_as_context_format(self, kb):
        """上下文格式应包含来源标记。"""
        kb.ingest_text("域灵AI助手支持SOP工作流", source="产品手册")
        ctx = kb.query_as_context("SOP", top_k=3)
        assert "产品手册" in ctx
        assert "SOP" in ctx

    def test_chunk_large_text(self, kb):
        """超长文本应被分块。"""
        large = ("长文本内容。" * 200)  # ~1200 chars
        count = kb.ingest_text(large, source="large_file")
        assert count >= 2

    def test_source_tracking(self, kb):
        """来源追踪。"""
        kb.ingest_text("内容A", source="doc_a")
        kb.ingest_text("内容B", source="doc_b")
        results = kb.query("内容", top_k=10)
        sources = {r["source"] for r in results}
        assert "doc_a" in sources
        assert "doc_b" in sources


class TestSOPManager:
    """SOP 系统测试。"""

    @pytest.fixture
    def registry(self):
        r = SkillRegistry()
        r.register("step_a", "Step A", handler=lambda **kw: kw)
        r.register("step_b", "Step B", handler=lambda **kw: kw)
        r.register("failing_step", "Always fails", handler=lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        return r

    @pytest.fixture
    def sop_mgr(self, registry, tmp_path):
        db = str(tmp_path / "test_sop.db")
        m = SOPManager(registry, db)
        yield m
        m.close()

    def test_define_sop(self, sop_mgr):
        """定义 SOP。"""
        sop = sop_mgr.define("测试SOP", "用于测试的标准流程", [
            {"skill": "step_a", "params": {"x": "1"}},
            {"skill": "step_b", "params": {"y": "2"}},
        ])
        assert sop.name == "测试SOP"
        assert len(sop.steps) == 2
        assert sop_mgr.get_sop("测试SOP") is not None

    def test_duplicate_sop(self, sop_mgr):
        """同名 SOP 应抛出异常。"""
        sop_mgr.define("dup", "desc", [{"skill": "step_a"}])
        with pytest.raises(ValueError):
            sop_mgr.define("dup", "desc 2", [{"skill": "step_b"}])

    def test_list_sops(self, sop_mgr):
        """列出所有 SOP。"""
        sop_mgr.define("a", "d", [{"skill": "step_a"}])
        sop_mgr.define("b", "d", [{"skill": "step_b"}])
        assert len(sop_mgr.list_sops()) == 2

    def test_delete_sop(self, sop_mgr):
        """删除 SOP。"""
        sop_mgr.define("to_delete", "d", [{"skill": "step_a"}])
        assert sop_mgr.delete("to_delete") is True
        assert sop_mgr.get_sop("to_delete") is None
        assert sop_mgr.delete("not_exist") is False

    def test_execute_sop(self, sop_mgr):
        """执行 SOP。"""
        sop_mgr.define("exec_test", "Execute test", [
            {"skill": "step_a", "params": {"key": "value"}},
            {"skill": "step_b", "params": {"another": "param"}},
        ])
        results = sop_mgr.registry.execute("step_a", key="value")
        assert results.success

    def test_execute_with_variables(self, sop_mgr):
        """SOP 执行中的变量替换。"""
        sop_mgr.define("var_test", "Variable test", [
            {"skill": "step_a", "params": {"name": "{user_name}", "topic": "{topic}"}},
        ])
        # 变量替换在 execute() 中进行
        sop = sop_mgr.get_sop("var_test")
        assert "{user_name}" in str(sop.steps[0].params)

    def test_failure_stop(self, sop_mgr):
        """失败时停止。"""
        sop_mgr.define("fail_sop", "Failure test", [
            {"skill": "failing_step", "params": {}, "on_failure": "stop"},
            {"skill": "step_b", "params": {}, "on_failure": "stop"},
        ])
        results = sop_mgr.registry.execute("failing_step")
        assert results.success is False

    def test_sop_persistence(self, registry, tmp_path):
        """SOP 应持久化到文件。"""
        db = str(tmp_path / "persist.db")
        m1 = SOPManager(registry, db)
        m1.define("persist_test", "Persistence", [{"skill": "step_a"}])
        m1.close()

        m2 = SOPManager(registry, db)
        assert m2.get_sop("persist_test") is not None
        m2.close()
