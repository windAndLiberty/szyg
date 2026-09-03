"""技能市场 API — 桥接 Hermes Skills Hub 到前端 SettingsSkills.vue

复用 ``tools/skills_hub.py`` (3749行成熟基础设施) 的搜索/安装/卸载全链路。
"""

import json
import logging
import os
import re
import asyncio
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from szyg.api.auth_routes import require_admin
from szyg.auth import User
from szyg.hermes_process_manager import hermes_process_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills-market"])

# ── Lazy imports (heavy modules only loaded when endpoints are hit) ──

_market_cache: dict[tuple[str, str, str], tuple[float, list[dict]]] = {}
_MARKET_CACHE_TTL_SECONDS = 15 * 60


async def _runtime_native(operation: str, payload: dict | None = None) -> dict:
    try:
        await asyncio.to_thread(hermes_process_manager.ensure_started)
    except RuntimeError as exc:
        raise HTTPException(
            503,
            "智能员工运行组件启动失败，请检查本地开发环境依赖",
        ) from exc
    async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
        response = await client.post(
            hermes_process_manager.base_url + "/v1/native",
            headers=hermes_process_manager.headers,
            json={"operation": operation, "payload": payload or {}},
        )
    if response.status_code >= 400:
        raise HTTPException(503, "智能员工能力暂时不可用")
    return response.json()


_MARKET_CATEGORIES = {
    "recommended": {
        "label": "精选推荐",
        "queries": ["email", "marketing", "research", "spreadsheet", "copywriting"],
    },
    "office": {"label": "办公提效", "queries": ["outlook", "email", "calendar", "meeting", "spreadsheet", "pdf"]},
    "marketing": {"label": "营销获客", "queries": ["marketing", "seo", "crm", "sales", "social-media"]},
    "research": {"label": "市场调研", "queries": ["research", "competitor", "news", "web-search"]},
    "data": {"label": "数据分析", "queries": ["spreadsheet", "excel", "dashboard", "analytics"]},
    "content": {"label": "内容创作", "queries": ["copywriting", "writer", "image", "video", "audio", "design"]},
}

_CATEGORY_EMOJI = {
    "office": "📄",
    "marketing": "🎯",
    "research": "🔍",
    "data": "📊",
    "content": "✍️",
}

# User-facing SZYG product skills. Keep these aggregated: never expose the
# lower-level capability registry or technical tool names in the market UI.
_BUILTIN_SKILL_CATALOG = {
    "content-planning": {
        "name": "内容策划与文案",
        "description": "结合企业资料策划选题、营销文案和多平台内容方案。",
        "category": "content",
        "emoji": "✍️",
    },
    "image-creation": {
        "name": "图片创作",
        "description": "根据业务目标生成海报、配图和营销视觉素材。",
        "category": "content",
        "emoji": "🎨",
    },
    "video-creation": {
        "name": "视频创作",
        "description": "完成视频选题、脚本、画面规划和视频生成任务。",
        "category": "content",
        "emoji": "🎬",
    },
    "public-lead-discovery": {
        "name": "公域客户发现",
        "description": "从公开内容和平台信号中发现高相关潜在客户机会。",
        "category": "marketing",
        "emoji": "🎯",
    },
    "customer-conversion": {
        "name": "客户转化跟进",
        "description": "判断客户意向，准备个性化沟通内容和下一步行动。",
        "category": "marketing",
        "emoji": "🤝",
    },
    "content-publishing": {
        "name": "内容发布协作",
        "description": "整理发布素材、检查内容并协助完成多平台发布。",
        "category": "marketing",
        "emoji": "📣",
    },
    "knowledge-assistant": {
        "name": "企业知识助手",
        "description": "检索企业知识库，从内部资料中提取可靠信息和来源。",
        "category": "office",
        "emoji": "📚",
    },
    "document-analysis": {
        "name": "文档与附件分析",
        "description": "阅读文档、表格、图片和音视频资料并整理重点。",
        "category": "office",
        "emoji": "📄",
    },
    "workflow-automation": {
        "name": "工作流自动化",
        "description": "把重复经营任务整理为可复用、可跟踪的自动化流程。",
        "category": "office",
        "emoji": "⚙️",
    },
    "browser-assistant": {
        "name": "网页代办",
        "description": "在可见浏览器中查找信息、填写内容并协助完成网页任务。",
        "category": "office",
        "emoji": "🌐",
    },
    "market-research": {
        "name": "市场调研",
        "description": "综合公开资料研究市场、人群、竞争格局和真实需求。",
        "category": "research",
        "emoji": "🔍",
    },
    "competitive-intelligence": {
        "name": "竞品与市场情报",
        "description": "跟踪竞品内容与市场变化，形成有依据的行动建议。",
        "category": "research",
        "emoji": "🧭",
    },
    "operations-insights": {
        "name": "运营数据洞察",
        "description": "汇总内容、获客和转化表现，识别问题与增长机会。",
        "category": "data",
        "emoji": "📊",
    },
    "materials-management": {
        "name": "经营素材整理",
        "description": "整理企业图片、视频和内容素材，便于后续创作与发布。",
        "category": "content",
        "emoji": "🗂️",
    },
}

