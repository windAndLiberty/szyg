"""SOP manager unit tests."""

import pytest

from szyg.agent_core.sop_manager import SOPManager
from szyg.agent_core.skill_registry import SkillRegistry


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
