"""Competitor intelligence storage and lightweight sync helpers."""

from __future__ import annotations

import html
import ipaddress
import re
import statistics
import threading
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, quote_plus, urljoin, urlparse

from szyg.atomic_file import atomic_read, atomic_write
from szyg.data_path import DATA_DIR


COMPETITOR_FILE = DATA_DIR / "competitor_accounts.json"
BUSINESS_PROFILE_FILE = DATA_DIR / "intelligence_business_profiles.json"
DISCOVERY_FILE = DATA_DIR / "intelligence_discoveries.json"
BRIEF_FILE = DATA_DIR / "intelligence_content_briefs.json"
SNAPSHOT_FILE = DATA_DIR / "intelligence_snapshots.json"
SOURCE_FILE = DATA_DIR / "intelligence_sources.json"
MARKET_NEWS_FILE = DATA_DIR / "intelligence_market_news.json"

_LOCK = threading.RLock()

PLATFORM_LABELS = {
    "douyin": "抖音",
    "xhs": "小红书",
    "kuaishou": "快手",
    "bilibili": "B站",
    "weibo": "微博",
    "tencent": "视频号",
}

COLLECTOR_LABELS = {
    "bilibili": ("B站公开数据", "public_api"),
    "douyin": ("抖音平台采集", "platform_collector"),
    "xhs": ("小红书页面采集", "browser_collector"),
    "kuaishou": ("快手页面采集", "browser_collector"),
    "weibo": ("微博公开搜索", "public_search"),
    "tencent": ("视频号桌面采集", "desktop_collector"),
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _rows() -> list[dict[str, Any]]:
    rows = atomic_read(COMPETITOR_FILE)
    return rows if isinstance(rows, list) else []


def _read_list(path) -> list[dict[str, Any]]:
    rows = atomic_read(path)
    return rows if isinstance(rows, list) else []


def _save(path, rows: list[dict[str, Any]]) -> None:
    atomic_write(path, rows)


def _brief_platform_suggestion(platforms: list[str]) -> list[str]:
    labels = [PLATFORM_LABELS.get(platform, platform) for platform in platforms if platform]
    return labels[:3] or ["小红书", "抖音", "B站"]


def _collector_metadata(platform: str, collected_at: str) -> dict[str, Any]:
    source_name, method = COLLECTOR_LABELS.get(platform, ("公开网络数据", "public_search"))
    return {
        "source_name": source_name,
        "collection_method": method,
        "collected_at": collected_at,
        "data_quality": "verified" if platform == "bilibili" else "observed",
    }


def _append_snapshot(row: dict[str, Any]) -> None:
    snapshot = {
        "id": f"snap_{uuid.uuid4().hex[:10]}",
        "entity_type": "competitor_account",
        "entity_id": row.get("id"),
        "platform": row.get("platform"),
        "name": row.get("name") or row.get("handle") or "",
        "followers": row.get("followers"),
        "following": row.get("following"),
        "works_count": row.get("works_count"),
        "recent_item_count": len(row.get("recent_items") or []),
        "sync_status": row.get("sync_status"),
        "captured_at": row.get("last_sync_at") or _now(),
    }
    rows = _read_list(SNAPSHOT_FILE)
    rows.insert(0, snapshot)
    _save(SNAPSHOT_FILE, rows[:5000])


def detect_platform(profile_url: str, fallback: str = "") -> str:
    host = urlparse(profile_url).netloc.lower()
    value = (fallback or "").strip().lower()
    if value:
        return value
    if "douyin" in host:
        return "douyin"
    if "xiaohongshu" in host or "xhslink" in host:
        return "xhs"
    if "kuaishou" in host:
        return "kuaishou"
    if "bilibili" in host:
        return "bilibili"
    if "weibo" in host:
        return "weibo"
    if "channels.weixin" in host:
        return "tencent"
    return "unknown"


def _handle_from_url(profile_url: str, platform: str) -> str:
    parsed = urlparse(profile_url)
    path = parsed.path.strip("/")
    if not path:
        return parsed.netloc
    if platform == "bilibili":
        match = re.search(r"space/([^/?#]+)", path)
        if match:
            return match.group(1)
    if platform == "weibo":
        parts = [part for part in path.split("/") if part]
        if parts:
            return parts[-1]
    parts = [part for part in path.split("/") if part]
    return parts[-1] if parts else parsed.netloc


def _bilibili_mid_from_url(profile_url: str, handle: str = "") -> str:
    text = f"{profile_url} {handle}"
    match = re.search(r"space\.bilibili\.com/(\d+)", text)
    if match:
        return match.group(1)
    if str(handle or "").isdigit():
        return str(handle)
    return ""


def _fetch_json(url: str, referer: str = "https://www.bilibili.com") -> dict[str, Any]:
    from urllib.request import Request, urlopen

    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Referer": referer,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    with urlopen(req, timeout=12) as resp:
        import json

        return json.loads(resp.read().decode("utf-8", "ignore"))


def _bilibili_recent_items_by_author(name: str, mid: str, limit: int = 5) -> list[dict[str, Any]]:
    if not name and not mid:
        return []

    from urllib.parse import quote as url_quote
    from urllib.request import Request, urlopen

    req = Request(
        f"https://search.bilibili.com/all?keyword={url_quote(name or mid)}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
            "Referer": "https://www.bilibili.com",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )
    try:
        with urlopen(req, timeout=12) as resp:
            page = resp.read().decode("utf-8", "ignore")
    except Exception:
        return []

    bvids: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"//www\.bilibili\.com/video/(BV[a-zA-Z0-9]+)/?", page):
        bvid = match.group(1)
        if bvid in seen:
            continue
        seen.add(bvid)
        bvids.append(bvid)
        if len(bvids) >= 20:
            break

    items: list[dict[str, Any]] = []
    for bvid in bvids:
        try:
            detail = _fetch_json(
                f"https://api.bilibili.com/x/web-interface/view?bvid={url_quote(bvid)}",
                referer=f"https://www.bilibili.com/video/{bvid}/",
            )
        except Exception:
            continue
        if detail.get("code") != 0:
            continue
        data = detail.get("data") or {}
        owner = data.get("owner") or {}
        owner_mid = str(owner.get("mid") or "")
        if mid and owner_mid != str(mid):
            continue
        stat = data.get("stat") or {}
        collected_at = _now()
        items.append({
            "id": f"recent_{bvid}",
            "platform": "bilibili",
            "title": data.get("title") or "",
            "url": f"https://www.bilibili.com/video/{bvid}/",
            "cover": data.get("pic") or "",
            "plays": stat.get("view", 0),
            "likes": stat.get("like", 0),
            "comments_count": stat.get("reply", 0),
            "favorites": stat.get("favorite", 0),
            "coins": stat.get("coin", 0),
            "danmaku": stat.get("danmaku", 0),
            "published_at": data.get("pubdate", ""),
            **_collector_metadata("bilibili", collected_at),
        })
        if len(items) >= limit:
            break
    return items


def _sync_bilibili_competitor(row: dict[str, Any], now: str) -> dict[str, Any]:
    profile_url = str(row.get("profile_url") or "")
    handle = str(row.get("handle") or "")
    mid = _bilibili_mid_from_url(profile_url, handle)
    if not mid:
        updated = dict(row)
        updated["sync_status"] = "partial"
        updated["sync_message"] = "未能从B站主页识别UP主ID，请确认主页链接是否为 space.bilibili.com"
        updated["last_sync_at"] = now
        updated["updated_at"] = now
        return updated

    card: dict[str, Any] = {}
    card_data: dict[str, Any] = {}
    stat: dict[str, Any] = {}
    try:
        card_resp = _fetch_json(f"https://api.bilibili.com/x/web-interface/card?mid={quote(mid)}", referer=f"https://space.bilibili.com/{mid}")
        if card_resp.get("code") == 0:
            card_data = card_resp.get("data") or {}
            card = card_data.get("card") or {}
    except Exception:
        card = {}
    try:
        stat_resp = _fetch_json(f"https://api.bilibili.com/x/relation/stat?vmid={quote(mid)}", referer=f"https://space.bilibili.com/{mid}")
        if stat_resp.get("code") == 0:
            stat = stat_resp.get("data") or {}
    except Exception:
        stat = {}

    name = str(card.get("name") or row.get("name") or "").strip()
    recent_items = _bilibili_recent_items_by_author(name, mid, limit=5) if name else []
    updated = dict(row)
    updated.update({
        "platform": "bilibili",
        "platform_label": PLATFORM_LABELS.get("bilibili", "B站"),
        "name": name or row.get("name") or f"B站UP主 {mid}",
        "profile_url": f"https://space.bilibili.com/{mid}",
        "handle": mid,
        "avatar_url": card.get("face") or row.get("avatar_url") or "",
        "followers": stat.get("follower", card.get("fans", row.get("followers"))),
        "following": stat.get("following", card.get("attention", row.get("following"))),
        "works_count": card_data.get("archive_count", row.get("works_count")),
        "bio": card.get("sign") or row.get("bio") or "",
        "recent_items": recent_items,
        "sync_status": "success" if card or stat else "partial",
        "sync_message": f"已同步B站账号资料，获取到 {len(recent_items)} 条近期公开作品样本" if (card or stat) else "B站公开账号接口暂未返回资料，可稍后重试",
        "last_sync_at": now,
        "updated_at": now,
    })
    return updated


