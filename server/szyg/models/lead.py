"""Lead Profile — 线索数据模型。

竞品对标: 探迹B2B Agent / 销氪AIsales
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class IntentLevel(str, Enum):
    HIGH = "high"       # 🔥 高意向 — 问了价格/购买方式
    MEDIUM = "medium"   # 🔶 中意向 — 关注但未表达购买意图
    LOW = "low"         # 🔹 低意向 — 浏览/点赞
    COLD = "cold"       # ❄️ 冷线索 — 仅关注


class LeadSource(str, Enum):
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    KUAISHOU = "kuaishou"
    SHIPINHAO = "shipinhao"
    WECHAT = "wechat"
    WECOM = "wecom"
    MANUAL = "manual"
    API = "api"


class ConversionStage(str, Enum):
    DISCOVERED = "discovered"       # 发现
    ENGAGED = "engaged"             # 已互动
    CONTACTED = "contacted"         # 已触达
    QUALIFIED = "qualified"         # 已确认意向
    NEGOTIATING = "negotiating"     # 洽谈中
    WON = "won"                     # 已成交
    LOST = "lost"                   # 已流失


# ── 互动记录 ────────────────────────────────────────────

class Interaction(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    platform: LeadSource
    content: str
    interaction_type: str = "comment"  # comment, dm, like, follow, share
    ai_responded: bool = False
    ai_response: str | None = None


# ── 线索主模型 ───────────────────────────────────────────

class LeadProfile(BaseModel):
    id: str = Field(default_factory=lambda: f"lead_{datetime.utcnow().timestamp()}")
    name: str | None = None
    platform: LeadSource
    platform_account: str = ""       # 平台账号名
    company: str | None = None       # 推测的公司名
    industry: str | None = None      # 行业分类
    tags: list[str] = Field(default_factory=list)
    intent_score: float = Field(default=0.0, ge=0.0, le=1.0)
    intent_level: IntentLevel = IntentLevel.COLD
    conversion_stage: ConversionStage = ConversionStage.DISCOVERED
    interactions: list[Interaction] = Field(default_factory=list)
    source_content: str | None = None  # 触发线索的原始内容
    recommended_action: str | None = None  # AI推荐的下一步
    followup_deadline: datetime | None = None
    assigned_to: str | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── 线索搜索请求 ─────────────────────────────────────────

class LeadSearchRequest(BaseModel):
    industry: str | None = None
    intent_level: IntentLevel | None = None
    conversion_stage: ConversionStage | None = None
    platform: LeadSource | None = None
    tags: list[str] | None = None
    query: str | None = None         # FTS 文本搜索
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


# ── AI评分请求/响应 ──────────────────────────────────────

class IntentScoringRequest(BaseModel):
    platform: LeadSource
    interaction_content: str         # 用户评论/私信内容
    context: str | None = None       # 上下文（源内容标题/描述）
    user_history: list[str] | None = None  # 该用户历史互动


class IntentScoringResult(BaseModel):
    intent_score: float
    intent_level: IntentLevel
    intent_signals: list[str]        # 识别到的意向信号
    suggested_reply: str             # 建议回复话术
    should_follow_up: bool           # 是否需要跟进
    tags: list[str] = Field(default_factory=list)
