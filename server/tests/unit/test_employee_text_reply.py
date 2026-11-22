import asyncio
import json

from szyg.hermes_capabilities import HermesCapabilityRegistry
from szyg.integrations.cloud_inference_client import CloudInferenceClient


def test_employee_text_runs_with_job_instructions_and_no_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("SZYG_DATA_DIR", str(tmp_path))
    directory = tmp_path / "openclaw"
    directory.mkdir()
    profile = {"title": "编辑", "instructions": "负责本周选题"}
    (directory / "xiaoyu-bots.json").write_text(json.dumps({
        "profiles": {"editor": profile, "former": profile}, "archived": {"former": 100},
    }))
    calls = []

    async def chat(self, messages, **kwargs):
        calls.append((messages, kwargs))
        return {"message": {"content": "选题清单"}}

    monkeypatch.setattr(CloudInferenceClient, "chat", chat)
    registry = HermesCapabilityRegistry()

    def run(employee, text="列选题"):
        return json.loads(asyncio.run(registry.execute("employee.reply", {"employee_id": employee, "prompt": text})))

    for employee in ("missing", "former"):
        assert run(employee)["ok"] is False
    assert run("editor", " ")["ok"] is False
    assert not calls
    assert run("editor") == {"ok": True, "text": "选题清单"}
    messages, params = calls[0]
    assert "负责本周选题" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "列选题"}
    assert "tools" not in params
    assert run("xiaoyu-wechat")["ok"] is True

    async def tool_call(self, *args, **kwargs):
        return {"message": {"content": "已发送", "tool_calls": [{"name": "send"}]}}
    monkeypatch.setattr(CloudInferenceClient, "chat", tool_call)
    assert run("editor")["ok"] is False
