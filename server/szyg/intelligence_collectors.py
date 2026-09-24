"""Read-only collector registry for marketing intelligence."""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from typing import Any


PLATFORM_LABELS = {
    "douyin": "抖音",
    "xhs": "小红书",
    "kuaishou": "快手",
    "bilibili": "B站",
    "weibo": "微博",
}

PLATFORM_METHODS = {
    "douyin": "browser_session",
    "xhs": "browser_session",
    "kuaishou": "browser_session",
    "bilibili": "public_page",
    "weibo": "browser_session",
}


@dataclass
class CollectorHealth:
    source: str
    label: str
    source_type: str = "platform"
    method: str = "browser_session"
    status: str = "no_data"
    item_count: int = 0
    attempted_queries: int = 0
    successful_queries: int = 0
    duration_ms: int = 0
    error_code: str = ""
    message: str = ""


@dataclass
class CollectorResult:
    health: CollectorHealth
    records: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "health": asdict(self.health),
            "records": self.records,
            "errors": self.errors,
        }


def _classify_failure(message: str) -> tuple[str, str, str]:
    text = str(message or "").lower()
    if any(token in text for token in ("login", "cookie", "登录", "扫码", "unauthorized", "forbidden")):
        return "needs_login", "login_required", "需要登录后才能读取公开内容"
    if any(token in text for token in ("captcha", "verify", "risk", "风控", "验证", "访问频繁", "安全检查")):
        return "restricted", "platform_restricted", "平台需要人工验证，本轮已停止读取"
    if any(token in text for token in ("timeout", "timed out", "超时")):
        return "timeout", "collection_timeout", "公开信息读取超时"
    if any(token in text for token in ("not implemented", "unsupported", "不可用", "not available")):
        return "unavailable", "collector_unavailable", "该渠道采集能力暂不可用"
    return "failed", "collection_failed", "公开信息读取失败"


def _as_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _to_video_target(platform: str, row: dict[str, Any]):
    from szyg.intercept_engine import VideoTarget, get_intercept_engine

    target = VideoTarget(
        video_id=str(row.get("video_id") or row.get("id") or row.get("url") or ""),
        platform=platform,
        title=str(row.get("title") or ""),
        description=str(row.get("description") or row.get("desc") or ""),
        author=str(row.get("author") or row.get("author_name") or ""),
        author_followers=_as_int(row.get("author_followers")),
        url=str(row.get("url") or ""),
        cover=str(row.get("cover") or ""),
        plays=_as_int(row.get("plays") or row.get("view_count")),
        likes=_as_int(row.get("likes") or row.get("like_count")),
        comments_count=_as_int(row.get("comments_count") or row.get("comments") or row.get("comment_count")),
        shares=_as_int(row.get("shares") or row.get("share_count")),
        favorites=_as_int(row.get("favorites") or row.get("favorite")),
        coins=_as_int(row.get("coins") or row.get("coin")),
        danmaku=_as_int(row.get("danmaku")),
        author_id=str(row.get("author_id") or row.get("mid") or ""),
        author_profile_url=str(row.get("author_profile_url") or ""),
        author_following=_as_int(row.get("author_following")),
        published_at=str(row.get("published_at") or row.get("publish_time") or ""),
        duration=_as_int(row.get("duration")),
        tags=row.get("tags") if isinstance(row.get("tags"), list) else [],
    )
    get_intercept_engine().score_video(target)
    return target


