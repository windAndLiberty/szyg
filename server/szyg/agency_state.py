"""Agency 专家激活状态管理 — 独立模块避免循环依赖.

被 agency_routes.py（设置/清除激活）与 hermes_chat.py（读取激活构建Prompt）共用。
激活状态持久化到 data/agency_active.json，重启后自动恢复。
"""
import json
import logging
import threading
from pathlib import Path
from typing import Optional

from szyg.data_path import DATA_DIR

logger = logging.getLogger(__name__)

_ACTIVE_FILE = DATA_DIR / "agency_active.json"
_lock = threading.Lock()
_active_expert: dict | None = None  # {slug, name, description, emoji, division, prompt}


def _load_persisted() -> dict | None:
    """从磁盘加载持久化的激活专家。"""
    if not _ACTIVE_FILE.exists():
        return None
    try:
        data = json.loads(_ACTIVE_FILE.read_text(encoding="utf-8"))
        # 校验对应 .md 仍存在
        agency_root = _agency_root()
        md_path = agency_root / data.get("division", "") / f"{data.get('slug')}.md"
        if not md_path.exists():
            logger.info("Persisted agency expert %s no longer exists, clearing", data.get("slug"))
            return None
        return data
    except Exception as e:
        logger.warning("Failed to load persisted agency active state: %s", e)
        return None


def _persist(data: dict | None) -> None:
    """持久化激活状态到磁盘。"""
    try:
        _ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if data is None:
            if _ACTIVE_FILE.exists():
                _ACTIVE_FILE.unlink()
        else:
            _ACTIVE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to persist agency active state: %s", e)


def _agency_root() -> Path:
    """Agency 专家数据根目录。"""
    # D:\szyg\external\agency-agents-main
    return Path(__file__).parent.parent.parent.parent / "external" / "agency-agents-main"


def get_active_expert() -> Optional[dict]:
    """获取当前激活的 Agency 专家（含完整 prompt），未激活返回 None。"""
    global _active_expert
    with _lock:
        if _active_expert is None:
            _active_expert = _load_persisted()
        return _active_expert


def set_active_expert(expert: dict) -> None:
    """设置激活专家。expert 需含 slug/name/description/emoji/division/prompt。"""
    global _active_expert
    with _lock:
        _active_expert = expert
        _persist(expert)
        logger.info("Agency expert activated: %s (%s)", expert.get("name"), expert.get("slug"))


def clear_active_expert() -> None:
    """清除激活专家，恢复默认 Hermes Prompt。"""
    global _active_expert
    with _lock:
        _active_expert = None
        _persist(None)
        logger.info("Agency expert deactivated, back to default Hermes prompt")
