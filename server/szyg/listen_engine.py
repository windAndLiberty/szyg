"""
Listen Engine — 评论区舆情监听、情感分析、客户线索发现

核心能力:
  - 后台异步轮询目标视频的新评论
  - 关键词情感分析: positive / negative / question / lead
  - 客户线索自动识别与持久化
  - 回调机制: 新评论通知 / 线索通知
"""

import asyncio
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from szyg.data_path import DATA_DIR

logger = logging.getLogger(__name__)

# ── Sentiment Keywords ──────────────────────────────────────────────────

POSITIVE_KEYWORDS = [
    "不错", "很好", "厉害", "牛", "专业", "收藏", "学到了", "干货",
    "支持", "点赞", "关注", "喜欢", "推荐", "感谢", "谢谢", "太棒了",
    "有用", "实用", "好详细", "良心", "赞", "666", "优秀",
]

NEGATIVE_KEYWORDS = [
    "假的", "骗人", "垃圾", "坑", "不好", "差评", "失望", "没用",
    "浪费时间", "取关", "退订", "举报", "抄袭", "广告", "营销号",
]

LEAD_KEYWORDS = [
    "怎么买", "多少钱", "价格", "想学", "怎么做", "在哪里",
    "能不能", "可以吗", "求带", "带我", "联系", "咨询", "接单吗",
    "怎么联系", "私信你了", "私聊", "有什么渠道", "卖吗", "教程",
    "课程", "怎么报名", "想了解", "了解下", "渠道",
]

QUESTION_KEYWORDS = [
    "?", "？", "怎么", "什么", "为什么", "哪里", "哪个", "谁",
    "可以吗", "行吗", "对吗", "是吗", "能不能", "有没有",
    "如何", "请问", "求问", "想问", "问一下",
]


# ── Data Models ─────────────────────────────────────────────────────────

@dataclass
class MonitorTarget:
    """监听目标 (一个视频/帖子)"""
    target_id: str
    platform: str
    video_id: str = ""
    video_title: str = ""
    video_url: str = ""
    owner: str = "own"           # own = 自己视频 | competitor = 竞品
    last_comment_id: str = ""     # 最后一次拉取的评论ID，用于增量检测
    last_poll_at: str = ""
    poll_interval: int = 300      # 轮询间隔 (秒)
    enabled: bool = True
    created_at: str = ""
    metadata: dict = field(default_factory=dict)
    outbound_comment_id: str = ""
    outbound_comment_text: str = ""
    outbound_account_id: str = ""
    outbound_author_id: str = ""
    outbound_author_name: str = ""
    monitoring_mode: str = "content"
    seen_comment_ids: list[str] = field(default_factory=list)
    last_error: str = ""


@dataclass
class ListenComment:
    """监听到的评论"""
    comment_id: str
    platform: str
    video_id: str = ""
    video_title: str = ""
    author: str = ""
    author_id: str = ""
    content: str = ""
    likes: int = 0
    sentiment: str = "neutral"  # positive / negative / question / neutral
    is_lead: bool = False
    lead_score: int = 0
    captured_at: str = ""


@dataclass
class LeadRecord:
    """客户线索"""
    lead_id: str
    platform: str
    source_video_id: str = ""
    source_video_title: str = ""
    comment_id: str = ""
    comment_text: str = ""
    author_name: str = ""
    author_id: str = ""
    intent_type: str = ""        # purchase / inquiry / learning / collaboration
    intent_score: int = 0        # 0-100
    grade: str = "C"             # A/B/C/D
    status: str = "new"          # new | contacted | replied | qualified | converted
    discovered_at: str = ""
    last_updated: str = ""
    notes: str = ""


# ── Listen Engine ────────────────────────────────────────────────────────

