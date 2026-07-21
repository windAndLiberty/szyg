"""
Intercept Engine — 智能截流流水线: 搜索→筛选→质评→生成→发送

核心能力:
  - 多平台视频搜索聚合
  - 五维质量评分: engagement(30) + plays(25) + freshness(20) + author(15) + bonus(10)
  - A/B 测试策略对比
  - 去重管理 (commented_videos.json)
  - 一键截流流水线
"""

import asyncio
import hashlib
import json
import logging
import random
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
class VideoTarget:
    """搜索结果中的视频目标"""
    video_id: str
    platform: str
    title: str = ""
    description: str = ""
    author: str = ""
    author_followers: int = 0
    url: str = ""
    cover: str = ""
    plays: int = 0
    likes: int = 0
    comments_count: int = 0
    shares: int = 0
    favorites: int = 0
    coins: int = 0
    danmaku: int = 0
    author_id: str = ""
    author_profile_url: str = ""
    author_following: int = 0
    published_at: str = ""
    duration: int = 0
    tags: list = field(default_factory=list)
    quality_score: int = 0
    score_detail: dict = field(default_factory=dict)


@dataclass
class ABTestResult:
    """A/B 测试结果"""
    test_id: str
    strategy_a: str
    strategy_b: str
    platform: str
    video_count: int = 0
    results_a: dict = field(default_factory=lambda: {"sent": 0, "success": 0, "likes": 0, "replies": 0})
    results_b: dict = field(default_factory=lambda: {"sent": 0, "success": 0, "likes": 0, "replies": 0})
    winner: str = ""  # "A" | "B" | "tie"
    started_at: str = ""
    ended_at: str = ""
    status: str = "running"


@dataclass
class SearchResult:
    """搜索结果聚合"""
    platform: str
    keyword: str
    videos: list = field(default_factory=list)
    total: int = 0
    searched_at: str = ""


# ── Intercept Engine ─────────────────────────────────────────────────────

