"""
Comment Engine — 评论队列管理、频率控制、DeAI 去AI味、批量发送

核心能力:
  - CommentQueue: 评论队列持久化 (JSON file)
  - CommentRateLimiter: 小时+日双上限频率控制
  - DeAIProcessor: LLM 评论后处理，去除 AI 模板痕迹
  - batch_send / preflight_check 完整流水线
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from szyg.data_path import DATA_DIR

logger = logging.getLogger(__name__)

# ── Data Models ─────────────────────────────────────────────────────────

@dataclass
class CommentItem:
    """评论队列条目"""
    platform: str
    id: str = ""
    video_id: str = ""
    video_title: str = ""
    video_url: str = ""
    comment_text: str = ""
    original_text: str = ""  # deAI 之前的原始文本
    author_name: str = ""
    status: str = "pending"  # pending | sent | failed | skipped | auto_repaired | retrying | delayed | needs_human
    risk_level: str = "low"  # low | medium | high
    risk_codes: list[str] = field(default_factory=list)
    decision: str = ""
    repair_attempts: int = 0
    repaired_text: str = ""
    next_run_at: str = ""
    platform_result: dict = field(default_factory=dict)
    human_confirmed: bool = False
    strategy: str = "balanced"
    created_at: str = ""
    sent_at: str = ""
    error_msg: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class CommentStats:
    """评论统计"""
    total_pending: int = 0
    total_sent: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_auto_repaired: int = 0
    total_retrying: int = 0
    total_delayed: int = 0
    total_needs_human: int = 0
    by_platform: dict = field(default_factory=dict)
    hourly_used: dict = field(default_factory=dict)
    daily_used: dict = field(default_factory=dict)


# ── Comment Queue ────────────────────────────────────────────────────────

class CommentQueue:
    """持久化评论队列 (JSON 文件存储)"""

    MAX_ACTIVE_BATCHES = 300
    MAX_ARCHIVED_BATCHES = 3000
    ARCHIVE_RETENTION_DAYS = 180
    TERMINAL_STATUSES = {"sent", "failed", "skipped", "cancelled"}

    def __init__(self, storage_path: str = "", archive_path: str = ""):
        self._path = Path(storage_path) if storage_path else DATA_DIR / "comment_queue.json"
        self._archive_path = Path(archive_path) if archive_path else self._path.with_name("comment_queue_archive.json")
        self._items: dict[str, CommentItem] = {}
        self._lock = asyncio.Lock()
        self._load()
        self._prune_archive()
        if self._items:
            self._save()

    def _load(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for item_data in data.get("items", []):
                    item = CommentItem(**item_data)
                    self._items[item.id] = item
                logger.info(f"CommentQueue loaded {len(self._items)} items")
            except Exception as e:
                logger.warning(f"CommentQueue load failed: {e}")
                self._items = {}

    def _save(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._archive_terminal_batches()
            data = {
                "items": [item.__dict__ for item in self._items.values()],
                "updated_at": datetime.now().isoformat(),
            }
            self._write_json(self._path, data)
        except Exception as e:
            logger.error(f"CommentQueue save failed: {e}")

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    @staticmethod
    def _record_time(value: object) -> datetime:
        raw = ""
        if isinstance(value, CommentItem):
            raw = value.sent_at or value.created_at
        elif isinstance(value, dict):
            raw = str(value.get("sent_at") or value.get("created_at") or value.get("archived_at") or "")
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except (TypeError, ValueError):
            return datetime.min

    @staticmethod
    def _batch_key(value: object, fallback: str = "") -> str:
        if isinstance(value, CommentItem):
            metadata = value.metadata if isinstance(value.metadata, dict) else {}
            return str(metadata.get("batch_id") or f"single:{value.id or fallback}")
        if isinstance(value, dict):
            metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
            return str(value.get("batch_id") or metadata.get("batch_id") or f"single:{value.get('id') or fallback}")
        return f"single:{fallback}"

    def _read_archive_rows(self) -> list[dict]:
        if not self._archive_path.exists():
            return []
        try:
            payload = json.loads(self._archive_path.read_text(encoding="utf-8"))
            return [row for row in payload.get("items", []) if isinstance(row, dict)]
        except Exception as exc:
            logger.warning("Comment queue archive load failed: %s", exc)
            return []

    def _bounded_archive_rows(self, rows: list[dict]) -> list[dict]:
        cutoff = datetime.now() - timedelta(days=self.ARCHIVE_RETENTION_DAYS)
        groups: dict[str, list[dict]] = defaultdict(list)
        for index, row in enumerate(rows):
            groups[self._batch_key(row, str(index))].append(row)

        retained_groups = []
        for batch_id, batch_rows in groups.items():
            newest = max((self._record_time(row) for row in batch_rows), default=datetime.min)
            if newest >= cutoff:
                retained_groups.append((batch_id, newest, batch_rows))
        retained_groups.sort(key=lambda item: item[1], reverse=True)

        retained_rows: list[dict] = []
        for _batch_id, _newest, batch_rows in retained_groups[:self.MAX_ARCHIVED_BATCHES]:
            retained_rows.extend(batch_rows)
        retained_rows.sort(key=self._record_time, reverse=True)
        return retained_rows

    def _write_archive_rows(self, rows: list[dict]) -> None:
        bounded = self._bounded_archive_rows(rows)
        self._write_json(self._archive_path, {
            "items": bounded,
            "updated_at": datetime.now().isoformat(),
            "retention_days": self.ARCHIVE_RETENTION_DAYS,
            "batch_limit": self.MAX_ARCHIVED_BATCHES,
        })

    def _prune_archive(self) -> None:
        if not self._archive_path.exists():
            return
        try:
            self._write_archive_rows(self._read_archive_rows())
        except Exception as exc:
            logger.warning("Comment queue archive prune failed: %s", exc)

    def _archive_terminal_batches(self) -> None:
        groups: dict[str, list[CommentItem]] = defaultdict(list)
        for index, item in enumerate(self._items.values()):
            groups[self._batch_key(item, str(index))].append(item)

        active_groups = []
        terminal_groups = []
        for batch_id, batch_items in groups.items():
            newest = max((self._record_time(item) for item in batch_items), default=datetime.min)
            group = (batch_id, newest, batch_items)
            if any(item.status not in self.TERMINAL_STATUSES for item in batch_items):
                active_groups.append(group)
            else:
                terminal_groups.append(group)

        terminal_groups.sort(key=lambda item: item[1], reverse=True)
        terminal_capacity = max(0, self.MAX_ACTIVE_BATCHES - len(active_groups))
        archive_groups = terminal_groups[terminal_capacity:]
        if not archive_groups:
            return

        archived_at = datetime.now().isoformat()
        archived_ids = {item.id for _batch_id, _newest, batch_items in archive_groups for item in batch_items}
        archive_rows = self._read_archive_rows()
        for _batch_id, _newest, batch_items in archive_groups:
            for item in batch_items:
                row = dict(item.__dict__)
                row["batch_id"] = self._batch_key(item)
                row["archived_at"] = archived_at
                archive_rows.append(row)

        self._write_archive_rows(archive_rows)
        self._items = {item_id: item for item_id, item in self._items.items() if item_id not in archived_ids}

    async def add(self, item: CommentItem) -> str:
        async with self._lock:
            if not item.id:
                item.id = _short_id()
            if not item.created_at:
                item.created_at = datetime.now().isoformat()
            self._items[item.id] = item
            self._save()
            return item.id

    async def add_batch(self, items: list[CommentItem]) -> list[str]:
        ids = []
        async with self._lock:
            for item in items:
                if not item.id:
                    item.id = _short_id()
                if not item.created_at:
                    item.created_at = datetime.now().isoformat()
                self._items[item.id] = item
                ids.append(item.id)
            self._save()
        return ids

    async def update(self, item_id: str, **kwargs):
        async with self._lock:
            if item_id in self._items:
                for k, v in kwargs.items():
                    setattr(self._items[item_id], k, v)
                self._save()

    async def get(self, item_id: str) -> Optional[CommentItem]:
        return self._items.get(item_id)

    async def list(self, status: str = "", platform: str = "",
                   limit: int = 50, offset: int = 0) -> list[CommentItem]:
        items = list(self._items.values())
        if status:
            items = [i for i in items if i.status == status]
        if platform:
            items = [i for i in items if i.platform == platform]
        items.sort(key=lambda i: i.created_at, reverse=True)
        return items[offset:offset + limit]

    async def list_archived(self, status: str = "", platform: str = "",
                            limit: int = 50, offset: int = 0) -> list[dict]:
        items = self._read_archive_rows()
        if status:
            items = [item for item in items if item.get("status") == status]
        if platform:
            items = [item for item in items if item.get("platform") == platform]
        items.sort(key=self._record_time, reverse=True)
        return items[offset:offset + limit]

    def archive_stats(self) -> dict:
        items = self._read_archive_rows()
        batches = {self._batch_key(item, str(index)) for index, item in enumerate(items)}
        return {
            "total_items": len(items),
            "total_batches": len(batches),
            "batch_limit": self.MAX_ARCHIVED_BATCHES,
            "retention_days": self.ARCHIVE_RETENTION_DAYS,
        }

    async def due(self, limit: int = 20) -> list[CommentItem]:
        now = datetime.now()
        due_items: list[CommentItem] = []
        for item in self._items.values():
            if item.status not in {"delayed", "retrying"} or not item.next_run_at:
                continue
            if not item.human_confirmed:
                continue
            try:
                if datetime.fromisoformat(item.next_run_at) <= now:
                    due_items.append(item)
            except ValueError:
                due_items.append(item)
        due_items.sort(key=lambda i: i.next_run_at or i.created_at)
        return due_items[:limit]

    async def stats(self) -> CommentStats:
        items = list(self._items.values())
        s = CommentStats()
        by_platform = defaultdict(lambda: {
            "pending": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "auto_repaired": 0,
            "retrying": 0,
            "delayed": 0,
            "needs_human": 0,
        })
        for item in items:
            if item.decision == "auto_repair_then_send":
                s.total_auto_repaired += 1
                by_platform[item.platform]["auto_repaired"] = by_platform[item.platform].get("auto_repaired", 0) + 1
            if item.status == "pending":
                s.total_pending += 1
            elif item.status == "sent":
                s.total_sent += 1
            elif item.status == "failed":
                s.total_failed += 1
            elif item.status == "skipped":
                s.total_skipped += 1
            elif item.status == "retrying":
                s.total_retrying += 1
            elif item.status == "delayed":
                s.total_delayed += 1
            elif item.status == "needs_human":
                s.total_needs_human += 1
            by_platform[item.platform][item.status] = by_platform[item.platform].get(item.status, 0) + 1
        s.by_platform = dict(by_platform)
        return s

    async def delete(self, item_id: str):
        async with self._lock:
            self._items.pop(item_id, None)
            self._save()

    async def clear_sent(self):
        """清理已发送的历史记录"""
        async with self._lock:
            self._items = {k: v for k, v in self._items.items() if v.status != "sent"}
            self._save()


# ── Rate Limiter ─────────────────────────────────────────────────────────

class CommentRateLimiter:
    """评论频率限制器: 小时上限 + 日上限"""

    def __init__(self, storage_path: str = ""):
        self._path = Path(storage_path) if storage_path else DATA_DIR / "comment_rate_limits.json"
        self._hourly: dict[str, list[float]] = defaultdict(list)  # platform → [timestamps]
        self._daily: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # platform → date → count
        self._default_hourly = 8
        self._default_daily = 30
        self._hourly_limits: dict[str, int] = {}
        self._daily_limits: dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._hourly = defaultdict(list, {
                platform: [float(ts) for ts in timestamps]
                for platform, timestamps in data.get("hourly", {}).items()
            })
            self._daily = defaultdict(lambda: defaultdict(int), {
                platform: defaultdict(int, {date: int(count) for date, count in counts.items()})
                for platform, counts in data.get("daily", {}).items()
            })
            self._hourly_limits = {k: int(v) for k, v in data.get("hourly_limits", {}).items()}
            self._daily_limits = {k: int(v) for k, v in data.get("daily_limits", {}).items()}
        except Exception as e:
            logger.warning("CommentRateLimiter load failed: %s", e)

    def _save(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "hourly": {platform: list(timestamps) for platform, timestamps in self._hourly.items()},
                "daily": {platform: dict(counts) for platform, counts in self._daily.items()},
                "hourly_limits": dict(self._hourly_limits),
                "daily_limits": dict(self._daily_limits),
                "updated_at": datetime.now().isoformat(),
            }
            self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("CommentRateLimiter save failed: %s", e)

    def apply_strategy(self, strategy: str = "balanced"):
        """根据策略批量设置限制"""
        from szyg.platforms.anti_detect import BehaviorStrategy, STRATEGY_CONFIG
        try:
            st = BehaviorStrategy(strategy)
        except ValueError:
            st = BehaviorStrategy.BALANCED
        cfg = STRATEGY_CONFIG[st]
        for platform in ["douyin", "xhs", "bilibili", "kuaishou"]:
            self._hourly_limits[platform] = cfg["hourly_limit"]
            self._daily_limits[platform] = cfg["daily_limit"]
        self._save()

    async def can_send(self, platform: str) -> bool:
        async with self._lock:
            now = time.time()
            today = datetime.now().strftime("%Y-%m-%d")
            hourly_limit = self._hourly_limits.get(platform, self._default_hourly)
            daily_limit = self._daily_limits.get(platform, self._default_daily)

            # Clean old hourly entries
            self._hourly[platform] = [t for t in self._hourly[platform] if now - t < 3600]
            if len(self._hourly[platform]) >= hourly_limit:
                return False
            if self._daily[platform].get(today, 0) >= daily_limit:
                return False
            self._save()
            return True

    async def record(self, platform: str):
        async with self._lock:
            now = time.time()
            today = datetime.now().strftime("%Y-%m-%d")
            self._hourly[platform].append(now)
            self._daily[platform][today] += 1
            self._save()

    async def remaining(self, platform: str) -> dict:
        async with self._lock:
            now = time.time()
            today = datetime.now().strftime("%Y-%m-%d")
            hourly_limit = self._hourly_limits.get(platform, self._default_hourly)
            daily_limit = self._daily_limits.get(platform, self._default_daily)
            self._hourly[platform] = [t for t in self._hourly[platform] if now - t < 3600]
            self._save()
            return {
                "hourly_remaining": max(0, hourly_limit - len(self._hourly[platform])),
                "daily_remaining": max(0, daily_limit - self._daily[platform].get(today, 0)),
                "hourly_limit": hourly_limit,
                "daily_limit": daily_limit,
            }

    async def status(self) -> dict:
        result = {}
        for platform in ["douyin", "xhs", "bilibili", "kuaishou"]:
            r = await self.remaining(platform)
            result[platform] = r
        return result


_COMMENT_QUEUE: CommentQueue | None = None
_COMMENT_RATE_LIMITER: CommentRateLimiter | None = None


def get_comment_queue() -> CommentQueue:
    global _COMMENT_QUEUE
    if _COMMENT_QUEUE is None:
        _COMMENT_QUEUE = CommentQueue()
    return _COMMENT_QUEUE


def get_comment_rate_limiter() -> CommentRateLimiter:
    global _COMMENT_RATE_LIMITER
    if _COMMENT_RATE_LIMITER is None:
        _COMMENT_RATE_LIMITER = CommentRateLimiter()
    return _COMMENT_RATE_LIMITER


# ── DeAI Processor ───────────────────────────────────────────────────────

class DeAIProcessor:
    """去除 AI 模板痕迹，让评论更像真人"""

    # 常见 AI 模板句式 → 去除
    AI_PATTERNS = [
        (re.compile(r'^(当然|好的|没问题|可以的|是的|确实)[,，!！]?\s*'), ''),
        (re.compile(r'(总的来说|总而言之|综上所述|通过以上分析)[,，]?\s*'), ''),
        (re.compile(r'(值得注意的是|需要提醒的是|需要说明的是)[,，]?\s*'), ''),
        (re.compile(r'(毫无疑问|毋庸置疑|显而易见)[,，]?\s*'), ''),
        (re.compile(r'从(这个|该|本).*?(来看|出发|角度)'), ''),
        (re.compile(r'(我们可以看到|可以看出|可以发现|不难发现)'), ''),
        (re.compile(r'(在这里|在此|下面).*?(推荐|建议|分享|介绍)'), ''),
        (re.compile(r'(希望|但愿).*?(喜欢|有用|有帮助)'), ''),
        (re.compile(r'(欢迎|期待).*?(点赞|关注|评论|收藏|转发)'), ''),
        (re.compile(r'[!！]{3,}'), '!!'),
        (re.compile(r'[.。]{3,}'), '..'),
        (re.compile(r'~\s*~'), '~'),
        (re.compile(r'(非常|特别|极其|十分|格外)(地)?'), ''),
        (re.compile(r'(众所周知|大家都知道|我们都知道)[,，]?\s*'), ''),
        (re.compile(r'(友情提示|温馨提示|小贴士)[:：]?\s*'), ''),
    ]

    # 敏感营销词映射
    SENSITIVE_MAP = {
        "加微信": "聊一下",
        "加我微信": "可以私我",
        "扫码": "看看",
        "免费领取": "可以看看",
        "免费获取": "了解一下",
        "免费送": "分享了",
        "点击链接": "去瞅瞅",
        "链接在": "在",
        "联系方式": "方式",
        "加QQ": "交流",
        "免费咨询": "可以问问",
        "优惠券": "福利",
        "限时折扣": "活动",
        "原价": "本来",
        "立减": "少",
        "下单": "入手",
        "购买链接": "哪里",
        "立即购买": "去看看",
        "马上抢": "冲冲",
        "限量": "不多",
        "保证正品": "挺好的",
        "正品保障": "还行的",
        "官方授权": "听说",
        "爆款": "挺火",
        "销量第一": "很多人看",
        "全网最低": "挺划算",
    }

    # 平台语气词/表情
    PLATFORM_EMOJI = {
        "douyin": ["😂", "👍", "🤔", "👀", "💪", "🔥"],
        "xhs": ["✨", "💕", "🌟", "🥰", "😊", "📝"],
        "bilibili": ["😂", "www", "（", "doge", "👍"],
        "kuaishou": ["😂", "👍", "🔥", "💪", "👏"],
    }
    PLATFORM_TONE = {
        "douyin": ["说实话", "讲真", "就说一句", "真的"],
        "xhs": ["姐妹们", "亲测", "谁懂啊", "真的好"],
        "bilibili": ["有一说一", "u1s1", "确实", "笑死"],
        "kuaishou": ["老铁", "说实话", "就这", "真的"],
    }

    @classmethod
    def process(cls, text: str, platform: str = "douyin") -> str:
        """完整 DeAI 处理流水线"""
        if not text:
            return text
        result = text.strip()

        # 1. 去除 AI 模板痕迹
        result = cls._strip_patterns(result)

        # 2. 替换敏感营销词
        result = cls._replace_sensitive(result)

        # 3. 调整句式
        result = cls._adjust_structure(result)

        # 4. 添加真人语气
        result = cls._add_human_tone(result, platform)

        # 5. 长度随机化
        result = cls._randomize_length(result)

        return result.strip()

    @classmethod
    def _strip_patterns(cls, text: str) -> str:
        for pattern, replacement in cls.AI_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

    @classmethod
    def _replace_sensitive(cls, text: str) -> str:
        for word, replacement in cls.SENSITIVE_MAP.items():
            if word in text:
                text = text.replace(word, replacement)
        return text

    @classmethod
    def _adjust_structure(cls, text: str) -> str:
        # 长句拆分
        if len(text) > 50:
            parts = text.split("，")
            if len(parts) > 2:
                text = "，".join(parts[:2])

        # 去除过多的感叹号
        text = re.sub(r'[!！]{2,}', '!', text)

        # 被动转主动
        text = re.sub(r'被(.*?)(了|过)', r'\1了', text)

        return text

    @classmethod
    def _add_human_tone(cls, text: str, platform: str) -> str:
        emoji_list = cls.PLATFORM_EMOJI.get(platform, ["😂", "👍"])
        tone_list = cls.PLATFORM_TONE.get(platform, [])

        # 15% 概率加语气前缀
        if tone_list and random.random() < 0.15:
            text = random.choice(tone_list) + "，" + text

        # 40% 概率加 emoji
        if random.random() < 0.4:
            text = text + random.choice(emoji_list)

        return text

    @classmethod
    def _randomize_length(cls, text: str) -> str:
        """偶尔缩短一点"""
        if len(text) > 15 and random.random() < 0.2:
            cut = len(text) * 3 // 4
            text = text[:cut].rstrip("，。！!？?") + "…"
        return text


# ── Preflight Check ──────────────────────────────────────────────────────

BLOCKED_WORDS = ["微信", "QQ", "qq", "wx", "链接", "http", "电话", "手机号",
                  "加v", "加V", "V信", "vx", "WX", "扫码", "二维码"]

CONTACT_PATTERNS = [
    re.compile(r'1[3-9]\d{9}'),
    re.compile(r'(微信|微[信x]|vx|wx|v信|加v|加V|QQ|qq|电话|手机号|联系方式)', re.IGNORECASE),
]
REGULATED_CLAIMS = ["包过", "稳赚", "保本", "治愈", "根治", "官方认证", "全网最低", "第一名"]
MARKETING_WORDS = ["免费领取", "免费获取", "优惠券", "限时", "立减", "下单", "购买", "咨询", "私信我", "关注我"]
SENSITIVE_ACTION_WORDS = ["加好友", "加微信", "私信", "付款", "支付", "删除", "群发", "批量"]

REPAIRABLE_CODES = {
    "too_long",
    "too_short",
    "contains_url",
    "marketing_tone",
    "ai_like",
    "repeated_chars",
    "low_chinese_ratio",
}
HUMAN_REQUIRED_CODES = {
    "contains_contact",
    "regulated_claim",
    "sensitive_platform_action",
    "login_required",
    "captcha_required",
    "account_risk",
    "unknown_security_popup",
    "duplicate_uncertain",
}


class MarketingAutomationPolicy:
    """统一营销自动化决策，避免普通失败被误判为需人工。"""

    @staticmethod
    def decide(check: dict) -> dict:
        codes = set(check.get("risk_codes") or [])
        risk_level = check.get("risk_level", "low")
        if codes & HUMAN_REQUIRED_CODES:
            return {
                "decision": "needs_human",
                "status": "needs_human",
                "message": "包含需要人工确认的敏感动作或账号风险",
            }
        if check.get("pass"):
            return {"decision": "auto_send", "status": "pending", "message": "预检通过，可自动发送"}
        if codes and codes <= REPAIRABLE_CODES:
            return {
                "decision": "auto_repair_then_send",
                "status": "auto_repaired",
                "message": "存在可自动修复的问题",
            }
        if risk_level == "high":
            return {"decision": "skip", "status": "skipped", "message": "高风险但不需要人工，已跳过"}
        return {
            "decision": "auto_repair_then_send",
            "status": "auto_repaired",
            "message": "中风险内容会先自动修复",
        }

    @staticmethod
    def classify_send_error(error: str) -> dict:
        text = (error or "").lower()
        if any(word in text for word in ["登录", "未登录", "login", "cookie", "session"]):
            return {"decision": "needs_human", "status": "needs_human", "code": "login_required"}
        if any(word in text for word in ["验证码", "captcha", "风控", "账号异常", "安全验证", "risk"]):
            return {"decision": "needs_human", "status": "needs_human", "code": "account_risk"}
        if any(word in text for word in ["timeout", "超时", "未找到", "button", "selector", "network", "net::"]):
            return {"decision": "delay_retry", "status": "retrying", "code": "transient_platform_error"}
        if any(word in text for word in ["结果未确认", "send_unverified", "未标记为成功"]):
            return {"decision": "delay_retry", "status": "retrying", "code": "send_unverified"}
        return {"decision": "failed", "status": "failed", "code": "send_failed"}


def preflight_check(text: str) -> dict:
    """发前检查: 敏感词 / 长度 / 垃圾模式"""
    risks = []
    risk_codes: list[str] = []
    suggestions: list[str] = []
    raw_text = text or ""

    # 检查屏蔽词
    for word in BLOCKED_WORDS:
        if word.lower() in raw_text.lower():
            risks.append(f"包含屏蔽词: {word}")
            code = "contains_url" if word.lower() in {"链接", "http"} else "contains_contact"
            if code not in risk_codes:
                risk_codes.append(code)

    if re.search(r'https?://|www\.', raw_text, re.IGNORECASE):
        risks.append("包含 URL")
        if "contains_url" not in risk_codes:
            risk_codes.append("contains_url")

    if any(pattern.search(raw_text) for pattern in CONTACT_PATTERNS):
        risks.append("包含联系方式或引流表达")
        if "contains_contact" not in risk_codes:
            risk_codes.append("contains_contact")

    for word in REGULATED_CLAIMS:
        if word in raw_text:
            risks.append(f"包含强承诺或合规敏感词: {word}")
            if "regulated_claim" not in risk_codes:
                risk_codes.append("regulated_claim")

    if any(word in raw_text for word in SENSITIVE_ACTION_WORDS):
        risks.append("包含敏感平台动作")
        if "sensitive_platform_action" not in risk_codes:
            risk_codes.append("sensitive_platform_action")

    if any(word in raw_text for word in MARKETING_WORDS):
        risks.append("营销感偏强")
        if "marketing_tone" not in risk_codes:
            risk_codes.append("marketing_tone")

    # 长度检查
    if len(raw_text) < 2:
        risks.append("评论过短 (<2字符)")
        risk_codes.append("too_short")
    elif len(raw_text) > 200:
        risks.append("评论过长 (>200字符)")
        risk_codes.append("too_long")

    # 检查中文内容比例
    chinese_chars = len(re.findall(r'[一-鿿]', raw_text))
    total_chars = len(raw_text.replace(" ", ""))
    if total_chars > 0 and chinese_chars / total_chars < 0.3:
        risks.append("中文占比过低")
        risk_codes.append("low_chinese_ratio")

    # 重复字符检查 (灌水模式)
    if re.search(r'(.)\1{5,}', raw_text):
        risks.append("重复字符过多")
        risk_codes.append("repeated_chars")

    ai_markers = ["总的来说", "值得注意的是", "综上所述", "希望对你有帮助", "欢迎点赞关注"]
    if any(marker in raw_text for marker in ai_markers):
        risks.append("AI 模板感明显")
        risk_codes.append("ai_like")

    risk_level = "low"
    unique_codes = list(dict.fromkeys(risk_codes))
    if set(unique_codes) & HUMAN_REQUIRED_CODES:
        risk_level = "high"
    elif len(risks) >= 3:
        risk_level = "high"
    elif len(risks) >= 1:
        risk_level = "medium"

    if "too_long" in unique_codes:
        suggestions.append("压缩到 200 字以内")
    if "contains_url" in unique_codes:
        suggestions.append("删除链接，改为自然提示")
    if "marketing_tone" in unique_codes or "ai_like" in unique_codes:
        suggestions.append("改成真实用户口吻")

    result = {"pass": len(risks) == 0, "risk_level": risk_level, "risks": risks,
              "risk_codes": unique_codes, "suggestions": suggestions}
    result.update(MarketingAutomationPolicy.decide(result))
    return result


def repair_comment(text: str, platform: str = "douyin", max_length: int = 200) -> dict:
    """自动修复可恢复的评论风险，不处理需要人工确认的敏感内容。"""
    original = text or ""
    repaired = original.strip()
    changes: list[str] = []

    repaired = re.sub(r'https?://\S+|www\.\S+', '', repaired, flags=re.IGNORECASE).strip()
    if repaired != original.strip():
        changes.append("已删除链接")

    before = repaired
    repaired = DeAIProcessor.process(repaired, platform)
    if repaired != before:
        changes.append("已去除 AI 味和强营销表达")

    before = repaired
    repaired = re.sub(r'(.)\1{5,}', r'\1\1', repaired)
    if repaired != before:
        changes.append("已清理重复字符")

    if len(repaired) > max_length:
        repaired = repaired[:max_length].rstrip("，。！!？?；;、 ") + "…"
        changes.append("已压缩长度")

    if len(repaired) < 2:
        repaired = "这个挺有参考价值"
        changes.append("已补全过短评论")

    check = preflight_check(repaired)
    return {
        "original": original,
        "repaired": repaired,
        "changed": repaired != original,
        "changes": changes,
        "preflight": check,
    }


# ── Batch Send Pipeline ──────────────────────────────────────────────────

async def generate_comments_with_llm(
    video_title: str,
    video_desc: str = "",
    count: int = 3,
    strategy: str = "balanced",
    shared_across_targets: bool = False,
) -> list[str]:
    """Generate context-specific comments with the configured lightweight model."""
    from szyg.config.loader import load_config
    from szyg.integrations.volcengine_client import VolcEngineClient

    count = max(1, min(int(count or 3), 5))
    config = load_config()
    model = str(
        (config.get("marketing") or {}).get("comment_generation_model")
        or "doubao-seed-2-0-lite-260428"
    )

    shared_rules = """