class PlatformCollector:
    def __init__(self, platform: str, method: str | None = None):
        if platform not in PLATFORM_LABELS:
            raise ValueError(f"Unsupported intelligence platform: {platform}")
        self.platform = platform
        self.method = str(method or PLATFORM_METHODS[platform])

    async def collect(
        self,
        keywords: list[str],
        *,
        limit: int,
        timeout_seconds: int,
    ) -> CollectorResult:
        from szyg.integrations.acquisition_adapters import get_acquisition_adapter

        started = time.perf_counter()
        health = CollectorHealth(
            source=self.platform,
            label=PLATFORM_LABELS[self.platform],
            method=self.method,
            attempted_queries=len(keywords),
        )
        records: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        statuses: list[str] = []

        try:
            adapter = get_acquisition_adapter(self.platform)
        except Exception as exc:
            status, code, message = _classify_failure(str(exc))
            health.status = status
            health.error_code = code
            health.message = message
            health.duration_ms = round((time.perf_counter() - started) * 1000)
            return CollectorResult(health=health, errors=[{
                "platform": self.platform,
                "keyword": "",
                "message": str(exc)[:200],
            }])

        for keyword in keywords:
            try:
                search = adapter.search_public if self.platform == "bilibili" and hasattr(adapter, "search_public") else adapter.search
                rows = await asyncio.wait_for(
                    search(keyword, limit=limit),
                    timeout=max(1, timeout_seconds),
                )
                diagnostics = adapter.search_diagnostics() if hasattr(adapter, "search_diagnostics") else {}
                diagnostic_status = str(diagnostics.get("status") or "")
                if rows:
                    health.successful_queries += 1
                    statuses.append("success")
                    for row in rows:
                        if isinstance(row, dict):
                            records.append({"keyword": keyword, "video": _to_video_target(self.platform, row)})
                elif diagnostic_status in {"needs_login", "restricted", "failed", "unavailable"}:
                    statuses.append(diagnostic_status)
                    errors.append({
                        "platform": self.platform,
                        "keyword": keyword,
                        "message": str(diagnostics.get("message") or "本轮未读取到公开内容")[:200],
                    })
                else:
                    statuses.append("no_data")
            except asyncio.TimeoutError:
                statuses.append("timeout")
                errors.append({"platform": self.platform, "keyword": keyword, "message": "公开信息读取超时"})
            except Exception as exc:
                status, _, _ = _classify_failure(str(exc))
                statuses.append(status)
                errors.append({"platform": self.platform, "keyword": keyword, "message": str(exc)[:200]})

        health.item_count = len(records)
        health.duration_ms = round((time.perf_counter() - started) * 1000)
        failed_statuses = [status for status in statuses if status not in {"success", "no_data"}]
        if records:
            health.status = "partial" if failed_statuses else "success"
            health.message = f"已读取 {len(records)} 条公开内容"
        elif statuses:
            priority = ("restricted", "needs_login", "timeout", "unavailable", "failed")
            health.status = next((status for status in priority if status in statuses), "no_data")
            if health.status == "no_data":
                health.message = "本轮未发现匹配的公开内容"
            else:
                first_message = errors[0]["message"] if errors else health.status
                _, health.error_code, health.message = _classify_failure(first_message)
        else:
            health.status = "no_data"
            health.message = "没有可执行的检索词"
        return CollectorResult(health=health, records=records, errors=errors)


class CollectorRegistry:
    def __init__(self, methods: dict[str, Any] | None = None):
        if methods is None:
            try:
                from szyg.config.loader import load_config

                methods = (load_config().get("intelligence", {}) or {}).get("collectors", {}) or {}
            except Exception:
                methods = {}
        self._collectors: dict[str, PlatformCollector] = {
            platform: PlatformCollector(platform, str(methods.get(platform) or PLATFORM_METHODS[platform]))
            for platform in PLATFORM_LABELS
            if methods.get(platform, PLATFORM_METHODS[platform]) not in {False, "disabled", "off"}
        }

    def register(self, source: str, collector: PlatformCollector) -> None:
        self._collectors[source] = collector

    def describe(self) -> list[dict[str, str]]:
        return [
            {
                "source": source,
                "label": PLATFORM_LABELS.get(source, source),
                "method": collector.method,
            }
            for source, collector in self._collectors.items()
        ]

    async def collect_many(
        self,
        platforms: list[str],
        keywords: list[str],
        *,
        limit: int,
        timeout_seconds: int,
    ) -> list[CollectorResult]:
        tasks = []
        for platform in platforms:
            collector = self._collectors.get(platform)
            if collector is None:
                health = CollectorHealth(
                    source=platform,
                    label=PLATFORM_LABELS.get(platform, platform),
                    status="unavailable",
                    error_code="collector_unavailable",
                    message="该渠道采集能力暂不可用",
                )
                tasks.append(asyncio.sleep(0, result=CollectorResult(health=health)))
            else:
                tasks.append(collector.collect(
                    keywords,
                    limit=limit,
                    timeout_seconds=timeout_seconds,
                ))
        return await asyncio.gather(*tasks)


_registry: CollectorRegistry | None = None


def get_intelligence_collector_registry() -> CollectorRegistry:
    global _registry
    if _registry is None:
        _registry = CollectorRegistry()
    return _registry