# Commercial catalog: only capabilities verified to work with SZYG's existing
# runtime, without asking a business user to install tools or provide API keys.
# Metadata and packages are still pulled from ClawHub at request/install time.
_INSTALL_READY_CATALOG = {
    "jmin-meeting-notes": {
        "name": "会议纪要整理",
        "description": "把会议记录整理成要点、决策、负责人和后续待办。",
        "category": "office",
        "downloads": 633,
    },
    "project-planning": {
        "name": "项目计划",
        "description": "拆解目标、任务依赖、里程碑和风险，形成清晰可执行的项目计划。",
        "category": "office",
        "downloads": 1429,
    },
    "sop-generator": {
        "name": "SOP 流程整理",
        "description": "把口述、笔记或转写内容整理成团队可以直接执行的标准流程。",
        "category": "office",
        "downloads": 767,
    },
    "weekly-report-writer": {
        "name": "周报整理",
        "description": "将零散工作记录整理成突出结果、风险和下一步计划的周报。",
        "category": "office",
        "downloads": 1720,
    },
    "proposal-writer": {
        "name": "商务提案",
        "description": "生成服务方案、项目报价和合作提案，清楚表达价值与执行计划。",
        "category": "office",
        "downloads": 3147,
    },
    "bing-search-cn": {
        "name": "联网搜索",
        "description": "通过必应查找最新公开信息、读取网页内容，并整理为清晰结论。",
        "category": "research",
        "downloads": 1281,
    },
    "in-depth-research": {
        "name": "深度调研",
        "description": "围绕一个问题进行多轮查找、核验来源并形成完整调研报告。",
        "category": "research",
        "downloads": 14000,
    },
    "multi-source-research": {
        "name": "多源信息调研",
        "description": "综合网页、新闻和公开平台信息，去重后按可信度整理。",
        "category": "research",
        "downloads": 2500,
    },
    "copywriting-pro": {
        "name": "专业文案创作",
        "description": "撰写广告、商品介绍、社交平台内容和销售文案。",
        "category": "content",
        "downloads": 5300,
    },
    "marketing-analytics": {
        "name": "营销效果分析",
        "description": "分析推广数据，找出有效渠道并给出下一步优化建议。",
        "category": "marketing",
        "downloads": 3800,
    },
    "spreadsheet": {
        "name": "表格处理",
        "description": "读取、整理和分析 Excel、CSV 等表格数据并生成报告。",
        "category": "data",
        "downloads": 5300,
    },
    "customer-persona-copy-map": {
        "name": "客户画像",
        "description": "梳理客户痛点、购买动机、常见异议和更合适的沟通表达。",
        "category": "marketing",
        "downloads": 483,
    },
    "ecommerce-aftersales-reply": {
        "name": "电商售后回复",
        "description": "为退换货、物流异常和补偿协商生成清晰、稳妥的中文回复。",
        "category": "marketing",
        "downloads": 613,
    },
    "social-media-content-calendar": {
        "name": "社媒内容日历",
        "description": "规划不同平台的选题、内容形式、标签和发布时间。",
        "category": "marketing",
        "downloads": 3218,
    },
    "product-description-writer": {
        "name": "商品描述",
        "description": "根据商品信息生成标题、核心卖点、详情页和平台适配文案。",
        "category": "content",
        "downloads": 1074,
    },
    "qf-content-repurpose": {
        "name": "内容多平台改写",
        "description": "把一份内容改写成适合小红书、抖音、公众号等平台的版本。",
        "category": "content",
        "downloads": 520,
    },
    "competitor-analysis-report": {
        "name": "竞品分析报告",
        "description": "对比竞品的功能、价格、定位和营销方式，形成行动建议。",
        "category": "research",
        "downloads": 2407,
    },
    "market-research": {
        "name": "市场调研",
        "description": "研究市场规模、细分人群、竞争格局、定价和真实需求。",
        "category": "research",
        "downloads": 23434,
    },
    "data-visualization-2": {
        "name": "数据可视化建议",
        "description": "根据业务数据选择合适图表，并优化颜色、标注和信息表达。",
        "category": "data",
        "downloads": 5263,
    },
}