批量共用规则:
- 输入包含多个目标视频，每条候选评论必须能原样用于全部目标
- 只围绕所有标题共同具备的主题表达，不引用只属于某一个视频的产品名、人物、情节或结论
- 不提“这几个视频”“以上内容”或目标数量，让评论放在任意单个评论区都自然
- 无法确认的细节宁可不写，严禁补充输入中没有的人物、时间、经历或观看情节
""" if shared_across_targets else ""
    grounding_rule = (
        "- 每条评论必须围绕多个标题共有的具体主题，不得挑选单个目标的独有细节"
        if shared_across_targets
        else "- 每条都必须引用标题或简介中的一个具体信息点"
    )

    prompt = f"""你正在为真实公开平台生成评论候选。只使用下面给出的本次输入，忽略任何无关人物、情节和先前话题。

为以下视频生成 {count} 条真人风格的评论区留言:

视频标题: {video_title}
视频简介: {video_desc or '无'}
策略: {strategy}

要求:
- 每条评论15-40字，简洁自然
- 像真实网友的口吻，不要AI腔
- 可以表达疑问、赞同、好奇、补充观点等
- 不要用"总的来说""值得注意的是"等模板句式
- 不要包含微信号/QQ/链接等引流内容

补充约束:
{grounding_rule}
- 各条评论的表达角度必须不同，不能只是替换近义词
- 不虚构没有提供的观看细节、使用体验或产品效果
- 禁止"收藏了"、"学到了"、"太有用了"等脱离内容也成立的万能评论
{shared_rules}

