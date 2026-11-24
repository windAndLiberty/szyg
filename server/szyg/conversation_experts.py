"""Local, per-desktop-conversation expert preferences and intent matching."""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from contextlib import closing
from threading import Lock

from szyg.data_path import DATA_DIR

DATABASE = DATA_DIR / "conversation-experts.sqlite3"
_SESSION = re.compile(r"agent:([a-z0-9_-]+):dashboard:(incognito-)?[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", re.I)
_private_sessions: dict[str, dict] = {}
_private_lock = Lock()
MAX_MANUAL = 3

# Explicit domain vocabulary avoids paying for a classifier or matching generic chat.
_CUES = {
    "marketing-xiaohongshu-specialist": ("小红书", "xiaohongshu", "rednote"),
    "marketing-douyin-strategist": ("抖音", "douyin"),
    "marketing-kuaishou-strategist": ("快手", "kuaishou"),
    "marketing-wechat-official-account": ("微信公众号", "公众号推文", "公众号选题", "公众号文章", "wechat official account"),
    "marketing-short-video-editing-coach": ("短视频剪辑", "抖音剪辑", "短视频脚本", "短视频拍摄", "视频分镜", "剪辑脚本", "视频号", "video editing"),
    "marketing-bilibili-content-strategist": ("哔哩哔哩", "bilibili", "b站"),
    "marketing-livestream-commerce-coach": ("直播带货", "直播间转化", "直播话术", "livestream shopping"),
    "marketing-multi-platform-publisher": ("多平台发布", "跨平台发布", "multi-platform publishing"),
    "marketing-email-strategist": ("邮件营销", "营销邮件", "email campaign", "email marketing"),
    "marketing-seo-specialist": ("搜索引擎优化", "自然搜索流量", "seo"),
    "marketing-baidu-seo-specialist": ("百度seo", "百度收录", "百度排名"),
    "marketing-china-ecommerce-operator": ("电商运营", "店铺运营", "电商转化"),
    "marketing-content-creator": ("内容创作", "文案策划", "宣传文案", "营销文案", "内容策划", "营销内容"),
    "marketing-social-media-strategist": ("营销方案", "营销策划", "新媒体运营", "社媒运营", "社交媒体", "social media strategy"),
    "marketing-pr-communications-manager": ("公关声明", "新闻稿", "公关危机", "press release"),
    "design-image-prompt-engineer": ("绘图提示词", "图片提示词", "生图提示词", "image prompt"),
    "support-analytics-reporter": ("经营分析", "营收数据", "数据报表", "经营报表", "business metrics"),
    "support-support-responder": ("客服工单", "工单回复", "工单分流", "support ticket"),
    "legal-document-review": ("合同审查", "审查合同", "合同审核", "审查条款", "contract review"),
    "paid-media-ppc-strategist": ("竞价广告", "搜索广告", "付费搜索", "pay per click", "ppc"),
    "paid-media-auditor": ("广告账户审计", "广告投放审计", "广告账户诊断", "ad account audit"),
    "design-ui-designer": ("界面设计", "ui设计", "ui 设计", "ui design", "界面排版"),
    "design-ux-researcher": ("用户访谈", "可用性测试", "用户研究", "ux research"),
    "design-brand-guardian": ("品牌视觉", "品牌识别", "品牌规范", "品牌设计", "brand identity"),
    "finance-financial-analyst": ("财务分析", "毛利率", "财报", "财务报表", "盈亏平衡", "现金流", "成本效益", "financial analysis", "cash flow"),
    "finance-bookkeeper-controller": ("会计分录", "银行对账", "账务核对", "bank reconciliation"),
    "finance-fpa-analyst": ("预算编制", "预算差异", "滚动预测", "budget variance"),
    "sales-pipeline-analyst": ("销售漏斗", "销售管道", "销售转化率", "sales pipeline"),
    "sales-proposal-strategist": ("销售提案", "客户提案", "投标方案", "sales proposal"),
    "project-management-meeting-notes-specialist": ("会议纪要", "会议记录", "meeting minutes"),
    "project-management-experiment-tracker": ("a/b测试", "a/b 测试", "ab测试", "a/b test", "实验样本量"),
    "product-feedback-synthesizer": ("用户反馈", "反馈归类", "客户反馈", "customer feedback"),
    "product-manager": ("产品需求", "产品路线图", "需求文档", "product roadmap"),
    "gis-analyst": ("地理信息", "空间分析", "地理空间", "gis", "geospatial"),
    "recruitment-specialist": ("招聘", "候选人筛选", "面试评分", "recruitment"),
    "customer-service": ("客服话术", "客户投诉", "客服回复", "customer complaint"),
    "supply-chain-strategist": ("供应链", "库存周转", "补货策略", "supply chain"),
}
_SPECIALIZED = {
    "accounts-payable-agent", "business-strategist", "change-management-consultant",
    "chief-financial-officer", "corporate-training-designer", "customer-service",
    "customer-success-manager", "data-consolidation-agent", "data-privacy-officer",
    "esg-sustainability-officer", "grant-writer", "hospitality-guest-services",
    "hr-onboarding", "language-translator", "legal-document-review", "operations-manager", "recruitment-specialist",
    "retail-customer-returns", "specialized-document-generator", "supply-chain-strategist",
}
_EXCLUDED = {"support-infrastructure-maintainer", "marketing-carousel-growth-engine"}
_FOLLOW_UP = re.compile(
    r"继续|接着|上述|上一|上面|刚才|这个|这段|这条|它们|把它|补充|细化|缩短|展开|改写|润色|重写|"
    r"再.{0,5}(?:写|说|想|给|来|做|改)|(?:第[一二三四五六七八九十0-9]+)(?:段|个|条|步)|"
    r"(?:改成|整理成|换成|换个|详细一点|简短一点)|"
    r"\b(?:continue|go on|revise|rewrite|shorten|elaborate|expand on|summarize (?:it|that))\b", re.I,
)


