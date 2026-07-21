"""Frozen SZYG desktop backend entry point."""

from __future__ import annotations

import multiprocessing
import faulthandler
import logging
import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    multiprocessing.freeze_support()
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
