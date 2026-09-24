"""Execution Kernel stability smoke runner.

Default mode uses an isolated temporary data directory and only exercises safe
failure paths. Use --generate-image to create a real image asset through
VolcEngine, and add --real-publish-note to submit that image to social-auto-upload.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


TERMINAL = {"success", "failed", "cancelled", "needs_human"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Execution Kernel stability smoke checks.")
    parser.add_argument("--keep-data", action="store_true", help="Keep the temporary data directory.")
    parser.add_argument("--data-dir", default="", help="Use a specific data directory instead of a temp dir.")
    parser.add_argument("--concurrent", type=int, default=12, help="Number of concurrent safe failure runs.")
    parser.add_argument("--generate-image", action="store_true", help="Generate a real image through VolcEngine.")
    parser.add_argument(
        "--real-publish-note",
        action="store_true",
        help="Submit the generated image as a real note publish task. Requires --generate-image.",
    )
    parser.add_argument("--platform", default="douyin", help="Target platform for optional real publish.")
    parser.add_argument(
        "--prompt",
        default="A clean product-style poster for a digital employee system serving small businesses, dashboard UI, realistic lighting, strong visual focus",
        help="Prompt used when --generate-image is enabled.",
    )
    return parser.parse_args()


def prepare_data_dir(args: argparse.Namespace) -> tuple[Path, bool]:
    if args.data_dir:
        data_dir = Path(args.data_dir).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        keep = True
    else:
        data_dir = Path(tempfile.mkdtemp(prefix="szyg_exec_smoke_"))
        keep = args.keep_data
    tools_file = data_dir / "tools.json"
    if not tools_file.exists():
        tools_file.write_text("[]", encoding="utf-8")
    os.environ["SZYG_DATA_DIR"] = str(data_dir)
    return data_dir, keep


async def wait_run(kernel: Any, run_id: str, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        last = kernel.get_run(run_id) or {}
        if last.get("status") in TERMINAL:
            return last
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Execution {run_id} did not finish; last status={last.get('status')}")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def safe_failure_checks(kernel: Any, data_dir: Path, concurrent: int) -> list[dict]:
    missing_video = data_dir / "missing.mp4"
    video_run = kernel.create_sau_upload_video_run(
        {
            "platform": "douyin",
            "file_path": str(missing_video),
            "title": "execution smoke missing video",
            "desc": "",
            "tags": ["szyg-smoke"],
            "headless": True,
        }
    )
    finished_video = await wait_run(kernel, video_run["id"])
    assert_true(finished_video["status"] == "failed", "missing video should fail")
    assert_true(finished_video["error_code"] == "material_missing", "missing video should be material_missing")

    note_run = kernel.create_sau_upload_note_run(
        {
            "platform": "douyin",
            "image_paths": [],
            "title": "execution smoke empty note images",
            "note": "",
            "tags": ["szyg-smoke"],
            "headless": True,
        }
    )
    finished_note = await wait_run(kernel, note_run["id"])
    assert_true(finished_note["status"] == "failed", "empty note image list should fail")
    assert_true(finished_note["error_code"] == "material_missing", "empty note should be material_missing")

    runs = [
        kernel.create_sau_upload_video_run(
            {
                "platform": "douyin",
                "file_path": str(data_dir / f"missing_{index}.mp4"),
                "title": f"execution smoke concurrent {index}",
                "desc": "",
                "tags": ["szyg-smoke"],
                "headless": True,
            }
        )
        for index in range(concurrent)
    ]
    finished = await asyncio.gather(*(wait_run(kernel, run["id"]) for run in runs))
    assert_true(len({run["id"] for run in finished}) == concurrent, "concurrent runs should keep unique ids")
    assert_true(all(run["error_code"] == "material_missing" for run in finished), "concurrent runs should fail safely")
    for run in finished:
        assert_true(kernel.list_audit(run["id"]), f"{run['id']} should have audit events")
    return [finished_video, finished_note, *finished]


async def generate_image_asset(prompt: str, data_dir: Path) -> str:
    from szyg.integrations.volcengine_client import VolcEngineClient

    output_dir = data_dir / "volcengine_output"
    client = VolcEngineClient(output_dir=str(output_dir))
    return await client.generate_image(prompt=prompt, model="doubao-image", size="1920x1920")


async def optional_real_note_publish(kernel: Any, args: argparse.Namespace, image_path: str) -> dict:
    run = kernel.create_sau_upload_note_run(
        {
            "platform": args.platform,
            "image_paths": [image_path],
            "title": "SZYG 图文发布稳定性测试",
            "note": "这是一条由 SZYG Execution Kernel 创建的图文发布验收任务。",
            "tags": ["szygtest", "图文测试"],
            "headless": False,
        }
    )
    return await wait_run(kernel, run["id"], timeout=600.0)


async def main() -> int:
    args = parse_args()
    if args.real_publish_note and not args.generate_image:
        raise SystemExit("--real-publish-note requires --generate-image")

    data_dir, keep_data = prepare_data_dir(args)

    try:
        from szyg.execution_kernel import get_execution_kernel

        kernel = get_execution_kernel()
        finished = await safe_failure_checks(kernel, data_dir, args.concurrent)
        print(f"safe_checks=passed runs={len(finished)} data_dir={data_dir}")

        image_path = ""
        if args.generate_image:
            image_path = await generate_image_asset(args.prompt, data_dir)
            print(f"generated_image={image_path}")

        if args.real_publish_note:
            published = await optional_real_note_publish(kernel, args, image_path)
            print(
                "real_note_publish="
                f"{published.get('status')} id={published.get('id')} "
                f"error_code={published.get('error_code')}"
            )

        return 0
    finally:
        if keep_data:
            print(f"kept_data_dir={data_dir}")
        else:
            shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
