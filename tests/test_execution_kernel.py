import asyncio
from pathlib import Path

import pytest

from szyg.execution_kernel import classify_error, get_execution_kernel


def test_classify_error_material_missing():
    assert classify_error("argument --file: File not found: D:/missing.mp4") == "material_missing"


@pytest.mark.asyncio
async def test_sau_video_missing_material_creates_failed_execution(tmp_path, monkeypatch):
    import szyg.execution_kernel as kernel_mod

    monkeypatch.setattr(kernel_mod, "RUNS_FILE", tmp_path / "execution_runs.json")
    monkeypatch.setattr(kernel_mod, "STEPS_FILE", tmp_path / "execution_steps.json")
    monkeypatch.setattr(kernel_mod, "AUDIT_FILE", tmp_path / "execution_audit_events.json")
    monkeypatch.setattr(kernel_mod, "OBSERVATIONS_FILE", tmp_path / "execution_observations.json")
    monkeypatch.setattr(kernel_mod, "ASSERTIONS_FILE", tmp_path / "execution_assertions.json")
    monkeypatch.setattr(kernel_mod, "_kernel", None)

    kernel = get_execution_kernel()
    run = kernel.create_run(
        "publish_video",
        "douyin",
        "browser",
        {
            "platform": "douyin",
            "file_path": str(tmp_path / "missing.mp4"),
            "title": "missing material smoke",
        },
        source_task_id="sau:",
    )

    await kernel.run_sau_publish(run["id"])
    finished = kernel.get_run(run["id"])

    assert finished["status"] == "failed"
    assert finished["error_code"] == "material_missing"
    assert len(kernel.list_steps(run["id"])) >= 1
    assert any(event["error_code"] == "material_missing" for event in kernel.list_audit(run["id"]))


def test_sau_compatible_tasks_maps_execution(tmp_path, monkeypatch):
    import szyg.execution_kernel as kernel_mod

    monkeypatch.setattr(kernel_mod, "RUNS_FILE", tmp_path / "execution_runs.json")
    monkeypatch.setattr(kernel_mod, "STEPS_FILE", tmp_path / "execution_steps.json")
    monkeypatch.setattr(kernel_mod, "AUDIT_FILE", tmp_path / "execution_audit_events.json")
    monkeypatch.setattr(kernel_mod, "OBSERVATIONS_FILE", tmp_path / "execution_observations.json")
    monkeypatch.setattr(kernel_mod, "ASSERTIONS_FILE", tmp_path / "execution_assertions.json")
    monkeypatch.setattr(kernel_mod, "_kernel", None)

    kernel = get_execution_kernel()
    run = kernel.create_run(
        "publish_video",
        "douyin",
        "browser",
        {"platform": "douyin", "file_path": str(Path("missing.mp4")), "title": "compat"},
        source_task_id="sau:",
    )
    kernel.complete_run(run["id"], "failed", error_code="material_missing", error_message="File not found")

    task = kernel.sau_compatible_tasks(limit=1)[0]

    assert task["id"] == run["id"]
    assert task["execution_id"] == run["id"]
    assert task["status"] == "failed"
    assert task["error_code"] == "material_missing"


@pytest.mark.asyncio
async def test_sau_note_empty_images_creates_failed_execution(tmp_path, monkeypatch):
    import szyg.execution_kernel as kernel_mod

    monkeypatch.setattr(kernel_mod, "RUNS_FILE", tmp_path / "execution_runs.json")
    monkeypatch.setattr(kernel_mod, "STEPS_FILE", tmp_path / "execution_steps.json")
    monkeypatch.setattr(kernel_mod, "AUDIT_FILE", tmp_path / "execution_audit_events.json")
    monkeypatch.setattr(kernel_mod, "OBSERVATIONS_FILE", tmp_path / "execution_observations.json")
    monkeypatch.setattr(kernel_mod, "ASSERTIONS_FILE", tmp_path / "execution_assertions.json")
    monkeypatch.setattr(kernel_mod, "_kernel", None)

    kernel = get_execution_kernel()
    run = kernel.create_run(
        "publish_note",
        "douyin",
        "browser",
        {
            "platform": "douyin",
            "image_paths": [],
            "title": "empty image smoke",
            "note": "",
        },
        source_task_id="sau:",
    )

    await kernel.run_sau_publish(run["id"])
    finished = kernel.get_run(run["id"])

    assert finished["status"] == "failed"
    assert finished["error_code"] == "material_missing"
    assert any(event["error_code"] == "material_missing" for event in kernel.list_audit(run["id"]))


