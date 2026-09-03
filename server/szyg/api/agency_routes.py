"""Agency Agents 市场 API — 集成 Agency 232 专家，保留 155 个领域专家.

数据源: SZYG 内置的 agency-agents 精选资源
保留 11 个 Division (排除 engineering/game-development/security/spatial-computing/testing)
激活专家后作为 Agent Profile 注入当前智能员工会话。
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import uuid
from datetime import datetime, timezone

from szyg import agency_state
from szyg.agency_manifest import EXCLUDED_DIVISIONS, RESOURCE_DIRNAME, RETAINED_DIVISIONS
from szyg.data_path import DATA_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agency", tags=["agency"])

def _resolve_agency_root() -> Path:
    """Return the single internal expert-resource root."""
    return Path(__file__).resolve().parent.parent / "resources" / RESOURCE_DIRNAME


AGENCY_ROOT = _resolve_agency_root()

# —— Marketplace 专属对话存储 ——
_AGENCY_CONV_DIR = DATA_DIR / "agency_conversations"
_AGENCY_CONV_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════
# 内存缓存 + 倒排索引（启动时预加载，避免每次请求读 155 个 .md 文件）
# ═══════════════════════════════════════════════════════════════════
_cache_agents: list[dict] = []          # 全部 agent 摘要 [{slug, name, desc, emoji, color, vibe, division}, ...]
_cache_divisions: list[dict] = []       # [{id, label, icon, color, count}, ...]
_cache_division_set: dict[str, dict] = {}  # division_id → division info
_search_index: dict[str, set[str]] = {}  # 倒排索引：关键词 → slug 集合
_cache_loaded = False


def _build_cache() -> None:
    """启动时一次性加载全部 agent，构建倒排索引。"""
    global _cache_agents, _cache_divisions, _cache_division_set, _search_index, _cache_loaded
    if _cache_loaded:
        return

    logger.info("Building agency agent cache (155 agents, 11 divisions)...")
    # 1) 扫描 divisions
    for div_id in RETAINED_DIVISIONS:
        meta = _DIVISIONS_META.get(div_id, {})
        d = AGENCY_ROOT / div_id
        count = len(list(d.glob("*.md"))) if d.is_dir() else 0
        info = {
            "id": div_id,
            "label": _DIVISION_CN.get(div_id, meta.get("label", div_id)),
            "icon": meta.get("icon", "Sparkles"),
            "color": meta.get("color", "#6366F1"),
            "count": count,
        }
        _cache_divisions.append(info)
        _cache_division_set[div_id] = info

    # 2) 扫描所有 agent
    for div_id in RETAINED_DIVISIONS:
        d = AGENCY_ROOT / div_id
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
                meta, _body = _parse_frontmatter(text)
                raw_name = meta.get("name", _slug_from_filename(f.name))
                raw_desc = meta.get("description", "")
                raw_vibe = meta.get("vibe", "")
                slug = _slug_from_filename(f.name)
                name_cn = _zh_name(raw_name)
                desc_cn = _get_desc(raw_name, raw_desc)
                vibe_cn = _zh_desc(raw_vibe) if raw_vibe else ""
                item = {
                    "slug": slug,
                    "name": name_cn,
                    "description": desc_cn,
                    "emoji": meta.get("emoji", "🤖"),
                    "color": meta.get("color", "#6366F1"),
                    "vibe": vibe_cn,
                    "division": div_id,
                }
                _cache_agents.append(item)

                # 3) 倒排索引：提取中文关键词
                keywords = _extract_keywords(name_cn + " " + desc_cn + " " + vibe_cn)
                for kw in keywords:
                    _search_index.setdefault(kw, set()).add(slug)
            except Exception as e:
                logger.debug("Cache skip %s: %s", f.name, e)

    _cache_loaded = True
    logger.info("Cache ready: %d agents, %d index keys", len(_cache_agents), len(_search_index))


def _extract_keywords(text: str) -> set[str]:
    """从中文文本提取单字、双字、三字片段作为搜索关键词。"""
    import re as _re
    # 去掉标点和空格，保留中文、英文、数字
    cleaned = _re.sub(r'[^一-鿿\w]', '', text)
    kw: set[str] = set()
    for length in (1, 2, 3):
        for i in range(len(cleaned) - length + 1):
            seg = cleaned[i:i + length]
            if seg.strip():
                kw.add(seg.lower())
    return kw


def _cache_query(division: str | None, search: str | None) -> list[dict]:
    """从缓存查询 agent 列表，支持 division 筛选 + 倒排索引搜索。"""
    _build_cache()
    result = _cache_agents

    if division and division in RETAINED_DIVISIONS:
        result = [a for a in result if a["division"] == division]

    if search and search.strip():
        q = search.strip().lower()
        # 拆分搜索词为多个 token，取交集
        tokens = [t for t in q.split() if t]
        if tokens:
            # 找匹配的 slug 集合
            matches: set[str] | None = None
            for token in tokens:
                token_slugs: set[str] = set()
                # 尝试精确匹配索引 key
                if token in _search_index:
                    token_slugs = _search_index[token]
                else:
                    # 模糊匹配：找包含该 token 的索引 key
                    for key, slugs in _search_index.items():
                        if token in key:
                            token_slugs.update(slugs)
                # 也对 slug/name/description 做直接匹配（兜底英文搜索）
                for a in result:
                    if (token in a["slug"].lower()
                        or token in a["name"].lower()
                        or token in a["description"].lower()):
                        token_slugs.add(a["slug"])
                if matches is None:
                    matches = token_slugs
                else:
                    matches = matches.intersection(token_slugs)
                if not matches:
                    return []
            result = [a for a in result if a["slug"] in matches]
        else:
            # 无有效 token → 返回空
            return []

    return result


def _cache_divisions_list() -> list[dict]:
    """返回 divisions 列表（含计数）。"""
    _build_cache()
    return _cache_divisions


def _cache_active_expert() -> dict | None:
    """返回当前激活专家（确保 name/description 为中文）。"""
    expert = agency_state.get_active_expert()
    if not expert:
        return None
    slug = expert.get("slug", "")
    # 从缓存中查找该专家以获取中文 name/description
    _build_cache()
    for a in _cache_agents:
        if a["slug"] == slug:
            return {
                "slug": slug,
                "name": a["name"],
                "description": a["description"],
                "emoji": a["emoji"],
                "division": a["division"],
                "division_label": _cache_division_set.get(a["division"], {}).get("label", a["division"]),
                "prompt": expert.get("prompt", ""),
            }
    # 缓存中没找到（可能是新专家），用存储的值
    div_meta = _cache_division_set.get(expert.get("division", ""), {})
    return {
        "slug": slug,
        "name": expert.get("name", slug),
        "description": expert.get("description", ""),
        "emoji": expert.get("emoji", "🤖"),
        "division": expert.get("division", ""),
        "division_label": _DIVISION_CN.get(expert.get("division", ""),
                                           div_meta.get("label", expert.get("division", ""))),
        "prompt": expert.get("prompt", ""),
    }

# ── Pydantic 模型 ────────────────────────────────────────────────────
class Division(BaseModel):
    id: str
    label: str
    icon: str
    color: str
    count: int


class AgentSummary(BaseModel):
    slug: str
    name: str
    description: str
    emoji: str = "🤖"
    color: str = "#6366F1"
    vibe: str = ""
    division: str


class AgentDetail(AgentSummary):
    prompt: str  # 完整 system prompt (.md 正文)
    division_label: str


class ActiveExpert(BaseModel):
    slug: str
    name: str
    description: str
    emoji: str
    division: str
    division_label: str
    prompt: str = ""  # 完整 system prompt，供前端在 marketplace 聊天时显式传递


# ── .md frontmatter 解析 ─────────────────────────────────────────────
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 YAML-like frontmatter，返回 (meta_dict, body_text)。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta_raw, body = m.group(1), m.group(2)
    meta: dict = {}
    for line in meta_raw.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body.strip()


def _load_divisions_meta() -> dict:
    """加载 divisions.json 的元数据 (label/icon/color)。"""
    dj = AGENCY_ROOT / "divisions.json"
    if not dj.exists():
        return {}
    try:
        data = json.loads(dj.read_text(encoding="utf-8"))
        return data.get("divisions", {})
    except Exception as e:
        logger.warning("Failed to load divisions.json: %s", e)
        return {}


_DIVISIONS_META = _load_divisions_meta()

# ═══════════════════════════════════════════════════════════════════
# 🌐 中文本地化 (C1 QA 阻塞修复) — 155 专家名称 + 11 Division
# ═══════════════════════════════════════════════════════════════════
_DIVISION_CN = {
    "academic": "学术研究", "design": "创意设计", "finance": "金融财务",
    "gis": "地理信息", "marketing": "营销增长", "paid-media": "付费投放",
    "product": "产品管理", "project-management": "项目管理",
    "sales": "销售策略", "specialized": "专项领域", "support": "客户支持",
}

# 英文词→中文 (描述/keyword 替换用)
_ZH_MAP = {
    "Content": "内容", "Social Media": "社交媒体", "Email": "邮件",
    "Digital": "数字", "Video": "视频", "Marketing": "营销", "Brand": "品牌",
    "Sales": "销售", "Strategy": "策略", "Growth": "增长", "Creative": "创意",
    "Community": "社群", "Campaign": "活动", "Product": "产品", "Project": "项目",
    "Design": "设计", "Customer": "客户", "Support": "客服", "Data": "数据",
    "Analytics": "分析", "Financial": "财务", "Legal": "法务", "Medical": "医疗",
    "China": "中国", "Cross-Border": "跨境", "E-Commerce": "电商",
    "Private Domain": "私域", "Livestream": "直播", "Supply Chain": "供应链",
    "Automation": "自动化", "Global": "全球", "Operation": "运营",
    "Intelligence": "情报", "Localization": "本地化", "Media": "媒体",
    # ── 新增 (2026-07-05 汉化补全) ──
    "AI": "AI", "SEO": "搜索引擎优化", "ASO": "应用商店优化",
    "AEO": "AI引擎优化", "GEO": "生成引擎优化", "SERP": "搜索结果",
    "ROI": "投资回报", "KPI": "关键指标", "CTA": "行动号召",
    "Organic": "自然流量", "Paid": "付费", "Podcast": "播客",
    "Newsletter": "邮件通讯", "Webinar": "网络研讨会",
    "Landing Page": "落地页", "Funnel": "漏斗", "Pipeline": "管道",
    "Lead": "线索", "Retention": "留存", "Churn": "流失",
    "B2B": "企业服务", "B2C": "消费者", "SaaS": "软件即服务",
    "CRM": "客户关系管理", "CMS": "内容管理", "API": "接口",
    "Agentic": "智能体", "Citation": "引用", "Foundations": "基础设施",
    "Discovery": "发现", "Co-Author": "合著", "Ghost": "代笔",
    "Context": "上下文", "Privacy": "隐私", "Compliance": "合规",
    "Accessibility": "无障碍", "Inclusive": "包容性", "Sustainability": "可持续",
    "Branding": "品牌建设", "Rebranding": "品牌重塑", "Positioning": "定位",
    "Messaging": "信息传达", "Storytelling": "故事叙述", "Narrative": "叙事",
    "Thought Leadership": "思想领导力", "Whitepaper": "白皮书",
    "Case Study": "案例研究", "Infographic": "信息图",
    "Motion": "动态", "Micro": "微型", "Nano": "极简",
    "Evergreen": "长青", "Viral": "病毒式传播", "UGC": "用户生成内容",
    "Influencer": "网红", "KOL": "关键意见领袖", "KOC": "关键意见消费者",
    "Ambassador": "品牌大使", "Affiliate": "联盟营销", "Referral": "推荐",
    "Loyalty": "忠诚度", "Gamification": "游戏化",
    "Omnichannel": "全渠道", "Multichannel": "多渠道",
    "DTC": "直营", "D2C": "直营",
    "Marketplace": "商城", "Shopify": "Shopify",
    "Amazon": "亚马逊", "Alibaba": "阿里巴巴",
    "JD": "京东", "Pinduoduo": "拼多多", "Meituan": "美团",
    "Pinterest": "Pinterest", "Snapchat": "Snapchat",
    "YouTube": "YouTube", "WhatsApp": "WhatsApp",
    "Telegram": "Telegram", "Discord": "Discord", "Slack": "Slack",
    "HubSpot": "HubSpot", "Mailchimp": "Mailchimp", "Klaviyo": "Klaviyo",
    "Salesforce": "Salesforce", "Zendesk": "Zendesk", "Intercom": "Intercom",
    "Google": "Google", "Microsoft": "微软", "Apple": "Apple",
    "App Store": "应用商店", "App": "应用", "Web": "网站",
    "Mobile": "移动端", "Desktop": "桌面端", "Cloud": "云端",
    "On-Premise": "本地部署", "Hybrid": "混合", "Remote": "远程",
    "Real-Time": "实时", "Batch": "批量", "Streaming": "流式",
    "Risk": "风险", "Governance": "治理", "Audit": "审计",
    "Forecast": "预测", "Budget": "预算", "Forensic": "法务",
    "M&A": "并购", "IPO": "上市", "Venture": "创投",
    "Seed": "种子轮", "Series A": "A轮", "Series B": "B轮",
    "PMF": "产品市场契合", "GTM": "市场进入", "PLG": "产品驱动增长",
    "ARPU": "客单价", "LTV": "客户终身价值", "CAC": "获客成本",
    "MRR": "月经常性收入", "ARR": "年经常性收入",
    "NPS": "净推荐值", "CSAT": "客户满意度",
    "SOP": "标准流程", "QA": "质量保障", "R&D": "研发",
    "HR": "人力资源", "PR": "公关", "IR": "投资者关系",
    "ESG": "ESG", "DEI": "多元化",
    "Book": "图书", "Carousel": "轮播", "Carousel Growth": "轮播增长",
    "China Market": "中国市场", "Ecommerce": "电商",
    "WebMCP": "WebMCP",
    "Small Language Model": "小语言模型", "SLM": "小语言模型",
    "Task Completion": "任务完成", "Agent": "智能体",
    "No-Code": "无代码", "Low-Code": "低代码",
    "White-Label": "白标", "Custom": "定制",
    "Enterprise": "企业级", "SMB": "中小企业",
    "Internal": "内部", "External": "外部",
    "Speed": "速度", "Scale": "规模化", "Quality": "质量",
    "Cold": "冷启动", "Warm": "温", "Hot": "热",
    "Inbound": "入站", "Outbound": "出站",
    "ABM": "目标客户营销", "AB Testing": "A/B测试",
    "Co-Branding": "联合品牌", "Co-Marketing": "联合营销",
    "User": "用户", "Buyer": "买家", "Consumer": "消费者",
    "Segment": "细分", "Cohort": "同期群", "Persona": "用户画像",
    "Journey": "旅程", "Touchpoint": "触点", "Engagement": "互动",
    "Activation": "激活", "Onboarding": "新手引导",
    "Monetization": "变现", "Expansion": "扩展",
    "Advocacy": "拥护", "Evangelism": "布道",
    "OKR": "目标与关键成果", "KPI Tree": "指标树",
    "North Star": "北极星指标", "AARRR": "海盗指标",
    "Agile": "敏捷", "Scrum": "Scrum", "Kanban": "看板",
    "Waterfall": "瀑布", "Lean": "精益", "Six Sigma": "六西格玛",
    # ── 第二轮补全 (翻译测试发现缺失) ──
    "Position": "排名", "Integration": "集成", "Optimization": "优化",
    "Expert": "专家", "companies": "企业", "company": "公司",
    "Specialist": "专家", "Manager": "经理", "Consultant": "顾问",
    "Architect": "架构师", "Strategist": "策略师",
    "Organic": "自然流量", "Paid": "付费",
    "specializing": "专注", "organic": "自然流量",
    "growth": "增长", "strategy": "策略",
    "content": "内容", "marketing": "营销",
    "conversion": "转化", "funnel": "漏斗",
    "design": "设计", "across": "跨",
    "platforms": "平台", "platform": "平台",
    "driven": "驱动", "AI-driven": "AI驱动",
    "SEO-driven": "搜索引擎优化驱动",
    "focused": "专注", "based": "基于",
    "powered": "驱动", "enabled": "赋能",
    "ready": "就绪", "first": "优先",
    "next": "下一代", "next-gen": "下一代",
    "modern": "现代", "traditional": "传统",
    "advanced": "高级", "basic": "基础",
    "standard": "标准", "premium": "高级",
    "professional": "专业", "personal": "个人",
    "team": "团队", "enterprise": "企业",
    "business": "业务", "consumer": "消费者",
    "service": "服务", "solution": "解决方案",
    "tool": "工具", "framework": "框架",
    "system": "系统", "process": "流程",
    "method": "方法", "approach": "方案",
    "model": "模型", "algorithm": "算法",
    "network": "网络", "chain": "链",
    "stack": "技术栈", "suite": "套件",
    "platform": "平台", "channel": "渠道",
    "Brand Safety": "品牌安全",
    "Keyword": "关键词", "keyword": "关键词",
    "Ranking": "排名", "Rank": "排名",
    "Traffic": "流量", "traffic": "流量",
    "Organic Traffic": "自然流量",
    "Paid Traffic": "付费流量",
    "Direct Traffic": "直接流量",
    "Referral Traffic": "推荐流量",
    "Social Traffic": "社交流量",
    "Email Traffic": "邮件流量",
    "Backlink": "外链", "backlink": "外链",
    "Domain Authority": "域名权威", "Page Authority": "页面权威",
    "Click-Through Rate": "点击率", "CTR": "点击率",
    "Conversion Rate": "转化率", "CVR": "转化率",
    "Bounce Rate": "跳出率",
    "Time on Page": "页面停留时间",
    "Pages per Session": "每次会话浏览页数",
    "Average Order Value": "平均订单价值", "AOV": "客单价",
    "Cost Per Click": "每次点击成本", "CPC": "点击成本",
    "Cost Per Mille": "千次展示成本", "CPM": "千次展示成本",
    "Cost Per Acquisition": "每次获客成本", "CPA": "获客成本",
    "Cost Per Lead": "每条线索成本", "CPL": "线索成本",
    "Return on Ad Spend": "广告支出回报", "ROAS": "广告回报率",
    "Return on Investment": "投资回报率",
    "Customer Acquisition Cost": "客户获取成本",
    "Customer Lifetime Value": "客户终身价值",
    "LTV:CAC Ratio": "终身价值获客成本比",
    "Churn Rate": "流失率",
    "Retention Rate": "留存率",
    "Net Promoter Score": "净推荐值",
    "Customer Satisfaction Score": "客户满意度评分",
    "Customer Effort Score": "客户费力度",
    "Monthly Active Users": "月活跃用户", "MAU": "月活",
    "Daily Active Users": "日活跃用户", "DAU": "日活",
    "Stickiness": "粘性", "DAU/MAU": "日活月活比",
    "Session": "会话", "User": "用户",
    "Visitor": "访客", "Subscriber": "订阅者",
    "Follower": "粉丝", "Fan": "粉丝",
    "Member": "会员", "Prospect": "潜在客户",
    "Lead Qualified": "合格线索", "MQL": "营销合格线索",
    "SQL": "销售合格线索", "PQL": "产品合格线索",
    "Opportunity": "商机", "Deal": "交易",
    "Pipeline Coverage": "销售管道覆盖",
    "Win Rate": "赢单率",
    "Sales Cycle": "销售周期",
    "Deal Velocity": "交易速度",
    "Quota": "配额", "Attainment": "达成率",
    "On-Track": "在轨", "At-Risk": "风险",
    "Committed": "承诺", "Upside": "上行空间",
    "Forecast Category": "预测类别",
    "Closed Won": "已赢单", "Closed Lost": "已丢单",
    "Slipped": "延期", "Pulled In": "提前",
    "Renewal": "续约", "Expansion": "扩展",
    "Upsell": "增购", "Cross-Sell": "交叉销售",
    "Downsell": "降级", "Contraction": "收缩",
    "Churn": "流失", "Logo Churn": "客户数流失",
    "Revenue Churn": "收入流失",
    "Net Revenue Retention": "净收入留存", "NRR": "净收入留存率",
    "Gross Revenue Retention": "毛收入留存", "GRR": "毛收入留存率",
    "Annual Contract Value": "年合同价值", "ACV": "年合同额",
    "Total Contract Value": "总合同价值", "TCV": "总合同额",
    "Annual Recurring Revenue": "年经常性收入",
    "Monthly Recurring Revenue": "月经常性收入",
    "Average Revenue Per User": "用户平均收入",
    "Average Revenue Per Account": "客户平均收入", "ARPA": "客均收入",
    "Employee": "员工", "Employee-Generated": "员工生成",
    "Employer": "雇主", "Employer Branding": "雇主品牌",
    "Recruitment": "招聘", "Recruitment Marketing": "招聘营销",
    "Talent": "人才", "Talent Brand": "人才品牌",
    "Career": "职业", "Career Site": "招聘网站",
    "Job": "职位", "Job Description": "职位描述",
    "Candidate": "候选人", "Candidate Experience": "候选人体验",
    "Interview": "面试", "Offer": "录用",
    "Onboarding": "入职", "Offboarding": "离职",
    "People": "人员", "Culture": "文化",
    # ── 常见英文虚词/功能词 (描述翻译补全) ──
    "and": "和", "or": "或", "the": "", "The": "",
    "in": "在", "for": "为", "with": "与",
    "from": "来自", "to": "到", "by": "通过",
    "of": "的", "on": "关于", "at": "在",
    "is a": "是一位", "is an": "是一位",
    "that": "", "this": "此", "these": "这些",
    "their": "他们的", "your": "您的", "our": "我们的",
    "its": "其", "all": "所有", "each": "每个",
    "every": "每", "some": "一些", "any": "任何",
    "more": "更多", "most": "大多数", "less": "更少",
    "how": "如何", "what": "什么", "why": "为什么",
    "when": "何时", "where": "何处", "who": "谁",
    "which": "哪个", "can": "可以", "will": "将",
    "should": "应当", "must": "必须", "may": "可能",
    "also": "也", "not": "不", "only": "仅",
    "very": "非常", "just": "刚刚", "now": "现在",
    "then": "然后", "across": "跨",
    "search engine": "搜索引擎",
    "search": "搜索", "engine": "引擎",
    "optimization": "优化",
    "focusing": "聚焦", "focused": "聚焦",
    "specializing": "专注", "specialized": "专注",
    "specializes": "专注",
    "Expert in": "专注于", "expert in": "专注于",
    "expertise in": "专长于",
    "helping": "帮助", "helps": "帮助",
    "ensuring": "确保", "ensures": "确保",
    "enabling": "赋能", "enables": "赋能",
    "driving": "驱动", "drives": "驱动",
    "building": "构建", "builds": "构建",
    "creating": "创建", "creates": "创建",
    "managing": "管理", "manages": "管理",
    "developing": "开发", "develops": "开发",
    "implementing": "实施", "implements": "实施",
    "delivering": "交付", "delivers": "交付",
    "providing": "提供", "provides": "提供",
    "supporting": "支持", "supports": "支持",
    "optimizing": "优化", "optimizes": "优化",
    "designing": "设计", "designs": "设计",
    "executing": "执行", "executes": "执行",
    "measuring": "衡量", "measures": "衡量",
    "analyzing": "分析", "analyzes": "分析",
    "improving": "改进", "improves": "改进",
    "increasing": "增加", "increases": "增加",
    "reducing": "减少", "reduces": "减少",
    "scaling": "扩展", "scales": "扩展",
    "transforming": "转变", "transforms": "转变",
    "consulting": "咨询", "advising": "建议",
    "coaching": "辅导", "mentoring": "指导",
    "training": "培训", "teaching": "教学",
    "writing": "撰写", "editing": "编辑",
    "reviewing": "审阅", "auditing": "审计",
    "reporting": "报告", "tracking": "追踪",
    "monitoring": "监控", "alerting": "告警",
    "forecasting": "预测", "predicting": "预测",
    "planning": "规划", "scheduling": "排程",
    "coordinating": "协调", "orchestrating": "编排",
    "automating": "自动化", "streamlining": "精简",
    "integrating": "集成", "connecting": "连接",
    "migrating": "迁移", "upgrading": "升级",
    "testing": "测试", "debugging": "调试",
    "deploying": "部署", "launching": "发布",
    "operating": "运营", "maintaining": "维护",
    "troubleshooting": "故障排查",
    "documenting": "文档记录",
    "researching": "研究", "investigating": "调查",
    "discovering": "发现", "exploring": "探索",
    "identifying": "识别", "evaluating": "评估",
    "comparing": "比较", "benchmarking": "基准测试",
    "calculating": "计算", "estimating": "估算",
    "budgeting": "预算编制",
    "negotiating": "谈判", "mediating": "调解",
    "facilitating": "引导", "moderating": "主持",
    "presenting": "演示", "communicating": "沟通",
    "storytelling": "讲述", "narrating": "叙述",
    "visualizing": "可视化", "illustrating": "插图",
    "animating": "动画制作",
    "filming": "拍摄", "recording": "录制",
    "editing video": "视频剪辑",
    "producing": "制作", "directing": "导演",
    "performing": "表演", "entertaining": "娱乐",
    "singing": "演唱", "dancing": "舞蹈",
    "composing": "作曲", "arranging": "编曲",
    "mixing": "混音", "mastering": "母带",
    "branding": "品牌建设",
    "rebranding": "品牌重塑",
    "positioning": "定位", "messaging": "信息传达",
    "targeting": "定向", "segmenting": "细分",
    "personalizing": "个性化", "customizing": "定制",
    "localizing": "本地化", "translating": "翻译",
    "transcreating": "创译", "adapting": "适配",
    "publishing": "发布", "distributing": "分发",
    "promoting": "推广", "advertising": "广告投放",
    "selling": "销售", "closing": "成交",
    "converting": "转化", "converting leads": "线索转化",
    "nurturing": "培育", "nurturing leads": "培育线索",
    "qualifying": "资格验证",
    "prospecting": "潜在客户开发",
    "outreaching": "外联", "cold emailing": "冷邮件",
    "cold calling": "冷电话",
    "following up": "跟进",
    "onboarding customers": "客户入驻",
    "upselling": "增购", "cross-selling": "交叉销售",
    "renewing": "续约", "expanding accounts": "客户扩展",
    "handling objections": "处理异议",
    "closing deals": "完成交易",
    "serving": "服务", "resolving": "解决",
    "answering": "回答", "responding": "响应",
    "escalating": "升级处理",
    "routing": "路由", "ticketing": "工单管理",
    "triaging": "分诊", "prioritizing": "优先级排序",
    "documenting solutions": "方案记录",
    "building knowledge base": "构建知识库",
    "SaaS": "SaaS", "B2B": "B2B", "B2C": "B2C",
    "companies": "公司", "businesses": "企业",
    "startups": "初创公司", "startup": "初创公司",
    "discoverability": "可发现性",
    "go-to-market": "市场进入", "go to market": "市场进入",
    "demand generation": "需求挖掘",
    "demand gen": "需求挖掘",
    "infrastructure": "基础设施",
    "availability": "可用性", "structured": "结构化",
    "Markdown": "Markdown", "robots.txt": "robots规则",
    "llms.txt": "LLM规则",
    "discovery": "发现", "files": "文件",
    "agents": "智能体",
    "it": "它", "its": "其",
    "&": "和",
}
# 平台名
_PLAT_ZH = {
    "Douyin": "抖音", "Xiaohongshu": "小红书", "Bilibili": "B站",
    "Zhihu": "知乎", "Kuaishou": "快手", "Weibo": "微博", "WeChat": "微信",
    "Baidu": "百度", "TikTok": "TikTok", "Instagram": "Instagram",
    "LinkedIn": "LinkedIn", "Reddit": "Reddit", "Twitter": "Twitter",
    "X/Twitter": "X/Twitter", "Jira": "Jira", "Salesforce": "Salesforce",
}
# 角色后缀
_ROLE_ZH = {
    "Strategist": "策略师", "Specialist": "专家", "Creator": "创作师",
    "Manager": "经理", "Analyst": "分析师", "Consultant": "顾问",
    "Optimizer": "优化师", "Designer": "设计师", "Engineer": "工程师",
    "Architect": "架构师", "Coach": "教练", "Officer": "专员",
    "Developer": "开发者", "Builder": "构建师", "Producer": "制作人",
    "Editor": "剪辑师", "Researcher": "研究员", "Operator": "运营专员",
    "Agent": "助手", "Publisher": "发布专员", "Curator": "策展人",
    "Guardian": "守护官", "Navigator": "导航顾问", "Auditor": "审计师",
    "Steward": "管理员", "Responder": "客服专员", "Tracker": "追踪师",
    "Assistant": "助理", "Planner": "策划师", "Mentor": "导师",
    "Scientist": "科学家", "Writer": "写手", "Translator": "翻译专员",
    "Orchestrator": "编排师", "Reviewer": "审阅师", "Reporter": "报告专员",
    # ── 新增 (2026-07-05 汉化补全) ──
    "Hacker": "黑客增长师", "Marketer": "营销师", "Evangelist": "布道师",
    "Advocate": "倡导者", "Catalyst": "催化师", "Facilitator": "引导师",
    "Diagnostician": "诊断师", "Mediator": "调解师", "Negotiator": "谈判师",
    "Forecaster": "预测师", "Visualizer": "可视化师", "Sculptor": "塑形师",
    "Conductor": "总指挥", "Composer": "作曲家",
    "Innovator": "创新师", "Pioneer": "先驱者", "Visionary": "愿景师",
    "Detective": "侦探", "Sleuth": "调查员", "Profiler": "画像师",
    "Storyteller": "故事师", "Wordsmith": "文字工匠", "Linguist": "语言学家",
    "Psychologist": "心理学家", "Sociologist": "社会学家", "Economist": "经济学家",
    "Statistician": "统计学家", "Mathematician": "数学家", "Logician": "逻辑学家",
    "Tactician": "战术师", "Executor": "执行专员",
    "Governor": "治理官", "Warden": "守护者", "Sentinel": "哨兵",
    "Cartographer": "制图师", "Surveyor": "测绘师", "Explorer": "探索者",
    "Pathfinder": "寻路者", "Scout": "侦察员", "Ranger": "巡护员",
    "Craftsman": "工匠", "Artisan": "手艺人", "Maestro": "大师",
    "Virtuoso": "演奏家", "Performer": "表演者", "Entertainer": "演艺师",
    "Healer": "疗愈师", "Therapist": "治疗师", "Counselor": "咨询师",
    "Advisor": "顾问", "Guide": "向导", "Sherpa": "引路人",
    "Moderator": "主持人", "Host": "主持人", "Emcee": "司仪",
    "Chronicler": "编年史家", "Archivist": "档案师", "Librarian": "图书管理员",
    "Cartoonist": "漫画家", "Illustrator": "插画师", "Animator": "动画师",
    "Photographer": "摄影师", "Videographer": "摄像师", "Cinematographer": "电影摄影师",
    "Sound": "音频", "Audio": "音频", "Musician": "音乐家",
    "Chef": "主厨", "Sommelier": "品鉴师", "Mixologist": "调酒师",
    "Gardener": "园丁", "Botanist": "植物学家", "Ecologist": "生态学家",
    "Coder": "程序员", "Programmer": "程序员",
    "Tester": "测试师", "Debugger": "调试师", "Refactorer": "重构师",
    "Integrator": "集成师", "Deployer": "部署师", "Monitor": "监控师",
    "Synthesizer": "综合师", "Summarizer": "摘要师", "Distiller": "提炼师",
}
# 特殊名称（155 个 agent 完整汉化，覆盖所有 division）
_NAME_OVERRIDE = {
    # === academic (5) ===
    "Anthropologist": "人类学家",
    "Geographer": "地理学家",
    "Historian": "历史学家",
    "Narratologist": "叙事学家",
    "Psychologist": "心理学家",
    # === design (9) ===
    "Brand Guardian": "品牌守护官",
    "Image Prompt Engineer": "图像提示词工程师",
    "Inclusive Visuals Specialist": "包容性视觉设计专家",
    "Persona Walkthrough Specialist": "用户画像体验模拟专家",
    "UI Designer": "UI设计师",
    "UX Architect": "UX架构师",
    "UX Researcher": "UX研究员",
    "Visual Storyteller": "视觉故事师",
    "Whimsy Injector": "趣味创意师",
    # === finance (5) ===
    "Bookkeeper & Controller": "记账与财务管控师",
    "Financial Analyst": "财务分析师",
    "FP&A Analyst": "财务规划与分析分析师",
    "Investment Researcher": "投资研究员",
    "Tax Strategist": "税务策略师",
    # === gis (13) ===
    "3D & Scene Developer": "三维场景开发者",
    "GIS Analyst": "地理信息系统分析师",
    "BIM/GIS Specialist": "建筑信息模型与地理信息专家",
    "Cartography Designer": "制图设计师",
    "Drone/Reality Mapping Specialist": "无人机实景测绘专家",
    "GeoAI/ML Engineer": "地理人工智能与机器学习工程师",
    "Geoprocessing Specialist": "地理处理专家",
    "GIS QA Engineer": "地理信息系统质量保障工程师",
    "Solution Engineer": "解决方案工程师",
    "Spatial Data Engineer": "空间数据工程师",
    "Spatial Data Scientist": "空间数据科学家",
    "Technical Consultant": "技术顾问",
    "Web GIS Developer": "Web地理信息系统开发者",
    # === marketing (36) ===
    "AEO Foundations Architect": "AI引擎优化基础设施架构师",
    "Agentic Search Optimizer": "智能体搜索优化师",
    "AI Citation Strategist": "AI引用策略师",
    "App Store Optimizer": "应用商店优化师",
    "Baidu SEO Specialist": "百度搜索优化专家",
    "Bilibili Content Strategist": "B站内容策略师",
    "Book Co-Author": "图书合著作者",
    "Carousel Growth Engine": "轮播增长引擎师",
    "China E-Commerce Operator": "中国电商运营专员",
    "China Market Localization Strategist": "中国市场本地化策略师",
    "Content Creator": "内容创作师",
    "Cross-Border E-Commerce Specialist": "跨境电商专家",
    "Douyin Strategist": "抖音策略师",
    "Email Marketing Strategist": "邮件营销策略师",
    "Global Podcast Strategist": "全球播客策略师",
    "Growth Hacker": "增长黑客",
    "Instagram Curator": "Instagram策展人",
    "Kuaishou Strategist": "快手策略师",
    "LinkedIn Content Creator": "LinkedIn内容创作师",
    "Livestream Commerce Coach": "直播电商教练",
    "Multi-Platform Publisher": "多平台发布专员",
    "Podcast Strategist": "播客策略师",
    "PR & Communications Manager": "公关与传播经理",
    "Private Domain Operator": "私域运营专员",
    "Reddit Community Builder": "Reddit社群构建师",
    "SEO Specialist": "搜索优化专家",
    "Short-Video Editing Coach": "短视频剪辑教练",
    "Social Media Strategist": "社交媒体策略师",
    "TikTok Strategist": "TikTok策略师",
    "Twitter Engager": "Twitter互动专家",
    "Video Optimization Specialist": "视频优化专家",
    "WeChat Official Account Manager": "微信公众号运营经理",
    "Weibo Strategist": "微博策略师",
    "X/Twitter Intelligence Analyst": "X/Twitter情报分析师",
    "Xiaohongshu Specialist": "小红书专家",
    "Zhihu Strategist": "知乎策略师",
    # === paid-media (7) ===
    "Paid Media Auditor": "付费媒体审计师",
    "Ad Creative Strategist": "广告创意策略师",
    "Paid Social Strategist": "付费社交广告策略师",
    "PPC Campaign Strategist": "点击付费广告活动策略师",
    "Programmatic & Display Buyer": "程序化展示广告采买师",
    "Search Query Analyst": "搜索查询分析师",
    "Tracking & Measurement Specialist": "追踪与测量专家",
    # === product (5) ===
    "Behavioral Nudge Engine": "行为助推引擎师",
    "Feedback Synthesizer": "反馈综合师",
    "Product Manager": "产品经理",
    "Sprint Prioritizer": "敏捷冲刺优先级规划师",
    "Trend Researcher": "趋势研究员",
    # === project-management (7) ===
    "Experiment Tracker": "实验追踪师",
    "Jira Workflow Steward": "Jira工作流管理员",
    "Meeting Notes Specialist": "会议纪要专家",
    "Project Shepherd": "项目护航师",
    "Studio Operations": "工作室运营专员",
    "Studio Producer": "工作室制作人",
    "Senior Project Manager": "高级项目经理",
    # === sales (9) ===
    "Account Strategist": "客户策略师",
    "Sales Coach": "销售教练",
    "Deal Strategist": "交易策略师",
    "Discovery Coach": "探索引导教练",
    "Sales Engineer": "销售工程师",
    "Offer & Lead Gen Strategist": "报价与线索生成策略师",
    "Outbound Strategist": "外联开发策略师",
    "Pipeline Analyst": "销售管道分析师",
    "Proposal Strategist": "提案策略师",
    # === specialized (53) ===
    "Accounts Payable Agent": "应付账款智能助手",
    "Agentic Identity & Trust Architect": "智能体身份与信任架构师",
    "Agents Orchestrator": "多智能体编排师",
    "Automation Governance Architect": "自动化治理架构师",
    "Business Strategist": "商业策略师",
    "Change Management Consultant": "变革管理顾问",
    "Chief Financial Officer": "首席财务官",
    "Corporate Training Designer": "企业培训设计师",
    "Customer Service": "客户服务专员",
    "Customer Success Manager": "客户成功经理",
    "Data Consolidation Agent": "数据整合智能助手",
    "Data Privacy Officer": "数据隐私专员",
    "ESG & Sustainability Officer": "ESG与可持续发展专员",
    "Government Digital Presales Consultant": "政务数字化售前顾问",
    "Grant Writer": "资助申请撰写师",
    "Healthcare Customer Service": "医疗健康客服专员",
    "Healthcare Marketing Compliance Specialist": "医疗营销合规专家",
    "Hospitality Guest Services": "酒店宾客服务专员",
    "HR Onboarding": "人事入职管理专员",
    "Identity Graph Operator": "身份图谱运营专员",
    "Language Translator": "语言翻译专员",
    "Legal Billing & Time Tracking": "法务计费与工时追踪专员",
    "Legal Client Intake": "法务客户接案专员",
    "Legal Document Review": "法务文档审阅师",
    "Loan Officer Assistant": "贷款专员助理",
    "LSP/Index Engineer": "语言服务提供商索引工程师",
    "M&A Integration Manager": "并购整合经理",
    "Medical Billing & Coding Specialist": "医疗计费与编码专家",
    "Operations Manager": "运营经理",
    "Organizational Psychologist": "组织心理学家",
    "Personal Growth Mentor": "个人成长导师",
    "Real Estate Buyer & Seller": "房地产买卖顾问",
    "Recruitment Specialist": "招聘专家",
    "Report Distribution Agent": "报告分发智能助手",
    "Retail Customer Returns": "零售客户退货处理专员",
    "Sales Data Extraction Agent": "销售数据提取智能助手",
    "Sales Outreach": "销售外联专员",
    "Chief of Staff": "幕僚长",
    "Civil Engineer": "土木工程师",
    "Cultural Intelligence Strategist": "跨文化情报策略师",
    "Developer Advocate": "开发者关系倡导者",
    "Document Generator": "文档生成器",
    "French Consulting Market Navigator": "法国咨询市场导航顾问",
    "Korean Business Navigator": "韩国商务导航顾问",
    "MCP Builder": "MCP构建师",
    "Model QA Specialist": "模型质量保障专家",
    "Pricing Analyst": "定价分析师",
    "Salesforce Architect": "Salesforce架构师",
    "Strategy Duel Agent": "策略对抗模拟师",
    "Workflow Architect": "工作流架构师",
    "Study Abroad Advisor": "留学顾问",
    "Supply Chain Strategist": "供应链策略师",
    "ZK Steward": "零知识证明管理员",
    # === support (6) ===
    "Analytics Reporter": "数据分析报告专员",
    "Executive Summary Generator": "高管摘要生成器",
    "Finance Tracker": "财务追踪师",
    "Infrastructure Maintainer": "基础设施维护师",
    "Legal Compliance Checker": "法务合规检查师",
    "Support Responder": "客服响应专员",
}



# Auto-generated Chinese description overrides for 155 agency agents
# Generated by merge_descs.py

_DESC_OVERRIDE = {
    "3D & Scene Developer": "使用Cesium等框架构建沉浸式3D场景与地形模型，打造交互式Web可视化体验。",
    "AEO Foundations Architect": "帮助企业构建AI搜索引擎优化基础设施，让AI爬虫轻松发现和解读网站内容",
    "AI Citation Strategist": "提升品牌在ChatGPT等AI推荐引擎中的可见度，让AI更频繁引用你的品牌",
    "Account Strategist": "专注于售后客户增长策略，通过系统化规划和多方关系维护，助您实现客户长期价值最大化。",
    "Accounts Payable Agent": "自动处理供应商付款和定期账单，支持加密货币、法币及稳定币等多种支付通道。",
    "Ad Creative Strategist": "广告创意与文案优化专家，架起投放数据与营销信息之间的桥梁，提升广告说服力。",
    "Agentic Identity & Trust Architect": "为多智能体环境设计身份认证与信任验证体系，确保代理身份可信、行为可追溯。",
    "Agentic Search Optimizer": "优化网站以支持AI代理自主完成任务，提升智能体在站内的任务完成率",
    "Agents Orchestrator": "自主管理工作流管道，统筹协调整个开发流程的全流程编排器。",
    "Analytics Reporter": "专业数据分析师，将原始数据转化为可执行的业务洞察，通过数据可视化与报表助力决策。",
    "Anthropologist": "专攻文化体系与民族志，助你打造有血有肉、真实可信的文明社会",
    "App Store Optimizer": "优化应用商店排名与转化率，提升App在各市场的发现度和下载量",
    "Automation Governance Architect": "以治理为先导，在实施前审计业务自动化的价值、风险与可维护性。",
    "BIM/GIS Specialist": "融合BIM与GIS数据，处理Revit/IFC转换、室内地图及数字孪生架构。",
    "Baidu SEO Specialist": "专注百度搜索引擎优化，提升网站在中文搜索环境中的排名与可见度",
    "Behavioral Nudge Engine": "基于行为心理学动态优化软件交互方式，最大化用户的使用动力与成功率。",
    "Bilibili Content Strategist": "制定B站内容运营策略，助力UP主成长并玩转弹幕文化与社区生态",
    "Book Co-Author": "帮助创始人将碎片化想法整理成结构化的专业书籍章节",
    "Bookkeeper & Controller": "处理日常记账、对账与月末结账，保障财务数据准确合规、随时可审计。",
    "Brand Guardian": "品牌战略专家，帮助企业打造统一品牌形象，维护品牌一致性，实现精准市场定位",
    "Business Strategist": "资深管理咨询专家，提供竞争分析、市场进入策略与商业模式设计等战略决策支持。",
    "Carousel Growth Engine": "自动生成TikTok和Instagram爆款轮播图，通过数据驱动持续优化内容",
    "Cartography Designer": "设计美观易读的地图，精通色彩理论、排版与视觉层次，适用于印刷与Web端。",
    "Change Management Consultant": "运用ADKAR和Prosci等框架，引导组织变革实施并确保成果长期固化。",
    "Chief Financial Officer": "战略财务高管，统筹资本配置与财务规划，驱动业务绩效与投资者信心。",
    "Chief of Staff": "创始人与高管的得力协调人，过滤噪音并确保决策落地，让领导专注核心思考。",
    "China E-Commerce Operator": "精通淘宝、京东等全平台电商运营，覆盖直播带货与大促营销策略",
    "China Market Localization Strategist": "将实时市场趋势转化为可执行的入华策略，实现品牌在中国市场的本土化落地",
    "Civil Engineer": "土木与结构工程专家，覆盖欧标美标国标等多元标准体系，胜任国际化项目设计。",
    "Content Creator": "制定多平台内容策略与编辑日历，打造有吸引力的品牌故事和营销文案",
    "Corporate Training Designer": "企业培训体系设计专家，精通需求分析与课程开发，持续优化培训效果。",
    "Cross-Border E-Commerce Specialist": "覆盖亚马逊、Shopee等跨境平台运营，精通物流合规与品牌全球化布局",
    "Cultural Intelligence Strategist": "文化智能策略师，识别隐性排斥并研究全球语境，确保产品包容多元身份群体。",
    "Customer Service": "友好专业的客服专家，高效处理咨询与投诉，致力提升客户满意度。",
    "Customer Success Manager": "战略客户成功专家，负责客户引导与续约管理，驱动长期合作伙伴关系。",
    "Data Consolidation Agent": "将销售数据整合至实时仪表板，提供区域与管道等维度的汇总概览。",
    "Data Privacy Officer": "企业数据隐私专家，构建全球隐私合规体系，涵盖数据映射与风险评估。",
    "Deal Strategist": "资深交易策略专家，精通复杂B2B销售中的商机评估与竞争定位，助您制定稳操胜券的赢单方案。",
    "Developer Advocate": "开发者关系专家，建设技术社区并优化开发者体验，推动平台采用与生态增长。",
    "Discovery Coach": "辅导销售团队掌握顶级需求挖掘方法，通过精准提问和现状分析，揭示客户真实购买动机。",
    "Document Generator": "专业文档生成专家，通过代码创建格式规范的PDF、PPTX及DOCX等办公文件。",
    "Douyin Strategist": "精通抖音算法与短视频营销，打造从爆款内容到直播带货的全链路增长",
    "Drone/Reality Mapping Specialist": "处理无人机影像生成正射影像、数字地形模型与三维网格，实现实景GIS数据生产。",
    "ESG & Sustainability Officer": "企业可持续发展与ESG报告专家，管理信息披露并推动脱碳与合规战略落地。",
    "Email Marketing Strategist": "设计全生命周期邮件营销自动化流程，提升客户触达与转化率",
    "Executive Summary Generator": "资深战略顾问级AI，运用顶级咨询框架生成精炼的高管摘要，助力管理层快速决策。",
    "Experiment Tracker": "专注实验设计与数据驱动决策，系统管理A/B测试与假设验证。",
    "FP&A Analyst": "负责预算编制、差异分析与滚动预测，连接财务数据与业务运营，优化资源配置。",
    "Feedback Synthesizer": "多渠道收集并分析用户反馈，将定性意见转化为可量化的产品优先级与战略建议。",
    "Finance Tracker": "专业财务分析师，专注财务规划与预算管理，优化现金流，提供战略性财务增长建议。",
    "Financial Analyst": "构建财务模型与预测，将数据转化为业务洞察，辅助战略与投资决策。",
    "French Consulting Market Navigator": "法国IT咨询自由职业市场导航，解读费率模式与薪资结算机制等生态规则。",
    "GIS Analyst": "负责日常GIS操作，包括地图制作、图层管理、空间查询及地理空间数据维护。",
    "GIS QA Engineer": "验证地理空间数据质量，执行拓扑检查、元数据审计、坐标参考系一致性及精度评估。",
    "GeoAI/ML Engineer": "构建地理空间机器学习模型，用于卫星与航拍影像的特征提取、目标检测及地表分类。",
    "Geographer": "精通自然与人文地理及气候系统，构建地形气候资源科学合理的地理世界",
    "Geoprocessing Specialist": "使用ArcPy和Python自动化空间工作流，构建自定义工具箱与批量地理处理脚本。",
    "Global Podcast Strategist": "打造全球化播客品牌，从内容定位、受众增长到商业变现的全流程指导",
    "Government Digital Presales Consultant": "政府数字化售前专家，精通政策解读与方案设计，熟悉等保密评与信创合规要求。",
    "Grant Writer": "非营利与科研机构资助申请专家，涵盖课题调研与提案撰写全流程。",
    "Growth Hacker": "通过数据驱动的实验与病毒增长策略，实现用户规模的快速扩张",
    "HR Onboarding": "入职管理专家，负责新员工引导与合规跟踪，助力人才快速融入与留存。",
    "Healthcare Customer Service": "富有同理心的医疗客服专家，处理患者支持与账单查询，提升就医体验。",
    "Healthcare Marketing Compliance Specialist": "中国医疗营销合规专家，精通广告法与药品管理法，保障健康营销合法合规。",
    "Historian": "精通历史分析与史料考证，确保设定符合史实，赋予作品真实时代底蕴",
    "Hospitality Guest Services": "酒店餐饮宾客服务专家，涵盖预订入住与投诉处理，打造卓越宾客体验。",
    "Identity Graph Operator": "维护共享身份图谱，确保多智能体系统对实体身份的解析一致且确定。",
    "Image Prompt Engineer": "精通图像生成的提示词工程师，能将视觉概念转化为精准语言，产出专业级摄影作品",
    "Inclusive Visuals Specialist": "消除人工智能系统性偏见，生成文化准确、包容正面、去刻板印象的图像与视频",
    "Infrastructure Maintainer": "资深基础设施专家，保障系统稳定与性能优化，打造安全高效、可扩展的技术架构。",
    "Instagram Curator": "打造高品质Instagram视觉美学，构建活跃社区与品牌互动",
    "Investment Researcher": "开展市场调研与尽职调查，进行资产估值与组合分析，识别投资机会与风险。",
    "Jira Workflow Steward": "强化Jira与Git工作流规范，确保提交可追溯、PR结构清晰及分支策略安全。",
    "Korean Business Navigator": "韩国商务文化导航，解读决策流程与商务礼仪，助力外籍人士高效开展本地业务。",
    "Kuaishou Strategist": "深耕快手平台的下沉市场运营，构建社区信任与直播电商增长",
    "LSP/Index Engineer": "语言服务器协议专家，通过客户端编排与语义索引构建统一代码智能系统。",
    "Language Translator": "实时西英互译专家，融合文化背景与方言差异，精准应对商务及应急场景。",
    "Legal Billing & Time Tracking": "法律计费与工时追踪专家，确保精准计时开票，最大化营收同时维护客户关系。",
    "Legal Client Intake": "法律客户收案专家，负责资格审核与利益冲突排查，生成律师就绪的案件摘要。",
    "Legal Compliance Checker": "专业法务合规顾问，确保业务运营与数据处理符合多地区法律法规与行业标准。",
    "Legal Document Review": "法律文档审查专家，审阅合同与诉讼文件，标记风险条款并确保合规性。",
    "LinkedIn Content Creator": "在LinkedIn上打造个人品牌与思想领导力，通过专业内容获取商业机会",
    "Livestream Commerce Coach": "培训主播与优化直播间运营，涵盖脚本设计、流量调控与转化技巧",
    "Loan Officer Assistant": "贷款专员助理，覆盖借款人准入与文件收集，协调抵押及商业贷款结案全流程。",
    "M&A Integration Manager": "并购整合专家，设计并执行投后整合方案，涵盖Day 1准备与百天计划协同推进。",
    "MCP Builder": "模型上下文协议开发专家，设计并构建MCP服务器以扩展AI代理的底层能力。",
    "Medical Billing & Coding Specialist": "医疗计费与编码专家，精通ICD与CPT编码，优化收入周期并提高理赔通过率。",
    "Meeting Notes Specialist": "从会议记录中提取决策、行动项和待定问题，生成四段式清晰摘要。",
    "Model QA Specialist": "独立模型质量审核专家，对机器学习与统计模型进行端到端审计与复现验证。",
    "Multi-Platform Publisher": "一键分发文章至知乎、小红书等多平台，自动适配各平台内容格式",
    "Narratologist": "专攻叙事理论与故事结构，依托经典框架，为你的创作提供专业叙事指导",
    "Offer & Lead Gen Strategist": "漏斗顶层设计专家，打造高转化率诱饵和系统化获客策略，帮您大规模吸引优质潜在客户。",
    "Operations Manager": "运营管理专家，运用精益六西格玛与系统思维优化流程、产能与供应商绩效。",
    "Organizational Psychologist": "应用组织心理学家，诊断团队动力与心理安全，助力构建高韧性健康组织。",
    "Outbound Strategist": "信号驱动型外呼专家，通过多渠道个性化触达策略，精准定位目标客户，高效构建销售管道。",
    "PPC Campaign Strategist": "搜索与购物广告策略专家，设计账户结构与出价方案，助力月消费从万级到千万级的投放规模。",
    "PR & Communications Manager": "制定媒体公关与品牌传播策略，处理危机沟通并维护企业声誉",
    "Paid Media Auditor": "系统审计Google Ads、Meta等平台广告账户，输出含优先级建议与预期影响的可执行报告。",
    "Paid Social Strategist": "跨平台社交媒体广告专家，覆盖Meta、TikTok、LinkedIn等渠道，定制从拉新到再营销的全漏斗策略。",
    "Persona Walkthrough Specialist": "基于目标用户心理视角模拟网页认知走查，结合行为心理学框架输出CRO优化报告",
    "Personal Growth Mentor": "跨领域个人成长导师，帮助明确目标与设计习惯，提供务实可行的战略决策建议。",
    "Pipeline Analyst": "营收运营分析专家，深挖CRM数据洞察管道健康与交易流速，提前预警风险确保业绩达成。",
    "Podcast Strategist": "针对中文播客市场提供内容策略与运营指导，助力创作者建立音频品牌",
    "Pricing Analyst": "专业定价分析师，通过市场研究与成本评估制定最优策略，驱动竞争优势。",
    "Private Domain Operator": "构建企业微信私域生态，通过SCRM系统实现用户全生命周期运营",
    "Product Manager": "主导产品全生命周期，贯通商业目标、用户需求与技术实现，确保适时交付正确产品。",
    "Programmatic & Display Buyer": "程序化展示广告与媒体购买专家，覆盖GDN、DV360及ABM定向策略，精准触达目标客户。",
    "Project Shepherd": "协调跨职能项目、管理进度与干系人，推动项目从概念到交付的全流程落地。",
    "Proposal Strategist": "标书与提案策略专家，将RFP转化为有说服力的赢单叙事，助您在竞争中脱颖而出。",
    "Psychologist": "精通人格理论与行为模式，基于研究框架塑造心理真实可信的角色",
    "Real Estate Buyer & Seller": "房地产买卖助理，支持买家代理与谈判议价，覆盖从看房到结案的全流程服务。",
    "Recruitment Specialist": "招聘运营与人才获取专家，精通中国主流招聘平台，助力雇主品牌建设。",
    "Reddit Community Builder": "在Reddit建立真实社区互动，通过价值内容驱动长期品牌关系",
    "Report Distribution Agent": "自动化销售报告分发代理，根据区域参数将整合报告定向推送至对应销售代表。",
    "Retail Customer Returns": "零售退换货处理专家，管理退换与退款流程，平衡政策执行与客户忠诚度维护。",
    "SEO Specialist": "专注搜索引擎优化，通过技术与内容双驱动提升网站自然搜索流量",
    "Sales Coach": "通过结构化辅导和实战反馈，帮助销售团队提升技巧优化流程，让每位成员业绩更上一层楼。",
    "Sales Data Extraction Agent": "专注监控Excel文件并提取关键销售指标，支持月度与年度实时内部报告。",
    "Sales Engineer": "资深售前技术专家，擅长技术方案演示与概念验证，架起产品能力与业务价值的桥梁，助力赢单。",
    "Sales Outreach": "顾问式B2B销售拓展专家，精通线索跟进与提案撰写，推动商机转化与成交。",
    "Salesforce Architect": "Salesforce平台架构专家，精通多云设计与集成模式，确保企业级架构合规。",
    "Search Query Analyst": "搜索词分析与否定关键词优化专家，消除浪费流量，放大高意向搜索词带来的优质流量。",
    "Senior Project Manager": "将需求规格拆解为可执行任务，参考历史项目经验，聚焦务实范围与精确需求。",
    "Short-Video Editing Coach": "手把手教授短视频剪辑全流程，精通CapCut Pro等主流剪辑工具",
    "Social Media Strategist": "制定LinkedIn与Twitter等多平台社媒策略，打造有影响力的专业形象",
    "Solution Engineer": "将技术咨询方案转化为可工作的GIS原型与概念验证，覆盖Esri及开源全栈技术。",
    "Spatial Data Engineer": "清洗并转换杂乱的地理空间数据为标准数据集，支持格式转换、投影重定义与自动化流水线。",
    "Spatial Data Scientist": "运用统计建模与空间计量分析，挖掘地理数据深层模式，揭示地图上看不到的洞察。",
    "Sprint Prioritizer": "专注于敏捷冲刺规划与功能优先级排序，通过数据驱动优化资源配置，最大化团队交付价值。",
    "Strategy Duel Agent": "运用博弈论与三十六计进行实时策略对决，以智谋推演辅助决策。",
    "Studio Operations": "优化工作室日常运营流程，协调资源分配，维护团队生产力与工作效率标准。",
    "Studio Producer": "统筹创意与技术项目及资源分配，管理多项目组合，对齐商业目标与创意愿景。",
    "Study Abroad Advisor": "全方位留学规划专家，涵盖选校与文书指导，为学子提供一站式出国申请服务。",
    "Supply Chain Strategist": "供应链管理与采购策略专家，立足中国制造生态打造高效稳健的可持续供应链。",
    "Support Responder": "专业客户支持专家，提供多渠道卓越服务，将每一次互动转化为积极的品牌体验。",
    "Tax Strategist": "制定税务优化策略，应对多司法管辖区合规与转让定价，在合法范围内降低税负。",
    "Technical Consultant": "将业务需求转化为GIS技术方案，提供差距分析、技术路线图与数字化转型策略。",
    "TikTok Strategist": "精通TikTok算法与爆款内容创作，助力品牌在短视频平台快速增长",
    "Tracking & Measurement Specialist": "转化追踪与归因建模专家，通过GTM、GA4等工具确保广告效果可衡量、每一分钱有迹可循。",
    "Trend Researcher": "专注市场情报分析，识别新兴趋势与竞争态势，提供战略洞见以驱动产品创新与决策。",
    "Twitter Engager": "通过实时互动与话题讨论在Twitter上建立品牌权威与影响力",
    "UI Designer": "UI设计专家，专精视觉设计体系、组件库与像素级完美界面的创建",
    "UX Architect": "技术与UX架构专家，为开发者提供稳固基础架构、CSS体系与清晰实现指引",
    "UX Researcher": "用户体验研究专家，专注用户行为分析、可用性测试与数据驱动设计洞察",
    "Video Optimization Specialist": "优化YouTube视频以提升观看时长与推荐流量，涵盖缩略图与章节设计",
    "Visual Storyteller": "视觉叙事专家，通过设计将复杂信息转化为引人入胜的品牌故事与多媒体内容",
    "WeChat Official Account Manager": "运营微信公众号，通过优质内容沉淀粉丝并实现商业转化",
    "Web GIS Developer": "构建交互式Web地图应用，集成MapLibre、ArcGIS JS API与Leaflet等前端框架及后端服务。",
    "Weibo Strategist": "玩转微博热搜与超话社区，通过粉丝经济助力品牌实现病毒式传播",
    "Whimsy Injector": "创意专家，为品牌体验注入个性与趣味，打造令人愉悦的差异化互动",
    "Workflow Architect": "工作流设计专家，绘制完整流程树并覆盖故障恢复，输出可直接实施的规格说明。",
    "X/Twitter Intelligence Analyst": "通过X/Twitter公开数据洞察趋势与受众，提供数据驱动的社交智能分析",
    "Xiaohongshu Specialist": "深耕小红书种草营销，通过精美内容与趋势策略实现品牌病毒式增长",
    "ZK Steward": "卢曼卡片盒理念的知识库管家，以原子化笔记和跨域决策支持助力知识体系建设。",
    "Zhihu Strategist": "在知乎构建专业领域影响力，通过高质量问答建立品牌信任与权威",
}

def _get_desc(en_name: str, raw_desc: str = "") -> str:
    """获取专家中文简介——优先使用人工翻译，无覆盖时回退到关键词替换。"""
    if en_name in _DESC_OVERRIDE:
        return _DESC_OVERRIDE[en_name]
    return _zh_desc(raw_desc) if raw_desc else ""

def _zh_name(en_name: str) -> str:
    """智能翻译 agent 英文名称为中文。"""
    if en_name in _NAME_OVERRIDE:
        return _NAME_OVERRIDE[en_name]
    # 专有名词 + 英文词替换
    parts: list[str] = []
    words = en_name.split()
    i = 0
    while i < len(words):
        matched = False
        for span in (3, 2):
            if i + span <= len(words):
                phrase = " ".join(words[i:i+span])
                found = _PLAT_ZH.get(phrase) or _ZH_MAP.get(phrase)
                if found:
                    parts.append(found); i += span; matched = True; break
        if matched:
            continue
        w = words[i]
        parts.append(_PLAT_ZH.get(w) or _ZH_MAP.get(w, w))
        i += 1
    # 最后一个原词是角色吗？（检查原始英文词，非翻译后的中文）
    last_original = words[-1] if words else ""
    if last_original in _ROLE_ZH:
        parts[-1] = _ROLE_ZH[last_original]
    return "".join(parts)

def _zh_desc(en_desc: str) -> str:
    """简化版英文描述翻译，按词边界替换关键词为中文（大小写不敏感）。"""
    if not en_desc:
        return ""
    import re as _re
    r = en_desc
    merged = {**_ZH_MAP, **_PLAT_ZH}
    # 按长度降序排列，优先匹配长词组；使用词边界避免 "or" 替换掉 "Store" 中的 "or"
    for en, cn in sorted(merged.items(), key=lambda x: -len(x[0])):
        if not en:
            continue
        flags = _re.IGNORECASE
        if not cn:
            # 空替换 → 删除该词及周围多余空格
            r = _re.sub(r'\b' + _re.escape(en) + r'\b\s*', '', r, flags=flags)
        elif ' ' in en or '-' in en:
            # 多词短语 → 大小写不敏感替换
            r = _re.sub(_re.escape(en), cn, r, flags=flags)
        else:
            # 单英文词 → 词边界替换，避免子串误伤
            r = _re.sub(r'\b' + _re.escape(en) + r'\b', cn, r, flags=flags)
    # 清理连续空格和标点前的多余空格
    r = _re.sub(r'\s{2,}', ' ', r)
    r = _re.sub(r'\s+([，。！？、；：）\)】\]》])', r'\1', r)
    r = _re.sub(r'([（\(【\[《])\s+', r'\1', r)
    # 去重连续逗号/句号
    r = _re.sub(r'，，+', '，', r)
    r = _re.sub(r'。。+', '。', r)
    return r.strip()


def _slug_from_filename(filename: str) -> str:
    return Path(filename).stem


def _scan_division(division: str) -> list[dict]:
    """扫描某个 division 目录下的所有 .md，返回专家摘要列表。"""
    d = AGENCY_ROOT / division
    if not d.is_dir():
        return []
    items = []
    for f in sorted(d.glob("*.md")):
        try:
            text = f.read_text(encoding="utf-8")
            meta, _body = _parse_frontmatter(text)
            raw_name = meta.get("name", _slug_from_filename(f.name))
            raw_desc = meta.get("description", "")
            raw_vibe = meta.get("vibe", "")
            items.append({
                "slug": _slug_from_filename(f.name),
                "name": _zh_name(raw_name),
                "description": _get_desc(raw_name, raw_desc),
                "emoji": meta.get("emoji", "🤖"),
                "color": meta.get("color", "#6366F1"),
                "vibe": _zh_desc(raw_vibe) if raw_vibe else "",
                "division": division,
            })
        except Exception as e:
            logger.debug("Skip %s: %s", f.name, e)
    return items


def _find_md(slug: str) -> Optional[tuple[str, Path]]:
    """按 slug 查找 .md 文件，返回 (division, path)。"""
    for division in RETAINED_DIVISIONS:
        p = AGENCY_ROOT / division / f"{slug}.md"
        if p.exists():
            return division, p
    return None


# ── 端点 ─────────────────────────────────────────────────────────────

@router.get("/divisions", response_model=list[Division])
async def list_divisions():
    """返回 11 个保留 Division 及其专家数量（内存缓存）。"""
    return [Division(**d) for d in _cache_divisions_list()]


@router.get("/agents", response_model=list[AgentSummary])
async def list_agents(division: Optional[str] = None, search: Optional[str] = None):
    """列出/搜索专家。倒排索引 O(1) 关键词查找。"""
    items = _cache_query(division, search)
    return [AgentSummary(**it) for it in items]


@router.get("/market-init")
async def market_init():
    """一次性返回 divisions + agents + active expert（减少 3 次 HTTP 往返）。"""
    _build_cache()
    return {
        "divisions": [Division(**d) for d in _cache_divisions],
        "agents": [AgentSummary(**a) for a in _cache_agents],
        "active": _cache_active_expert(),
    }


@router.get("/agents/{slug}", response_model=AgentDetail)
async def get_agent_detail(slug: str):
    """返回单个专家完整信息（含完整 system prompt 正文）。"""
    found = _find_md(slug)
    if not found:
        raise HTTPException(404, f"专家不存在: {slug}")
    division, path = found
    try:
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        div_meta = _DIVISIONS_META.get(division, {})
        return AgentDetail(
            slug=slug,
            name=_zh_name(meta.get("name", slug)),
            description=_get_desc(meta.get("name", slug), meta.get("description", "")),
            emoji=meta.get("emoji", "🤖"),
            color=meta.get("color", "#6366F1"),
            vibe=_zh_desc(meta.get("vibe", "")) if meta.get("vibe") else "",
            division=division,
            division_label=_DIVISION_CN.get(division, div_meta.get("label", division)),
            prompt=body,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"读取专家失败: {e}")


@router.get("/active", response_model=Optional[ActiveExpert])
async def get_active():
    """返回当前激活的专家（内存缓存，避免读磁盘）。"""
    cached = _cache_active_expert()
    if not cached:
        return None
    return ActiveExpert(**cached)


@router.post("/activate/{slug}")
async def activate_expert(slug: str):
    """激活专家：读取其完整 prompt 并设为当前对话的 system prompt。"""
    found = _find_md(slug)
    if not found:
        raise HTTPException(404, f"专家不存在: {slug}")
    division, path = found
    try:
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        raw_name = meta.get("name", slug)
        raw_desc = meta.get("description", "")
        expert = {
            "slug": slug,
            "name": _zh_name(raw_name),
            "description": _get_desc(raw_name, raw_desc),
            "emoji": meta.get("emoji", "🤖"),
            "division": division,
            "prompt": body,
        }
        agency_state.set_active_expert(expert)
        return {"ok": True, "expert": {"slug": slug, "name": expert["name"], "emoji": expert["emoji"], "prompt": body}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"激活专家失败: {e}")


@router.post("/deactivate")
async def deactivate_expert():
    """清除激活专家，恢复默认 Hermes Prompt。"""
    agency_state.clear_active_expert()
    return {"ok": True}




# ═══════════════════════════════════════════════════════════════════
# Marketplace 专属对话 API（每个对话绑定激活的专家）
# ═══════════════════════════════════════════════════════════════════

class AgencyMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    timestamp: float = 0.0


class AgencyConversation(BaseModel):
    id: str
    title: str
    expert_slug: str
    expert_name: str
    expert_emoji: str = "🤖"
    expert_division: str = ""
    messages: list[AgencyMessage] = []
    created_at: str = ""
    updated_at: str = ""


def _conv_path(conv_id: str) -> Path:
    return _AGENCY_CONV_DIR / f"{conv_id}.json"


def _load_conv(conv_id: str) -> dict | None:
    p = _conv_path(conv_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_conv(conv_id: str, data: dict) -> None:
    _conv_path(conv_id).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _list_convs() -> list[dict]:
    """列出所有对话，按更新时间倒序。"""
    items = []
    for f in sorted(
        _AGENCY_CONV_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    ):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return items


@router.get("/conversations", response_model=list[AgencyConversation])
async def list_agency_conversations():
    """列出 marketplace 所有历史对话（含专家信息）。"""
    return [AgencyConversation(**c) for c in _list_convs()]


@router.post("/conversations", response_model=AgencyConversation)
async def create_agency_conversation():
    """基于当前激活专家创建新对话。"""
    expert = agency_state.get_active_expert()
    if not expert:
        raise HTTPException(400, "请先激活一位专家")
    now = datetime.now(timezone.utc).isoformat()
    conv = {
        "id": uuid.uuid4().hex[:12],
        "title": expert.get("name", "专家"),
        "expert_slug": expert.get("slug", ""),
        "expert_name": expert.get("name", ""),
        "expert_emoji": expert.get("emoji", "🤖"),
        "expert_division": expert.get("division", ""),
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }
    _save_conv(conv["id"], conv)
    return AgencyConversation(**conv)


@router.get("/conversations/{conv_id}", response_model=AgencyConversation)
async def get_agency_conversation(conv_id: str):
    """获取单个对话详情（含消息列表）。"""
    c = _load_conv(conv_id)
    if not c:
        raise HTTPException(404, "对话不存在")
    return AgencyConversation(**c)


@router.post("/conversations/{conv_id}/messages")
async def append_agency_message(conv_id: str, msg: AgencyMessage):
    """向对话追加一条消息。"""
    c = _load_conv(conv_id)
    if not c:
        raise HTTPException(404, "对话不存在")
    c["messages"].append(msg.model_dump())
    c["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_conv(conv_id, c)
    return {"ok": True}


@router.delete("/conversations/{conv_id}")
async def delete_agency_conversation(conv_id: str):
    """删除对话。"""
    p = _conv_path(conv_id)
    if p.exists():
        p.unlink()
    return {"ok": True}