只返回包含恰好 {count} 条评论的 JSON：{{"comments":["评论1","评论2"]}}"""

    try:
        response = await VolcEngineClient(timeout=60).responses_text(
            [{
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }],
            model=model,
            max_output_tokens=800,
            reasoning_effort="minimal",
        )
        raw = str((response.get("message") or {}).get("content") or "").strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
        match = re.search(r"\{[\s\S]*\}", raw)
        payload = json.loads(match.group(0) if match else raw)
        comments = [str(item).strip() for item in payload.get("comments", []) if str(item).strip()]
        unique = list(dict.fromkeys(comments))
        if len(unique) < count:
            raise ValueError("模型返回的有效评论数量不足")
        return unique[:count]
    except Exception as e:
        logger.warning("Comment generation failed with %s: %s", model, e)
        raise RuntimeError("评论生成暂时不可用，请稍后重试") from e


async def _call_llm_direct(prompt: str, temperature: float = 0.85) -> str:
    """直接调用 LLM (兼容 Ollama / OpenRouter)"""
    import httpx
    from szyg.config.loader import load_config

    cfg = load_config()
    llm_cfg = cfg.get("llm", {}).get("openrouter", {}) or cfg.get("llm", {}).get("ollama", {})

    if not llm_cfg:
        raise RuntimeError("No LLM configured")

    base_url = llm_cfg.get("base_url", "http://localhost:11434/v1")
    api_key = llm_cfg.get("api_key", "ollama")
    model = llm_cfg.get("model", "qwen3")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 500,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _template_comments(title: str, count: int) -> list[str]:
    """模板生成评论 (无 LLM 时的备用方案)"""
    templates = [
        f"这个{title[:10]}讲得不错，学到了",
        "确实是这样，很有道理",
        "想问一下这个具体怎么操作？",
        "感谢分享，收藏了",
        "太有用了，正好需要这个",
        "哈哈笑死，太真实了",
        "收藏了，慢慢看",
        "评论区都说得好有道理",
        "第一次看到这么详细的分析👍",
        "这个观点有意思，关注了",
    ]
    random.shuffle(templates)
    return templates[:count]


async def batch_send(
    platform: str,
    comments: list[dict],
    strategy: str = "balanced",
    deai: bool = True,
    create_execution: bool = True,
) -> list[dict]:
    """批量发送评论完整流水线"""
    from szyg.platforms.registry import get_registry
    from szyg.publisher import Platform as PlatEnum

    limiter = get_comment_rate_limiter()
    limiter.apply_strategy(strategy)
    queue = get_comment_queue()
    results = []

    try:
        p = PlatEnum(platform)
    except ValueError:
        return [{
            "status": "failed",
            "decision": "failed",
            "risk_codes": ["unsupported_platform"],
            "error": f"Unsupported platform: {platform}",
        }]

    registry = get_registry()
    if not registry.is_registered(p):
        return [{
            "status": "failed",
            "decision": "failed",
            "risk_codes": ["unsupported_platform"],
            "error": f"Platform not registered: {platform}",
        }]

    adapter = await registry.get(p)

    # 尝试获取 AcquisitionAdapter 作为优先发送方式
    acq_adapter = None
    try:
        from szyg.integrations.acquisition_adapters import get_acquisition_adapter
        acq_adapter = get_acquisition_adapter(platform)
    except Exception as e:
        logger.debug("AcquisitionAdapter unavailable for %s: %s", platform, e)

    for comment_data in comments:
        text = comment_data.get("text", comment_data.get("comment_text", ""))
        original = text
        queue_item_id = str(comment_data.get("queue_item_id") or "")
        human_confirmed = bool(comment_data.get("human_confirmed"))
        execution = _start_marketing_execution(platform, comment_data, original) if create_execution else {}
        existing_item = await queue.get(queue_item_id) if queue_item_id else None
        base_metadata = dict(existing_item.metadata) if existing_item and isinstance(existing_item.metadata, dict) else {}
        if execution:
            base_metadata["execution_id"] = execution.get("run_id", "")
        validate_step = _execution_step(execution, "validate", "Validate marketing comment", "validate_comment")

        if not human_confirmed:
            item = CommentItem(
                id=queue_item_id,
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                video_title=comment_data.get("video_title", ""),
                video_url=comment_data.get("video_url", ""),
                comment_text=original,
                original_text=original,
                status="needs_human",
                risk_level="medium",
                risk_codes=["confirmation_required"],
                decision="needs_human",
                error_msg="发送前需要人工确认",
                human_confirmed=False,
                strategy=strategy,
                metadata=dict(base_metadata),
            )
            await queue.add(item)
            _finish_execution_step(execution, validate_step, "needs_human", item.error_msg, "confirmation_required")
            _complete_marketing_execution(
                execution,
                "needs_human",
                {"status": "needs_human", "queue_item_id": item.id},
                "confirmation_required",
                item.error_msg,
            )
            results.append({
                "id": item.id,
                "execution_id": execution.get("run_id", "") if execution else "",
                "status": "needs_human",
                "decision": "needs_human",
                "risk_codes": item.risk_codes,
                "reason": [item.error_msg],
            })
            continue

        original_check = preflight_check(original)
        if set(original_check.get("risk_codes") or []) & HUMAN_REQUIRED_CODES:
            _finish_execution_step(execution, validate_step, "needs_human", "敏感内容需要人工确认", "sensitive_action")
            item = CommentItem(
                id=queue_item_id,
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                video_title=comment_data.get("video_title", ""),
                video_url=comment_data.get("video_url", ""),
                comment_text=original,
                original_text=original,
                status="needs_human",
                risk_level=original_check["risk_level"],
                risk_codes=original_check.get("risk_codes", []),
                decision="needs_human",
                human_confirmed=human_confirmed,
                strategy=strategy,
                error_msg="; ".join(original_check["risks"]),
                metadata=dict(base_metadata),
            )
            await queue.add(item)
            _complete_marketing_execution(execution, "needs_human", {
                "status": "needs_human",
                "risk_codes": item.risk_codes,
                "queue_item_id": item.id,
            }, "sensitive_action", item.error_msg)
            results.append({
                "id": item.id,
                "execution_id": execution.get("run_id", "") if execution else "",
                "status": "needs_human",
                "decision": "needs_human",
                "risk_codes": item.risk_codes,
                "reason": original_check["risks"],
            })
            continue
        _finish_execution_step(execution, validate_step, "success", "评论原文安全意图已确认")

        # DeAI 处理
        repair_step = _execution_step(execution, "repair", "DeAI and repair comment", "repair_comment")
        if deai:
            text = DeAIProcessor.process(text, platform)

        # 发前检查
        check = preflight_check(text)
        repair_attempts = 0
        repair_info = None
        if check.get("decision") == "auto_repair_then_send":
            for _ in range(2):
                repair_attempts += 1
                repair_info = repair_comment(text, platform)
                text = repair_info["repaired"]
                check = repair_info["preflight"]
                if check.get("pass") or check.get("decision") != "auto_repair_then_send":
                    break
        _add_execution_observation(
            execution,
            repair_step,
            "text",
            f"修复次数：{repair_attempts}；决策：{check.get('decision', '')}",
        )
        _finish_execution_step(execution, repair_step, "success", "评论修复与预检完成")

        if check.get("decision") == "needs_human":
            _finish_execution_step(execution, None, "needs_human", "修复后仍需人工确认", "sensitive_action")
            item = CommentItem(
                id=queue_item_id,
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                video_title=comment_data.get("video_title", ""),
                video_url=comment_data.get("video_url", ""),
                comment_text=text,
                original_text=original,
                status="needs_human",
                risk_level=check["risk_level"],
                risk_codes=check.get("risk_codes", []),
                decision="needs_human",
                human_confirmed=human_confirmed,
                strategy=strategy,
                repair_attempts=repair_attempts,
                repaired_text=text if text != original else "",
                error_msg="; ".join(check["risks"]),
                metadata=dict(base_metadata),
            )
            await queue.add(item)
            _complete_marketing_execution(execution, "needs_human", {
                "status": "needs_human",
                "risk_codes": item.risk_codes,
                "queue_item_id": item.id,
            }, "sensitive_action", item.error_msg)
            results.append({
                "id": item.id,
                "execution_id": execution.get("run_id", "") if execution else "",
                "status": "needs_human",
                "decision": "needs_human",
                "risk_codes": item.risk_codes,
                "reason": check["risks"],
            })
            continue

        if check.get("decision") == "skip" or check["risk_level"] == "high":
            _finish_execution_step(execution, None, "success", "评论被自动跳过")
            item = CommentItem(
                id=queue_item_id,
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                video_title=comment_data.get("video_title", ""),
                video_url=comment_data.get("video_url", ""),
                comment_text=text,
                original_text=original,
                status="skipped",
                risk_level=check["risk_level"],
                risk_codes=check.get("risk_codes", []),
                decision="skip",
                human_confirmed=human_confirmed,
                strategy=strategy,
                repair_attempts=repair_attempts,
                repaired_text=text if text != original else "",
                error_msg="; ".join(check["risks"]),
                metadata=dict(base_metadata),
            )
            await queue.add(item)
            _complete_marketing_execution(execution, "success", {
                "status": "skipped",
                "risk_codes": item.risk_codes,
                "queue_item_id": item.id,
            })
            results.append({
                "id": item.id,
                "execution_id": execution.get("run_id", "") if execution else "",
                "status": "skipped",
                "decision": "skip",
                "risk_codes": item.risk_codes,
                "reason": check["risks"],
            })
            continue

        # 频率检查
        rate_step = _execution_step(execution, "rate_limit", "Check marketing rate limit", "rate_limit")
        if not await limiter.can_send(platform):
            next_run = (datetime.now() + timedelta(hours=1)).isoformat()
            _finish_execution_step(execution, rate_step, "success", "触发频率限制，已延后发送")
            item = CommentItem(
                id=queue_item_id,
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                video_title=comment_data.get("video_title", ""),
                video_url=comment_data.get("video_url", ""),
                comment_text=text,
                original_text=original,
                status="delayed",
                risk_level=check["risk_level"],
                risk_codes=check.get("risk_codes", []),
                decision="delay_retry",
                repair_attempts=repair_attempts,
                repaired_text=text if text != original else "",
                next_run_at=next_run,
                error_msg="Rate limit exceeded",
                human_confirmed=human_confirmed,
                strategy=strategy,
                metadata=dict(base_metadata),
            )
            await queue.add(item)
            _complete_marketing_execution(execution, "success", {
                "status": "delayed",
                "queue_item_id": item.id,
                "next_run_at": next_run,
            })
            results.append({
                "id": item.id,
                "execution_id": execution.get("run_id", "") if execution else "",
                "status": "delayed",
                "decision": "delay_retry",
                "reason": "Rate limit",
                "next_run_at": next_run,
            })
            continue
        _finish_execution_step(execution, rate_step, "success", "频率检查通过")

        # 发送 — 优先使用 AcquisitionAdapter
        send_step = _execution_step(execution, "send", "Send marketing comment", "send_comment")
        send_result: dict = {}
        try:
            send_result = {"success": True}
            if acq_adapter:
                send_result = await acq_adapter.send_comment(
                    video_url=comment_data.get("video_url", ""),
                    comment_text=text,
                )
                if not send_result.get("success", False):
                    raise Exception(send_result.get("error", "send failed"))
            else:
                await adapter.send_comment(
                    video_url=comment_data.get("video_url", ""),
                    comment_text=text,
                )
            await limiter.record(platform)
            item = CommentItem(
                id=queue_item_id,
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                video_title=comment_data.get("video_title", ""),
                video_url=comment_data.get("video_url", ""),
                comment_text=text,
                original_text=original,
                status="sent",
                risk_level=check["risk_level"],
                risk_codes=check.get("risk_codes", []),
                decision="auto_send" if repair_attempts == 0 else "auto_repair_then_send",
                human_confirmed=human_confirmed,
                repair_attempts=repair_attempts,
                repaired_text=text if text != original else "",
                platform_result=send_result if isinstance(send_result, dict) else {"result": str(send_result)},
                strategy=strategy,
                sent_at=datetime.now().isoformat(),
                metadata=dict(base_metadata),
            )
            await queue.add(item)
            _finish_execution_step(execution, send_step, "success", "评论已发送")
            _complete_marketing_execution(execution, "success", {
                "status": "sent",
                "queue_item_id": item.id,
                "decision": item.decision,
            })
            results.append({
                "id": item.id,
                "execution_id": execution.get("run_id", "") if execution else "",
                "status": "sent",
                "decision": item.decision,
                "repair_attempts": repair_attempts,
                "text": text[:50],
                "repaired_text": item.repaired_text,
                "repair_changes": (repair_info or {}).get("changes", []),
            })
        except Exception as e:
            error_text = str(e)[:200]
            explicit_status = str(send_result.get("status") or "")
            explicit_code = str(send_result.get("error_code") or "")
            if explicit_status == "needs_human":
                classified = {
                    "decision": "needs_human",
                    "status": "needs_human",
                    "code": explicit_code or "account_risk",
                }
            elif explicit_code == "send_unverified":
                classified = {
                    "decision": "delay_retry",
                    "status": "retrying",
                    "code": "send_unverified",
                }
            else:
                classified = MarketingAutomationPolicy.classify_send_error(error_text)
            status = classified["status"]
            next_run = (datetime.now() + timedelta(minutes=20)).isoformat() if status == "retrying" else ""
            risk_codes = check.get("risk_codes", [])
            if classified["code"] not in risk_codes:
                risk_codes = [*risk_codes, classified["code"]]
            item = CommentItem(
                id=queue_item_id,
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                video_title=comment_data.get("video_title", ""),
                video_url=comment_data.get("video_url", ""),
                comment_text=text,
                original_text=original,
                status=status,
                risk_level=check["risk_level"],
                risk_codes=risk_codes,
                decision=classified["decision"],
                human_confirmed=human_confirmed,
                strategy=strategy,
                repair_attempts=repair_attempts,
                repaired_text=text if text != original else "",
                next_run_at=next_run,
                error_msg=error_text,
                platform_result=send_result if isinstance(send_result, dict) else {},
                metadata=dict(base_metadata),
            )
            await queue.add(item)
            step_status = "needs_human" if status == "needs_human" else "failed"
            _finish_execution_step(execution, send_step, step_status, error_text, classified["code"])
            run_status = "needs_human" if status == "needs_human" else "failed"
            _complete_marketing_execution(execution, run_status, {
                "status": status,
                "queue_item_id": item.id,
                "next_run_at": next_run,
            }, classified["code"], error_text)
            results.append({
                "id": item.id,
                "execution_id": execution.get("run_id", "") if execution else "",
                "status": status,
                "decision": classified["decision"],
                "risk_codes": risk_codes,
                "next_run_at": next_run,
                "error": error_text[:100],
            })

        # 发送间隔
        await asyncio.sleep(random.uniform(3, 8))

    return results


async def process_due_comments(limit: int = 20, strategy: str = "balanced", deai: bool = True) -> dict:
    """Queue confirmed delayed/retrying items whose next_run_at has arrived."""
    queue = get_comment_queue()
    due_items = await queue.due(limit)
    processed: list[dict] = []
    for item in due_items:
        retry_count = int(item.metadata.get("retry_count", 0) or 0) + 1
        await queue.update(
            item.id,
            status="pending",
            metadata={**item.metadata, "retry_count": retry_count, "processing_started_at": datetime.now().isoformat()},
        )
        try:
            from szyg.execution_kernel import get_execution_kernel

            run = get_execution_kernel().create_marketing_comment_run({
                "platform": item.platform,
                "video_id": item.video_id,
                "video_title": item.video_title,
                "video_url": item.video_url,
                "text": item.comment_text,
                "queue_item_id": item.id,
                "human_confirmed": True,
                "strategy": item.strategy or strategy,
                "deai": deai,
            })
            await queue.update(
                item.id,
                status="pending",
                next_run_at="",
                metadata={
                    **item.metadata,
                    "execution_id": run["id"],
                    "retry_count": retry_count,
                    "last_retry_at": datetime.now().isoformat(),
                },
            )
            processed.append({"id": item.id, "status": "pending", "execution_id": run["id"]})
        except Exception as exc:
            error_text = str(exc)[:200]
            next_run = (datetime.now() + timedelta(minutes=20)).isoformat()
            await queue.update(
                item.id,
                status="retrying",
                next_run_at=next_run,
                error_msg=error_text,
                metadata={**item.metadata, "retry_count": retry_count, "last_retry_at": datetime.now().isoformat()},
            )
            processed.append({"id": item.id, "status": "retrying", "error": error_text, "next_run_at": next_run})
    return {"total_due": len(due_items), "processed": len(processed), "items": processed}


async def enqueue_confirmed_comment(
    platform: str,
    comment_data: dict,
    strategy: str = "balanced",
    deai: bool = False,
    delay_seconds: int = 0,
) -> dict:
    """Persist a confirmed comment before handing it to the execution kernel."""
    text = str(comment_data.get("text") or comment_data.get("comment_text") or "").strip()
    if not text:
        raise ValueError("评论内容不能为空")

    check = preflight_check(text)
    if check.get("decision") in {"needs_human", "skip"} or check.get("risk_level") == "high":
        raise ValueError("评论包含高风险内容，请修改后重新预检")

    queue = get_comment_queue()
    delay_seconds = max(0, int(delay_seconds or 0))
    delayed_until = (datetime.now() + timedelta(seconds=delay_seconds)).isoformat() if delay_seconds else ""
    item = CommentItem(
        platform=platform,
        video_id=str(comment_data.get("video_id") or ""),
        video_title=str(comment_data.get("video_title") or ""),
        video_url=str(comment_data.get("video_url") or ""),
        comment_text=text,
        original_text=text,
        status="delayed" if delay_seconds else "pending",
        risk_level=str(check.get("risk_level") or "low"),
        risk_codes=list(check.get("risk_codes") or []),
        decision=str(check.get("decision") or "auto_send"),
        human_confirmed=True,
        strategy=strategy,
        next_run_at=delayed_until,
        metadata={"batch_id": str(comment_data.get("batch_id") or "")},
    )
    await queue.add(item)

    if delay_seconds:
        return {
            "id": item.id,
            "execution_id": "",
            "status": "delayed",
            "next_run_at": delayed_until,
            "decision": item.decision,
            "risk_level": item.risk_level,
        }

    from szyg.execution_kernel import get_execution_kernel

    run = get_execution_kernel().create_marketing_comment_run({
        "platform": platform,
        "video_id": item.video_id,
        "video_title": item.video_title,
        "video_url": item.video_url,
        "text": text,
        "queue_item_id": item.id,
        "human_confirmed": True,
        "strategy": strategy,
        "deai": deai,
    })
    await queue.update(item.id, metadata={**item.metadata, "execution_id": run["id"]})
    return {
        "id": item.id,
        "execution_id": run["id"],
        "status": "pending",
        "decision": item.decision,
        "risk_level": item.risk_level,
    }


# ── Execution Kernel Bridge ──────────────────────────────────────────────

def _start_marketing_execution(platform: str, comment_data: dict, text: str) -> dict:
    """Create a lightweight observable execution run for outbound marketing actions."""
    try:
        from szyg.execution_kernel import get_execution_kernel

        kernel = get_execution_kernel()
        run = kernel.create_run(
            "marketing_comment",
            platform,
            "browser",
            {
                "platform": platform,
                "video_id": comment_data.get("video_id", ""),
                "video_title": comment_data.get("video_title", ""),
                "video_url": comment_data.get("video_url", ""),
                "text": text,
            },
            title=comment_data.get("video_title", "") or "营销评论外发",
            source_task_id="acquisition:",
            auto_start=False,
        )
        return {"kernel": kernel, "run_id": run["id"]}
    except Exception as exc:
        logger.debug("Marketing execution bridge unavailable: %s", exc)
        return {}


def _execution_step(execution: dict, step_id: str, name: str, action: str) -> dict | None:
    if not execution:
        return None
    try:
        return execution["kernel"].start_step(execution["run_id"], step_id, name, "browser", action)
    except Exception as exc:
        logger.debug("Marketing execution step failed: %s", exc)
        return None


def _add_execution_observation(execution: dict, step: dict | None, observation_type: str, summary: str) -> None:
    if not execution or not step:
        return
    try:
        execution["kernel"].add_observation(execution["run_id"], step["id"], observation_type, summary)
    except Exception as exc:
        logger.debug("Marketing execution observation failed: %s", exc)


def _finish_execution_step(
    execution: dict,
    step: dict | None,
    status: str,
    message: str,
    error_code: str = "",
) -> None:
    if not execution or not step:
        return
    try:
        execution["kernel"].finish_step(step, status, message, error_code=error_code)
    except Exception as exc:
        logger.debug("Marketing execution finish step failed: %s", exc)


def _complete_marketing_execution(
    execution: dict,
    status: str,
    result: dict,
    error_code: str = "",
    error_message: str = "",
) -> None:
    if not execution:
        return
    try:
        execution["kernel"].complete_run(execution["run_id"], status, result, error_code, error_message)
    except Exception as exc:
        logger.debug("Marketing execution complete failed: %s", exc)


# ── Utilities ────────────────────────────────────────────────────────────

def _short_id() -> str:
    return hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:10]