_SECRET_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET)\b")
_EXTRA_SETUP_PATTERN = re.compile(
    r"\b(?:pip3?|npm|pnpm|yarn|uv\s+pip|apt(?:-get)?|brew)\s+install\b",
    re.IGNORECASE,
)

_MARKET_QUERY_ALIASES = {
    "办公": "office productivity",
    "邮件": "email",
    "日程": "calendar",
    "会议": "meeting notes",
    "文档": "document",
    "表格": "spreadsheet",
    "营销": "marketing",
    "获客": "sales leads",
    "客户": "customer management",
    "调研": "business research",
    "竞品": "competitor research",
    "数据": "data analysis",
    "报表": "business report",
    "写作": "content writing",
    "图片": "image",
    "视频": "video",
}

_MARKET_BLOCKED_TERMS = {
    "crypto", "wallet", "trading", "blockchain", "mining", "exploit", "pentest",
    "malware", "credential", "ssh", "terminal", "shell", "devops", "kubernetes",
    "humanoid", "surveillance", "object detection", "robotics",
    "crop", "agriculture", "plant disease", "orchid", "rooting status", "livestock",
}

_MARKET_CATEGORY_TERMS = {
    "office": {
        "office", "outlook", "email", "mail", "calendar", "meeting", "document",
        "pdf", "word", "spreadsheet", "excel", "presentation", "slides", "productivity",
        "m365", "microsoft 365", "mailbox",
        "办公", "邮件", "日程", "会议", "文档", "表格",
    },
    "marketing": {
        "marketing", "campaign", "social media", "seo", "sales", "customer", "lead",
        "crm", "brand", "营销", "获客", "客户", "销售", "品牌",
    },
    "research": {
        "research", "search", "competitor", "market", "news", "insight", "survey",
        "调研", "搜索", "竞品", "市场", "情报",
    },
    "data": {
        "data analytics", "business analysis", "business report", "spreadsheet", "excel",
        "dashboard", "statistics", "数据分析", "业务报表", "表格", "统计",
    },
    "content": {
        "copywriting", "writer", "article", "image", "video", "audio", "design",
        "social media", "文案", "文章", "图片", "视频", "音频", "设计",
    },
}


def _normalize_market_query(query: str) -> str:
    normalized = query.strip()
    if not normalized:
        return normalized
    for chinese, english in _MARKET_QUERY_ALIASES.items():
        normalized = normalized.replace(chinese, f" {english} ")
    return " ".join(normalized.split())


def _friendly_market_description(item: dict, category: str) -> str:
    raw = str(item.get("summary") or item.get("description") or "").strip()
    combined = " ".join([
        str(item.get("slug") or ""),
        str(item.get("displayName") or ""),
        raw,
        " ".join(str(value) for value in (item.get("topics") or [])),
    ]).lower()

    chinese_chars = re.findall(r"[\u4e00-\u9fff]", raw)
    if raw and len(chinese_chars) / max(len(raw), 1) >= 0.2:
        chinese_part = raw.split("|")[-1].strip() if "|" in raw else raw
        return chinese_part[:120]

    if category == "research":
        return "帮助查找公开资料、筛选有用信息并整理调研结论。"
    if category == "marketing":
        return "帮助策划营销内容、整理渠道信息并复盘推广效果。"
    if category == "data":
        return "帮助汇总业务数据、发现变化并形成清晰报告。"
    if category == "content":
        if any(word in combined for word in ("image", "design", "video", "audio")):
            return "帮助处理内容素材，让创作和整理工作更省时。"
        return "帮助起草、改写和整理日常经营所需的文字内容。"

    if any(word in combined for word in ("outlook", "email", "mail")):
        return "帮助整理邮件、草拟回复，并把重要事项归纳得更清楚。"
    if any(word in combined for word in ("calendar", "meeting", "schedule")):
        return "帮助安排日程、整理会议内容和后续待办。"
    if any(word in combined for word in ("spreadsheet", "excel", "csv", "table")):
        return "帮助处理表格、汇总数据并形成容易阅读的结果。"
    if any(word in combined for word in ("document", "pdf", "word", "presentation", "slides")):
        return "帮助阅读和整理文档，提取重点并生成可继续使用的内容。"
    if any(word in combined for word in ("marketing", "seo", "social media", "campaign")):
        return "帮助策划营销内容、整理渠道信息并复盘推广效果。"
    if any(word in combined for word in ("sales", "crm", "customer", "lead")):
        return "帮助整理客户线索、判断跟进重点并准备沟通内容。"
    if any(word in combined for word in ("research", "search", "competitor", "news")):
        return "帮助查找公开资料、筛选有用信息并整理调研结论。"
    if any(word in combined for word in ("analytics", "analysis", "report", "dashboard")):
        return "帮助汇总业务数据、发现变化并形成分析报告。"
    if any(word in combined for word in ("image", "design", "video", "audio")):
        return "帮助处理内容素材，让创作和整理工作更省时。"
    if any(word in combined for word in ("writing", "content", "copy")):
        return "帮助起草、改写和整理日常经营所需的文字内容。"

    fallbacks = {
        "office": "帮助完成常见办公事务，减少重复操作。",
        "marketing": "帮助处理营销和客户经营中的日常工作。",
        "research": "帮助查找、筛选并整理有价值的公开信息。",
        "data": "帮助整理业务数据并形成清晰结论。",
        "content": "帮助更高效地完成内容创作和素材整理。",
    }
    return fallbacks.get(category, "为超级员工增加一项可复用的工作能力。")