class ListenEngine:
    """后台评论监听引擎"""

    MAX_LEADS = 1000

    def __init__(self):
        self._targets: dict[str, MonitorTarget] = {}
        self._leads: dict[str, LeadRecord] = {}
        self._poll_task: Optional[asyncio.Task] = None
        self._running = False
        self._lock = asyncio.Lock()

        # Callbacks
        self._new_comment_callbacks: list[Callable] = []
        self._new_lead_callbacks: list[Callable] = []

        self._load_targets()
        self._load_leads()

    # ── Target Management ──────────────────────────────────────────

    def _load_targets(self):
        path = DATA_DIR / "monitor_targets.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for item in data.get("targets", []):
                    t = MonitorTarget(**item)
                    self._targets[t.target_id] = t
                logger.info(f"ListenEngine loaded {len(self._targets)} targets")
            except Exception as e:
                logger.warning(f"Load targets failed: {e}")

    def _save_targets(self):
        path = DATA_DIR / "monitor_targets.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "targets": [t.__dict__ for t in self._targets.values()],
            "updated_at": datetime.now().isoformat(),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_leads(self):
        path = DATA_DIR / "leads.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for item in data.get("leads", []):
                    lead = LeadRecord(**item)
                    self._leads[lead.lead_id] = lead
                logger.info(f"ListenEngine loaded {len(self._leads)} leads")
            except Exception as e:
                logger.warning(f"Load leads failed: {e}")

    def _save_leads(self):
        path = DATA_DIR / "leads.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        # Rolling window
        leads = list(self._leads.values())[-self.MAX_LEADS:]
        data = {
            "leads": [l.__dict__ for l in leads],
            "total": len(leads),
            "updated_at": datetime.now().isoformat(),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    async def add_target(self, target: MonitorTarget) -> str:
        async with self._lock:
            if not target.target_id:
                import hashlib
                target.target_id = hashlib.md5(
                    f"{target.platform}{target.video_id}{datetime.now()}".encode()
                ).hexdigest()[:12]
            if not target.created_at:
                target.created_at = datetime.now().isoformat()
            self._targets[target.target_id] = target
            self._save_targets()
            return target.target_id

    async def remove_target(self, target_id: str):
        async with self._lock:
            self._targets.pop(target_id, None)
            self._save_targets()

    async def list_targets(self) -> list[dict]:
        return [
            {
                "target_id": t.target_id, "platform": t.platform,
                "video_title": t.video_title, "video_url": t.video_url,
                "owner": t.owner, "enabled": t.enabled,
                "last_poll_at": t.last_poll_at,
                "poll_interval": t.poll_interval,
                "outbound_comment_id": t.outbound_comment_id,
                "outbound_account_id": t.outbound_account_id,
                "monitoring_mode": t.monitoring_mode,
                "last_error": t.last_error,
            }
            for t in self._targets.values()
        ]

    async def get_target(self, target_id: str) -> Optional[dict]:
        t = self._targets.get(target_id)
        if t:
            return t.__dict__
        return None

    # ── Sentiment Analysis ─────────────────────────────────────────

    @staticmethod
    def analyze_sentiment(text: str) -> dict:
        """关键词情感分析"""
        scores = {"positive": 0, "negative": 0, "question": 0, "lead": 0}

        for kw in POSITIVE_KEYWORDS:
            if kw in text:
                scores["positive"] += 1

        for kw in NEGATIVE_KEYWORDS:
            if kw in text:
                scores["negative"] += 1

        for kw in QUESTION_KEYWORDS:
            if kw in text:
                scores["question"] += 1

        for kw in LEAD_KEYWORDS:
            if kw in text:
                scores["lead"] += 1

        # 确定主情感
        if scores["lead"] >= 2:
            sentiment, is_lead = "lead", True
        elif scores["question"] >= 1:
            sentiment, is_lead = "question", scores["lead"] >= 1
        elif scores["negative"] > scores["positive"]:
            sentiment, is_lead = "negative", False
        elif scores["positive"] > 0:
            sentiment, is_lead = "positive", scores["lead"] >= 1
        else:
            sentiment, is_lead = "neutral", False

        lead_score = min(100, scores["lead"] * 25 + scores["question"] * 10)

        return {
            "sentiment": sentiment,
            "is_lead": is_lead,
            "lead_score": lead_score,
            "scores": scores,
        }

    # ── Polling ────────────────────────────────────────────────────

    async def start(self, interval: int = 300):
        """启动后台轮询 (interval 秒)"""
        if self._running:
            return
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop(interval))
        logger.info(f"ListenEngine started (interval={interval}s)")

    async def stop(self):
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("ListenEngine stopped")

    async def _poll_loop(self, interval: int):
        while self._running:
            try:
                targets = [t for t in self._targets.values() if t.enabled]
                for target in targets:
                    try:
                        await self._poll_target(target)
                    except Exception as e:
                        logger.error(f"Poll {target.target_id} failed: {e}")
            except Exception as e:
                logger.error(f"Poll loop error: {e}")
            await asyncio.sleep(interval)

    async def _poll_target(self, target: MonitorTarget):
        """轮询单个目标的评论"""
        target.last_poll_at = datetime.now().isoformat()
        try:
            from szyg.integrations.acquisition_adapters import get_acquisition_adapter
            acq_adapter = get_acquisition_adapter(target.platform)
            if target.monitoring_mode == "reply_thread" or target.owner == "comment_campaign":
                if not target.outbound_comment_id:
                    target.last_error = "平台未返回评论ID，无法精确监听回复"
                    self._save_targets()
                    return
                comments_raw = await acq_adapter.get_comment_replies(
                    target.video_url,
                    target.outbound_comment_id,
                    limit=50,
                )
            else:
                comments_raw = await acq_adapter.get_comments(target.video_url, limit=50)
            target.last_error = ""
        except Exception as primary_error:
            logger.debug("AcquisitionAdapter comment read failed for %s: %s", target.platform, primary_error)
            if target.monitoring_mode == "reply_thread" or target.owner == "comment_campaign":
                target.last_error = f"精确回复读取失败：{str(primary_error)[:160]}"
                self._save_targets()
                return
            try:
                from szyg.platforms.registry import get_registry
                from szyg.publisher import Platform as PlatEnum

                p = PlatEnum(target.platform)
                registry = get_registry()
                if not registry.is_registered(p):
                    target.last_error = "平台评论读取能力未注册"
                    self._save_targets()
                    return
                adapter = await registry.get(p)
                comments_raw = await adapter.get_comments(target.video_url)
                target.last_error = ""
            except Exception as fallback_error:
                target.last_error = f"评论读取失败：{str(fallback_error)[:160]}"
                logger.error("Poll %s failed: %s", target.target_id, fallback_error)
                self._save_targets()
                return

        try:
            seen = set(target.seen_comment_ids or [])
            normalized = []
            for row in comments_raw or []:
                cid = str(row.get("comment_id") or row.get("id") or "")
                author_id = str(row.get("author_id") or "")
                author_name = str(row.get("author") or row.get("user_name") or "").strip()
                from_outbound_account = (
                    bool(target.outbound_author_id and author_id == target.outbound_author_id)
                    or bool(target.outbound_author_name and author_name == target.outbound_author_name)
                )
                if not cid or cid in seen or from_outbound_account:
                    continue
                normalized.append(row)

            for c in normalized:
                text = str(c.get("content") or c.get("text") or "").strip()
                if not text:
                    continue
                analysis = self.analyze_sentiment(text)
                comment = ListenComment(
                    comment_id=str(c.get("comment_id") or c.get("id") or ""),
                    platform=target.platform,
                    video_id=target.video_id,
                    video_title=target.video_title,
                    author=str(c.get("author") or c.get("user_name") or ""),
                    author_id=str(c.get("author_id") or ""),
                    content=text,
                    likes=int(c.get("likes", 0) or 0),
                    sentiment=analysis["sentiment"],
                    is_lead=analysis["is_lead"],
                    lead_score=analysis["lead_score"],
                    captured_at=datetime.now().isoformat(),
                )
                for callback in self._new_comment_callbacks:
                    try:
                        callback(comment)
                    except Exception as exc:
                        logger.warning("Comment callback failed: %s", exc)

                if analysis["is_lead"]:
                    import hashlib
                    score = analysis["lead_score"]
                    grade = "A" if score >= 75 else "B" if score >= 50 else "C" if score >= 25 else "D"
                    lead = LeadRecord(
                        lead_id=hashlib.md5(f"{target.target_id}{comment.comment_id}{comment.author_id or comment.author}".encode()).hexdigest()[:12],
                        platform=target.platform,
                        source_video_id=target.video_id,
                        source_video_title=target.video_title,
                        comment_id=comment.comment_id,
                        comment_text=text,
                        author_name=comment.author,
                        author_id=comment.author_id,
                        intent_type=self._classify_intent(text),
                        intent_score=score,
                        grade=grade,
                        status="new",
                        discovered_at=datetime.now().isoformat(),
                        last_updated=datetime.now().isoformat(),
                    )
                    async with self._lock:
                        self._leads[lead.lead_id] = lead
                        if len(self._leads) > self.MAX_LEADS:
                            for old in sorted(self._leads.values(), key=lambda item: item.discovered_at)[:100]:
                                self._leads.pop(old.lead_id, None)
                    self._save_leads()
                    for callback in self._new_lead_callbacks:
                        try:
                            callback(lead)
                        except Exception as exc:
                            logger.warning("Lead callback failed: %s", exc)

            fetched_ids = [str(row.get("comment_id") or row.get("id") or "") for row in comments_raw or []]
            target.seen_comment_ids = list(dict.fromkeys([*target.seen_comment_ids, *filter(None, fetched_ids)]))[-500:]
            if fetched_ids:
                target.last_comment_id = fetched_ids[0]
        except Exception as exc:
            target.last_error = f"回复分析失败：{str(exc)[:160]}"
            logger.error("Poll target %s analysis failed: %s", target.video_id, exc)
        finally:
            self._save_targets()

    @staticmethod
    def _classify_intent(text: str) -> str:
        if any(w in text for w in ["怎么买", "多少钱", "价格", "卖吗", "渠道"]):
            return "purchase"
        if any(w in text for w in ["想学", "怎么做", "教程", "课程", "报名"]):
            return "learning"
        if any(w in text for w in ["接单", "合作", "联系", "私聊"]):
            return "collaboration"
        if any(w in text for w in ["?", "？", "怎么", "什么"]):
            return "inquiry"
        return "inquiry"

    # ── Callbacks ─────────────────────────────────────────────────

    def on_new_comments(self, callback: Callable):
        self._new_comment_callbacks.append(callback)

    def on_leads(self, callback: Callable):
        self._new_lead_callbacks.append(callback)

    # ── Lead Management ───────────────────────────────────────────

    async def list_leads(self, status: str = "", grade: str = "",
                         platform: str = "", limit: int = 50) -> list[dict]:
        leads = list(self._leads.values())
        if status:
            leads = [l for l in leads if l.status == status]
        if grade:
            leads = [l for l in leads if l.grade == grade]
        if platform:
            leads = [l for l in leads if l.platform == platform]
        leads.sort(key=lambda l: l.discovered_at, reverse=True)
        return [l.__dict__ for l in leads[:limit]]

    async def update_lead(self, lead_id: str, **kwargs):
        async with self._lock:
            if lead_id in self._leads:
                for k, v in kwargs.items():
                    if hasattr(self._leads[lead_id], k):
                        setattr(self._leads[lead_id], k, v)
                self._leads[lead_id].last_updated = datetime.now().isoformat()
                self._save_leads()

    async def lead_stats(self) -> dict:
        leads = list(self._leads.values())
        by_status = defaultdict(int)
        by_grade = defaultdict(int)
        by_intent = defaultdict(int)
        for l in leads:
            by_status[l.status] += 1
            by_grade[l.grade] += 1
            by_intent[l.intent_type] += 1
        return {
            "total": len(leads),
            "by_status": dict(by_status),
            "by_grade": dict(by_grade),
            "by_intent": dict(by_intent),
        }


# ── Singleton ────────────────────────────────────────────────────────────

_listen_engine = None


def get_listen_engine() -> ListenEngine:
    global _listen_engine
    if _listen_engine is None:
        _listen_engine = ListenEngine()
    return _listen_engine
