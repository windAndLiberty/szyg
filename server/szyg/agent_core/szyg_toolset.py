"""
szyg_toolset.py — 把 szyg 数字员工的业务能力注册成 Hermes 内核的原生 toolset。

设计目标（浅层封装）：
- 直接复用仓库内置的 Hermes 源码（``server/`` 下的 ``tools.registry``），
  把 szyg 的业务工具以 *进程内* 原生工具的形式注册进同一个 registry。
- 不依赖本机 ``~/.hermes`` 配置，也不启动任何 MCP 子进程，完全自包含。
- 注册后即可通过 ``AIAgent(enabled_toolsets=["szyg"])`` 让 Hermes runtime
  直接调度这些工具，获得 streaming / 并发调度 / 重试 / guardrail 等全部能力。

工具规约（与 ``tools/yuanbao_tools.py`` 一致）：
- handler 签名为 ``handler(args: dict, **kwargs) -> str``，返回 JSON 字符串
  （用 ``tool_result`` / ``tool_error`` 包装）。
- schema 为 OpenAI function 的内层格式 ``{"name", "description", "parameters"}``。
- 通过 ``registry.register(toolset="szyg", ...)`` 注册；由于 "szyg" 不在静态
  ``TOOLSETS`` 中，Hermes 会把它识别为 *plugin toolset*，
  ``validate_toolset("szyg")`` / ``resolve_toolset("szyg")`` 自动可用。

这个模块在被 import 时即完成注册（幂等）。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

# Hermes 内核（仓库内置源码）
from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

TOOLSET = "szyg"

# szyg 仓库根目录（用于定位 data/*.json）
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = _PROJECT_ROOT / "data"


# ---------------------------------------------------------------------------
# 后端单例（懒加载 + 缓存），避免每次工具调用重复构造
# ---------------------------------------------------------------------------

_backends: dict = {}


def _publisher():
    if "pub" not in _backends:
        from szyg.publisher import get_publisher

        _backends["pub"] = get_publisher()
    return _backends["pub"]


def _scheduler():
    if "sched" not in _backends:
        from szyg.scheduler_engine import get_scheduler

        _backends["sched"] = get_scheduler()
    return _backends["sched"]


def _tool_runtime():
    if "tools_rt" not in _backends:
        from szyg.tool_runtime import ToolRuntime

        _backends["tools_rt"] = ToolRuntime()
    return _backends["tools_rt"]


def _knowledge():
    if "kb" not in _backends:
        from szyg.agent_core.knowledge import KnowledgeBase

        _backends["kb"] = KnowledgeBase()
    return _backends["kb"]


def _lead_store():
    if "lead_store" not in _backends:
        from szyg.lead_store import get_lead_store

        _backends["lead_store"] = get_lead_store()
    return _backends["lead_store"]


def _scripts() -> list:
    if "scripts" not in _backends:
        path = _DATA_DIR / "scripts.json"
        try:
            _backends["scripts"] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to load scripts.json: %s", exc)
            _backends["scripts"] = []
    return _backends["scripts"]


# ---------------------------------------------------------------------------
# Tool handlers  (handler(args: dict, **kw) -> JSON str)
# ---------------------------------------------------------------------------

# ── publisher ──

def _h_pub_list(args, **kw):
    pub = _publisher()
    items = pub.list_contents(
        args.get("status", ""), args.get("content_type", ""), "", int(args.get("limit", 50))
    )
    return tool_result([
        {"id": i.id, "title": i.title, "status": i.status.value, "type": i.content_type.value}
        for i in items
    ])


def _h_pub_create(args, **kw):
    from szyg.publisher import Platform

    pub = _publisher()
    platforms = args.get("platforms", "all")
    pl = [Platform(p) for p in platforms.split(",")] if platforms and platforms != "all" else [Platform.ALL]
    c = pub.create(
        title=args.get("title", ""),
        body=args.get("body", ""),
        content_type=args.get("content_type", "post"),
        platforms=pl,
    )
    return tool_result({"id": c.id, "title": c.title, "status": c.status.value})


def _h_pub_submit(args, **kw):
    c = _publisher().submit_review(args.get("content_id", ""))
    return tool_result({"id": c.id, "status": c.status.value}) if c else tool_error("not found")


def _h_pub_approve(args, **kw):
    c = _publisher().approve(args.get("content_id", ""))
    return tool_result({"id": c.id, "status": c.status.value}) if c else tool_error("not found")


def _h_pub_publish(args, **kw):
    r = _publisher().publish_now(args.get("content_id", ""))
    if r:
        return tool_result({"published": 1, "platforms": [r.get("platform")]})
    return tool_result({"published": 0, "platforms": []})


# ── scheduler ──

def _h_sched_list(args, **kw):
    jobs = _scheduler().list_jobs(limit=int(args.get("limit", 50)))
    return tool_result([
        {"id": j.id, "name": j.name, "status": j.status.value,
         "trigger": j.trigger_type.value, "trigger_config": j.trigger_config,
         "action": j.action.value, "next_run_at": j.next_run_at}
        for j in jobs
    ])


def _h_sched_create(args, **kw):
    from szyg.scheduler_engine import TriggerType, JobAction

    cron = args.get("cron", "") or args.get("schedule", "")
    interval = int(args.get("interval_minutes", 0) or 0)
    if cron:
        trigger_type, trigger_config = TriggerType.CRON, {"cron": cron}
    elif interval:
        trigger_type, trigger_config = TriggerType.INTERVAL, {"minutes": interval}
    else:
        trigger_type, trigger_config = TriggerType.MANUAL, {}
    job = _scheduler().create_job(
        name=args.get("name", ""),
        description=args.get("description", ""),
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        action=JobAction.CUSTOM,
    )
    return tool_result({
        "id": job.id, "name": job.name, "status": job.status.value,
        "trigger": job.trigger_type.value, "next_run_at": job.next_run_at,
    })


def _h_sched_execute(args, **kw):
    try:
        ex = _scheduler().execute_job(args.get("job_id", ""))
    except ValueError as exc:
        return tool_error(str(exc))
    return tool_result({
        "id": ex.id, "job_id": ex.job_id, "status": ex.status,
        "result": ex.result, "error": ex.error,
    })


def _h_sched_stats(args, **kw):
    return tool_result(_scheduler().get_stats())


# ── tools marketplace ──

def _get_catalog() -> list[dict]:
    from szyg.data_path import DATA_DIR
    import json
    f = DATA_DIR / "tools.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _h_tools_catalog(args, **kw):
    items = _get_catalog()
    category = args.get("category", "")
    if category:
        items = [i for i in items if i.get("category") == category]
    return tool_result(items[: int(args.get("limit", 50))])


def _h_tools_categories(args, **kw):
    cats = {i.get("category", "other") for i in _get_catalog()}
    return tool_result(sorted(cats))


def _h_tools_stats(args, **kw):
    rt = _tool_runtime()
    return tool_result({"total": len(_get_catalog()), "installed": len(rt.list_installed())})


# ── knowledge ──

def _h_kb_search(args, **kw):
    kb = _knowledge()
    if not kb:
        return tool_result([])
    results = kb.query(args.get("query", ""), top_k=int(args.get("limit", 10)))
    return tool_result(results)


def _h_kb_stats(args, **kw):
    kb = _knowledge()
    if not kb:
        return tool_result({"total": 0})
    try:
        conn = kb.memory._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM memory WHERE json_extract(metadata, '$.type') = 'knowledge'")
        total = cursor.fetchone()[0]
    except Exception:
        try:
            conn = kb.memory._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memory")
            total = cursor.fetchone()[0]
        except Exception:
            total = 0
    return tool_result({"total": total, "sources": len(kb._sources)})


# ── agents ──

def _h_agents_list(args, **kw):
    path = _DATA_DIR / "agents.json"
    try:
        agents = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except Exception:
        agents = []
    tier = args.get("tier", "")
    category = args.get("category", "")
    if tier:
        agents = [a for a in agents if a.get("tier") == tier]
    if category:
        agents = [a for a in agents if a.get("category") == category]
    return tool_result([
        {"id": a["id"], "name": a["name"], "description": a["description"],
         "tier": a["tier"], "category": a["category"]}
        for a in agents
    ])


def _h_agents_tiers(args, **kw):
    return tool_result(["base", "task", "domain"])


# ── leads ──

def _h_lead_search(args, **kw):
    from szyg.models.lead import IntentLevel

    store = _lead_store()
    query = args.get("query", "")
    limit = int(args.get("limit", 20))
    if query:
        rows = store.search(query, limit)
    else:
        intent_level = args.get("intent_level", "")
        il = IntentLevel(intent_level) if intent_level else None
        rows = store.list_leads(intent_level=il, limit=limit)
    return tool_result([
        {"id": l.id, "name": l.name, "platform": l.platform.value,
         "intent_score": l.intent_score, "intent_level": l.intent_level.value,
         "stage": l.conversion_stage.value}
        for l in rows
    ])


def _h_lead_score(args, **kw):
    from szyg.lead_scoring import score_intent
    from szyg.models.lead import IntentScoringRequest, LeadSource

    try:
        ps = LeadSource(args.get("platform", ""))
    except ValueError:
        ps = LeadSource.MANUAL
    r = score_intent(IntentScoringRequest(
        platform=ps, interaction_content=args.get("content", ""), context=args.get("context", "")
    ))
    return tool_result({"score": r.intent_score, "level": r.intent_level.value})


def _h_lead_create(args, **kw):
    from szyg.models.lead import LeadProfile, LeadSource

    try:
        ps = LeadSource(args.get("platform", ""))
    except ValueError:
        ps = LeadSource.MANUAL
    account = args.get("account", "")
    l = _lead_store().create(LeadProfile(
        name=args.get("name", "") or account,
        platform=ps,
        platform_account=account,
        source_content=args.get("content", ""),
    ))
    return tool_result({"id": l.id, "name": l.name})


def _h_lead_update(args, **kw):
    from szyg.models.lead import ConversionStage

    kwargs = {}
    stage = args.get("stage", "")
    if stage:
        try:
            kwargs["conversion_stage"] = ConversionStage(stage)
        except ValueError:
            pass
    if args.get("notes"):
        kwargs["notes"] = args["notes"]
    u = _lead_store().update(args.get("lead_id", ""), **kwargs)
    return tool_result({"id": u.id, "stage": u.conversion_stage.value}) if u else tool_error("not found")


def _h_lead_stats(args, **kw):
    return tool_result(_lead_store().stats())


# ── scripts ──

def _h_script_list(args, **kw):
    s = _scripts()
    industry = args.get("industry", "")
    search = args.get("search", "")
    if industry:
        s = [x for x in s if x["industry"] == industry]
    if search:
        kw_l = search.lower()
        s = [x for x in s if kw_l in x["title"].lower()]
    return tool_result([{"id": x["id"], "title": x["title"], "industry": x["industry"]} for x in s])


def _h_script_generate(args, **kw):
    industry = args.get("industry", "")
    scenario = args.get("scenario", "")
    product_info = args.get("product_info", "")
    scripts = _scripts()
    matches = [x for x in scripts if x["industry"] == industry and scenario.lower() in x["scenario"].lower()]
    if not matches:
        matches = [x for x in scripts if x["industry"] == industry]
    if not matches:
        return tool_error(f"no template for {industry}/{scenario}")
    t = matches[0]
    filled = {}
    for k, v in t["template"].items():
        v = v.replace("[卖点1]", product_info[:50] if product_info else "核心功能")
        v = v.replace("[卖点2]", product_info[50:100] if len(product_info) > 50 else "品质保障")
        filled[k] = v
    return tool_result({"title": t["title"], "persona": t["persona"], "steps": filled, "tips": t.get("tips", [])})


# ── oem ──

def _h_oem_config(args, **kw):
    from szyg.config.loader import load_config

    cfg = load_config()
    return tool_result(cfg.get("oem", {}) if isinstance(cfg, dict) else {})


# ---------------------------------------------------------------------------
# Tool table: (name, description, parameters, handler, emoji)
# ---------------------------------------------------------------------------

_S = "string"
_I = "integer"


def _params(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or []}


_TOOLS = [
    # publisher
    ("pub_list", "列出所有内容项目（可按状态/类型过滤）",
     _params({"status": {"type": _S}, "content_type": {"type": _S}, "limit": {"type": _I}}),
     _h_pub_list, "📝"),
    ("pub_create", "创建新内容草稿",
     _params({"title": {"type": _S}, "body": {"type": _S}, "content_type": {"type": _S}, "platforms": {"type": _S}}, ["title"]),
     _h_pub_create, "📝"),
    ("pub_submit", "提交内容审核",
     _params({"content_id": {"type": _S}}, ["content_id"]), _h_pub_submit, "📤"),
    ("pub_approve", "批准内容发布",
     _params({"content_id": {"type": _S}}, ["content_id"]), _h_pub_approve, "✅"),
    ("pub_publish", "立即发布内容到平台",
     _params({"content_id": {"type": _S}}, ["content_id"]), _h_pub_publish, "🚀"),
    # scheduler
    ("sched_list", "列出所有定时任务",
     _params({"limit": {"type": _I}}), _h_sched_list, "⚡"),
    ("sched_create", "创建定时任务（cron 为表达式如 0 9 * * *；或用 interval_minutes 设置固定间隔；都不填则为手动触发）",
     _params({"name": {"type": _S}, "cron": {"type": _S}, "interval_minutes": {"type": _I}, "description": {"type": _S}}, ["name"]),
     _h_sched_create, "⚡"),
    ("sched_execute", "立即执行定时任务",
     _params({"job_id": {"type": _S}}, ["job_id"]), _h_sched_execute, "▶"),
    ("sched_stats", "定时任务统计",
     _params({}), _h_sched_stats, "📊"),
    # tools marketplace
    ("tools_catalog", "浏览工具市场（可按分类过滤）",
     _params({"category": {"type": _S}, "limit": {"type": _I}}), _h_tools_catalog, "🧰"),
    ("tools_categories", "列出工具分类",
     _params({}), _h_tools_categories, "🧰"),
    ("tools_stats", "工具市场统计",
     _params({}), _h_tools_stats, "📊"),
    # knowledge
    ("kb_search", "知识库全文检索",
     _params({"query": {"type": _S}, "limit": {"type": _I}}, ["query"]), _h_kb_search, "📚"),
    ("kb_stats", "知识库统计",
     _params({}), _h_kb_stats, "📚"),
    # agents
    ("agents_list", "列出可用 AI 智能体",
     _params({"tier": {"type": _S}, "category": {"type": _S}}), _h_agents_list, "🤖"),
    ("agents_tiers", "列出智能体等级",
     _params({}), _h_agents_tiers, "🤖"),
    # leads
    ("lead_search", "搜索/筛选客户线索",
     _params({"query": {"type": _S}, "intent_level": {"type": _S, "enum": ["high", "medium", "low", "cold"]}, "limit": {"type": _I}}),
     _h_lead_search, "🔍"),
    ("lead_score", "AI 评估线索意向分",
     _params({"platform": {"type": _S}, "content": {"type": _S}, "context": {"type": _S}}, ["platform", "content"]),
     _h_lead_score, "🎯"),
    ("lead_create", "创建新线索",
     _params({"platform": {"type": _S}, "account": {"type": _S}, "name": {"type": _S}, "content": {"type": _S}}, ["platform"]),
     _h_lead_create, "➕"),
    ("lead_update", "更新线索阶段/备注",
     _params({"lead_id": {"type": _S}, "stage": {"type": _S, "enum": ["discovered", "engaged", "contacted", "qualified", "won", "lost"]}, "notes": {"type": _S}}, ["lead_id"]),
     _h_lead_update, "✏"),
    ("lead_stats", "线索统计",
     _params({}), _h_lead_stats, "📊"),
    # scripts
    ("script_list", "列出销售话术模板",
     _params({"industry": {"type": _S}, "search": {"type": _S}}), _h_script_list, "💬"),
    ("script_generate", "生成个性化销售话术",
     _params({"industry": {"type": _S}, "scenario": {"type": _S}, "product_info": {"type": _S}}, ["industry", "scenario"]),
     _h_script_generate, "💬"),
    # oem
    ("oem_config", "获取品牌（OEM）配置",
     _params({}), _h_oem_config, "🎨"),
]


def _check_szyg() -> bool:
    """szyg toolset 始终可用（业务后端进程内可用）。"""
    return True


_registered = False


def register_szyg_toolset() -> list[str]:
    """把 szyg 工具注册进 Hermes registry（幂等）。返回已注册工具名列表。"""
    global _registered
    names: list[str] = []
    for name, desc, params, handler, emoji in _TOOLS:
        names.append(name)
        if _registered:
            continue
        registry.register(
            name=name,
            toolset=TOOLSET,
            schema={"name": name, "description": desc, "parameters": params},
            handler=handler,
            check_fn=_check_szyg,
            is_async=False,
            description=desc,
            emoji=emoji,
        )
    if not _registered:
        logger.info("szyg toolset registered: %d tools", len(names))
        _registered = True
    return names


# 在 import 时即完成注册
register_szyg_toolset()
