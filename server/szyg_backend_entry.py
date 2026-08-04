"""Frozen SZYG desktop backend entry point."""

from __future__ import annotations

import multiprocessing
import faulthandler
import json
import logging
import os
import sys
from pathlib import Path

import uvicorn


def run_social_upload_cli(arguments: list[str] | None = None) -> int:
    default_home = Path(os.environ.get("SZYG_DATA_DIR", "data")) / "social_auto_upload"
    runtime_home = Path(os.environ.get("SZYG_SAU_RUNTIME_HOME", str(default_home)))
    os.environ["SZYG_SAU_RUNTIME_HOME"] = str(runtime_home)
    runtime_home.mkdir(parents=True, exist_ok=True)
    (runtime_home / "cookies").mkdir(parents=True, exist_ok=True)
    (runtime_home / "logs").mkdir(parents=True, exist_ok=True)

    from szyg.integrations.social_auto_upload.cli import main as sau_main

    return int(sau_main(arguments if arguments is not None else sys.argv[2:]) or 0)


def run_runtime_probe() -> int:
    result: dict[str, object] = {}
    try:
        from szyg.integrations import wxauto_vendor

        result["wxauto"] = {"ok": True, "module": wxauto_vendor.__name__}
    except Exception as exc:
        result["wxauto"] = {"ok": False, "error": str(exc)}
    try:
        from szyg.integrations.social_auto_upload import cli

        result["social_auto_upload"] = {"ok": True, "module": cli.__name__}
    except Exception as exc:
        result["social_auto_upload"] = {"ok": False, "error": str(exc)}
    result["ok"] = all(bool(item.get("ok")) for item in result.values() if isinstance(item, dict))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


def main() -> None:
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] == "--runtime-probe":
        raise SystemExit(run_runtime_probe())
    if Path(sys.executable).stem.lower() == "sau-cli":
        # The dedicated console executable preserves stdout/stderr for the
        # parent adapter while sharing the same frozen module archive.
        raise SystemExit(run_social_upload_cli(sys.argv[1:]))
    if len(sys.argv) > 1 and sys.argv[1] == "--sau-cli":
        raise SystemExit(run_social_upload_cli())
    data_dir = Path(os.environ.get("SZYG_DATA_DIR", "data"))
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_stream = (log_dir / "backend.log").open("a", encoding="utf-8", buffering=1)
    sys.stdout = log_stream
    sys.stderr = log_stream
    logging.basicConfig(
        level=os.environ.get("SZYG_LOG_LEVEL", "WARNING").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=log_stream,
        force=True,
    )
    if os.environ.get("SZYG_STARTUP_DIAGNOSTICS", "").lower() in {"1", "true", "yes"}:
        faulthandler.enable(file=log_stream, all_threads=True)
        faulthandler.dump_traceback_later(20, repeat=True, file=log_stream)
    uvicorn.run(
        "szyg.api.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=int(os.environ.get("SZYG_BACKEND_PORT", "8000")),
        access_log=False,
        log_level=os.environ.get("SZYG_LOG_LEVEL", "warning").lower(),
        log_config=None,
        use_colors=False,
    )


if __name__ == "__main__":
    main()