def list_competitors(platform: str = "", keyword: str = "") -> list[dict[str, Any]]:
    with _LOCK:
        rows = _rows()
    platform = platform.strip().lower()
    keyword = keyword.strip().lower()
    if platform:
        rows = [row for row in rows if str(row.get("platform", "")).lower() == platform]
    if keyword:
        rows = [
            row
            for row in rows
            if keyword in str(row.get("name", "")).lower()
            or keyword in str(row.get("profile_url", "")).lower()
            or keyword in str(row.get("handle", "")).lower()
            or keyword in " ".join(str(tag).lower() for tag in row.get("tags", []))
        ]
    return sorted(rows, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)


def overview() -> dict[str, Any]:
    rows = list_competitors()
    synced = [row for row in rows if row.get("sync_status") in {"success", "synced"}]
    needs_sync = [row for row in rows if row.get("sync_status") in {"pending", "partial", "failed"}]
    platforms: dict[str, int] = {}
    for row in rows:
        platform = str(row.get("platform") or "unknown")
        platforms[platform] = platforms.get(platform, 0) + 1
    return {
        "total_competitors": len(rows),
        "synced_competitors": len(synced),
        "needs_sync": len(needs_sync),
        "platforms": platforms,
        "available_platforms": [
            {"value": key, "label": label}
            for key, label in PLATFORM_LABELS.items()
        ],
    }


def create_competitor(payload: dict[str, Any]) -> dict[str, Any]:
    profile_url = str(payload.get("profile_url") or "").strip()
    if not profile_url:
        raise ValueError("请输入竞品账号主页链接")
    platform = detect_platform(profile_url, str(payload.get("platform") or ""))
    now = _now()
    row = {
        "id": f"comp_{uuid.uuid4().hex[:10]}",
        "platform": platform,
        "platform_label": PLATFORM_LABELS.get(platform, platform or "未知平台"),
        "name": str(payload.get("name") or "").strip() or "未命名竞品",
        "profile_url": profile_url,
        "handle": _handle_from_url(profile_url, platform),
        "avatar_url": "",
        "followers": payload.get("followers") if payload.get("followers") is not None else None,
        "following": payload.get("following") if payload.get("following") is not None else None,
        "works_count": None,
        "tags": [str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()],
        "sync_status": "pending",
        "sync_message": "已加入监控，等待同步公开数据",
        "last_sync_at": "",
        "recent_items": [],
        "created_at": now,
        "updated_at": now,
    }
    with _LOCK:
        rows = _rows()
        rows.insert(0, row)
        _save(COMPETITOR_FILE, rows)
    return row


def delete_competitor(competitor_id: str) -> bool:
    with _LOCK:
        rows = _rows()
        next_rows = [row for row in rows if row.get("id") != competitor_id]
        changed = len(next_rows) != len(rows)
        if changed:
            _save(COMPETITOR_FILE, next_rows)
    return changed


def sync_competitor(competitor_id: str) -> dict[str, Any]:
    """Sync one competitor without holding the persistence lock during network IO."""
    now = _now()
    with _LOCK:
        rows = _rows()
        row = next((dict(item) for item in rows if item.get("id") == competitor_id), None)
    if not row:
        raise KeyError("竞品账号不存在")

    platform = detect_platform(str(row.get("profile_url") or ""), str(row.get("platform") or ""))
    if platform == "bilibili":
        updated = _sync_bilibili_competitor(row, now)
    else:
        updated = dict(row)
        updated["platform"] = platform
        updated["platform_label"] = PLATFORM_LABELS.get(platform, platform or "未知平台")
        updated["handle"] = updated.get("handle") or _handle_from_url(str(updated.get("profile_url") or ""), platform)
        updated["sync_status"] = "partial"
        updated["sync_message"] = "已确认账号链接，深度作品数据待接入平台采集器"
        updated["last_sync_at"] = now
        updated["updated_at"] = now

    with _LOCK:
        rows = _rows()
        for index, item in enumerate(rows):
            if item.get("id") == competitor_id:
                rows[index] = updated
                _save(COMPETITOR_FILE, rows)
                _append_snapshot(updated)
                return updated
    raise KeyError("竞品账号不存在")


def sync_competitors(platform: str = "", limit: int = 20) -> list[dict[str, Any]]:
    with _LOCK:
        rows = _rows()
    platform = platform.strip().lower()
    selected = [
        row for row in rows
        if not platform or str(row.get("platform") or "").lower() == platform
    ][: max(1, min(limit, 50))]
    synced: list[dict[str, Any]] = []
    for row in selected:
        try:
            synced.append(sync_competitor(str(row.get("id") or "")))
        except Exception:
            continue
    return synced


def _split_terms(value: Any) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        raw = re.split(r"[\s,，、;；\n]+", str(value or ""))
    return [str(item).strip() for item in raw if str(item).strip()]


