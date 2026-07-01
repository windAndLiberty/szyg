"""
Comment Engine — 评论队列管理、频率控制、DeAI 去AI味、批量发送

核心能力:
  - CommentQueue: 评论队列持久化 (JSON file)
  - CommentRateLimiter: 小时+日双上限频率控制
  - DeAIProcessor: LLM 评论后处理，去除 AI 模板痕迹
  - batch_send / preflight_check 完整流水线
"""

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
    id: str
    platform: str
    video_id: str = ""
    video_title: str = ""
    video_url: str = ""
    comment_text: str = ""
    original_text: str = ""  # deAI 之前的原始文本
    author_name: str = ""
    status: str = "pending"  # pending | sent | failed | skipped
    risk_level: str = "low"  # low | medium | high
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
    by_platform: dict = field(default_factory=dict)
    hourly_used: dict = field(default_factory=dict)
    daily_used: dict = field(default_factory=dict)


# ── Comment Queue ────────────────────────────────────────────────────────

class CommentQueue:
    """持久化评论队列 (JSON 文件存储)"""

    MAX_SIZE = 10000

    def __init__(self, storage_path: str = ""):
        self._path = Path(storage_path) if storage_path else DATA_DIR / "comment_queue.json"
        self._items: dict[str, CommentItem] = {}
        self._lock = asyncio.Lock()
        self._load()

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
            data = {
                "items": [item.__dict__ for item in list(self._items.values())[-self.MAX_SIZE:]],
                "updated_at": datetime.now().isoformat(),
            }
            self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"CommentQueue save failed: {e}")

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

    async def stats(self) -> CommentStats:
        items = list(self._items.values())
        s = CommentStats()
        by_platform = defaultdict(lambda: {"pending": 0, "sent": 0, "failed": 0, "skipped": 0})
        for item in items:
            if item.status == "pending":
                s.total_pending += 1
            elif item.status == "sent":
                s.total_sent += 1
            elif item.status == "failed":
                s.total_failed += 1
            elif item.status == "skipped":
                s.total_skipped += 1
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

    def __init__(self):
        self._hourly: dict[str, list[float]] = defaultdict(list)  # platform → [timestamps]
        self._daily: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))  # platform → date → count
        self._default_hourly = 8
        self._default_daily = 30
        self._hourly_limits: dict[str, int] = {}
        self._daily_limits: dict[str, int] = {}
        self._lock = asyncio.Lock()

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
            return True

    async def record(self, platform: str):
        async with self._lock:
            now = time.time()
            today = datetime.now().strftime("%Y-%m-%d")
            self._hourly[platform].append(now)
            self._daily[platform][today] += 1

    async def remaining(self, platform: str) -> dict:
        async with self._lock:
            now = time.time()
            today = datetime.now().strftime("%Y-%m-%d")
            hourly_limit = self._hourly_limits.get(platform, self._default_hourly)
            daily_limit = self._daily_limits.get(platform, self._default_daily)
            self._hourly[platform] = [t for t in self._hourly[platform] if now - t < 3600]
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


def preflight_check(text: str) -> dict:
    """发前检查: 敏感词 / 长度 / 垃圾模式"""
    risks = []

    # 检查屏蔽词
    for word in BLOCKED_WORDS:
        if word.lower() in text.lower():
            risks.append(f"包含屏蔽词: {word}")

    # 长度检查
    if len(text) < 2:
        risks.append("评论过短 (<2字符)")
    elif len(text) > 200:
        risks.append("评论过长 (>200字符)")

    # 检查 URL
    if re.search(r'https?://', text):
        risks.append("包含 URL")

    # 检查中文内容比例
    chinese_chars = len(re.findall(r'[一-鿿]', text))
    total_chars = len(text.replace(" ", ""))
    if total_chars > 0 and chinese_chars / total_chars < 0.3:
        risks.append("中文占比过低")

    # 重复字符检查 (灌水模式)
    if re.search(r'(.)\1{5,}', text):
        risks.append("重复字符过多")

    risk_level = "low"
    if len(risks) >= 3:
        risk_level = "high"
    elif len(risks) >= 1:
        risk_level = "medium"

    return {"pass": len(risks) == 0, "risk_level": risk_level, "risks": risks}


