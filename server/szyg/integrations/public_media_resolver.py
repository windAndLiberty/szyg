"""Resolve downloadable media from public work pages with the shared browser pool."""

from __future__ import annotations

import asyncio
import ipaddress
import mimetypes
import re
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx


DOWNLOADABLE_VIDEO_SUFFIXES = {".mp4", ".mov"}
DOWNLOADABLE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DOWNLOADABLE_SUFFIXES = DOWNLOADABLE_VIDEO_SUFFIXES | DOWNLOADABLE_IMAGE_SUFFIXES
JSON_CONTENT_TYPES = {"application/json", "text/json"}
MAX_RESPONSE_JSON_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class ResolvedPublicMedia:
    url: str
    page_url: str
    title: str = ""
    content_type: str = ""
    cover_url: str = ""
    score: int = 0


def _suffix(url: str) -> str:
    return Path(unquote(urlparse(url).path)).suffix.lower()


def _is_http_url(value: str) -> bool:
    try:
        return urlparse(value).scheme.lower() in {"http", "https"} and bool(urlparse(value).hostname)
    except ValueError:
        return False


def _is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def validate_public_url(value: str) -> str:
    """Reject local/private destinations before giving a URL to the browser."""
    url = str(value or "").strip()
    if not _is_http_url(url):
        raise ValueError("请输入可公开访问的 HTTP 或 HTTPS 链接")
    parsed = urlparse(url)
    hostname = str(parsed.hostname or "").strip().lower()
    if hostname in {"localhost", "localhost.localdomain"}:
        raise ValueError("请输入可公开访问的链接")

    def resolve() -> list[str]:
        return list({row[4][0] for row in socket.getaddrinfo(hostname, parsed.port or 443)})

    try:
        addresses = await asyncio.to_thread(resolve)
    except OSError as exc:
        raise ValueError("链接地址无法访问，请检查后重试") from exc
    if not addresses or any(not _is_public_ip(address) for address in addresses):
        raise ValueError("请输入可公开访问的链接")
    return url


def _candidate_score(url: str, context: str = "", content_type: str = "") -> int:
    suffix = _suffix(url)
    mime = content_type.split(";", 1)[0].strip().lower()
    if suffix not in DOWNLOADABLE_SUFFIXES and not mime.startswith(("video/", "image/")):
        return -1000
    score = 0
    if suffix in DOWNLOADABLE_VIDEO_SUFFIXES:
        score += 90
    elif suffix in DOWNLOADABLE_IMAGE_SUFFIXES:
        score += 25
    if mime.startswith("video/"):
        score += 80
    elif mime.startswith("image/"):
        score += 15

    haystack = f"{context} {url}".casefold()

    def has_marker(token: str) -> bool:
        return bool(re.search(rf"(?:^|[^a-z0-9]){re.escape(token)}(?:$|[^a-z0-9])", haystack))

    if any(has_marker(token) for token in ("output", "result", "final", "generated", "creative")):
        score += 35
    if any(token in haystack for token in ("resource.resource", "video_url", "play_url", "download_url")):
        score += 30
    if any(token in haystack for token in ("cover", "poster", "avatar", "thumbnail", "logo")):
        score -= 70
    if any(has_marker(token) for token in ("source", "input", "reference", "original")):
        score -= 35
    return score