def _normalize_business_profile(payload: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    profile_id = str(payload.get("id") or "default")
    return {
        "id": profile_id,
        "product_name": str(payload.get("product_name") or "").strip(),
        "industry": str(payload.get("industry") or "").strip(),
        "audience": str(payload.get("audience") or "").strip(),
        "region": str(payload.get("region") or "").strip(),
        "goals": _split_terms(payload.get("goals")),
        "selling_points": _split_terms(payload.get("selling_points")),
        "seed_keywords": _split_terms(payload.get("seed_keywords")),
        "platforms": _split_terms(payload.get("platforms")) or ["douyin", "xhs", "bilibili", "weibo"],
        "use_knowledge_base": bool(payload.get("use_knowledge_base", True)),
        "knowledge_query": str(payload.get("knowledge_query") or "").strip(),
        "created_at": str(payload.get("created_at") or now),
        "updated_at": now,
    }


def upsert_business_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = _normalize_business_profile(payload)
    profile_id = str(profile["id"])
    with _LOCK:
        rows = _read_list(BUSINESS_PROFILE_FILE)
        rows = [row for row in rows if row.get("id") != profile_id]
        rows.insert(0, profile)
        _save(BUSINESS_PROFILE_FILE, rows)
    return profile


def list_business_profiles() -> list[dict[str, Any]]:
    with _LOCK:
        return sorted(_read_list(BUSINESS_PROFILE_FILE), key=lambda row: str(row.get("updated_at") or ""), reverse=True)


def _search_url(platform: str, keyword: str) -> str:
    encoded = quote(keyword)
    if platform == "douyin":
        return f"https://www.douyin.com/search/{encoded}"
    if platform == "xhs":
        return f"https://www.xiaohongshu.com/search_result?keyword={encoded}"
    if platform == "kuaishou":
        return f"https://www.kuaishou.com/search/video?searchKey={encoded}"
    if platform == "bilibili":
        return f"https://search.bilibili.com/all?keyword={encoded}"
    if platform == "weibo":
        return f"https://s.weibo.com/weibo?q={encoded}"
    return f"https://www.baidu.com/s?wd={encoded}"


def _load_knowledge_context(profile: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    if not profile.get("use_knowledge_base", True):
        return []
    query = str(profile.get("knowledge_query") or "").strip()
    if not query:
        query = " ".join(filter(None, [
            str(profile.get("product_name") or "").strip(),
            str(profile.get("industry") or "").strip(),
            " ".join(_split_terms(profile.get("selling_points"))[:3]),
        ])).strip()
    if not query:
        return []
    try:
        from szyg.knowledge_service import get_knowledge_service
        results = get_knowledge_service().search_sync(query, limit=max(1, min(limit, 10)))
    except Exception:
        return []
    return [
        {
            "content": re.sub(r"\s+", " ", str(item.get("content") or "")).strip()[:500],
            "source": str(item.get("filename") or item.get("source") or "知识库"),
            "score": item.get("score", 0),
        }
        for item in results
        if str(item.get("content") or "").strip()
    ]


def _knowledge_seed_terms(context: list[dict[str, Any]]) -> list[str]:
    terms: list[str] = []
    for item in context:
        source = re.sub(r"\.[A-Za-z0-9]{1,6}$", "", str(item.get("source") or "")).strip()
        if 2 <= len(source) <= 20 and source not in {"manual", "知识库", "unknown"}:
            terms.append(source)
        text = str(item.get("content") or "")
        for quoted in re.findall(r"[“「『](.{2,16}?)[”」』]", text):
            terms.append(quoted.strip())
    return terms[:4]


def generate_discovery_keywords(
    profile: dict[str, Any],
    limit: int = 8,
    knowledge_context: list[dict[str, Any]] | None = None,
) -> list[str]:
    product = str(profile.get("product_name") or "").strip()
    industry = str(profile.get("industry") or "").strip()
    audience = str(profile.get("audience") or "").strip()
    region = str(profile.get("region") or "").strip()
    seeds = _split_terms(profile.get("seed_keywords"))
    points = _split_terms(profile.get("selling_points"))

    candidates: list[str] = []
    for item in seeds:
        candidates.append(item)
    for item in _knowledge_seed_terms(knowledge_context or []):
        candidates.append(item)
    if product:
        candidates.extend([product, f"{product} 推荐", f"{product} 测评", f"{product} 使用体验"])
    if industry and audience:
        candidates.extend([f"{audience} {industry}", f"{industry} 同行", f"{industry} 爆款"])
    elif industry:
        candidates.extend([industry, f"{industry} 爆款", f"{industry} 同行"])
    if audience and product:
        candidates.append(f"{audience} {product}")
    if region and industry:
        candidates.append(f"{region} {industry}")
    for point in points[:3]:
        if product:
            candidates.append(f"{product} {point}")
        elif industry:
            candidates.append(f"{industry} {point}")

    seen = set()
    keywords = []
    for item in candidates:
        normalized = re.sub(r"\s+", " ", item).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            keywords.append(normalized)
        if len(keywords) >= limit:
            break
    return keywords


def _video_to_item(video: Any, keyword: str) -> dict[str, Any]:
    platform = getattr(video, "platform", "")
    collected_at = _now()
    title = getattr(video, "title", "")
    description = getattr(video, "description", "")
    return {
        "id": f"content_{uuid.uuid4().hex[:10]}",
        "platform": platform,
        "platform_label": PLATFORM_LABELS.get(platform, platform),
        "keyword": keyword,
        "title": title,
        "description": description,
        "author": getattr(video, "author", ""),
        "source_url": getattr(video, "url", ""),
        "cover": getattr(video, "cover", ""),
        "plays": getattr(video, "plays", 0),
        "likes": getattr(video, "likes", 0),
        "comments_count": getattr(video, "comments_count", 0),
        "shares": getattr(video, "shares", 0),
        "favorites": getattr(video, "favorites", 0),
        "coins": getattr(video, "coins", 0),
        "danmaku": getattr(video, "danmaku", 0),
        "author_id": getattr(video, "author_id", ""),
        "author_profile_url": getattr(video, "author_profile_url", ""),
        "author_followers": getattr(video, "author_followers", 0),
        "author_following": getattr(video, "author_following", 0),
        "published_at": getattr(video, "published_at", ""),
        "quality_score": getattr(video, "quality_score", 0),
        "score_detail": getattr(video, "score_detail", {}),
        "relevance_score": _content_relevance(keyword, f"{title} {description}"),
        **_collector_metadata(platform, collected_at),
    }


def _content_relevance(keyword: str, text: str) -> int:
    query = re.sub(r"\s+", "", str(keyword or "")).lower()
    haystack = re.sub(r"\s+", "", str(text or "")).lower()
    if not query or not haystack:
        return 0
    if query in haystack:
        return 100
    terms = re.findall(r"[a-z0-9]+", query)
    for chinese in re.findall(r"[\u4e00-\u9fff]+", query):
        if len(chinese) <= 2:
            terms.append(chinese)
        else:
            terms.extend(chinese[index:index + 2] for index in range(0, len(chinese) - 1, 2))
    terms = [term for term in terms if len(term) >= 2]
    if not terms:
        return 0
    matched = sum(1 for term in terms if term in haystack)
    return round(matched / len(terms) * 100)


def _candidate_from_author(platform: str, author: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    best = sorted(evidence, key=lambda item: int(item.get("quality_score") or 0), reverse=True)[0]
    author_id = str(best.get("author_id") or "")
    profile_url = str(best.get("author_profile_url") or "")
    if not profile_url and platform == "bilibili" and author_id:
        profile_url = f"https://space.bilibili.com/{author_id}"
    followers = max([int(item.get("author_followers") or 0) for item in evidence] or [0])
    following = max([int(item.get("author_following") or 0) for item in evidence] or [0])
    return {
        "id": f"candidate_{uuid.uuid4().hex[:10]}",
        "platform": platform,
        "platform_label": PLATFORM_LABELS.get(platform, platform),
        "name": author or "未知作者",
        "profile_url": profile_url,
        "author_id": author_id,
        "followers": followers,
        "following": following,
        "evidence_url": best.get("source_url", ""),
        "reason": f"在 {best.get('keyword', '')} 下出现高相关内容，互动质量分 {best.get('quality_score', 0)}",
        "matched_items": len(evidence),
        "top_title": best.get("title", ""),
        "tags": [str(best.get("keyword", ""))] if best.get("keyword") else [],
    }


def _annotate_breakouts(content_items: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in content_items:
        grouped.setdefault(str(item.get("platform") or "unknown"), []).append(item)

    for platform_items in grouped.values():
        engagements = [_item_engagement(item) for item in platform_items]
        median_engagement = float(statistics.median(engagements)) if engagements else 0.0
        ordered = sorted(engagements)
        sample_size = len(ordered)
        for item, engagement in zip(platform_items, engagements):
            has_raw_metrics = any(
                item.get(field) not in (None, "")
                for field in ("views", "plays", "likes", "comments_count", "favorites", "shares")
            )
            if not has_raw_metrics and item.get("hot_score") is not None:
                item.setdefault("engagement", engagement)
                item.setdefault("breakout_reason", "沿用历史采集时的爆款判断")
                item.setdefault("comparison_sample_size", sample_size)
                continue
            rank = ordered.index(engagement) + 1 if ordered else 0
            percentile = round(rank / sample_size * 100, 1) if sample_size else 0.0
            quality = max(0, min(100, int(item.get("quality_score") or 0)))
            relative = min(100.0, (engagement / max(1.0, median_engagement)) * 50.0)
            relevance = max(0, min(100, int(item.get("relevance_score") or 0)))
            hot_score = round(quality * 0.35 + percentile * 0.30 + relative * 0.20 + relevance * 0.15)
            reasons: list[str] = []
            if sample_size >= 3 and percentile >= 80:
                reasons.append(f"同批样本互动位于前 {max(1, round(100 - percentile))}%")
            if median_engagement and engagement >= median_engagement * 2:
                reasons.append("互动量超过同平台样本中位数 2 倍")
            if quality >= 80:
                reasons.append(f"内容质量分 {quality}")
            if not reasons:
                reasons.append("当前样本量有限，建议继续观察")
            item["engagement"] = engagement
            item["hot_score"] = hot_score
            item["is_breakout"] = hot_score >= 70 and (sample_size < 3 or percentile >= 60)
            item["breakout_reason"] = "；".join(reasons)
            item["comparison_sample_size"] = sample_size


def _top_content(content_items: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    return sorted(
        content_items,
        key=lambda item: (
            int(item.get("hot_score") or 0),
            int(item.get("quality_score") or 0),
            int(item.get("likes") or 0),
            int(item.get("comments_count") or 0),
        ),
        reverse=True,
    )[:limit]


def _make_comment_insights(comments: list[dict[str, Any]]) -> dict[str, Any]:
    raw_texts = [
        re.sub(r"\s+", " ", str(comment.get("text") or "")).strip()
        for comment in comments
        if str(comment.get("text") or "").strip()
    ]
    texts = []
    seen = set()
    for text in raw_texts:
        snippet = text[:120] + ("..." if len(text) > 120 else "")
        if snippet in seen:
            continue
        seen.add(snippet)
        texts.append(snippet)
    question_terms = ("?", "？", "吗", "如何", "怎么", "多少", "价格", "适合", "哪里")
    need_terms = ("想要", "想买", "想学", "求", "需要", "推荐", "怎么买", "链接", "有没有")
    questions = [text for text in texts if any(term in text for term in question_terms)][:3]
    question_set = set(questions)
    needs = [text for text in texts if text not in question_set and any(term in text for term in need_terms)][:3]
    if questions:
        summary = f"评论区出现 {len(questions)} 条明确问题，可转化为选题或私域跟进话术。"
    elif needs:
        summary = f"评论区出现 {len(needs)} 条潜在需求表达，适合提炼痛点内容。"
    elif texts:
        summary = "评论样本以反馈和态度表达为主，可用于判断受众语气。"
    else:
        summary = "公开接口暂未返回可用评论样本。"
    return {
        "sample_count": len(texts),
        "questions": questions,
        "needs": needs,
        "summary": summary,
    }


async def _enrich_bilibili_comment_samples(content_items: list[dict[str, Any]]) -> None:
    targets = [
        item for item in _top_content(content_items, limit=12)
        if item.get("platform") == "bilibili"
        and int(item.get("comments_count") or 0) > 0
        and item.get("source_url")
    ][:3]
    if not targets:
        return

    try:
        from szyg.integrations.acquisition_adapters import get_acquisition_adapter

        adapter = get_acquisition_adapter("bilibili")
    except Exception:
        return

    for item in targets:
        try:
            comments = await adapter.get_comments(str(item.get("source_url") or ""), limit=5)
        except Exception:
            comments = []
        samples = [
            {
                "comment_id": comment.get("comment_id"),
                "author": comment.get("author"),
                "text": comment.get("text"),
                "likes": comment.get("likes", 0),
                "created_at": comment.get("created_at"),
            }
            for comment in comments[:5]
            if str(comment.get("text") or "").strip()
        ]
        item["comment_samples"] = samples
        item["comment_insights"] = _make_comment_insights(samples)


def _make_summary(profile: dict[str, Any], content_items: list[dict[str, Any]], candidates: list[dict[str, Any]], errors: list[dict[str, str]]) -> dict[str, Any]:
    platforms: dict[str, int] = {}
    keywords: dict[str, int] = {}
    for item in content_items:
        platform = str(item.get("platform") or "unknown")
        keyword = str(item.get("keyword") or "")
        platforms[platform] = platforms.get(platform, 0) + 1
        if keyword:
            keywords[keyword] = keywords.get(keyword, 0) + 1
    return {
        "headline": f"围绕 {profile.get('product_name') or profile.get('industry') or '当前业务'} 找到 {len(content_items)} 条公开内容和 {len(candidates)} 个候选账号",
        "content_count": len(content_items),
        "candidate_count": len(candidates),
        "platforms": platforms,
        "keywords": keywords,
        "error_count": len(errors),
        "confidence": "medium" if content_items else "low",
    }


def _make_content_analysis(profile: dict[str, Any], content_items: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    product = str(profile.get("product_name") or profile.get("industry") or "当前业务")
    topic_map: dict[str, dict[str, Any]] = {}
    for item in content_items:
        topic = str(item.get("keyword") or item.get("title") or "未分类主题").strip()[:40] or "未分类主题"
        row = topic_map.setdefault(topic, {
            "topic": topic,
            "count": 0,
            "score_total": 0,
            "engagement": 0,
            "top_title": "",
            "source_url": "",
        })
        row["count"] += 1
        row["score_total"] += int(item.get("quality_score") or 0)
        engagement = (
            int(item.get("likes") or 0)
            + int(item.get("comments_count") or 0) * 3
            + int(item.get("favorites") or 0) * 2
            + int(item.get("coins") or 0) * 4
        )
        row["engagement"] += engagement
        if not row["top_title"] or engagement > int(row.get("_best_engagement") or 0):
            row["top_title"] = item.get("title") or item.get("description") or ""
            row["source_url"] = item.get("source_url") or ""
            row["_best_engagement"] = engagement

    top_topics = []
    for row in topic_map.values():
        count = max(1, int(row.get("count") or 1))
        clean = {key: value for key, value in row.items() if key != "_best_engagement"}
        clean["avg_quality_score"] = round(float(row.get("score_total") or 0) / count, 1)
        top_topics.append(clean)
    top_topics.sort(key=lambda item: (int(item.get("engagement") or 0), float(item.get("avg_quality_score") or 0)), reverse=True)

    demand_seen: set[str] = set()
    demand_signals: list[dict[str, Any]] = []
    for item in _top_content(content_items, limit=20):
        insights = item.get("comment_insights") or {}
        for text in list(insights.get("questions") or []) + list(insights.get("needs") or []):
            signal = str(text or "").strip()
            if not signal or signal in demand_seen:
                continue
            demand_seen.add(signal)
            demand_signals.append({
                "text": signal,
                "source_title": item.get("title") or item.get("description") or "",
                "source_url": item.get("source_url") or "",
                "platform": item.get("platform") or "",
                "platform_label": item.get("platform_label") or PLATFORM_LABELS.get(str(item.get("platform") or ""), ""),
            })
            if len(demand_signals) >= 8:
                break
        if len(demand_signals) >= 8:
            break

    account_opportunities = []
    for candidate in candidates[:6]:
        account_opportunities.append({
            "name": candidate.get("name") or "候选账号",
            "platform": candidate.get("platform") or "",
            "platform_label": candidate.get("platform_label") or PLATFORM_LABELS.get(str(candidate.get("platform") or ""), ""),
            "profile_url": candidate.get("profile_url") or "",
            "evidence_url": candidate.get("evidence_url") or "",
            "matched_items": candidate.get("matched_items") or 0,
            "followers": candidate.get("followers"),
            "reason": candidate.get("reason") or "",
        })

    content_angles = []
    for index, item in enumerate(_top_content(content_items, limit=5), start=1):
        title = str(item.get("title") or item.get("description") or "").strip()
        keyword = str(item.get("keyword") or "").strip()
        if not title and not keyword:
            continue
        content_angles.append({
            "title": f"{keyword or title[:14]} 的差异化选题",
            "description": f"参考高互动内容《{title[:50] or keyword}》，围绕 {product} 做一条不同立场、不同场景或不同人群的内容。",
            "source_url": item.get("source_url") or "",
            "platform_label": item.get("platform_label") or PLATFORM_LABELS.get(str(item.get("platform") or ""), ""),
            "priority": index,
        })

    return {
        "top_topics": top_topics[:6],
        "demand_signals": demand_signals,
        "account_opportunities": account_opportunities,
        "content_angles": content_angles,
    }


def _item_engagement(item: dict[str, Any]) -> int:
    return (
        int(item.get("likes") or 0)
        + int(item.get("comments_count") or 0) * 3
        + int(item.get("favorites") or 0) * 2
        + int(item.get("coins") or 0) * 4
        + int(item.get("danmaku") or 0)
    )


def _make_monitoring_digest(limit_accounts: int = 6, limit_items: int = 8) -> dict[str, Any]:
    rows = list_competitors()
    account_updates: list[dict[str, Any]] = []
    all_items: list[dict[str, Any]] = []
    for row in rows:
        recent = row.get("recent_items") or []
        if not recent:
            continue
        account_updates.append({
            "account_id": row.get("id"),
            "name": row.get("name") or row.get("handle") or "未命名竞品",
            "platform": row.get("platform") or "",
            "platform_label": row.get("platform_label") or PLATFORM_LABELS.get(str(row.get("platform") or ""), ""),
            "profile_url": row.get("profile_url") or "",
            "followers": row.get("followers"),
            "recent_count": len(recent),
            "last_sync_at": row.get("last_sync_at") or "",
        })
        for item in recent:
            enriched = dict(item)
            enriched["account_id"] = row.get("id")
            enriched["account_name"] = row.get("name") or row.get("handle") or "未命名竞品"
            enriched["platform"] = row.get("platform") or enriched.get("platform") or ""
            enriched["platform_label"] = row.get("platform_label") or PLATFORM_LABELS.get(str(enriched.get("platform") or ""), "")
            enriched["engagement"] = _item_engagement(enriched)
            all_items.append(enriched)

    account_updates.sort(key=lambda item: (int(item.get("recent_count") or 0), int(item.get("followers") or 0)), reverse=True)
    top_items = sorted(all_items, key=lambda item: (int(item.get("engagement") or 0), int(item.get("plays") or 0)), reverse=True)[:limit_items]
    latest_items = sorted(all_items, key=lambda item: str(item.get("published_at") or ""), reverse=True)[:limit_items]
    return {
        "account_count": len(rows),
        "accounts_with_updates": len(account_updates),
        "recent_item_count": len(all_items),
        "account_updates": account_updates[:limit_accounts],
        "top_recent_items": top_items,
        "latest_items": latest_items,
    }


def _make_action_suggestions(profile: dict[str, Any], content_items: list[dict[str, Any]], candidates: list[dict[str, Any]], now: str) -> list[dict[str, Any]]:
    product = str(profile.get("product_name") or profile.get("industry") or "你的产品")
    audience = str(profile.get("audience") or "目标客户")
    suggestions: list[dict[str, Any]] = []
    top_items = _top_content(content_items, limit=3)

    for index, item in enumerate(top_items, start=1):
        title = str(item.get("title") or item.get("description") or "").strip()
        keyword = str(item.get("keyword") or "").strip()
        source_url = str(item.get("source_url") or "")
        suggestions.append({
            "id": f"sugg_{uuid.uuid4().hex[:10]}",
            "type": "content",
            "priority": index,
            "title": f"围绕“{keyword or title[:16]}”生成同题材内容",
            "description": f"参考竞品内容《{title[:60] or '高相关内容'}》，为 {audience} 输出一条强调 {product} 差异化卖点的图文或短视频脚本。",
            "reason": f"该内容质量分 {item.get('quality_score', 0)}，可作为选题方向但不要照搬表达。{(' 评论区信号：' + str((item.get('comment_insights') or {}).get('summary') or '')) if item.get('comment_insights') else ''}",
            "source_item_ids": [item.get("id")],
            "source_urls": [source_url] if source_url else [],
            "created_at": now,
        })

    if candidates:
        top_candidate = candidates[0]
        suggestions.append({
            "id": f"sugg_{uuid.uuid4().hex[:10]}",
            "type": "monitor",
            "priority": len(suggestions) + 1,
            "title": f"优先监控“{top_candidate.get('name') or '候选账号'}”",
            "description": "该账号在当前搜索目标中多次出现，可加入监控后持续跟踪作品更新、标题策略和评论区需求。",
            "reason": str(top_candidate.get("reason") or "候选账号相关度较高"),
            "source_item_ids": [],
            "source_urls": [str(top_candidate.get("evidence_url") or "")] if top_candidate.get("evidence_url") else [],
            "created_at": now,
        })

    if not suggestions:
        suggestions.append({
            "id": f"sugg_{uuid.uuid4().hex[:10]}",
            "type": "research",
            "priority": 1,
            "title": "补充更具体的种子关键词",
            "description": "当前没有拿到足够公开内容。建议补充竞品品牌名、用户痛点词、地区词或平台常见口语表达后重新发现。",
            "reason": "公开搜索链路未形成可验证内容样本",
            "source_item_ids": [],
            "source_urls": [],
            "created_at": now,
        })
    return suggestions[:6]


def _validate_source_url(value: str) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("请输入有效的公开信息源地址")
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise ValueError("信息源必须是公开网络地址")
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            raise ValueError("信息源必须是公开网络地址")
    except ValueError as exc:
        if "必须是公开网络地址" in str(exc):
            raise
    return url


def create_information_source(payload: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    url = _validate_source_url(str(payload.get("url") or ""))
    name = str(payload.get("name") or "").strip() or (urlparse(url).hostname or "自定义信息源")
    source = {
        "id": f"source_{uuid.uuid4().hex[:10]}",
        "name": name[:80],
        "url": url,
        "keywords": _split_terms(payload.get("keywords"))[:20],
        "enabled": bool(payload.get("enabled", True)),
        "status": "pending",
        "last_sync_at": "",
        "last_error": "",
        "item_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    with _LOCK:
        rows = _read_list(SOURCE_FILE)
        if any(str(row.get("url") or "").rstrip("/") == url.rstrip("/") for row in rows):
            raise ValueError("该信息源已经添加")
        rows.insert(0, source)
        _save(SOURCE_FILE, rows[:100])
    return source


def list_information_sources() -> list[dict[str, Any]]:
    with _LOCK:
        return sorted(_read_list(SOURCE_FILE), key=lambda row: str(row.get("created_at") or ""), reverse=True)


def update_information_source(source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        rows = _read_list(SOURCE_FILE)
        target = next((row for row in rows if row.get("id") == source_id), None)
        if target is None:
            raise KeyError(source_id)
        if "name" in payload:
            target["name"] = str(payload.get("name") or "").strip()[:80] or target.get("name")
        if "url" in payload:
            target["url"] = _validate_source_url(str(payload.get("url") or ""))
        if "keywords" in payload:
            target["keywords"] = _split_terms(payload.get("keywords"))[:20]
        if "enabled" in payload:
            target["enabled"] = bool(payload.get("enabled"))
        target["updated_at"] = _now()
        _save(SOURCE_FILE, rows)
        return dict(target)


def delete_information_source(source_id: str) -> bool:
    with _LOCK:
        rows = _read_list(SOURCE_FILE)
        remaining = [row for row in rows if row.get("id") != source_id]
        if len(remaining) == len(rows):
            return False
        _save(SOURCE_FILE, remaining)
        return True


def _clean_feed_text(value: Any, limit: int = 500) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _child_text(element: ET.Element, names: set[str]) -> str:
    for child in element.iter():
        local_name = child.tag.rsplit("}", 1)[-1].lower()
        if local_name in names and child.text:
            return str(child.text).strip()
    return ""


def _parse_feed(content: bytes, source: dict[str, Any], limit: int = 30) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError("该地址没有返回可识别的资讯列表") from exc
    root_name = root.tag.rsplit("}", 1)[-1].lower()
    if root_name not in {"rss", "feed", "rdf"}:
        raise ValueError("该地址不是标准资讯源")
    entries = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}]
    collected_at = _now()
    rows: list[dict[str, Any]] = []
    for entry in entries[: max(1, min(limit, 100))]:
        title = _clean_feed_text(_child_text(entry, {"title"}), 240)
        summary = _clean_feed_text(_child_text(entry, {"description", "summary", "content"}), 800)
        link = _child_text(entry, {"link"})
        if not link:
            for child in entry.iter():
                if child.tag.rsplit("}", 1)[-1].lower() == "link" and child.attrib.get("href"):
                    link = str(child.attrib.get("href") or "")
                    break
        published_at = _child_text(entry, {"pubdate", "published", "updated", "date"})
        if not title and not summary:
            continue
        rows.append({
            "id": f"news_{uuid.uuid4().hex[:10]}",
            "title": title or summary[:80],
            "summary": summary,
            "source_url": link,
            "source_id": source.get("id") or "",
            "source_name": source.get("name") or "公开资讯",
            "collection_method": source.get("collection_method") or "public_feed",
            "data_quality": "verified_source",
            "published_at": published_at,
            "collected_at": collected_at,
        })
    return rows


def _parse_public_page(content: bytes, source: dict[str, Any], limit: int = 30) -> list[dict[str, Any]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "html.parser")
    base_url = str(source.get("url") or "")
    collected_at = _now()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    selectors = "article a[href], h1 a[href], h2 a[href], h3 a[href], [class*='title'] a[href]"
    for anchor in soup.select(selectors):
        title = _clean_feed_text(anchor.get_text(" ", strip=True), 240)
        href = str(anchor.get("href") or "").strip()
        if len(title) < 6 or not href or href.startswith(("javascript:", "#")):
            continue
        item_url = urljoin(base_url, href)
        if urlparse(item_url).scheme not in {"http", "https"} or item_url in seen:
            continue
        seen.add(item_url)
        parent = anchor.find_parent(["article", "li", "div"])
        parent_text = _clean_feed_text(parent.get_text(" ", strip=True) if parent else title, 900)
        summary = parent_text[len(title):].strip() if parent_text.startswith(title) else parent_text
        published_match = re.search(r"(?:\d+\s*(?:分钟|小时|天)前|\d{4}[-年/]\d{1,2}[-月/]\d{1,2}日?)", summary)
        rows.append({
            "id": f"news_{uuid.uuid4().hex[:10]}",
            "title": title,
            "summary": summary[:800],
            "source_url": item_url,
            "source_id": source.get("id") or "",
            "source_name": source.get("name") or (urlparse(base_url).hostname or "公开资讯"),
            "collection_method": "public_page",
            "data_quality": "observed",
            "published_at": published_match.group(0) if published_match else "",
            "collected_at": collected_at,
        })
        if len(rows) >= max(1, min(limit, 100)):
            break
    if not rows:
        raise ValueError("该地址没有找到可识别的公开资讯")
    return rows


async def _fetch_market_feed(source: dict[str, Any], limit: int = 30) -> list[dict[str, Any]]:
    import httpx

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0),
        follow_redirects=True,
        trust_env=False,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SZYG/1.0"},
    ) as client:
        response = await client.get(str(source.get("url") or ""))
        response.raise_for_status()
    content = response.content[:2_000_000]
    try:
        return _parse_feed(content, source, limit=limit)
    except ValueError:
        return _parse_public_page(content, source, limit=limit)


async def _fetch_public_news_search(keyword: str, limit: int = 20) -> list[dict[str, Any]]:
    import httpx
    from bs4 import BeautifulSoup

    url = f"https://www.baidu.com/s?tn=news&word={quote_plus(keyword)}"
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0),
        follow_redirects=True,
        trust_env=False,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    collected_at = _now()
    items: list[dict[str, Any]] = []
    for card in soup.select("div.c-container")[: max(1, min(limit, 50))]:
        anchor = card.select_one("h3 a")
        if anchor is None:
            continue
        title = _clean_feed_text(anchor.get_text(" ", strip=True), 240)
        source_url = str(anchor.get("href") or "").strip()
        card_text = _clean_feed_text(card.get_text(" ", strip=True), 900)
        summary = card_text[len(title):].strip() if card_text.startswith(title) else card_text
        if not title or not source_url:
            continue
        source_host = (urlparse(source_url).hostname or "公开资讯").removeprefix("www.")
        published_match = re.search(r"(?:\d+\s*(?:分钟|小时|天)前|\d{4}年\d{1,2}月\d{1,2}日)", summary)
        items.append({
            "id": f"news_{uuid.uuid4().hex[:10]}",
            "title": title,
            "summary": summary[:800],
            "source_url": source_url,
            "source_id": f"auto_{keyword}",
            "source_name": source_host,
            "collection_method": "public_news_search",
            "data_quality": "observed",
            "published_at": published_match.group(0) if published_match else "",
            "collected_at": collected_at,
        })
    return items


def _news_relevance(item: dict[str, Any], profile: dict[str, Any], keywords: list[str]) -> int:
    profile_query = " ".join(filter(None, [
        str(profile.get("product_name") or "").strip(),
        str(profile.get("industry") or "").strip(),
        str(profile.get("audience") or "").strip(),
        " ".join(_split_terms(profile.get("seed_keywords"))[:5]),
    ]))
    content_text = f"{item.get('title', '')} {item.get('summary', '')}"
    score = _content_relevance(profile_query, content_text)
    haystack = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    keyword_hits = sum(1 for keyword in keywords if keyword and keyword.lower() in haystack)
    return min(100, score + min(30, keyword_hits * 10))


async def collect_market_news(
    profile_id: str = "default",
    include_auto_search: bool = True,
    profile_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profiles = list_business_profiles()
    profile = (
        _normalize_business_profile(profile_override)
        if profile_override is not None
        else next((row for row in profiles if row.get("id") == profile_id), profiles[0] if profiles else {"id": profile_id})
    )
    knowledge_context = _load_knowledge_context(profile)
    keywords = generate_discovery_keywords(profile, limit=5, knowledge_context=knowledge_context)
    sources = [dict(row) for row in list_information_sources() if row.get("enabled", True)]
    if include_auto_search:
        for keyword in keywords[:3]:
            sources.append({
                "id": f"auto_{keyword}",
                "name": f"公开资讯 · {keyword}",
                "url": f"https://www.baidu.com/s?tn=news&word={quote_plus(keyword)}",
                "keywords": [keyword],
                "collection_method": "public_news_search",
                "automatic": True,
            })

    collected: list[dict[str, Any]] = []
    source_results: list[dict[str, Any]] = []
    for source in sources[:20]:
        try:
            items = (
                await _fetch_public_news_search(str((source.get("keywords") or [""])[0]), limit=20)
                if source.get("automatic") is True
                else await _fetch_market_feed(source, limit=30)
            )
            relevant = []
            source_keywords = _split_terms(source.get("keywords")) or keywords
            for item in items:
                item["relevance_score"] = _news_relevance(item, profile, source_keywords)
                item["matched_keywords"] = [word for word in source_keywords if word.lower() in f"{item.get('title', '')} {item.get('summary', '')}".lower()][:5]
                if item["relevance_score"] >= 20 or source.get("automatic") is not True:
                    relevant.append(item)
            collected.extend(relevant)
            distinct_keys = {
                str(item.get("source_url") or "").strip().lower()
                or re.sub(r"\s+", "", str(item.get("title") or "")).lower()
                for item in relevant
            }
            source_results.append({"id": source.get("id"), "status": "success", "count": len(distinct_keys), "error": ""})
        except Exception as exc:
            source_results.append({"id": source.get("id"), "status": "failed", "count": 0, "error": str(exc)[:300]})

    deduplicated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sorted(collected, key=lambda row: (int(row.get("relevance_score") or 0), str(row.get("published_at") or "")), reverse=True):
        key = str(item.get("source_url") or "").strip().lower() or re.sub(r"\s+", "", str(item.get("title") or "")).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)

    with _LOCK:
        existing = _read_list(MARKET_NEWS_FILE)
        combined = deduplicated + existing
        unique_rows: list[dict[str, Any]] = []
        stored_seen: set[str] = set()
        for item in combined:
            key = str(item.get("source_url") or "").strip().lower() or re.sub(r"\s+", "", str(item.get("title") or "")).lower()
            if not key or key in stored_seen:
                continue
            stored_seen.add(key)
            unique_rows.append(item)
        _save(MARKET_NEWS_FILE, unique_rows[:1000])

        source_rows = _read_list(SOURCE_FILE)
        result_map = {str(row.get("id") or ""): row for row in source_results}
        now = _now()
        for row in source_rows:
            result = result_map.get(str(row.get("id") or ""))
            if not result:
                continue
            row["status"] = result["status"]
            row["item_count"] = result["count"]
            row["last_error"] = result["error"]
            row["last_sync_at"] = now
            row["updated_at"] = now
        _save(SOURCE_FILE, source_rows)

    return {
        "items": deduplicated[:100],
        "total": len(deduplicated),
        "sources": source_results,
        "keywords": keywords,
        "knowledge_sources": sorted({str(item.get("source") or "知识库") for item in knowledge_context}),
        "updated_at": _now(),
    }


def list_market_news(limit: int = 100, keyword: str = "", source_id: str = "") -> list[dict[str, Any]]:
    rows = _read_list(MARKET_NEWS_FILE)
    needle = keyword.strip().lower()
    if source_id:
        rows = [row for row in rows if str(row.get("source_id") or "") == source_id]
    if needle:
        rows = [row for row in rows if needle in f"{row.get('title', '')} {row.get('summary', '')} {row.get('source_name', '')}".lower()]
    return sorted(
        rows,
        key=lambda row: (int(row.get("relevance_score") or 0), str(row.get("published_at") or row.get("collected_at") or "")),
        reverse=True,
    )[: max(1, min(limit, 500))]


async def discover_from_profile(
    payload: dict[str, Any],
    persist_profile: bool = True,
    persist_discovery: bool = True,
) -> dict[str, Any]:
    profile = upsert_business_profile(payload) if persist_profile else _normalize_business_profile(payload)
    platforms = _split_terms(profile.get("platforms")) or ["douyin", "xhs", "bilibili", "weibo"]
    knowledge_context = _load_knowledge_context(profile)
    keywords = generate_discovery_keywords(profile, knowledge_context=knowledge_context)
    per_keyword_limit = max(1, min(int(payload.get("per_keyword_limit") or 5), 10))
    max_keywords = max(1, min(int(payload.get("max_keywords") or 4), len(keywords) or 1))
    selected_keywords = keywords[:max_keywords]
    now = _now()

    search_plans = [
        {
            "platform": platform,
            "platform_label": PLATFORM_LABELS.get(platform, platform),
            "keyword": keyword,
            "search_url": _search_url(platform, keyword),
        }
        for keyword in selected_keywords
        for platform in platforms
    ]

    content_items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    try:
        from szyg.intercept_engine import get_intercept_engine

        engine = get_intercept_engine()
        for keyword in selected_keywords:
            results = await engine.search(keyword, platforms=platforms, limit=per_keyword_limit, strict_dedup=False)
            for result in results:
                for video in result.videos:
                    content_items.append(_video_to_item(video, keyword))
                if not result.videos:
                    errors.append({
                        "platform": result.platform,
                        "keyword": keyword,
                        "message": "未返回公开内容，可从搜索入口人工确认",
                    })
    except Exception as exc:
        errors.append({"platform": "all", "keyword": "", "message": str(exc)})

    content_items = [item for item in content_items if int(item.get("relevance_score") or 0) >= 25]
    await _enrich_bilibili_comment_samples(content_items)
    _annotate_breakouts(content_items)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in content_items:
        author = str(item.get("author") or "").strip()
        if not author:
            continue
        key = (str(item.get("platform") or ""), author)
        grouped.setdefault(key, []).append(item)
    candidates = [
        _candidate_from_author(platform, author, evidence)
        for (platform, author), evidence in grouped.items()
    ]
    candidates.sort(key=lambda item: (int(item.get("matched_items") or 0), str(item.get("reason") or "")), reverse=True)
    top_items = _top_content(content_items, limit=10)
    summary = _make_summary(profile, content_items, candidates, errors)
    analysis = _make_content_analysis(profile, content_items, candidates)
    action_suggestions = _make_action_suggestions(profile, content_items, candidates, now)

    discovery = {
        "id": f"disc_{uuid.uuid4().hex[:10]}",
        "profile": profile,
        "keywords": selected_keywords,
        "platforms": platforms,
        "search_plans": search_plans,
        "knowledge_context": knowledge_context,
        "knowledge_sources": sorted({str(item.get("source") or "知识库") for item in knowledge_context}),
        "content_items": content_items[:100],
        "top_content": top_items,
        "candidates": candidates[:30],
        "summary": summary,
        "analysis": analysis,
        "action_suggestions": action_suggestions,
        "errors": errors,
        "created_at": now,
        "updated_at": now,
    }
    if persist_discovery:
        with _LOCK:
            rows = _read_list(DISCOVERY_FILE)
            rows.insert(0, discovery)
            _save(DISCOVERY_FILE, rows[:100])
    return discovery


def list_discoveries(limit: int = 20) -> list[dict[str, Any]]:
    with _LOCK:
        rows = _read_list(DISCOVERY_FILE)
    return rows[: max(1, min(limit, 100))]


def list_content_items(limit: int = 50, platform: str = "", keyword: str = "") -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for discovery in list_discoveries(limit=100):
        for item in discovery.get("content_items", []):
            enriched = dict(item)
            enriched["discovery_id"] = discovery.get("id")
            enriched["captured_at"] = discovery.get("created_at")
            items.append(enriched)
    if platform:
        items = [item for item in items if str(item.get("platform") or "") == platform]
    if keyword:
        q = keyword.lower()
        items = [
            item for item in items
            if q in str(item.get("title") or "").lower()
            or q in str(item.get("description") or "").lower()
            or q in str(item.get("author") or "").lower()
            or q in str(item.get("keyword") or "").lower()
        ]
    return _top_content(items, limit=max(1, min(limit, 200)))


def _make_market_signals(discovery: dict[str, Any], monitoring: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for item in discovery.get("top_content", []) or []:
        if not item.get("is_breakout"):
            continue
        signals.append({
            "id": f"signal_{item.get('id')}",
            "type": "breakout",
            "level": "high" if int(item.get("hot_score") or 0) >= 85 else "medium",
            "title": item.get("title") or "高互动内容",
            "summary": item.get("breakout_reason") or "同批样本中表现突出",
            "platform": item.get("platform") or "",
            "platform_label": item.get("platform_label") or "",
            "source_url": item.get("source_url") or "",
            "source_name": item.get("source_name") or "公开平台数据",
            "observed_at": item.get("collected_at") or discovery.get("created_at") or "",
            "score": item.get("hot_score") or 0,
        })

    analysis = discovery.get("analysis") or {}
    for index, item in enumerate((analysis.get("demand_signals") or [])[:4]):
        signals.append({
            "id": f"signal_demand_{index}_{discovery.get('id', '')}",
            "type": "demand",
            "level": "medium",
            "title": "用户需求信号",
            "summary": item.get("text") or "",
            "platform": item.get("platform") or "",
            "platform_label": item.get("platform_label") or "",
            "source_url": item.get("source_url") or "",
            "source_name": "公开评论样本",
            "observed_at": discovery.get("created_at") or "",
            "score": 0,
        })

    for index, item in enumerate((monitoring.get("latest_items") or [])[:3]):
        signals.append({
            "id": f"signal_update_{index}_{item.get('account_id', '')}",
            "type": "competitor_update",
            "level": "info",
            "title": f"{item.get('account_name') or '竞品账号'} 发布新内容",
            "summary": item.get("title") or "监控账号出现新作品",
            "platform": item.get("platform") or "",
            "platform_label": item.get("platform_label") or "",
            "source_url": item.get("url") or "",
            "source_name": item.get("source_name") or "竞品账号监控",
            "observed_at": item.get("collected_at") or item.get("published_at") or "",
            "score": item.get("engagement") or 0,
        })
    return signals[:12]


def visualization_data() -> dict[str, Any]:
    discoveries = list_discoveries(limit=100)
    latest = discoveries[0] if discoveries else {}
    content_items = [dict(item) for item in (latest.get("content_items") or [])]
    _annotate_breakouts(content_items)
    platform_distribution = [
        {
            "platform": platform,
            "label": PLATFORM_LABELS.get(platform, platform),
            "count": count,
        }
        for platform, count in sorted(
            (latest.get("summary") or {}).get("platforms", {}).items(),
            key=lambda pair: int(pair[1]),
            reverse=True,
        )
    ]
    topic_engagement = [
        {
            "topic": item.get("topic") or "未分类",
            "engagement": item.get("engagement") or 0,
            "count": item.get("count") or 0,
            "quality": item.get("avg_quality_score") or 0,
        }
        for item in ((latest.get("analysis") or {}).get("top_topics") or [])[:8]
    ]

    timeline_map: dict[str, dict[str, Any]] = {}
    for discovery in reversed(discoveries):
        date_key = str(discovery.get("created_at") or "")[:10]
        if not date_key:
            continue
        row = timeline_map.setdefault(date_key, {"date": date_key, "content": 0, "competitors": 0})
        row["content"] += len(discovery.get("content_items") or [])
        row["competitors"] += len(discovery.get("candidates") or [])

    snapshots = _read_list(SNAPSHOT_FILE)
    account_groups: dict[str, list[dict[str, Any]]] = {}
    for snapshot in snapshots:
        account_groups.setdefault(str(snapshot.get("entity_id") or ""), []).append(snapshot)
    account_growth = []
    for values in account_groups.values():
        values.sort(key=lambda item: str(item.get("captured_at") or ""))
        latest_snapshot = values[-1]
        first_snapshot = values[0]
        latest_followers = latest_snapshot.get("followers")
        first_followers = first_snapshot.get("followers")
        growth = None
        if isinstance(latest_followers, (int, float)) and isinstance(first_followers, (int, float)):
            growth = latest_followers - first_followers
        account_growth.append({
            "entity_id": latest_snapshot.get("entity_id") or "",
            "name": latest_snapshot.get("name") or "竞品账号",
            "platform": latest_snapshot.get("platform") or "",
            "followers": latest_followers,
            "growth": growth,
            "points": [
                {"time": item.get("captured_at") or "", "followers": item.get("followers")}
                for item in values[-30:]
            ],
        })
    account_growth.sort(key=lambda item: int(item.get("growth") or 0), reverse=True)

    source_map: dict[tuple[str, str], dict[str, Any]] = {}
    for item in content_items:
        key = (str(item.get("source_name") or "公开网络数据"), str(item.get("collection_method") or "unknown"))
        row = source_map.setdefault(key, {
            "name": key[0],
            "method": key[1],
            "count": 0,
            "quality": item.get("data_quality") or "observed",
            "last_collected_at": "",
        })
        row["count"] += 1
        row["last_collected_at"] = max(str(row["last_collected_at"]), str(item.get("collected_at") or ""))

    return {
        "platform_distribution": platform_distribution,
        "topic_engagement": topic_engagement,
        "collection_timeline": list(timeline_map.values())[-30:],
        "account_growth": account_growth[:10],
        "data_sources": list(source_map.values()),
        "breakouts": [item for item in _top_content(content_items, limit=20) if item.get("is_breakout")][:8],
        "sample_size": len(content_items),
        "updated_at": latest.get("updated_at") or latest.get("created_at") or "",
    }


def latest_report() -> dict[str, Any]:
    monitoring = _make_monitoring_digest()
    visualization = visualization_data()
    discoveries = list_discoveries(limit=1)
    if not discoveries:
        return {
            "summary": {
                "headline": "还没有情报发现记录",
                "content_count": 0,
                "candidate_count": 0,
                "platforms": {},
                "keywords": {},
                "error_count": 0,
                "confidence": "low",
            },
            "action_suggestions": [],
            "top_content": [],
            "monitoring": monitoring,
            "analysis": {
                "top_topics": [],
                "demand_signals": [],
                "account_opportunities": [],
                "content_angles": [],
            },
            "visualization": visualization,
            "market_signals": _make_market_signals({}, monitoring),
            "knowledge_sources": [],
            "updated_at": "",
        }
    discovery = discoveries[0]
    report_discovery = dict(discovery)
    report_items = [dict(item) for item in (discovery.get("content_items") or [])]
    _annotate_breakouts(report_items)
    report_discovery["content_items"] = report_items
    report_discovery["top_content"] = _top_content(report_items, limit=10)
    return {
        "discovery_id": discovery.get("id"),
        "summary": discovery.get("summary") or {},
        "analysis": discovery.get("analysis") or {},
        "monitoring": monitoring,
        "action_suggestions": discovery.get("action_suggestions") or [],
        "top_content": report_discovery["top_content"],
        "visualization": visualization,
        "market_signals": _make_market_signals(report_discovery, monitoring),
        "knowledge_sources": discovery.get("knowledge_sources") or [],
        "updated_at": discovery.get("updated_at") or discovery.get("created_at"),
    }


def list_content_briefs(limit: int = 20) -> list[dict[str, Any]]:
    with _LOCK:
        rows = _read_list(BRIEF_FILE)
    return sorted(rows, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)[: max(1, min(limit, 100))]


def content_brief_prompt(brief_id: str) -> dict[str, Any]:
    brief = next((item for item in list_content_briefs(limit=100) if item.get("id") == brief_id), None)
    if not brief:
        raise KeyError("选题简报不存在")
    demand_lines = [
        f"- {str(signal.get('text') or '').strip()}"
        for signal in brief.get("demand_signals", [])
        if str(signal.get("text") or "").strip()
    ]
    source_lines = [
        f"- {url}"
        for url in brief.get("source_urls", [])
        if str(url or "").strip()
    ]
    prompt = "\n".join([
        f"请根据以下情报选题简报生成一组可直接用于内容发布的营销文案。",
        "",
        f"选题标题：{brief.get('title') or ''}",
        f"内容目标：{brief.get('objective') or ''}",
        f"建议平台：{'、'.join(brief.get('platform_suggestion') or []) or '小红书、抖音'}",
        f"参考主题：{brief.get('reference_topic') or ''}",
        f"参考内容：{brief.get('reference_content') or ''}",
        "",
        "内容结构：",
        *[f"{index + 1}. {line}" for index, line in enumerate(brief.get("outline") or [])],
        "",
        "评论区需求信号：",
        *(demand_lines or ["- 暂无明确评论需求，请围绕目标受众痛点表达。"]),
        "",
        "来源链接：",
        *(source_lines or ["- 暂无"]),
        "",
        "要求：",
        "- 不要照搬竞品标题或表达。",
        "- 输出中文自然、具体、可直接发布。",
        "- 强调自身产品差异化卖点和用户收益。",
    ]).strip()
    return {
        "brief_id": brief_id,
        "prompt": prompt,
        "copy_type": "情报选题文案",
        "title": brief.get("title") or "情报选题简报",
    }


def _save_content_brief(brief: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        rows = _read_list(BRIEF_FILE)
        rows.insert(0, brief)
        _save(BRIEF_FILE, rows[:200])
    return brief


def _unique_urls(values: list[Any]) -> list[str]:
    seen_urls: set[str] = set()
    urls = []
    for value in values:
        url = str(value or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        urls.append(url)
    return urls


def _create_monitoring_content_brief(payload: dict[str, Any]) -> dict[str, Any]:
    monitoring = _make_monitoring_digest(limit_items=20)
    source_url = str(payload.get("source_url") or "").strip()
    items = monitoring.get("top_recent_items") or []
    source_item = next((item for item in items if source_url and item.get("url") == source_url), None) or (items[0] if items else None)
    if not source_item:
        raise ValueError("还没有可用于生成简报的监控作品，请先同步竞品账号")
    title_text = str(source_item.get("title") or "竞品近期作品").strip()
    account_name = str(source_item.get("account_name") or "竞品账号").strip()
    platform_label = str(source_item.get("platform_label") or PLATFORM_LABELS.get(str(source_item.get("platform") or ""), "内容平台"))
    now = _now()
    brief = {
        "id": f"brief_{uuid.uuid4().hex[:10]}",
        "discovery_id": "",
        "source": "monitoring",
        "title": str(payload.get("title") or f"围绕《{title_text[:24]}》做差异化内容").strip()[:80],
        "objective": f"参考 {account_name} 的近期高互动作品，为自身业务生成一条不同角度、不同表达的内容方向。",
        "platform_suggestion": [platform_label],
        "outline": [
            f"开头：抓住《{title_text[:40]}》中的用户兴趣点，但换成自身品牌视角。",
            "主体：拆出竞品内容背后的用户需求，再给出自身产品/服务的差异化解决方式。",
            "证明：补充真实场景、体验细节或对比理由，避免只复述竞品观点。",
            "结尾：引导用户评论问题、收藏或进入私域咨询。",
        ],
        "reference_topic": title_text,
        "reference_content": title_text,
        "demand_signals": [],
        "source_urls": _unique_urls([source_item.get("url")]),
        "notes": str(payload.get("notes") or "").strip(),
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    return _save_content_brief(brief)


def create_content_brief(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    if str(payload.get("source") or "").strip() == "monitoring":
        return _create_monitoring_content_brief(payload)
    discoveries = list_discoveries(limit=1)
    if not discoveries:
        return _create_monitoring_content_brief(payload)
    discovery = discoveries[0]
    profile = discovery.get("profile") or {}
    analysis = discovery.get("analysis") or {}
    angles = analysis.get("content_angles") or []
    angle_index = max(0, min(int(payload.get("angle_index") or 0), max(0, len(angles) - 1))) if angles else 0
    angle = angles[angle_index] if angles else {}
    top_content = discovery.get("top_content") or discovery.get("content_items") or []
    source_item = top_content[0] if top_content else {}
    demand_signals = analysis.get("demand_signals") or []
    source_urls = _unique_urls([
        angle.get("source_url"),
        source_item.get("source_url"),
        *((signal.get("source_url") for signal in demand_signals[:2])),
    ])
    product = str(profile.get("product_name") or profile.get("industry") or "当前产品").strip()
    audience = str(profile.get("audience") or "目标客户").strip()
    title = str(payload.get("title") or angle.get("title") or f"{product} 情报选题简报").strip()
    now = _now()
    brief = {
        "id": f"brief_{uuid.uuid4().hex[:10]}",
        "discovery_id": discovery.get("id"),
        "source": "discovery",
        "title": title[:80],
        "objective": f"面向{audience}，基于竞品公开内容，为 {product} 生成一条差异化内容方向。",
        "platform_suggestion": _brief_platform_suggestion(discovery.get("platforms") or []),
        "outline": [
            f"开头：用“{(demand_signals[0].get('text') if demand_signals else source_item.get('title') or product)[:40]}”作为用户痛点或好奇钩子。",
            f"主体：围绕 {product} 的差异化卖点展开，避免照搬竞品标题和表达。",
            "证明：结合真实使用场景、对比体验或评论区问题给出可信解释。",
            "结尾：给出低压力行动建议，例如收藏、评论提问、私信咨询或查看下一篇。",
        ],
        "reference_topic": angle.get("title") or source_item.get("keyword") or "",
        "reference_content": source_item.get("title") or angle.get("description") or "",
        "demand_signals": demand_signals[:5],
        "source_urls": source_urls[:5],
        "notes": str(payload.get("notes") or "").strip(),
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    return _save_content_brief(brief)


def accept_discovery_candidate(discovery_id: str, candidate_id: str) -> dict[str, Any]:
    discoveries = list_discoveries(limit=100)
    for discovery in discoveries:
        if discovery.get("id") != discovery_id:
            continue
        for candidate in discovery.get("candidates", []):
            if candidate.get("id") != candidate_id:
                continue
            payload = {
                "profile_url": candidate.get("profile_url") or candidate.get("evidence_url") or "",
                "platform": candidate.get("platform") or "",
                "name": candidate.get("name") or "",
                "followers": candidate.get("followers"),
                "following": candidate.get("following"),
                "tags": candidate.get("tags") or [],
            }
            row = create_competitor(payload)
            if row.get("platform") == "bilibili":
                try:
                    row = sync_competitor(str(row.get("id") or ""))
                    row["sync_message"] = "由自动发现加入监控，已同步B站账号资料"
                except Exception:
                    row["sync_message"] = "由自动发现加入监控，B站账号资料同步失败，可稍后手动同步"
            else:
                row["sync_message"] = "由自动发现加入监控，等待账号主页补全和深度采集"
            with _LOCK:
                rows = _rows()
                for index, item in enumerate(rows):
                    if item.get("id") == row["id"]:
                        rows[index] = row
                        _save(COMPETITOR_FILE, rows)
                        break
            return row
    raise KeyError("候选项不存在")
