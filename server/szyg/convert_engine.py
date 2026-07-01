"""
Convert Engine — 线索评分、自动回复、转化漏斗追踪

核心能力:
  - 四维线索评分: intent(40) + engagement(25) + urgency(20) + value(15)
  - A/B/C/D 等级分档及对应的跟进策略
  - 基于规则的智能自动回复模板
  - 转化漏斗: discovered→replied→dm_sent→responded→qualified→converted
  - 回复上下文记忆 (per-user conversation history)
"""

import asyncio
import hashlib
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from szyg.data_path import DATA_DIR

logger = logging.getLogger(__name__)


# ── Data Models ────────────────────────────────────────────────────────

@dataclass
class LeadScore:
    """线索评分"""
    lead_id: str
    intent_score: int = 0       # 0-40 意图强度
    engagement_score: int = 0    # 0-25 互动程度
    urgency_score: int = 0       # 0-20 紧迫度
    value_score: int = 0         # 0-15 用户价值
    total: int = 0               # 0-100
    grade: str = "C"             # A≥70, B≥45, C≥20, D<20
    scored_at: str = ""


@dataclass
class ReplyTemplate:
    """自动回复模板"""
    template_id: str
    intent_type: str             # link_request / price_inquiry / tutorial_request / appreciation / question / default
    trigger_keywords: list = field(default_factory=list)
    template: str = ""
    description: str = ""


@dataclass
class ConversionRecord:
    """转化记录"""
    record_id: str
    lead_id: str
    platform: str
    user_name: str = ""
    stage: str = "discovered"    # discovered→replied→dm_sent→responded→qualified→converted
    comment_text: str = ""
    reply_text: str = ""
    dm_text: str = ""
    notes: str = ""
    stage_updated_at: str = ""
    created_at: str = ""


@dataclass
class ReplyContext:
    """回复上下文 (per-user)"""
    user_key: str               # platform:user_name
    platform: str
    user_name: str
    history: list = field(default_factory=list)  # [{role, content, time}]
    last_reply_at: str = ""


# ── Convert Engine ──────────────────────────────────────────────────────