@pytest.mark.asyncio
async def test_sau_note_missing_image_creates_failed_execution(tmp_path, monkeypatch):
    import szyg.execution_kernel as kernel_mod

    monkeypatch.setattr(kernel_mod, "RUNS_FILE", tmp_path / "execution_runs.json")
    monkeypatch.setattr(kernel_mod, "STEPS_FILE", tmp_path / "execution_steps.json")
    monkeypatch.setattr(kernel_mod, "AUDIT_FILE", tmp_path / "execution_audit_events.json")
    monkeypatch.setattr(kernel_mod, "OBSERVATIONS_FILE", tmp_path / "execution_observations.json")
    monkeypatch.setattr(kernel_mod, "ASSERTIONS_FILE", tmp_path / "execution_assertions.json")
    monkeypatch.setattr(kernel_mod, "_kernel", None)

    kernel = get_execution_kernel()
    missing_image = tmp_path / "missing.png"
    run = kernel.create_run(
        "publish_note",
        "douyin",
        "browser",
        {
            "platform": "douyin",
            "image_paths": [str(missing_image)],
            "title": "missing image smoke",
            "note": "",
        },
        source_task_id="sau:",
    )

    await kernel.run_sau_publish(run["id"])
    finished = kernel.get_run(run["id"])

    assert finished["status"] == "failed"
    assert finished["error_code"] == "material_missing"
    assert str(missing_image) in finished["error_message"]


def test_sau_compatible_task_maps_note_kind(tmp_path, monkeypatch):
    import szyg.execution_kernel as kernel_mod

    monkeypatch.setattr(kernel_mod, "RUNS_FILE", tmp_path / "execution_runs.json")
    monkeypatch.setattr(kernel_mod, "STEPS_FILE", tmp_path / "execution_steps.json")
    monkeypatch.setattr(kernel_mod, "AUDIT_FILE", tmp_path / "execution_audit_events.json")
    monkeypatch.setattr(kernel_mod, "OBSERVATIONS_FILE", tmp_path / "execution_observations.json")
    monkeypatch.setattr(kernel_mod, "ASSERTIONS_FILE", tmp_path / "execution_assertions.json")
    monkeypatch.setattr(kernel_mod, "_kernel", None)

    kernel = get_execution_kernel()
    run = kernel.create_run(
        "publish_note",
        "douyin",
        "browser",
        {"platform": "douyin", "image_paths": [], "title": "note compat"},
        source_task_id="sau:",
    )

    task = kernel.sau_compatible_task(run)

    assert task["id"] == run["id"]
    assert task["kind"] == "upload_note"


@pytest.mark.asyncio
async def test_cancel_run_cancels_running_asyncio_task(tmp_path, monkeypatch):
    import szyg.execution_kernel as kernel_mod

    monkeypatch.setattr(kernel_mod, "RUNS_FILE", tmp_path / "execution_runs.json")
    monkeypatch.setattr(kernel_mod, "STEPS_FILE", tmp_path / "execution_steps.json")
    monkeypatch.setattr(kernel_mod, "AUDIT_FILE", tmp_path / "execution_audit_events.json")
    monkeypatch.setattr(kernel_mod, "OBSERVATIONS_FILE", tmp_path / "execution_observations.json")
    monkeypatch.setattr(kernel_mod, "ASSERTIONS_FILE", tmp_path / "execution_assertions.json")
    monkeypatch.setattr(kernel_mod, "_kernel", None)

    kernel = get_execution_kernel()
    run = kernel.create_run("publish_video", "douyin", "browser", {"title": "cancel"})
    task = asyncio.create_task(asyncio.sleep(60))
    kernel._running[run["id"]] = task

    kernel.cancel_run(run["id"])
    await asyncio.sleep(0)

    assert task.cancelled()
    assert kernel.get_run(run["id"])["status"] == "cancelled"


@pytest.mark.asyncio
async def test_audit_writes_are_not_lost_under_concurrency(tmp_path, monkeypatch):
    import szyg.execution_kernel as kernel_mod

    monkeypatch.setattr(kernel_mod, "RUNS_FILE", tmp_path / "execution_runs.json")
    monkeypatch.setattr(kernel_mod, "STEPS_FILE", tmp_path / "execution_steps.json")
    monkeypatch.setattr(kernel_mod, "AUDIT_FILE", tmp_path / "execution_audit_events.json")
    monkeypatch.setattr(kernel_mod, "OBSERVATIONS_FILE", tmp_path / "execution_observations.json")
    monkeypatch.setattr(kernel_mod, "ASSERTIONS_FILE", tmp_path / "execution_assertions.json")
    monkeypatch.setattr(kernel_mod, "_kernel", None)

    kernel = get_execution_kernel()
    run = kernel.create_run("publish_video", "douyin", "browser", {"title": "audit"})

    await asyncio.gather(*[
        asyncio.to_thread(kernel.add_audit, run["id"], "", "event", "success", f"event {index}")
        for index in range(50)
    ])

    assert len(kernel.list_audit(run["id"])) == 50