def available(agent: dict) -> bool:
    return agent["slug"] not in _EXCLUDED and (agent["division"] != "specialized" or agent["slug"] in _SPECIALIZED)


def _match(message: str, catalog: dict, excluded: list[str]) -> str | None:
    text = unicodedata.normalize("NFKC", message).casefold()
    scores = {}
    for slug, agent in catalog.items():
        if slug in excluded:
            continue
        phrases = (*_CUES.get(slug, ()), agent["name"], agent["name_en"])
        hits = []
        for phrase in phrases:
            term = phrase.strip().casefold()
            if len(term) < 2:
                continue
            pattern = re.escape(term)
            if term.isascii():
                pattern = rf"(?<![a-z0-9]){pattern}(?![a-z0-9])"
            match = re.search(pattern, text)
            if match and not re.search(r"(?:不要|不用|不做|不想做|别用|不用做|不考虑|排除|without|excluding)\s*$", text[:match.start()]):
                hits.append(len(term))
        if hits:
            scores[slug] = max(hits)
    platforms = {"marketing-xiaohongshu-specialist", "marketing-douyin-strategist", "marketing-kuaishou-strategist",
                 "marketing-wechat-official-account", "marketing-bilibili-content-strategist"}
    publisher = "marketing-multi-platform-publisher"
    if len(scores.keys() & platforms) > 1 and publisher in catalog and publisher not in excluded:
        return publisher
    if not scores:
        return None
    best = max(scores.values())
    top = [slug for slug, score in scores.items() if score == best]
    return top[0] if len(top) == 1 else None


def selection(agent_id: str, key: str, catalog: dict, *, action: str = "get", value: str = "") -> dict:
    match = _SESSION.fullmatch(key)
    if not match or match[1] != agent_id:
        raise ValueError("该对话不属于当前员工")
    if action in {"attach", "detach"} and value not in catalog:
        raise KeyError(value)

    def update(state):
        manual = state.setdefault("manual", [])
        excluded = state.setdefault("excluded", [])
        if action == "resolve" and not manual:
            candidate = _match(value[:8192], catalog, excluded)
            if candidate:
                state["auto"] = candidate
            elif state.get("auto") and not _FOLLOW_UP.search(value):
                state.pop("auto")
        if action == "attach":
            if value not in manual:
                if len(manual) >= MAX_MANUAL:
                    raise ValueError("每个对话最多可同时加载三位专家")
                manual.append(value)
            if value in excluded:
                excluded.remove(value)
            state.pop("auto", None)
        if action == "detach":
            if value in manual:
                manual.remove(value)
            if state.get("auto") == value:
                state.pop("auto", None)
            if value not in excluded:
                excluded.append(value)
        if manual or state.get("auto"):
            state["previously_active"] = True
        return state

    if match[2]:
        with _private_lock:
            state = update(_private_sessions.setdefault(key, {}))
            return {**state, "manual": list(state["manual"]), "excluded": list(state["excluded"])}
    with closing(sqlite3.connect(DATABASE)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS expert_selection (session_key TEXT PRIMARY KEY, preferences TEXT NOT NULL)")
        if action != "get":
            db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT preferences FROM expert_selection WHERE session_key=?", (key,)).fetchone()
        old = row[0] if row else None
        state = update(json.loads(old) if old else {})
        if action != "get" and (state.get("previously_active") or state["excluded"]):
            new = json.dumps(state, ensure_ascii=False)
            if new != old:
                db.execute("INSERT OR REPLACE INTO expert_selection VALUES (?,?)", (key, new))
        return state