class ConvertEngine:
    """转化引擎: 评分 + 自动回复 + 漏斗追踪"""

    MAX_CONTEXTS = 5000

    def __init__(self):
        self._leads: dict[str, LeadScore] = {}
        self._conversions: dict[str, ConversionRecord] = {}
        self._contexts: dict[str, ReplyContext] = {}
        self._templates: list[ReplyTemplate] = []
        self._lock = asyncio.Lock()
        self._leads_path = DATA_DIR / "lead_scores.json"
        self._conversions_path = DATA_DIR / "conversions.json"
        self._context_path = DATA_DIR / "reply_context.json"

        self._init_templates()
        self._load()

    # ── Reply Templates ────────────────────────────────────────────

    def _init_templates(self):
        self._templates = [
            ReplyTemplate(
                template_id="link_request",
                intent_type="link_request",
                trigger_keywords=["在哪里", "怎么找", "链接", "去哪", "搜索什么", "在哪儿", "哪里看"],
                template="就在{platform_name}上搜「{hint}」就能找到啦～",
                description="用户问哪里能找到/链接",
            ),
            ReplyTemplate(
                template_id="price_inquiry",
                intent_type="price_inquiry",
                trigger_keywords=["多少钱", "价格", "收费", "费用", "贵不贵", "怎么收费", "划算吗"],
                template="具体可以了解一下哦，每个人需求不一样呢～",
                description="用户问价格",
            ),
            ReplyTemplate(
                template_id="tutorial_request",
                intent_type="tutorial_request",
                trigger_keywords=["怎么做", "教程", "怎么弄", "学习", "教", "能出教程", "求教程", "怎么学"],
                template="这个其实不难的，多练练就会了！有兴趣可以关注我，后面会出详细教程～",
                description="用户求教程",
            ),
            ReplyTemplate(
                template_id="appreciation",
                intent_type="appreciation",
                trigger_keywords=["谢谢", "感谢", "收藏", "好有用", "干货", "学到了", "太棒了", "赞"],
                template="谢谢支持！有需要可以随时问我😊",
                description="用户表示感谢/赞赏",
            ),
            ReplyTemplate(
                template_id="question",
                intent_type="question",
                trigger_keywords=["?", "？", "怎么", "什么", "为什么", "能不能", "可以吗", "是吗"],
                template="这个问题问得好！简单来说就是{answer_hint}，具体得看你的情况～",
                description="用户提问",
            ),
            ReplyTemplate(
                template_id="default",
                intent_type="default",
                trigger_keywords=[],
                template="说得对！👍",
                description="默认通用回复",
            ),
        ]

    # ── Lead Scoring ───────────────────────────────────────────────

    @staticmethod
    def score_lead(comment_text: str, author_name: str = "",
                   likes: int = 0, user_followers: int = 0) -> LeadScore:
        """
        四维线索评分:
          intent:     0-40 意图强度 (关键词匹配)
          engagement: 0-25 互动程度
          urgency:    0-20 紧迫度 (时间相关)
          value:      0-15 用户价值
        """
        lead_id = hashlib.md5(f"{comment_text}{author_name}{datetime.now()}".encode()).hexdigest()[:12]

        # 1. Intent (0-40)
        intent_kw = {
            "high": ["怎么买", "多少钱", "在哪买", "想买", "购买", "下单", "怎么联系", "接单吗"],
            "medium": ["想学", "教程", "怎么做", "怎么弄", "能教", "求带", "私信", "私聊"],
            "low": ["?", "？", "可以吗", "有没有", "推荐", "能告诉"],
        }
        intent = 0
        for kw in intent_kw["high"]:
            if kw in comment_text:
                intent += 8
        for kw in intent_kw["medium"]:
            if kw in comment_text:
                intent += 4
        for kw in intent_kw["low"]:
            if kw in comment_text:
                intent += 2
        intent = min(40, intent)

        # 2. Engagement (0-25)
        engagement = 0
        engagement += min(15, likes)  # 点赞
        if len(comment_text) > 30:
            engagement += 5  # 长评论
        if "?" in comment_text or "？" in comment_text:
            engagement += 5  # 提问
        engagement = min(25, engagement)

        # 3. Urgency (0-20)
        urgency_kw = ["现在", "马上", "立即", "急", "今天", "最快", "赶紧", "快点"]
        urgency = 0
        for kw in urgency_kw:
            if kw in comment_text:
                urgency += 5
        urgency = min(20, urgency)
        # Give base urgency
        if urgency == 0:
            urgency = 5

        # 4. Value (0-15)
        value = 5  # base
        if user_followers > 1000:
            value += 5  # 有影响力的用户
        if len(comment_text) > 50:
            value += 3  # 认真评论
        if author_name and not re.match(r'^[a-zA-Z0-9_]+$', author_name):
            value += 2  # 中文名用户 (更真实)
        value = min(15, value)

        total = intent + engagement + urgency + value

        # Grade
        if total >= 70:
            grade = "A"
        elif total >= 45:
            grade = "B"
        elif total >= 20:
            grade = "C"
        else:
            grade = "D"

        return LeadScore(
            lead_id=lead_id,
            intent_score=intent,
            engagement_score=engagement,
            urgency_score=urgency,
            value_score=value,
            total=total,
            grade=grade,
            scored_at=datetime.now().isoformat(),
        )

    # ── Auto Reply ────────────────────────────────────────────────

    def select_template(self, comment_text: str) -> ReplyTemplate:
        """根据评论内容选择回复模板"""
        for template in self._templates:
            if template.template_id == "default":
                continue
            for kw in template.trigger_keywords:
                if kw in comment_text:
                    return template
        return self._templates[-1]  # default

    def generate_reply(self, comment_text: str, author_name: str = "",
                       platform: str = "douyin", **kwargs) -> str:
        """生成自动回复"""
        template = self.select_template(comment_text)
        reply = template.template

        # 变量替换
        platform_names = {"douyin": "抖音", "xhs": "小红书", "bilibili": "B站", "kuaishou": "快手"}
        reply = reply.replace("{platform_name}", platform_names.get(platform, platform))
        reply = reply.replace("{hint}", kwargs.get("hint", "相关关键词"))

        if "{answer_hint}" in reply:
            reply = reply.replace("{answer_hint}", kwargs.get("answer_hint", "因人而异"))

        if author_name and random.random() < 0.3:
            reply = f"@{author_name} " + reply

        return reply

    async def auto_reply(self, comments: list[dict], platform: str = "douyin",
                         dry_run: bool = False) -> list[dict]:
        """对评论列表进行自动回复"""
        from szyg.platforms.registry import get_registry
        from szyg.publisher import Platform as PlatEnum

        import random as _random

        results = []
        try:
            p = PlatEnum(platform)
            registry = get_registry()
            if not registry.is_registered(p):
                return [{"error": f"Platform not registered: {platform}"}]
            adapter = await registry.get(p)
        except Exception as e:
            return [{"error": str(e)}]

        # 尝试获取 AcquisitionAdapter 作为优先发送方式
        acq_adapter = None
        try:
            from szyg.integrations.acquisition_adapters import get_acquisition_adapter
            acq_adapter = get_acquisition_adapter(platform)
        except Exception as e:
            logger.debug("AcquisitionAdapter unavailable for %s: %s", platform, e)

        for comment in comments:
            text = comment.get("content", comment.get("text", ""))
            author = comment.get("author", comment.get("user_name", ""))
            video_url = comment.get("video_url", "")

            # 评分
            score = self.score_lead(text, author)

            # 选择+生成回复
            reply = self.generate_reply(text, author, platform,
                                        hint=comment.get("hint", ""),
                                        answer_hint=comment.get("answer_hint", ""))

            result = {
                "comment_text": text[:80],
                "author": author,
                "lead_score": score.total,
                "grade": score.grade,
                "reply": reply,
                "sent": False,
            }

            if not dry_run and score.grade in ("A", "B"):
                try:
                    if acq_adapter:
                        send_result = await acq_adapter.send_comment(
                            video_url=video_url,
                            comment_text=reply,
                        )
                        if not send_result.get("success", False):
                            raise Exception(send_result.get("error", "send failed"))
                    else:
                        await adapter.send_comment(
                            video_url=video_url,
                            comment_text=reply,
                        )
                    result["sent"] = True
                    # Track conversion
                    await self.track_stage(score.lead_id, platform, "replied",
                                           comment_text=text, reply_text=reply)
                except Exception as e:
                    result["sent"] = False
                    result["error"] = str(e)[:100]

            # 更新回复上下文
            await self.update_context(platform, author, "assistant", reply)

            results.append(result)

            # Rate limit
            await asyncio.sleep(_random.uniform(5, 15))

        return results

    # ── Conversion Funnel ──────────────────────────────────────────

    async def track_stage(self, lead_id: str, platform: str, stage: str,
                          user_name: str = "", comment_text: str = "",
                          reply_text: str = "", dm_text: str = ""):
        """追踪转化阶段"""
        async with self._lock:
            rec = self._conversions.get(lead_id)
            if not rec:
                rec = ConversionRecord(
                    record_id=hashlib.md5(f"{lead_id}{platform}".encode()).hexdigest()[:10],
                    lead_id=lead_id,
                    platform=platform,
                    user_name=user_name,
                    stage=stage,
                    comment_text=comment_text,
                    reply_text=reply_text,
                    dm_text=dm_text,
                    stage_updated_at=datetime.now().isoformat(),
                    created_at=datetime.now().isoformat(),
                )
            else:
                rec.stage = stage
                rec.stage_updated_at = datetime.now().isoformat()
                if reply_text:
                    rec.reply_text = reply_text
                if dm_text:
                    rec.dm_text = dm_text

            self._conversions[lead_id] = rec
            self._save_conversions()

    async def get_funnel(self) -> dict:
        """获取转化漏斗统计"""
        stages = ["discovered", "replied", "dm_sent", "responded", "qualified", "converted"]
        counts = defaultdict(int)
        for rec in self._conversions.values():
            counts[rec.stage] += 1

        funnel = []
        for stage in stages:
            funnel.append({"stage": stage, "count": counts[stage]})
        return {
            "funnel": funnel,
            "total_leads": len(self._conversions),
            "conversion_rate": (counts["converted"] / max(1, len(self._conversions))) * 100,
        }

    async def list_conversions(self, stage: str = "", platform: str = "",
                               limit: int = 50) -> list[dict]:
        items = list(self._conversions.values())
        if stage:
            items = [i for i in items if i.stage == stage]
        if platform:
            items = [i for i in items if i.platform == platform]
        items.sort(key=lambda i: i.stage_updated_at, reverse=True)
        return [i.__dict__ for i in items[:limit]]

    # ── Reply Context ──────────────────────────────────────────────

    async def update_context(self, platform: str, user_name: str,
                             role: str, content: str):
        """更新回复上下文"""
        user_key = f"{platform}:{user_name}"
        async with self._lock:
            ctx = self._contexts.get(user_key)
            if not ctx:
                ctx = ReplyContext(user_key=user_key, platform=platform, user_name=user_name)
            ctx.history.append({"role": role, "content": content, "time": datetime.now().isoformat()})
            # Keep last 20 messages
            if len(ctx.history) > 20:
                ctx.history = ctx.history[-20:]
            ctx.last_reply_at = datetime.now().isoformat()
            self._contexts[user_key] = ctx

            # Cleanup old contexts
            if len(self._contexts) > self.MAX_CONTEXTS:
                sorted_ctx = sorted(self._contexts.values(),
                                    key=lambda c: c.last_reply_at or "")
                for old in sorted_ctx[:1000]:
                    self._contexts.pop(old.user_key, None)

            self._save_contexts()

    async def get_context(self, platform: str, user_name: str) -> Optional[dict]:
        ctx = self._contexts.get(f"{platform}:{user_name}")
        return ctx.__dict__ if ctx else None

    # ── Persistence ────────────────────────────────────────────────

    def _load(self):
        for path, target, cls in [
            (self._leads_path, self._leads, LeadScore),
            (self._context_path, self._contexts, ReplyContext),
        ]:
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    for item in data.get("items", []):
                        obj = cls(**item)
                        target[getattr(obj, list(item.keys())[0])] = obj
                except Exception as e:
                    logger.warning(f"Load {path} failed: {e}")

        # Load conversions separately (different key)
        if self._conversions_path.exists():
            try:
                data = json.loads(self._conversions_path.read_text(encoding="utf-8"))
                for item in data.get("items", []):
                    rec = ConversionRecord(**item)
                    self._conversions[rec.lead_id] = rec
            except Exception as e:
                logger.warning(f"Load conversions failed: {e}")

    def _save_conversions(self):
        self._save_json(self._conversions_path, list(self._conversions.values()))

    def _save_contexts(self):
        self._save_json(self._context_path, list(self._contexts.values()))

    def _save_leads(self):
        self._save_json(self._leads_path, list(self._leads.values()))

    def _save_json(self, path: Path, items: list):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {"items": [i.__dict__ for i in items], "updated_at": datetime.now().isoformat()}
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Save {path} failed: {e}")


# ── Singleton ────────────────────────────────────────────────────────────

_convert_engine = None


def get_convert_engine() -> ConvertEngine:
    global _convert_engine
    if _convert_engine is None:
        _convert_engine = ConvertEngine()
    return _convert_engine
