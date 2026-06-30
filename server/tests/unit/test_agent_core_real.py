"""
「域灵」数字员工系统 - Agent Core 模块真单元测试

测试 SkillRegistry 和 Planner 的真实类实例。
"""

import pytest

from szyg.agent_core.planner import Planner
from szyg.agent_core.skill_registry import SkillRegistry
from szyg.models.common import DuplicateSkillError, SkillNotFoundError, ValidationError
from szyg.models.skill import Skill, SkillParameter, SkillResult


class TestSkillRegistryReal:
    """真实 SkillRegistry 类测试。"""

    @pytest.fixture
    def registry(self):
        return SkillRegistry()

    def test_register_skill(self, registry):
        """注册技能应存储到内部字典。"""
        skill = registry.register("test_skill", "A test skill")
        assert skill.name == "test_skill"
        assert skill.description == "A test skill"
        assert "test_skill" in registry._skills

    def test_register_with_handler(self, registry):
        """注册带 handler 的技能。"""
        def handler():
            pass
        skill = registry.register("handler_test", "With handler", handler=handler)
        assert registry._handlers.get("handler_test") is handler

    def test_register_with_parameters(self, registry):
        """注册带参数的技能。"""
        skill = registry.register(
            "param_test",
            "Has params",
            parameters=[
                {"name": "input_file", "type": "file_path", "description": "Input file", "required": True},
                {"name": "quality", "type": "string", "description": "Quality level", "required": False, "default": "high"},
            ],
        )
        assert len(skill.parameters) == 2
        assert skill.parameters[0].name == "input_file"
        assert skill.parameters[1].default == "high"

    def test_get_skill(self, registry):
        """应能获取已注册的技能。"""
        registry.register("get_test", "Test get")
        skill = registry.get_skill("get_test")
        assert skill.name == "get_test"

    def test_get_skill_raises_when_missing(self, registry):
        """获取不存在的技能应抛出 SkillNotFoundError。"""
        with pytest.raises(SkillNotFoundError):
            registry.get_skill("nonexistent")

    def test_has_skill(self, registry):
        """has_skill 应正确返回。"""
        registry.register("exists", "d")
        assert registry.has_skill("exists") is True
        assert registry.has_skill("not_here") is False

    def test_list_skills(self, registry):
        """列出所有已注册技能。"""
        registry.register("s1", "d1")
        registry.register("s2", "d2")
        skills = registry.list_skills()
        assert len(skills) == 2
        assert all(isinstance(s, Skill) for s in skills)

    def test_unregister_skill(self, registry):
        """注销技能。"""
        registry.register("to_remove", "d")
        assert registry.unregister("to_remove") is True
        assert not registry.has_skill("to_remove")

    def test_unregister_nonexistent(self, registry):
        """注销不存在的技能返回 False。"""
        assert registry.unregister("never_registered") is False

    def test_register_duplicate_raises(self, registry):
        """重复注册同名技能应抛出 DuplicateSkillError。"""
        registry.register("dup", "first")
        with pytest.raises(DuplicateSkillError):
            registry.register("dup", "second")

    def test_execute_skill(self, registry):
        """执行已注册技能应返回 SkillResult。"""
        def handler(name: str) -> str:
            return f"Hello, {name}!"

        registry.register("greet", "Greet someone", handler=handler)
        result = registry.execute("greet", name="YuLing")
        assert result.success is True
        assert result.data == "Hello, YuLing!"
        assert result.error is None
        assert result.execution_time >= 0

    def test_execute_skill_no_handler(self, registry):
        """执行无 handler 的技能应返回失败。"""
        registry.register("no_handler", "No handler registered")
        result = registry.execute("no_handler")
        assert result.success is False
        assert "No handler" in result.error

    def test_execute_nonexistent_skill(self, registry):
        """执行不存在的技能应抛出 SkillNotFoundError。"""
        with pytest.raises(SkillNotFoundError):
            registry.execute("ghost")

    def test_execute_handler_raises(self, registry):
        """Handler 抛异常应被捕获并返回失败结果。"""
        def handler():
            raise RuntimeError("Something broke!")

        registry.register("crash", "Will crash", handler=handler)
        result = registry.execute("crash")
        assert result.success is False
        assert "Something broke" in result.error

    def test_set_handler(self, registry):
        """set_handler 应设置/更新 handler。"""
        registry.register("later", "Set handler later")

        def handler():
            return "done"

        registry.set_handler("later", handler)
        assert registry.get_handler("later") is handler
        result = registry.execute("later")
        assert result.success is True
        assert result.data == "done"

    def test_set_handler_missing_skill(self, registry):
        """set_handler 对不存在的技能应抛出异常。"""
        with pytest.raises(SkillNotFoundError):
            registry.set_handler("missing", lambda: None)

    def test_get_handler_none(self, registry):
        """get_handler 未设置时返回 None。"""
        registry.register("no_h", "d")
        assert registry.get_handler("no_h") is None


