"""Frozen/development entry point for the isolated Hermes agent process."""

from __future__ import annotations

import logging
import os
import sys
import traceback
import faulthandler
from pathlib import Path

import uvicorn
import yaml


def _trace_startup(stage: str) -> None:
    if os.environ.get("SZYG_HERMES_STARTUP_TRACE") != "1":
        return
    trace_dir = Path(os.environ.get("SZYG_HERMES_HOME", "data/hermes")).resolve()
    trace_dir.mkdir(parents=True, exist_ok=True)
    with (trace_dir / "runtime-startup-trace.log").open("a", encoding="utf-8") as handle:
        handle.write(stage + "\n")


def _prepare_imports() -> None:
    _trace_startup("prepare-imports.started")
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        root = Path(__file__).resolve().parent
    vendor = root / "vendor" / "hermes_agent"
    if vendor.is_dir() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    _trace_startup("prepare-imports.vendor-ready")
    hermes_home = Path(os.environ.get("SZYG_HERMES_HOME", "data/hermes")).resolve()
    hermes_home.mkdir(parents=True, exist_ok=True)
    os.environ["HERMES_HOME"] = str(hermes_home)
    config_path = hermes_home / "config.yaml"
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    except (OSError, yaml.YAMLError):
        config = {}
    if not isinstance(config, dict):
        config = {}
    model = config.setdefault("model", {})
    if not isinstance(model, dict):
        model = {}
        config["model"] = model
    model.update({
        "default": "text.fast",
        "provider": "custom:szyg-cloud",
        "base_url": os.environ["SZYG_INTERNAL_API_URL"].rstrip("/") + "/api/internal/hermes/openai/v1",
        "context_length": 256000,
        "max_tokens": 32768,
    })
    auxiliary = config.setdefault("auxiliary", {})
    if not isinstance(auxiliary, dict):
        auxiliary = {}
        config["auxiliary"] = auxiliary
    auxiliary["vision"] = {
        "provider": "main",
        "model": "text.vision",
        "timeout": 90,
        "reasoning_effort": "low",
    }
    config.setdefault("network", {})["force_ipv4"] = True
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _trace_startup("prepare-imports.completed")


def main() -> None:
    _trace_startup("main.started")
    if os.environ.get("SZYG_HERMES_STARTUP_TRACE") == "1":
        trace_dir = Path(os.environ.get("SZYG_HERMES_HOME", "data/hermes")).resolve()
        trace_dir.mkdir(parents=True, exist_ok=True)
        stack_stream = (trace_dir / "runtime-startup-stack.log").open("w", encoding="utf-8")
        faulthandler.enable(file=stack_stream, all_threads=True)
        faulthandler.dump_traceback_later(8, repeat=True, file=stack_stream)
    _prepare_imports()
    _trace_startup("app.importing")
    from szyg.hermes_runtime_app import create_app
    _trace_startup("app.imported")

    logging.basicConfig(
        level=os.environ.get("SZYG_LOG_LEVEL", "WARNING").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    app = create_app()
    _trace_startup("app.created")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ["SZYG_HERMES_RUNTIME_PORT"]),
        access_log=False,
        log_config=None,
        use_colors=False,
    )


if __name__ == "__main__":
    _trace_startup("entry.started")
    try:
        main()
    except BaseException:  # Frozen windowed processes otherwise fail silently.
        crash_dir = Path(os.environ.get("SZYG_HERMES_HOME", "data/hermes")).resolve()
        crash_dir.mkdir(parents=True, exist_ok=True)
        (crash_dir / "runtime-startup-error.log").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )
        raise