def extract_media_candidates(value: Any, context: str = "") -> list[dict[str, Any]]:
    """Recursively find media URLs while retaining their semantic JSON path."""
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{context}.{key}" if context else str(key)
            rows.extend(extract_media_candidates(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(extract_media_candidates(child, f"{context}[{index}]"))
    elif isinstance(value, str) and _is_http_url(value):
        score = _candidate_score(value, context)
        if score > -1000:
            rows.append({"url": value, "context": context, "content_type": "", "score": score})
    return rows


def _best_candidate(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        url = str(row.get("url") or "")
        if not _is_http_url(url):
            continue
        score = int(row.get("score") or _candidate_score(url, str(row.get("context") or ""), str(row.get("content_type") or "")))
        current = unique.get(url)
        if current is None or int(current.get("score") or 0) < score:
            unique[url] = {**row, "score": score}
    video_rows = [row for row in unique.values() if _suffix(str(row.get("url") or "")) in DOWNLOADABLE_VIDEO_SUFFIXES or str(row.get("content_type") or "").startswith("video/")]
    pool = video_rows or list(unique.values())
    return max(pool, key=lambda row: int(row.get("score") or 0), default=None)


async def resolve_public_media(page_url: str, timeout_seconds: float = 18.0) -> ResolvedPublicMedia:
    """Load a public page in the background and resolve its primary downloadable media."""
    page_url = await validate_public_url(page_url)
    direct_suffix = _suffix(page_url)
    if direct_suffix in DOWNLOADABLE_SUFFIXES:
        return ResolvedPublicMedia(url=page_url, page_url=page_url, score=100)

    from szyg.platforms.browser_pool import get_browser_pool

    pool = get_browser_pool(headless=True)
    context = await pool.get_context("public_media_resolver")
    page = await context.new_page()
    candidates: list[dict[str, Any]] = []
    response_tasks: set[asyncio.Task] = set()
    media_found = asyncio.Event()
    validation_tasks: dict[str, asyncio.Task] = {}

    async def allow_public_request(route: Any, request: Any) -> None:
        request_url = str(request.url or "")
        if not request_url.lower().startswith(("http://", "https://")):
            await route.continue_()
            return
        try:
            hostname = str(urlparse(request_url).hostname or "").lower()
            task = validation_tasks.get(hostname)
            if task is None:
                task = asyncio.create_task(validate_public_url(request_url))
                validation_tasks[hostname] = task
            await task
            await route.continue_()
        except Exception:
            await route.abort("blockedbyclient")

    await page.route("**/*", allow_public_request)

    async def inspect_response(response: Any) -> None:
        try:
            content_type = str((await response.all_headers()).get("content-type") or "").split(";", 1)[0].lower()
            direct_score = _candidate_score(response.url, "network.response", content_type)
            if direct_score > -1000:
                candidates.append({
                    "url": response.url,
                    "context": "network.response",
                    "content_type": content_type,
                    "score": direct_score,
                })
                if direct_score >= 130:
                    media_found.set()
            if content_type not in JSON_CONTENT_TYPES and not content_type.endswith("+json"):
                return
            length = int((await response.all_headers()).get("content-length") or 0)
            if length > MAX_RESPONSE_JSON_BYTES:
                return
            payload = await response.json()
            found = extract_media_candidates(payload, "response")
            candidates.extend(found)
            if any(int(row.get("score") or 0) >= 110 for row in found):
                media_found.set()
        except Exception:
            return

    def on_response(response: Any) -> None:
        task = asyncio.create_task(inspect_response(response))
        response_tasks.add(task)
        task.add_done_callback(response_tasks.discard)

    page.on("response", on_response)
    title = ""
    cover_url = ""
    try:
        await page.goto(page_url, wait_until="domcontentloaded", timeout=45_000)
        try:
            await asyncio.wait_for(media_found.wait(), timeout=timeout_seconds)
            await asyncio.sleep(0.8)
        except asyncio.TimeoutError:
            pass
        if response_tasks:
            await asyncio.gather(*list(response_tasks), return_exceptions=True)
        dom = await page.evaluate(
            """
            () => ({
              title: document.querySelector('meta[property="og:title"]')?.content || document.title || '',
              cover: document.querySelector('meta[property="og:image"]')?.content || '',
              media: Array.from(document.querySelectorAll('video,video source')).flatMap((node) => [
                node.currentSrc || '', node.src || '', node.getAttribute('src') || '', node.poster || ''
              ]).filter(Boolean)
            })
            """
        )
        title = str(dom.get("title") or "").strip()
        cover_url = str(dom.get("cover") or "").strip()
        for media_url in dom.get("media") or []:
            score = _candidate_score(str(media_url), "dom.media")
            if score > -1000:
                candidates.append({"url": media_url, "context": "dom.media", "content_type": "", "score": score})
    finally:
        await page.close()
        await pool.return_context("public_media_resolver")

    best = _best_candidate(candidates)
    if not best:
        raise ValueError("未能从此页面找到可分析的视频，请尝试上传原视频")
    media_url = await validate_public_url(str(best["url"]))
    return ResolvedPublicMedia(
        url=media_url,
        page_url=page_url,
        title=title,
        content_type=str(best.get("content_type") or ""),
        cover_url=cover_url if _is_http_url(cover_url) else "",
        score=int(best.get("score") or 0),
    )


async def download_public_media(
    resolved: ResolvedPublicMedia,
    destination_dir: Path,
    *,
    max_bytes: int,
) -> tuple[Path, str, str]:
    """Download resolved media with a hard size cap and no proxy inheritance."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    headers = {"Referer": resolved.page_url, "User-Agent": "Mozilla/5.0"}
    timeout = httpx.Timeout(180, connect=20)
    temp_path: Path | None = None
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, trust_env=False, headers=headers) as client:
            async with client.stream("GET", resolved.url) as response:
                response.raise_for_status()
                await validate_public_url(str(response.url))
                declared = int(response.headers.get("content-length") or 0)
                if declared > max_bytes:
                    raise ValueError("视频文件过大，请下载后再上传")
                content_type = response.headers.get("content-type", resolved.content_type).split(";", 1)[0].strip().lower()
                suffix = _suffix(str(response.url)) or mimetypes.guess_extension(content_type) or ".mp4"
                if suffix not in DOWNLOADABLE_SUFFIXES:
                    suffix = ".mp4" if content_type.startswith("video/") else ".jpg"
                with tempfile.NamedTemporaryFile(dir=destination_dir, suffix=suffix, delete=False) as handle:
                    temp_path = Path(handle.name)
                    size = 0
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError("视频文件过大，请下载后再上传")
                        handle.write(chunk)
        raw_name = Path(unquote(urlparse(str(response.url)).path)).name
        filename = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", raw_name, flags=re.UNICODE)[:100] or f"inspiration{suffix}"
        with temp_path.open("rb") as handle:
            signature = handle.read(32)
        if suffix in DOWNLOADABLE_VIDEO_SUFFIXES and b"ftyp" not in signature:
            raise ValueError("未能获取有效的视频文件，请尝试上传原视频")
        if suffix in DOWNLOADABLE_IMAGE_SUFFIXES and not (
            signature.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF"))
        ):
            raise ValueError("未能获取有效的图片文件，请尝试上传原图")
        return temp_path, filename, content_type
    except Exception:
        if temp_path:
            temp_path.unlink(missing_ok=True)
        raise