class InterceptEngine:
    """智能截流引擎"""

    MAX_HISTORY = 10000
    DEDUP_WINDOW_DAYS = 90

    def __init__(self):
        self._history: set = set()       # set of "platform:video_id"
        self._history_path = DATA_DIR / "commented_videos.json"
        self._targets_path = DATA_DIR / "intercept_targets.json"
        self._ab_results_path = DATA_DIR / "ab_results.json"
        self._ab_tests: dict[str, ABTestResult] = {}
        self._lock = asyncio.Lock()
        self._load_history()
        self._load_ab_results()

    # ── History / Dedup ───────────────────────────────────────────

    def _load_history(self):
        if self._history_path.exists():
            try:
                data = json.loads(self._history_path.read_text(encoding="utf-8"))
                entries = data.get("commented", [])
                for entry in entries:
                    self._history.add(f"{entry.get('platform')}:{entry.get('video_id')}")
                logger.info(f"InterceptEngine loaded {len(self._history)} history entries")
            except Exception as e:
                logger.warning(f"Load history failed: {e}")

    def _save_history(self):
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            entries = []
            for h in list(self._history)[-self.MAX_HISTORY:]:
                parts = h.split(":", 1)
                entries.append({"platform": parts[0], "video_id": parts[1] if len(parts) > 1 else ""})
            data = {"commented": entries, "updated_at": datetime.now().isoformat()}
            self._history_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Save history failed: {e}")

    def is_duplicate(self, platform: str, video_id: str) -> bool:
        return f"{platform}:{video_id}" in self._history

    async def mark_commented(self, platform: str, video_id: str):
        async with self._lock:
            self._history.add(f"{platform}:{video_id}")
            if len(self._history) > self.MAX_HISTORY:
                # Remove oldest (set doesn't maintain order, so take first N)
                keep = list(self._history)[-self.MAX_HISTORY:]
                self._history = set(keep)
            self._save_history()

    async def history_count(self) -> int:
        return len(self._history)

    # ── Quality Scoring ──────────────────────────────────────────

    @staticmethod
    def score_video(video: VideoTarget) -> int:
        """
        五维质量评分:
          engagement: 0-30分 (likes+comments+shares / plays 比率)
          plays:      0-25分 (播放量)
          freshness:  0-20分 (发布时间)
          author:     0-15分 (粉丝量)
          bonus:      0-10分 (额外加分)
        """
        detail = {}
        total = 0

        # 1. Engagement (0-30)
        if video.plays > 0:
            eng_rate = (video.likes + video.comments_count * 2 + video.shares * 3) / video.plays
            eng_score = min(30, int(eng_rate * 300))
        else:
            eng_score = min(30, (video.likes + video.comments_count + video.shares) // 10)
        detail["engagement"] = eng_score
        total += eng_score

        # 2. Plays (0-25)
        if video.plays > 100000:
            plays_score = 25
        elif video.plays > 50000:
            plays_score = 20
        elif video.plays > 10000:
            plays_score = 15
        elif video.plays > 1000:
            plays_score = 10
        elif video.plays > 100:
            plays_score = 5
        else:
            plays_score = 2
        detail["plays"] = plays_score
        total += plays_score

        # 3. Freshness (0-20)
        try:
            pub_date = datetime.fromisoformat(video.published_at.replace("Z", "+00:00"))
            hours_ago = (datetime.now().astimezone() - pub_date.replace(tzinfo=None)).total_seconds() / 3600
            if hours_ago < 1:
                fresh_score = 20
            elif hours_ago < 6:
                fresh_score = 18
            elif hours_ago < 24:
                fresh_score = 15
            elif hours_ago < 72:
                fresh_score = 10
            elif hours_ago < 168:  # 7 days
                fresh_score = 5
            else:
                fresh_score = 1
        except Exception:
            fresh_score = 8
        detail["freshness"] = fresh_score
        total += fresh_score

        # 4. Author size (0-15) — prefer smaller creators (easier to stand out)
        if 0 < video.author_followers < 1000:
            author_score = 15
        elif video.author_followers < 5000:
            author_score = 12
        elif video.author_followers < 50000:
            author_score = 8
        elif video.author_followers < 500000:
            author_score = 4
        elif video.author_followers == 0:
            author_score = 8  # unknown
        else:
            author_score = 1
        detail["author"] = author_score
        total += author_score

        # 5. Bonus (0-10): title relevance, has comments, etc.
        bonus = 0
        if video.comments_count > 0:
            bonus += 3  # already has discussion
        if video.comments_count < 50:
            bonus += 3  # not flooded yet
        if video.likes > 0 and video.plays > 0 and video.likes / max(1, video.plays) > 0.03:
            bonus += 2  # good like rate
        if video.description and len(video.description) > 20:
            bonus += 2  # has description
        detail["bonus"] = min(10, bonus)
        total += min(10, bonus)

        video.quality_score = total
        video.score_detail = detail
        return total

    # ── Multi-platform Search ─────────────────────────────────────

    async def search(self, keyword: str, platforms: list[str] = None,
                     limit: int = 20, strict_dedup: bool = True) -> list[SearchResult]:
        """多平台搜索聚合"""
        if platforms is None:
            platforms = ["douyin", "xhs", "bilibili", "kuaishou"]

        results = []
        for plat_name in platforms:
            try:
                videos = await self._search_platform(plat_name, keyword, limit)
                # Dedup + score
                scored = []
                for v_data in videos:
                    vid = v_data.get("video_id", v_data.get("id", ""))
                    if not str(vid or "").strip():
                        logger.debug("Skip non-commentable %s result without video id: %s", plat_name, v_data.get("url", ""))
                        continue
                    if strict_dedup and self.is_duplicate(plat_name, vid):
                        continue
                    target = VideoTarget(
                        video_id=vid,
                        platform=plat_name,
                        title=v_data.get("title", ""),
                        description=v_data.get("description", v_data.get("desc", "")),
                        author=v_data.get("author", v_data.get("author_name", "")),
                        author_followers=int(v_data.get("author_followers", 0)),
                        url=v_data.get("url", ""),
                        cover=v_data.get("cover", ""),
                        plays=int(v_data.get("plays", v_data.get("view_count", 0))),
                        likes=int(v_data.get("likes", v_data.get("like_count", 0))),
                        comments_count=int(v_data.get("comments_count", v_data.get("comments", v_data.get("comment_count", 0)))),
                        shares=int(v_data.get("shares", v_data.get("share_count", 0))),
                        favorites=int(v_data.get("favorites", v_data.get("favorite", 0))),
                        coins=int(v_data.get("coins", v_data.get("coin", 0))),
                        danmaku=int(v_data.get("danmaku", 0)),
                        author_id=str(v_data.get("author_id", v_data.get("mid", ""))),
                        author_profile_url=str(v_data.get("author_profile_url", "")),
                        author_following=int(v_data.get("author_following", 0)),
                        published_at=v_data.get("published_at", v_data.get("publish_time", "")),
                        duration=int(v_data.get("duration", 0)),
                        tags=v_data.get("tags", []),
                    )
                    self.score_video(target)
                    scored.append(target)

                # Sort by quality score descending
                scored.sort(key=lambda v: v.quality_score, reverse=True)

                results.append(SearchResult(
                    platform=plat_name,
                    keyword=keyword,
                    videos=scored[:limit],
                    total=len(scored),
                    searched_at=datetime.now().isoformat(),
                ))
            except Exception as e:
                logger.error(f"Search {plat_name} failed: {e}")
                results.append(SearchResult(
                    platform=plat_name, keyword=keyword,
                    searched_at=datetime.now().isoformat(),
                ))

        return results

    async def _search_platform(self, platform: str, keyword: str, limit: int) -> list[dict]:
        """调用平台适配器搜索 — 优先使用 AcquisitionAdapter，fallback 到平台适配器"""
        # 优先使用 AcquisitionAdapter (集成开源库)
        try:
            from szyg.integrations.acquisition_adapters import get_acquisition_adapter
            acq_adapter = get_acquisition_adapter(platform)
            results = await acq_adapter.search(keyword, limit=limit)
            if results:
                return results
        except Exception as e:
            logger.debug(f"AcquisitionAdapter search for {platform} failed, trying platform adapter: {e}")

        # Fallback: 使用平台适配器
        try:
            from szyg.platforms.registry import get_registry
            from szyg.publisher import Platform as PlatEnum

            p = PlatEnum(platform)
            registry = get_registry()
            if not registry.is_registered(p):
                logger.warning(f"Platform {platform} not registered, returning empty")
                return []

            adapter = await registry.get(p)
            if not hasattr(adapter, 'search'):
                logger.warning(f"Platform {platform} adapter has no search() method")
                return []

            results = await adapter.search(keyword, limit=limit)
            return results if isinstance(results, list) else []
        except ValueError:
            logger.warning(f"Unknown platform: {platform}")
            return []
        except Exception as e:
            logger.error(f"Search {platform} error: {e}")
            return []

    # ── Intercept Pipeline ─────────────────────────────────────────

    async def find_targets(self, keyword: str, platforms: list[str] = None,
                           min_score: int = 40, limit: int = 20) -> list[VideoTarget]:
        """搜索→筛选→去重→质评→排序→Top-N"""
        search_results = await self.search(keyword, platforms, limit * 2)
        all_videos = []
        for sr in search_results:
            all_videos.extend(sr.videos)

        # Filter by quality
        qualified = [v for v in all_videos if v.quality_score >= min_score]

        # Dedup by video_id
        seen = set()
        unique = []
        for v in qualified:
            key = f"{v.platform}:{v.video_id}"
            if key not in seen:
                seen.add(key)
                unique.append(v)

        # Sort by quality score
        unique.sort(key=lambda v: v.quality_score, reverse=True)
        return unique[:limit]

    async def run_pipeline(self, keyword: str, platforms: list[str] = None,
                           comment_count: int = 5, strategy: str = "balanced",
                           deai: bool = True, confirmed: bool = False) -> dict:
        """一键截流流水线: 搜索→筛选→生成→DeAI→发送"""
        from szyg.comment_engine import generate_comments_with_llm, batch_send, DeAIProcessor

        # 1. Find targets
        targets = await self.find_targets(keyword, platforms, min_score=35, limit=10)
        if not targets:
            return {"ok": False, "message": "No qualified targets found", "targets": []}

        # 2. For each target: generate + send comments
        all_results = []
        for target in targets:
            # Generate comments
            raw_comments = await generate_comments_with_llm(
                target.title, target.description, comment_count, strategy
            )

            # Prepare comment data
            comments_data = [
                {
                    "text": c,
                    "video_id": target.video_id,
                    "video_title": target.title,
                    "video_url": target.url,
                    "human_confirmed": confirmed,
                }
                for c in raw_comments
            ]

            # Batch send
            send_results = await batch_send(target.platform, comments_data, strategy, deai)

            # Mark as commented
            for r in send_results:
                if r.get("status") == "sent":
                    await self.mark_commented(target.platform, target.video_id)

            all_results.append({
                "video_id": target.video_id,
                "platform": target.platform,
                "title": target.title[:50],
                "quality_score": target.quality_score,
                "comments_sent": len([r for r in send_results if r["status"] == "sent"]),
                "comments_failed": len([r for r in send_results if r["status"] == "failed"]),
                "comments_skipped": len([r for r in send_results if r["status"] == "skipped"]),
                "comments_delayed": len([r for r in send_results if r["status"] == "delayed"]),
                "comments_retrying": len([r for r in send_results if r["status"] == "retrying"]),
                "comments_needs_human": len([r for r in send_results if r["status"] == "needs_human"]),
            })

            # Delay between targets
            await asyncio.sleep(random.uniform(10, 30))

        total_sent = sum(r["comments_sent"] for r in all_results)
        return {
            "ok": True,
            "keyword": keyword,
            "targets_found": len(targets),
            "total_comments_sent": total_sent,
            "details": all_results,
        }

    # ── A/B Testing ────────────────────────────────────────────────

    async def start_ab_test(self, strategy_a: str, strategy_b: str,
                            platform: str = "douyin", video_count: int = 10) -> ABTestResult:
        test_id = hashlib.md5(f"ab_{time.time()}_{random.random()}".encode()).hexdigest()[:12]
        test = ABTestResult(
            test_id=test_id,
            strategy_a=strategy_a,
            strategy_b=strategy_b,
            platform=platform,
            video_count=video_count,
            started_at=datetime.now().isoformat(),
        )
        async with self._lock:
            self._ab_tests[test_id] = test
            self._save_ab_results()
        return test

    async def record_ab_result(self, test_id: str, group: str,  # "A" or "B"
                               sent: int = 0, success: int = 0,
                               likes: int = 0, replies: int = 0):
        async with self._lock:
            test = self._ab_tests.get(test_id)
            if not test:
                return
            target = test.results_a if group == "A" else test.results_b
            target["sent"] += sent
            target["success"] += success
            target["likes"] += likes
            target["replies"] += replies

            # Auto-select winner if enough data
            total_a = test.results_a["sent"]
            total_b = test.results_b["sent"]
            if total_a >= test.video_count and total_b >= test.video_count:
                self._select_winner(test)

            self._save_ab_results()

    def _select_winner(self, test: ABTestResult):
        score_a = (test.results_a["success"] * 3 + test.results_a["likes"] * 2 +
                   test.results_a["replies"] * 4)
        score_b = (test.results_b["success"] * 3 + test.results_b["likes"] * 2 +
                   test.results_b["replies"] * 4)

        if score_a > score_b * 1.15:
            test.winner = "A"
        elif score_b > score_a * 1.15:
            test.winner = "B"
        else:
            test.winner = "tie"

        test.status = "completed"
        test.ended_at = datetime.now().isoformat()

    async def get_ab_test(self, test_id: str) -> Optional[dict]:
        test = self._ab_tests.get(test_id)
        return test.__dict__ if test else None

    async def list_ab_tests(self, status: str = "") -> list[dict]:
        tests = list(self._ab_tests.values())
        if status:
            tests = [t for t in tests if t.status == status]
        tests.sort(key=lambda t: t.started_at, reverse=True)
        return [t.__dict__ for t in tests]

    def _load_ab_results(self):
        if self._ab_results_path.exists():
            try:
                data = json.loads(self._ab_results_path.read_text(encoding="utf-8"))
                for item in data.get("tests", []):
                    test = ABTestResult(**item)
                    self._ab_tests[test.test_id] = test
            except Exception as e:
                logger.warning(f"Load AB results failed: {e}")

    def _save_ab_results(self):
        try:
            self._ab_results_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "tests": [t.__dict__ for t in self._ab_tests.values()],
                "updated_at": datetime.now().isoformat(),
            }
            self._ab_results_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Save AB results failed: {e}")

    # ── Stats ──────────────────────────────────────────────────────

    async def stats(self) -> dict:
        return {
            "history_count": len(self._history),
            "active_ab_tests": len([t for t in self._ab_tests.values() if t.status == "running"]),
            "completed_ab_tests": len([t for t in self._ab_tests.values() if t.status == "completed"]),
        }


# ── Singleton ────────────────────────────────────────────────────────────

_intercept_engine = None


def get_intercept_engine() -> InterceptEngine:
    global _intercept_engine
    if _intercept_engine is None:
        _intercept_engine = InterceptEngine()
    return _intercept_engine
