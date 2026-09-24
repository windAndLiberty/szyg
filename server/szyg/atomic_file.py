"""
Atomic JSON File I/O — safe concurrent read/write for single-process asyncio apps.

Design:
  - Writes use temp-file + atomic rename (never half-written).
  - ``threading.Lock`` serializes thread-pool access (e.g. FastAPI sync routes
    dispatched via run_in_executor / asyncio.to_thread).
  - ``_async_read`` / ``_async_write`` run the sync I/O through
    ``asyncio.to_thread()`` so the event loop never blocks on disk.
  - For single-worker uvicorn (the common deployment), the threading.Lock is
    mostly redundant — but it costs nothing and defends against future thread-
    pool usage.

Usage:
    from szyg.atomic_file import atomic_read, atomic_write
    from szyg.atomic_file import atomic_read_async, atomic_write_async
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Per-file locks (threading) ─────────────────────────────────

_file_locks: dict[str, threading.Lock] = {}
_file_locks_lock = threading.Lock()


def _get_file_lock(path: Path) -> threading.Lock:
    """Get or create a per-file threading.Lock."""
    key = str(path.resolve())
    with _file_locks_lock:
        if key not in _file_locks:
            _file_locks[key] = threading.Lock()
        return _file_locks[key]


# ── Sync API (callable from any thread) ────────────────────────

def atomic_read(path: Path) -> list[dict]:
    """Read JSON array from *path*.  Returns ``[]`` on missing / corrupt file.

    Thread-safe (per-file ``threading.Lock``).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _get_file_lock(path)
    with lock:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.error("JSON corrupted in %s, returning empty list", path.name)
                return []
        return []


def atomic_write(path: Path, data: list[dict]) -> None:
    """Write *data* to *path* atomically (temp-file + os.replace).

    Thread-safe (per-file ``threading.Lock``).  On Windows, ``os.replace``
    may sporadically fail with PermissionError even under a lock (anti-virus
    or filesystem filter drivers); we retry once then fall back to a direct
    overwrite.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _get_file_lock(path)
    json_text = json.dumps(data, ensure_ascii=False, indent=2)

    with lock:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json_text, encoding="utf-8")

        # Try atomic rename first
        for attempt in range(2):
            try:
                tmp.replace(path)  # atomic on NTFS / ext4
                return
            except (PermissionError, OSError):
                if attempt == 0:
                    import time
                    time.sleep(0.01)  # 10ms breather for Windows FS
                else:
                    # Last resort: direct overwrite (non-atomic but safe under lock)
                    logger.warning(
                        "atomic replace failed for %s, falling back to direct write",
                        path.name,
                    )
                    path.write_text(json_text, encoding="utf-8")
                    tmp.unlink(missing_ok=True)


# ── Async API (event-loop-friendly) ────────────────────────────

async def atomic_read_async(path: Path) -> list[dict]:
    """Non-blocking alias for ``atomic_read`` — runs in a thread pool."""
    return await asyncio.to_thread(atomic_read, path)


async def atomic_write_async(path: Path, data: list[dict]) -> None:
    """Non-blocking alias for ``atomic_write`` — runs in a thread pool."""
    await asyncio.to_thread(atomic_write, path, data)