class FakeComputerUseAdapter:
    async def health(self):
        return {
            "ok": True,
            "backend": "fake",
            "available": False,
            "platform": "nt",
            "terminator": {"available": False},
            "providers": {
                "terminator": {"available": False},
                "playwright": {"available": True},
                "omniparser": {"available": False},
            },
            "message": "fake desktop ready",
        }

    async def active_window(self):
        return {"title": "Fake Window", "process": "fake", "pid": 1}

    async def list_windows(self):
        return [{"title": "Fake Window", "process": "fake", "pid": 1}]

    async def screenshot(self):
        return {"ok": True, "path": "fake-screen.png"}

    async def observe(self):
        return {
            "ok": True,
            "summary": "当前窗口：Fake Window；可见窗口 1 个；已截图",
            "active_window": await self.active_window(),
            "windows": await self.list_windows(),
            "screenshot": await self.screenshot(),
            "elements": [],
        }

    async def plan_actions(self, payload, observation=None):
        return {"success": True, "actions": [], "message": "planned"}

    async def execute_computer_actions(self, payload, plan=None):
        return {"success": True, "message": "executed", "actions": []}

    async def launch_app(self, target_app):
        return {"success": True, "message": f"opened {target_app}"}

    async def type_text(self, text):
        return {"success": True, "message": f"typed {text}"}

    async def cleanup(self):
        return {"success": True, "message": "cleaned"}


def _isolate_kernel(tmp_path, monkeypatch):
    import szyg.execution_kernel as kernel_mod

    monkeypatch.setattr(kernel_mod, "RUNS_FILE", tmp_path / "execution_runs.json")
    monkeypatch.setattr(kernel_mod, "STEPS_FILE", tmp_path / "execution_steps.json")
    monkeypatch.setattr(kernel_mod, "AUDIT_FILE", tmp_path / "execution_audit_events.json")
    monkeypatch.setattr(kernel_mod, "OBSERVATIONS_FILE", tmp_path / "execution_observations.json")
    monkeypatch.setattr(kernel_mod, "ASSERTIONS_FILE", tmp_path / "execution_assertions.json")
    monkeypatch.setattr(kernel_mod, "_kernel", None)
    return get_execution_kernel()


@pytest.mark.asyncio
async def test_registered_runner_can_start_pause_and_resume_from_checkpoint(tmp_path, monkeypatch):
    kernel = _isolate_kernel(tmp_path, monkeypatch)
    started = asyncio.Event()
    release = asyncio.Event()

    async def runner(run_id):
        run = kernel.get_run(run_id)
        completed = list((run.get("result") or {}).get("completed_step_ids") or [])
        if "first" not in completed:
            completed.append("first")
            kernel.complete_run(run_id, "running", {"completed_step_ids": completed})
        started.set()
        await release.wait()
        return kernel.complete_run(run_id, "success", {"completed_step_ids": completed})

    kernel.register_task_runner("workflow_test", runner)
    run = kernel.create_run("workflow_test", "", "hermes", {})
    kernel.start_run(run["id"])
    await started.wait()
    kernel.pause_run(run["id"])
    await asyncio.sleep(0)

    assert kernel.get_run(run["id"])["status"] == "paused"
    assert kernel.get_run(run["id"])["result"]["completed_step_ids"] == ["first"]

    started.clear()
    kernel.resume_run(run["id"])
    await started.wait()
    release.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert kernel.get_run(run["id"])["status"] == "success"
    assert kernel.get_run(run["id"])["result"]["completed_step_ids"] == ["first"]


@pytest.mark.asyncio
async def test_computer_use_observe_only_completes_with_fake_adapter(tmp_path, monkeypatch):
    import szyg.integrations.computer_use_adapter as adapter_mod

    kernel = _isolate_kernel(tmp_path, monkeypatch)
    monkeypatch.setattr(adapter_mod, "get_computer_use_adapter", lambda: FakeComputerUseAdapter())

    run = kernel.create_run(
        "computer_use",
        "windows",
        "desktop",
        {"instruction": "观察当前桌面", "target_app": "windows", "mode": "observe_only"},
    )

    await kernel.run_computer_use(run["id"])
    finished = kernel.get_run(run["id"])

    assert finished["status"] == "success"
    assert any(item["artifact_path"] == "fake-screen.png" for item in kernel.list_observations(run["id"]))
    assert [step["step_id"] for step in kernel.list_steps(run["id"])][:3] == [
        "validate_request",
        "preflight_providers",
        "observe_initial",
    ]


@pytest.mark.asyncio
async def test_computer_use_sensitive_action_needs_human(tmp_path, monkeypatch):
    import szyg.integrations.computer_use_adapter as adapter_mod

    kernel = _isolate_kernel(tmp_path, monkeypatch)
    monkeypatch.setattr(adapter_mod, "get_computer_use_adapter", lambda: FakeComputerUseAdapter())

    run = kernel.create_run(
        "computer_use",
        "wechat",
        "desktop",
        {"instruction": "打开微信并发送消息", "target_app": "wechat", "mode": "execute"},
    )

    await kernel.run_computer_use(run["id"])
    finished = kernel.get_run(run["id"])

    assert finished["status"] == "needs_human"
    assert finished["error_code"] == "sensitive_action"
    assert any(step["status"] == "needs_human" for step in kernel.list_steps(run["id"]))