# ── Batch Send Pipeline ──────────────────────────────────────────────────

async def generate_comments_with_llm(
    video_title: str,
    video_desc: str = "",
    count: int = 3,
    strategy: str = "balanced",
) -> list[str]:
    """使用 LLM 生成评论 (通过 Hermes 内核)"""
    try:
        from szyg.api.hermes_chat import _call_llm_direct
    except ImportError:
        # Fallback: simple template-based generation
        return _template_comments(video_title, count)

    prompt = f"""为以下视频生成 {count} 条真人风格的评论区留言:

视频标题: {video_title}
视频简介: {video_desc or '无'}
策略: {strategy}

要求:
- 每条评论15-40字，简洁自然
- 像真实网友的口吻，不要AI腔
- 可以表达疑问、赞同、好奇、补充观点等
- 不要用"总的来说""值得注意的是"等模板句式
- 不要包含微信号/QQ/链接等引流内容

直接返回评论列表，每行一条，编号 1. 2. 3."""

    try:
        response = await _call_llm_direct(prompt, temperature=0.85)
        lines = []
        for line in response.strip().split("\n"):
            line = re.sub(r'^\d+[.、)\s]+', '', line).strip()
            if line and len(line) >= 5:
                lines.append(line)
        return lines[:count]
    except Exception as e:
        logger.warning(f"LLM generate failed: {e}, using template fallback")
        return _template_comments(video_title, count)


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
) -> list[dict]:
    """批量发送评论完整流水线"""
    from szyg.platforms.registry import get_registry
    from szyg.publisher import Platform as PlatEnum

    limiter = CommentRateLimiter()
    limiter.apply_strategy(strategy)
    queue = CommentQueue()
    results = []

    try:
        p = PlatEnum(platform)
    except ValueError:
        return [{"error": f"Unsupported platform: {platform}"}]

    registry = get_registry()
    if not registry.is_registered(p):
        return [{"error": f"Platform not registered: {platform}"}]

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

        # DeAI 处理
        original = text
        if deai:
            text = DeAIProcessor.process(text, platform)

        # 发前检查
        check = preflight_check(text)
        if check["risk_level"] == "high":
            item = CommentItem(
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                video_title=comment_data.get("video_title", ""),
                comment_text=text,
                original_text=original,
                status="skipped",
                risk_level="high",
                error_msg="; ".join(check["risks"]),
            )
            await queue.add(item)
            results.append({"id": item.id, "status": "skipped", "reason": check["risks"]})
            continue

        # 频率检查
        if not await limiter.can_send(platform):
            item = CommentItem(
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                comment_text=text,
                original_text=original,
                status="skipped",
                risk_level=check["risk_level"],
                error_msg="Rate limit exceeded",
            )
            await queue.add(item)
            results.append({"id": item.id, "status": "skipped", "reason": "Rate limit"})
            continue

        # 发送 — 优先使用 AcquisitionAdapter
        try:
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
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                video_title=comment_data.get("video_title", ""),
                comment_text=text,
                original_text=original,
                status="sent",
                risk_level=check["risk_level"],
                strategy=strategy,
                sent_at=datetime.now().isoformat(),
            )
            await queue.add(item)
            results.append({"id": item.id, "status": "sent", "text": text[:50]})
        except Exception as e:
            item = CommentItem(
                platform=platform,
                video_id=comment_data.get("video_id", ""),
                comment_text=text,
                original_text=original,
                status="failed",
                risk_level=check["risk_level"],
                error_msg=str(e)[:200],
            )
            await queue.add(item)
            results.append({"id": item.id, "status": "failed", "error": str(e)[:100]})

        # 发送间隔
        await asyncio.sleep(random.uniform(3, 8))

    return results


# ── Utilities ────────────────────────────────────────────────────────────

def _short_id() -> str:
    return hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:10]
