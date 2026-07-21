import json


def test_runtime_session_uses_hermes_builtin_memory(tmp_path, monkeypatch):
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override
    from szyg import hermes_runtime

    token = set_hermes_home_override(tmp_path)
    monkeypatch.setattr(
        hermes_runtime,
        "_config",
        lambda: {
            "memory": {
                "memory_enabled": True,
                "user_profile_enabled": True,
                "memory_char_limit": 2200,
                "user_char_limit": 1375,
                "provider": "",
            }
        },
    )
    try:
        runtime = hermes_runtime.HermesRuntimeSession.create("test-session")
        result = json.loads(runtime.execute_tool("memory", {
            "action": "add",
            "target": "user",
            "content": "用户偏好简洁、可验证的工程结论。",
        }))
        assert result["success"] is True
        assert (tmp_path / "memories" / "USER.md").exists()
        runtime.close()

        reloaded = hermes_runtime.HermesRuntimeSession.create("test-session")
        assert "用户偏好简洁" in reloaded.system_context("如何回答")
        reloaded.close()
    finally:
        reset_hermes_home_override(token)


def test_native_skill_tool_contract_is_exposed():
    from szyg.hermes_runtime import native_skill_tool_schemas

    names = {schema["function"]["name"] for schema in native_skill_tool_schemas()}
    assert names == {"skills_list", "skill_view", "skill_manage"}
