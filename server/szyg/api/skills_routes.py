"""技能市场 API — 桥接 Hermes Skills Hub 到前端 SettingsSkills.vue

复用 ``tools/skills_hub.py`` (3749行成熟基础设施) 的搜索/安装/卸载全链路。
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

# hermes CLI root → tools/, agent/, etc.
_HERMES_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_HERMES_ROOT) not in sys.path:
    sys.path.insert(0, str(_HERMES_ROOT))

router = APIRouter(prefix="/api/skills", tags=["skills-market"])

# ── Lazy imports (heavy modules only loaded when endpoints are hit) ──

_source_router = None
_hub_lock = None


def _get_source_router():
    global _source_router
    if _source_router is None:
        from tools.skills_hub import create_source_router
        _source_router = create_source_router()
    return _source_router


def _get_lock():
    global _hub_lock
    if _hub_lock is None:
        from tools.skills_hub import HubLockFile
        _hub_lock = HubLockFile()
    return _hub_lock


def _skill_meta_to_dict(sm) -> dict:
    """Convert SkillMeta dataclass to JSON-safe dict."""
    return {
        "name": sm.name,
        "description": sm.description,
        "source": sm.source,
        "identifier": sm.identifier,
        "trust_level": sm.trust_level,
        "repo": sm.repo,
        "path": sm.path,
        "tags": sm.tags,
        "extra": sm.extra,
    }


# ═══════════════════════════════════════════════════════════════
# 技能市场 — 搜索 / 浏览 / 详情
# ═══════════════════════════════════════════════════════════════

@router.get("/market")
async def market_list(q: str = "", page: int = 1, page_size: int = 20,
                      source: str = "all"):
    """搜索外部技能市场，返回真实技能元数据。

    - **q**: 搜索关键词（空 = 浏览全部）
    - **page / page_size**: 分页
    - **source**: 筛选来源 (all / github / hermes-index / skillssh / lobehub …)
    """
    from tools.skills_hub import parallel_search_sources

    sources = _get_source_router()
    results, src_counts, timed_out = parallel_search_sources(
        sources, query=q, source_filter=source, per_source_limits={"skillssh": 15, "lobehub": 15},
        overall_timeout=20,
    )

    # Sort: trusted first, then by name
    TRUST_ORDER = {"builtin": 0, "trusted": 1, "community": 2}
    results.sort(key=lambda m: (TRUST_ORDER.get(m.trust_level, 3), m.name))

    # Paginate
    total = len(results)
    start = (page - 1) * page_size
    page_items = results[start:start + page_size]

    return {
        "items": [_skill_meta_to_dict(sm) for sm in page_items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "source_counts": src_counts,
        "timed_out_sources": timed_out,
    }


@router.get("/market/{identifier:path}")
async def market_detail(identifier: str):
    """获取单个技能的元数据 + SKILL.md 预览。"""
    sources = _get_source_router()
    for src in sources:
        try:
            meta = src.inspect(identifier)
            if meta is not None:
                result = _skill_meta_to_dict(meta)
                # Try to get the bundle for a SKILL.md preview
                try:
                    bundle = src.fetch(identifier)
                    if bundle and "SKILL.md" in bundle.files:
                        skill_md = bundle.files["SKILL.md"]
                        if isinstance(skill_md, bytes):
                            skill_md = skill_md.decode("utf-8", errors="replace")
                        # First 80 lines as preview
                        lines = skill_md.split("\n")[:80]
                        result["skill_md_preview"] = "\n".join(lines)
                        result["skill_md_full_lines"] = len(skill_md.split("\n"))
                except Exception as e:
                    logger.debug("Failed to fetch SKILL.md for %s: %s", identifier, e)
                return result
        except Exception as e:
            logger.debug("Source %s failed for %s: %s", type(src).__name__, identifier, e)
            continue
    raise HTTPException(404, f"技能不存在: {identifier}")


# ═══════════════════════════════════════════════════════════════
# 安装管理
# ═══════════════════════════════════════════════════════════════

@router.post("/install")
async def install_skill(body: dict):
    """安装技能到 ~/.hermes/skills/。

    执行完整安全流程: fetch → quarantine → scan → install。
    """
    identifier = body.get("identifier", "").strip()
    category = body.get("category", "").strip()
    force = body.get("force", False)

    if not identifier:
        raise HTTPException(422, "identifier 必填")

    sources = _get_source_router()
    from tools.skills_hub import quarantine_bundle, install_from_quarantine
    from tools.skills_hub import clear_skills_system_prompt_cache
    from tools.skills_guard import scan_skill, should_allow_install

    # 1. Locate source adapter
    src = None
    meta = None
    for s in sources:
        try:
            meta = s.inspect(identifier)
            if meta is not None:
                src = s
                break
        except Exception:
            continue

    if src is None or meta is None:
        raise HTTPException(404, f"技能不存在或无法访问: {identifier}")

    # 2. Fetch bundle
    bundle = src.fetch(identifier)
    if bundle is None:
        raise HTTPException(500, f"无法下载技能包: {identifier}")

    # 3. Quarantine → Scan → Install
    try:
        quarantine_path = quarantine_bundle(bundle)
        scan_result = scan_skill(quarantine_path, source=meta.source or "community")
        allowed, reason = should_allow_install(scan_result, force=force)
        if not allowed:
            # Clean up quarantine on rejection
            import shutil
            shutil.rmtree(quarantine_path, ignore_errors=True)
            raise HTTPException(403, f"安装被安全策略拒绝: {reason}")

        install_path = install_from_quarantine(
            quarantine_path, bundle.name, category, bundle, scan_result
        )
        clear_skills_system_prompt_cache()

        return {
            "ok": True,
            "skill_name": bundle.name,
            "install_path": str(install_path),
            "trust_level": meta.trust_level,
            "scan_warnings": scan_result.warnings if hasattr(scan_result, 'warnings') else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"安装失败: {str(e)[:300]}")


@router.get("/installed")
async def list_installed():
    """列出已安装的技能 (从 ~/.hermes/skills/.hub/lock.json 读取)。"""
    lock = _get_lock()
    data = lock.load()
    installed = data.get("installed", {})
    items = []
    for name, entry in installed.items():
        items.append({
            "name": name,
            "install_path": entry.get("install_path", ""),
            "source": entry.get("source", ""),
            "identifier": entry.get("identifier", ""),
            "trust_level": entry.get("trust_level", "community"),
            "installed_at": entry.get("installed_at", ""),
            "version": entry.get("version", ""),
        })
    return {"items": items, "total": len(items)}


@router.delete("/installed/{skill_name}")
async def remove_skill(skill_name: str):
    """卸载已安装的技能。"""
    from tools.skills_hub import uninstall_skill

    ok, message = uninstall_skill(skill_name)
    if not ok:
        raise HTTPException(400, message)
    return {"ok": True, "message": message}