def _friendly_market_name(item: dict, slug: str) -> str:
    raw = str(item.get("displayName") or item.get("name") or slug.replace("-", " ").title()).strip()
    combined = f"{slug} {raw}".lower()
    if "outlook" in combined:
        return "Outlook 助手"
    if "m365" in combined or "microsoft 365" in combined:
        return "Microsoft 365 助手"
    if "mailbox" in combined or re.search(r"\bemail\b|\bmail\b", combined):
        return "邮件助手"
    cleaned = re.sub(r"\bMCP\b", "助手", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _clawhub_item(item: dict, category: str) -> Optional[dict]:
    slug = str(item.get("slug") or "").strip()
    if not slug:
        return None
    combined = " ".join([
        slug,
        str(item.get("displayName") or ""),
        str(item.get("summary") or ""),
        " ".join(str(value) for value in (item.get("topics") or [])),
    ]).lower()
    if any(term in combined for term in _MARKET_BLOCKED_TERMS):
        return None
    stats = item.get("stats") if isinstance(item.get("stats"), dict) else {}
    setup = (item.get("metadata") or {}).get("setup") if isinstance(item.get("metadata"), dict) else []
    return {
        "name": _friendly_market_name(item, slug),
        "description": _friendly_market_description(item, category),
        "identifier": slug,
        "category": category,
        "category_label": _MARKET_CATEGORIES.get(category, {}).get("label", "实用能力"),
        "downloads": int(stats.get("downloads") or item.get("downloads") or 0),
        "installs": int(stats.get("installs") or 0),
        "stars": int(stats.get("stars") or 0),
        "requires_connection": bool(setup),
        "updated_at": item.get("updatedAt"),
    }


def _market_item_matches(item: dict, category: str, search_query: str = "") -> bool:
    identity = " ".join([
        str(item.get("slug") or ""),
        str(item.get("displayName") or ""),
        " ".join(str(value) for value in (item.get("topics") or [])),
    ]).lower()
    combined = " ".join([
        identity,
        str(item.get("summary") or ""),
        str(item.get("description") or ""),
    ]).lower()
    if search_query.strip():
        terms = [term for term in re.split(r"[^a-z0-9\u4e00-\u9fff]+", search_query.lower()) if len(term) >= 2]
        return not terms or any(term in combined for term in terms)
    if category == "recommended":
        return any(
            term in identity
            for terms in _MARKET_CATEGORY_TERMS.values()
            for term in terms
        )
    return any(term in identity for term in _MARKET_CATEGORY_TERMS.get(category, set()))


async def _search_clawhub(query: str, limit: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=18, follow_redirects=True) as client:
        response = await client.get(
            "https://clawhub.ai/api/v1/search",
            params={"q": query, "limit": limit},
        )
        response.raise_for_status()
        payload = response.json()
    items = payload.get("results", payload) if isinstance(payload, dict) else payload
    return items if isinstance(items, list) else []


async def _get_clawhub_skill(identifier: str) -> Optional[dict]:
    async with httpx.AsyncClient(timeout=18, follow_redirects=True) as client:
        response = await client.get(f"https://clawhub.ai/api/v1/skills/{identifier}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        return None
    skill = payload.get("skill")
    if not isinstance(skill, dict):
        return None
    item = dict(skill)
    item["latestVersion"] = payload.get("latestVersion")
    item["metadata"] = payload.get("metadata") or {}
    return item


def _install_ready_item(identifier: str, raw: Optional[dict] = None) -> dict:
    raw = raw or {}
    config = _INSTALL_READY_CATALOG[identifier]
    stats = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}
    category = config["category"]
    return {
        "name": config["name"],
        "description": config["description"],
        "identifier": identifier,
        "category": category,
        "category_label": _MARKET_CATEGORIES[category]["label"],
        "downloads": int(stats.get("downloads") or config.get("downloads") or 0),
        "installs": int(stats.get("installs") or 0),
        "stars": int(stats.get("stars") or 0),
        "ready_to_use": True,
        "availability_label": "添加后即可使用",
        "source": "external",
        "builtin": False,
        "emoji": _CATEGORY_EMOJI.get(category, "🧩"),
        "updated_at": raw.get("updatedAt"),
    }


def _builtin_market_item(identifier: str, config: dict) -> dict:
    category = config["category"]
    return {
        "name": config["name"],
        "description": config["description"],
        "identifier": f"szyg:{identifier}",
        "category": category,
        "category_label": _MARKET_CATEGORIES[category]["label"],
        "downloads": 0,
        "installs": 0,
        "stars": 0,
        "ready_to_use": True,
        "availability_label": "系统内置",
        "source": "builtin",
        "builtin": True,
        "emoji": config.get("emoji") or _CATEGORY_EMOJI.get(category, "✨"),
    }


def _validate_install_ready_bundle(identifier: str, bundle) -> tuple[bool, str]:
    """Reject packages that need secrets/setup or reference missing scripts."""
    if identifier not in _INSTALL_READY_CATALOG:
        return False, "这项能力尚未通过可用性验证"
    skill_md = bundle.files.get("SKILL.md")
    if isinstance(skill_md, bytes):
        skill_md = skill_md.decode("utf-8", errors="replace")
    if not isinstance(skill_md, str) or not skill_md.strip():
        return False, "能力包缺少使用说明"
    if _SECRET_PATTERN.search(skill_md):
        return False, "这项能力需要额外密钥，暂不提供安装"
    if _EXTRA_SETUP_PATTERN.search(skill_md):
        return False, "这项能力需要额外安装程序，暂不提供安装"

    referenced_files = set(
        re.findall(r"(?:python3?|node|bash|sh)\s+(?:\./)?([\w./-]+\.(?:py|js|mjs|sh))", skill_md)
    )
    available_files = {str(path).replace("\\", "/").lstrip("./") for path in bundle.files}
    missing = [path for path in referenced_files if path.replace("\\", "/").lstrip("./") not in available_files]
    if missing:
        return False, "能力包文件不完整，暂不提供安装"
    return True, "添加后即可使用"


class NativeSkillManageRequest(BaseModel):
    action: str
    name: str
    content: Optional[str] = None
    category: Optional[str] = None
    file_path: Optional[str] = None
    file_content: Optional[str] = None
    old_string: Optional[str] = None
    new_string: Optional[str] = None
    replace_all: bool = False
    absorbed_into: Optional[str] = None


class CuratorPauseRequest(BaseModel):
    paused: bool


# ═══════════════════════════════════════════════════════════════
# Hermes native runtime — active skills, procedural memory, curator
# ═══════════════════════════════════════════════════════════════

@router.get("/runtime")
async def hermes_runtime_status():
    return await _runtime_native("status")


@router.get("/native")
async def list_native_skills():
    return await _runtime_native("skills_list")


@router.get("/native/{skill_name}")
async def native_skill_detail(skill_name: str):
    result = await _runtime_native("skill_view", {"name": skill_name})
    if not result.get("success"):
        raise HTTPException(404, result.get("error") or f"技能不存在: {skill_name}")
    return result


@router.post("/native/manage")
async def manage_native_skill(
    body: NativeSkillManageRequest,
    admin: User = Depends(require_admin),
):
    result = await _runtime_native("skill_manage", body.model_dump())
    if not result.get("success"):
        raise HTTPException(400, result.get("error") or "技能操作失败")
    return result


@router.post("/curator/run")
async def run_native_curator(admin: User = Depends(require_admin)):
    return await _runtime_native("curator_run")


@router.put("/curator/paused")
async def pause_native_curator(
    body: CuratorPauseRequest,
    admin: User = Depends(require_admin),
):
    return await _runtime_native("curator_pause", {"paused": body.paused})


# ═══════════════════════════════════════════════════════════════
# 技能市场 — 搜索 / 浏览 / 详情
# ═══════════════════════════════════════════════════════════════

@router.get("/market")
async def market_list(
    q: str = "",
    category: str = "recommended",
    source: str = "all",
    page: int = 1,
    page_size: int = 20,
):
    """返回 SZYG 内置技能与经过可用性验证的外部技能目录。"""
    if category not in _MARKET_CATEGORIES:
        category = "recommended"
    if source not in {"all", "builtin", "external"}:
        source = "all"
    page = max(1, page)
    page_size = min(40, max(1, page_size))

    cache_key = (source, category, q.strip().lower())
    cached = _market_cache.get(cache_key)
    if cached and time.time() - cached[0] < _MARKET_CACHE_TTL_SECONDS:
        results = cached[1]
        total = len(results)
        start = (page - 1) * page_size
        return {
            "items": results[start:start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
            "category": category,
            "categories": [
                {"id": category_id, "label": config["label"]}
                for category_id, config in _MARKET_CATEGORIES.items()
            ],
        }

    normalized_query = q.strip().lower()
    results = []
    catalogs = []
    if source in {"all", "builtin"}:
        catalogs.extend(
            _builtin_market_item(identifier, config)
            for identifier, config in _BUILTIN_SKILL_CATALOG.items()
        )
    if source in {"all", "external"}:
        catalogs.extend(_install_ready_item(identifier) for identifier in _INSTALL_READY_CATALOG)

    for item in catalogs:
        if category != "recommended" and item["category"] != category:
            continue
        searchable = " ".join((item["name"], item["description"], item["identifier"])).lower()
        if normalized_query and normalized_query not in searchable:
            translated_query = _normalize_market_query(normalized_query)
            if not any(term in searchable for term in translated_query.split()):
                continue
        results.append(item)

    results.sort(
        key=lambda item: (
            0 if item.get("builtin") else 1,
            -(item["downloads"] + item["installs"] * 5 + item["stars"] * 25),
            item["name"].lower(),
        )
    )
    _market_cache[cache_key] = (time.time(), results)
    total = len(results)
    start = (page - 1) * page_size
    return {
        "items": results[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "category": category,
        "categories": [
            {"id": category_id, "label": config["label"]}
            for category_id, config in _MARKET_CATEGORIES.items()
        ],
    }


@router.get("/market/{identifier:path}")
async def market_detail(identifier: str):
    """获取单个技能的元数据 + SKILL.md 预览。"""
    result = await _runtime_native("market_detail", {"identifier": identifier})
    if result.get("ok") is False:
        raise HTTPException(404, result.get("error") or f"技能不存在: {identifier}")
    return result


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
    if identifier.startswith("szyg:"):
        raise HTTPException(400, "这是系统内置技能，无需添加")

    result = await _runtime_native("market_install", {
        "identifier": identifier,
        "category": category,
        "force": force,
    })
    if not result.get("ok"):
        raise HTTPException(422, result.get("error") or "安装失败")
    return result


@router.get("/installed")
async def list_installed():
    """只列出用户从外部能力市场添加的技能，不暴露 SZYG 内部技能。"""
    data = await _runtime_native("installed_list")
    installed = data.get("installed", {})
    items = []
    for name, entry in installed.items():
        identifier = entry.get("identifier", "")
        catalog_item = _INSTALL_READY_CATALOG.get(identifier, {})
        items.append({
            "name": catalog_item.get("name") or name,
            "skill_name": name,
            "identifier": identifier,
            "installed_at": entry.get("installed_at", ""),
            "version": entry.get("version", ""),
            "description": catalog_item.get("description") or "已添加到超级员工，可在合适的工作中自动使用。",
        })
    return {"items": items, "total": len(items)}


@router.delete("/installed/{skill_name}")
async def remove_skill(skill_name: str):
    """卸载已安装的技能。"""
    result = await _runtime_native("skill_uninstall", {"name": skill_name})
    if not result.get("ok"):
        raise HTTPException(400, result.get("message") or "移除失败")
    return result