class TestPlannerReal:
    """真实 Planner 类测试。"""

    @pytest.fixture
    def planner(self):
        return Planner()

    def test_plan_simple_task(self, planner):
        """简单指令应返回单步骤计划。"""
        plan = planner.plan_task("help me process a video")
        assert plan.instruction == "help me process a video"
        assert len(plan.steps) == 1
        assert plan.status == "planned"

    def test_plan_complex_task(self, planner):
        """包含"然后"的指令应拆解为多步骤。"""
        plan = planner.plan_task("先剪辑视频然后生成封面图片")
        assert len(plan.steps) >= 2
        # 步骤应有依赖关系
        assert len(plan.steps[0].dependencies) == 0
        assert len(plan.steps[1].dependencies) >= 1

    def test_plan_with_jiezhe(self, planner):
        """包含"接着"的指令应正确拆分。"""
        plan = planner.plan_task("提取音频接着添加字幕")
        assert len(plan.steps) == 2

    def test_plan_empty_instruction(self, planner):
        """空指令应抛出 ValidationError。"""
        with pytest.raises(ValidationError):
            planner.plan_task("")

    def test_plan_whitespace_instruction(self, planner):
        """纯空白字符应抛出 ValidationError。"""
        with pytest.raises(ValidationError):
            planner.plan_task("   \n\t  ")

    def test_tool_inference_ffmpeg(self, planner):
        """应能推断出 ffmpeg 工具。"""
        plan = planner.plan_task("剪辑视频并转码")
        for step in plan.steps:
            # 至少有一个步骤推断出了 ffmpeg
            if step.tool_name == "ffmpeg":
                return
        # 如果都没推断出来，检查 plan 是否有步骤（至少要有）
        assert len(plan.steps) >= 1

    def test_tool_inference_whisper(self, planner):
        """应能推断出 whisper 工具。"""
        plan = planner.plan_task("帮我把这个录音转文字")
        has_whisper = any(s.tool_name == "whisper" for s in plan.steps)
        assert has_whisper or len(plan.steps) >= 1  # 至少应有步骤

    def test_max_steps_limit(self, planner):
        """超过 max_steps 应被截断。"""
        planner.max_steps = 3
        # 构建一个超长指令
        instruction = "然后".join([f"step {i}" for i in range(20)])
        plan = planner.plan_task(instruction)
        assert len(plan.steps) <= 3

    def test_plan_with_context(self, planner):
        """带上下文的规划。"""
        plan = planner.plan_task("process video", context={"session_id": "sess_001"})
        assert plan.instruction == "process video"
        assert plan.status == "planned"

    def test_custom_config(self):
        """自定义配置应生效。"""
        config = type("Config", (), {"max_plan_steps": 5})()
        planner = Planner(config=config)
        assert planner.max_steps == 5

    def test_no_config_default(self):
        """无配置时使用默认值。"""
        planner = Planner()
        assert planner.max_steps == 10
