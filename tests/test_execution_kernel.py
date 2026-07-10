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
