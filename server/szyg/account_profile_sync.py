"""Sync channel account profile metadata from platform pages."""

from __future__ import annotations

import asyncio
import json
import re
import urllib.request
from datetime import datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from szyg.channel_accounts import get_account, patch_account, safe_token
from szyg.data_path import DATA_DIR
from szyg.integrations.desktop_browser_session import get_desktop_browser_session
from szyg.platforms.weibo_desktop import WEIBO_HOME_URL, weibo_profile_key


PROFILE_SYNC_TTL_HOURS = 24
SAU_STEALTH_SCRIPT = Path(str(files("szyg.resources").joinpath("social_auto_upload", "stealth.min.js")))
SAU_COOKIES_DIR = DATA_DIR / "social_auto_upload" / "cookies"


def _now_iso() -> str:
    return datetime.now().isoformat()


def _parse_count(value: str) -> int:
    text = (value or "").strip().replace(",", "").replace("，", "")
    if not text:
        return 0
    match = re.search(r"([\d.]+)\s*([万wW千kK]?)", text)
    if not match:
        return 0
    number = float(match.group(1))
    unit = match.group(2).lower()
    if unit in ("万", "w"):
        number *= 10000
    elif unit in ("千", "k"):
        number *= 1000
    return int(number)


async def _first_text(page, selectors: list[str]) -> str:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count():
                text = (await locator.inner_text(timeout=2500)).strip()
                if text:
                    return re.sub(r"\s+", " ", text)
        except Exception:
            continue
    return ""


async def _first_attr(page, selectors: list[str], attr: str) -> str:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count():
                value = await locator.get_attribute(attr, timeout=2500)
                if value:
                    return value.strip()
        except Exception:
            continue
    return ""


def _extract_metric_from_text(text: str, labels: list[str]) -> int:
    normalized = re.sub(r"\s+", " ", text or "")
    for label in labels:
        patterns = [
            rf"{label}\s*[:：]?\s*([\d.,]+(?:万|w|W|千|k|K)?)",
            rf"([\d.,]+(?:万|w|W|千|k|K)?)\s*{label}",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                return _parse_count(match.group(1))
    return 0


def _text_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _line_after_label(lines: list[str], labels: list[str]) -> str:
    for index, line in enumerate(lines):
        if line in labels and index + 1 < len(lines):
            return lines[index + 1].strip()
    return ""


def _extract_metric_from_lines(lines: list[str], labels: list[str]) -> int:
    return _parse_count(_line_after_label(lines, labels))


def _extract_douyin_work_count(text: str) -> int:
    match = re.search(r"共\s*([\d,，]+)\s*个作品", text or "")
    if match:
        return _parse_count(match.group(1))
    return 0


def _extract_weibo_work_count(text: str) -> int:
    patterns = [
        r"全部微博[（(]\s*([\d,，]+)\s*[）)]",
        r"微博[（(]\s*([\d,，]+)\s*[）)]",
        r"([\d,，]+)\s*条微博",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            return _parse_count(match.group(1))
    return 0


def _extract_count_before_label(text: str, label: str) -> int:
    match = re.search(rf"([\d.,，]+(?:万|w|W|千|k|K)?)\s*{re.escape(label)}", text or "")
    return _parse_count(match.group(1)) if match else 0


def _to_int(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return _parse_count(str(value))


def _public_url(platform: str, platform_user_id: str, page_url: str) -> str:
    if platform_user_id:
        if platform == "douyin":
            return f"https://www.douyin.com/user/{platform_user_id}"
        if platform == "xhs":
            return f"https://www.xiaohongshu.com/user/profile/{platform_user_id}"
        if platform == "kuaishou":
            return f"https://www.kuaishou.com/profile/{platform_user_id}"
        if platform == "bilibili":
            return f"https://space.bilibili.com/{platform_user_id}"
        if platform == "tencent":
            return "https://channels.weixin.qq.com/platform"
    return page_url


def _sau_cookie_file(platform: str, account: dict) -> Path:
    sau_name = account.get("sau_account_name") or safe_token(account.get("id", ""))
    return SAU_COOKIES_DIR / f"{platform}_{sau_name}.json"


def _extract_cookie_header(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    cookies: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        if isinstance(raw.get("cookies"), list):
            cookies = [item for item in raw["cookies"] if isinstance(item, dict)]
        elif all(key in raw for key in ("name", "value")):
            cookies = [raw]
        else:
            for value in raw.values():
                if isinstance(value, dict) and all(key in value for key in ("name", "value")):
                    cookies.append(value)
    elif isinstance(raw, list):
        cookies = [item for item in raw if isinstance(item, dict)]

    pairs = []
    for cookie in cookies:
        name = str(cookie.get("name") or "").strip()
        value = str(cookie.get("value") or "").strip()
        domain = str(cookie.get("domain") or "")
        if name and value and ("bilibili" in domain or not domain):
            pairs.append(f"{name}={value}")
    return "; ".join(pairs)


def _http_json(url: str, cookie_header: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Cookie": cookie_header,
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.bilibili.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


async def _sync_with_page(account: dict) -> dict[str, Any]:
    platform = account.get("platform", "")
    if platform == "bilibili":
        return await asyncio.to_thread(_sync_bilibili, account)
    if platform == "tencent":
        return await _sync_tencent_channels(account)
    if platform == "weibo":
        return await _sync_weibo_desktop(account)

    storage_state = account.get("session_path", "")
    if not storage_state or not Path(storage_state).exists():
        return {
            "sync_status": "failed",
            "sync_message": "登录态文件不存在",
            "last_profile_sync_at": _now_iso(),
        }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="chromium")
        try:
            context = await browser.new_context(storage_state=storage_state)
            if SAU_STEALTH_SCRIPT.exists():
                await context.add_init_script(path=SAU_STEALTH_SCRIPT)
            page = await context.new_page()
            if platform == "douyin":
                return await _sync_douyin(page)
            if platform == "xhs":
                return await _sync_xhs(page)
            if platform == "kuaishou":
                return await _sync_kuaishou(page)
            return {
                "sync_status": "unsupported",
                "sync_message": "当前平台暂未接入账号资料同步",
                "last_profile_sync_at": _now_iso(),
            }
        finally:
            await browser.close()


async def _sync_douyin(page) -> dict[str, Any]:
    await page.goto("https://creator.douyin.com/creator-micro/home", wait_until="domcontentloaded", timeout=60000)
    try:
        await page.wait_for_function(
            "() => document.body && /抖音号|粉丝|获赞/.test(document.body.innerText || '')",
            timeout=12000,
        )
    except Exception:
        await page.wait_for_timeout(5000)
    if "login" in page.url.lower() or await page.get_by_text("扫码登录").count():
        return {
            "status": "needs_login",
            "sync_status": "failed",
            "sync_message": "抖音登录态已失效",
            "last_profile_sync_at": _now_iso(),
        }

    body_text = await page.locator("body").inner_text(timeout=5000)
    lines = _text_lines(body_text)
    douyin_id = ""
    nickname_from_lines = ""
    for index, line in enumerate(lines):
        match = re.search(r"抖音号[:：]\s*([\w.-]+)", line)
        if match:
            douyin_id = match.group(1)
            if index > 0:
                nickname_from_lines = lines[index - 1]
            break

    nickname = nickname_from_lines or await _first_text(page, [
        '[class*="user-name"]',
        '[class*="nickname"]',
        '[class*="account-name"]',
        '[class*="creator-name"]',
        'span[class*="name"]',
    ])
    avatar_url = await _first_attr(page, [
        'img[class*="avatar"]',
        'img[class*="Avatar"]',
        '[class*="avatar"] img',
    ], "src")
    followers = _extract_metric_from_lines(lines, ["粉丝", "关注者"]) or _extract_metric_from_text(body_text, ["粉丝", "关注者"])
    following = _extract_metric_from_lines(lines, ["关注"]) or _extract_metric_from_text(body_text, ["关注"])
    works_count = _extract_metric_from_lines(lines, ["作品", "内容"]) or _extract_metric_from_text(body_text, ["作品", "内容"])
    likes_count = _extract_metric_from_lines(lines, ["获赞", "点赞"]) or _extract_metric_from_text(body_text, ["获赞", "点赞"])

    try:
        await page.goto(
            "https://creator.douyin.com/creator-micro/content/manage?enter_from=publish",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        await page.wait_for_function(
            "() => document.body && /共\\s*\\d+\\s*个作品/.test(document.body.innerText || '')",
            timeout=20000,
        )
        manage_text = await page.locator("body").inner_text(timeout=5000)
        works_count = _extract_douyin_work_count(manage_text) or works_count
        work_data = await page.evaluate(
            """async () => {
              const response = await fetch('/janus/douyin/creator/pc/work_list?status=0&count=12&max_cursor=0&scene=star_atlas&device_platform=android&aid=1128', { credentials: 'same-origin' });
              return await response.json();
            }"""
        )
        if isinstance(work_data, dict):
            works_count = int(work_data.get("total") or works_count or 0)
            aweme_list = work_data.get("aweme_list") or []
            if aweme_list and isinstance(aweme_list[0], dict):
                author = aweme_list[0].get("author") or {}
                if isinstance(author, dict):
                    followers = int(author.get("follower_count") or followers or 0)
                    following = int(author.get("following_count") or following or 0)
                    likes_count = int(author.get("total_favorited") or likes_count or 0)
                    nickname = author.get("nickname") or nickname
    except Exception:
        pass

    if not nickname and not any([followers, following, works_count, likes_count]):
        return {
            "sync_status": "failed",
            "sync_message": "抖音页面已打开，但未识别到账号资料",
            "last_profile_sync_at": _now_iso(),
        }

    return {
        "nickname": nickname,
        "avatar_url": avatar_url,
        "platform_user_id": douyin_id,
        "profile_url": _public_url("douyin", douyin_id, page.url),
        "followers": followers,
        "following": following,
        "works_count": works_count,
        "likes_count": likes_count,
        "status": "connected",
        "sync_status": "success",
        "sync_message": "账号资料已同步",
        "last_profile_sync_at": _now_iso(),
    }


async def _sync_weibo_desktop(account: dict) -> dict[str, Any]:
    profile_key = account.get("desktop_profile_key") or weibo_profile_key(account.get("id", "weibo_default"))
    launch = get_desktop_browser_session().launch(
        WEIBO_HOME_URL,
        profile_key=profile_key,
        no_proxy=True,
        new_window=False,
    )
    if not launch.ok:
        return {
            "status": "needs_login",
            "sync_status": "failed",
            "sync_message": launch.error or launch.message or "打开微博失败",
            "last_profile_sync_at": _now_iso(),
        }
    if not launch.cdp_available:
        return {
            "status": "connected",
            "sync_status": "partial",
            "sync_message": "微博已打开，但暂时无法读取账号资料",
            "desktop_profile_key": profile_key,
            "last_profile_sync_at": _now_iso(),
        }
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(launch.cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            pages = [page for page in context.pages if "weibo.com" in page.url]
            page = pages[0] if pages else await context.new_page()
            await page.goto(WEIBO_HOME_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3500)
            body_text = await page.locator("body").inner_text(timeout=5000)
            data = await page.evaluate(
                """() => {
                  const text = document.body ? document.body.innerText : '';
                  const avatar = Array.from(document.querySelectorAll('img')).map((img) => img.src || '').find((src) => /sinaimg|weibo/.test(src)) || '';
                  const accountLink = Array.from(document.querySelectorAll('a[href*="/u/"]')).map((el) => ({
                    title: (el.getAttribute('title') || '').trim(),
                    aria: (el.getAttribute('aria-label') || '').trim(),
                    text: (el.innerText || el.textContent || '').trim(),
                    href: el.href || '',
                  })).find((item) => item.title || item.aria || item.text) || null;
                  const candidates = Array.from(document.querySelectorAll('a,span,div')).map((el) => (el.innerText || el.textContent || '').trim()).filter(Boolean).slice(0, 120);
                  const editors = Array.from(document.querySelectorAll('textarea,[contenteditable="true"],div[role="textbox"]')).map((el) => ({
                    text: (el.innerText || el.value || el.textContent || '').trim(),
                    placeholder: el.getAttribute('placeholder') || '',
                  }));
                  const hasPublisher = editors.some((item) => /新鲜事|分享|微博/.test(item.placeholder || item.text))
                    || /内容声明\\s*表情\\s*图片\\s*视频|图片\\s*视频\\s*话题|公开\\s*发送/.test(text);
                  const loginOnly = /登录|扫码|验证码|安全验证/.test(text)
                    && !hasPublisher
                    && !/首页\\s*全部关注|最新微博|特别关注/.test(text);
                  return { text, avatar, accountLink, candidates, editors, hasPublisher, loginOnly };
                }"""
            )
            if data.get("loginOnly"):
                return {
                    "status": "needs_login",
                    "sync_status": "failed",
                    "sync_message": "微博需要重新登录",
                    "desktop_profile_key": profile_key,
                    "last_profile_sync_at": _now_iso(),
                }
            text = str(data.get("text") or body_text)
            candidates = [str(item).strip() for item in data.get("candidates") or [] if str(item).strip()]
            nav_words = {
                "Weibo",
                "首页",
                "推荐",
                "视频",
                "消息",
                "全部关注",
                "最新微博",
                "特别关注",
                "好友圈",
                "自定义分组",
                "管理",
                "电影",
                "同学",
                "名人明星",
                "展开",
                "内容声明",
                "表情",
                "图片",
                "话题",
                "更多",
                "公开",
                "发送",
                "个人主页",
            }

            def valid_weibo_nickname(value: Any) -> str:
                item = str(value or "").strip()
                if not item or "\n" in item or "\r" in item:
                    return ""
                if item in nav_words:
                    return ""
                if not (1 <= len(item) <= 32):
                    return ""
                if re.search(r"首页|视频|发现|消息|登录|发布|粉丝|关注|微博|自定义分组|管理", item):
                    return ""
                return item

            account_link = data.get("accountLink") or {}
            profile_url = str(account_link.get("href") or "").strip()
            platform_user_id_match = re.search(r"/u/(\d+)", profile_url)
            platform_user_id = platform_user_id_match.group(1) if platform_user_id_match else ""
            nickname = (
                valid_weibo_nickname(account_link.get("title"))
                or valid_weibo_nickname(account_link.get("aria"))
                or valid_weibo_nickname(account_link.get("text"))
            )
            if not nickname:
                for item in candidates:
                    candidate = valid_weibo_nickname(item)
                    if candidate:
                        nickname = candidate
                        break
            followers = _extract_metric_from_text(text, ["粉丝"])
            following = _extract_metric_from_text(text, ["关注"])
            works_count = _extract_weibo_work_count(text) or _extract_metric_from_text(text, ["微博", "博文"])
            likes_count = _extract_metric_from_text(text, ["转评赞", "获赞", "点赞"])
            avatar_url = data.get("avatar") or account.get("avatar_url", "")
            bio = ""

            if profile_url:
                try:
                    await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(3500)
                    profile_data = await page.evaluate(
                        """() => {
                          const text = document.body ? document.body.innerText : '';
                          const avatar = Array.from(document.querySelectorAll('img')).map((img) => img.src || '').find((src) => /sinaimg|weibo/.test(src)) || '';
                          const header = Array.from(document.querySelectorAll('[class*="wrap_6c8b7"], [class*="box1"]'))
                            .map((el) => (el.innerText || el.textContent || '').trim())
                            .find((value) => /粉丝/.test(value) && /关注/.test(value) && /转评赞/.test(value)) || '';
                          const name = Array.from(document.querySelectorAll('[class*="_name_1yc79"], [class*="name_1yc79"]'))
                            .map((el) => (el.innerText || el.textContent || '').trim())
                            .find(Boolean) || '';
                          return { text, avatar, header, name };
                        }"""
                    )
                    profile_text = str(profile_data.get("text") or "")
                    profile_header = str(profile_data.get("header") or "")
                    profile_header_lines = _text_lines(profile_header)
                    profile_name = (
                        valid_weibo_nickname(profile_header_lines[0] if profile_header_lines else "")
                        or valid_weibo_nickname(profile_data.get("name"))
                    )
                    nickname = profile_name or nickname
                    avatar_url = profile_data.get("avatar") or avatar_url
                    metric_text = profile_header or profile_text
                    followers = _extract_count_before_label(metric_text, "粉丝") or followers
                    following = _extract_count_before_label(metric_text, "关注") or following
                    works_count = _extract_weibo_work_count(profile_text) or works_count
                    likes_count = (
                        _extract_count_before_label(metric_text, "转评赞")
                        or _extract_count_before_label(metric_text, "获赞")
                        or _extract_count_before_label(metric_text, "点赞")
                        or likes_count
                    )
                    bio_lines = _text_lines(profile_text)
                    for index, line in enumerate(bio_lines):
                        if line == (nickname or "") and index + 4 < len(bio_lines):
                            candidate = bio_lines[index + 4]
                            if candidate and not re.search(r"粉丝|关注|转评赞|精选|微博|相册", candidate):
                                bio = candidate[:120]
                            break
                except Exception:
                    pass
            return {
                "status": "connected",
                "sync_status": "success",
                "sync_message": "微博账号资料已同步",
                "nickname": nickname or account.get("nickname") or account.get("label") or "微博账号",
                "avatar_url": avatar_url,
                "platform_user_id": platform_user_id,
                "profile_url": profile_url or WEIBO_HOME_URL,
                "followers": followers,
                "following": following,
                "works_count": works_count,
                "likes_count": likes_count,
                "bio": bio,
                "desktop_profile_key": profile_key,
                "last_profile_sync_at": _now_iso(),
            }
    except Exception as exc:
        return {
            "status": "connected",
            "sync_status": "partial",
            "sync_message": f"微博已打开，但资料读取不完整：{exc}",
            "desktop_profile_key": profile_key,
            "last_profile_sync_at": _now_iso(),
        }


async def _sync_xhs(page) -> dict[str, Any]:
    await page.goto("https://creator.xiaohongshu.com", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2500)
    login_box = page.locator("div[class*='login-box']").first
    login_box_visible = False
    if await login_box.count():
        try:
            login_box_visible = await login_box.is_visible()
        except Exception:
            login_box_visible = True
    if "login" in page.url.lower() or login_box_visible:
        return {
            "status": "needs_login",
            "sync_status": "failed",
            "sync_message": "小红书登录态已失效",
            "last_profile_sync_at": _now_iso(),
        }

    profile_data: dict[str, Any] = {}
    user_data: dict[str, Any] = {}
    try:
        api_data = await page.evaluate(
            """async () => {
              const readJson = async (url) => {
                const response = await fetch(url, { credentials: 'include' });
                if (!response.ok) return null;
                const payload = await response.json();
                if (!payload || payload.success === false || payload.code !== 0) return null;
                return payload.data || null;
              };
              const profile = await readJson('/api/galaxy/creator/home/personal_info');
              const user = await readJson('/api/galaxy/user/info');
              return { profile, user };
            }"""
        )
        if isinstance(api_data, dict):
            raw_profile = api_data.get("profile")
            raw_user = api_data.get("user")
            if isinstance(raw_profile, dict):
                profile_data = raw_profile
            if isinstance(raw_user, dict):
                user_data = raw_user
    except Exception:
        profile_data = {}
        user_data = {}

    nickname = await _first_text(page, [
        ".creator-name",
        ".user-name",
        ".name",
        '[class*="creator-name"]',
        '[class*="user-name"]',
        '[class*="nickname"]',
    ])
    avatar_url = await _first_attr(page, [
        'img[class*="avatar"]',
        'img[class*="Avatar"]',
        '[class*="avatar"] img',
    ], "src")
    body_text = await page.locator("body").inner_text(timeout=5000)
    followers = _extract_metric_from_text(body_text, ["粉丝"])
    following = _extract_metric_from_text(body_text, ["关注"])
    works_count = _extract_metric_from_text(body_text, ["笔记", "作品", "发布"])
    likes_count = _extract_metric_from_text(body_text, ["获赞", "点赞", "赞藏"])
    user_id = str(user_data.get("userId") or "").strip()

    if profile_data:
        nickname = str(profile_data.get("name") or nickname or "").strip()
        avatar_url = str(profile_data.get("avatar") or avatar_url or "").strip()
        followers = _to_int(profile_data.get("fans_count")) or followers
        following = _to_int(profile_data.get("follow_count")) or following
        likes_count = _to_int(profile_data.get("faved_count")) or likes_count
        if not user_id:
            user_id = str(user_data.get("userId") or "").strip()

    if user_data:
        nickname = str(user_data.get("userName") or nickname or "").strip()
        avatar_url = str(user_data.get("userAvatar") or avatar_url or "").strip()

    try:
        note_count_future = asyncio.get_running_loop().create_future()

        async def capture_note_count(response) -> None:
            if "/api/galaxy/v2/creator/note/user/posted" not in response.url:
                return
            if note_count_future.done():
                return
            try:
                payload = await response.json()
                data = payload.get("data") if isinstance(payload, dict) else None
                notes = data.get("notes") if isinstance(data, dict) else None
                if isinstance(notes, list):
                    note_count_future.set_result(len(notes))
            except Exception:
                if not note_count_future.done():
                    note_count_future.set_result(0)

        page.on("response", capture_note_count)
        await page.goto("https://creator.xiaohongshu.com/new/note-manager", wait_until="domcontentloaded", timeout=60000)
        works_count = await asyncio.wait_for(note_count_future, timeout=15000)
    except Exception:
        pass

    return {
        "nickname": nickname,
        "avatar_url": avatar_url,
        "platform_user_id": user_id,
        "profile_url": _public_url("xhs", user_id, page.url),
        "followers": followers,
        "following": following,
        "works_count": works_count,
        "likes_count": likes_count,
        "status": "connected",
        "sync_status": "success",
        "sync_message": "账号资料已同步",
        "last_profile_sync_at": _now_iso(),
    }


async def _sync_kuaishou(page) -> dict[str, Any]:
    api_payloads: list[dict[str, Any]] = []

    async def capture_profile_response(response) -> None:
        url = response.url
        if not any(
            key in url
            for key in (
                "/rest/cp/creator/pc/home/infoV2",
                "/rest/cp/creator/pc/home/userInfo",
                "/rest/v2/creator/pc/authority/account/current",
                "/rest/cp/works/v2/video/pc/home/photo/list",
            )
        ):
            return
        try:
            api_payloads.append({"url": url, "data": await response.json()})
        except Exception:
            pass

    page.on("response", capture_profile_response)
    await page.goto("https://cp.kuaishou.com/article/publish/video", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3000)
    if "passport.kuaishou.com" in page.url.lower() or await page.get_by_text("扫码登录").count():
        return {
            "status": "needs_login",
            "sync_status": "failed",
            "sync_message": "快手登录态已失效",
            "last_profile_sync_at": _now_iso(),
        }

    body_text = ""
    try:
        body_text = await page.locator("body").inner_text(timeout=5000)
    except Exception:
        body_text = ""
    lines = _text_lines(body_text)
    nickname = await _first_text(page, [
        '[class*="user-name"]',
        '[class*="nickname"]',
        '[class*="account-name"]',
        '[class*="profile-name"]',
        '[class*="name"]',
    ])
    avatar_url = await _first_attr(page, [
        'img[class*="avatar"]',
        'img[class*="Avatar"]',
        '[class*="avatar"] img',
    ], "src")

    followers = _extract_metric_from_lines(lines, ["粉丝", "粉丝数"]) or _extract_metric_from_text(body_text, ["粉丝", "粉丝数"])
    following = _extract_metric_from_lines(lines, ["关注", "关注数"]) or _extract_metric_from_text(body_text, ["关注", "关注数"])
    works_count = _extract_metric_from_lines(lines, ["作品", "视频", "内容"]) or _extract_metric_from_text(body_text, ["作品", "视频", "内容"])
    likes_count = _extract_metric_from_lines(lines, ["获赞", "点赞"]) or _extract_metric_from_text(body_text, ["获赞", "点赞"])
    platform_user_id = ""

    try:
        await page.goto("https://cp.kuaishou.com/profile", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        await page.goto("https://cp.kuaishou.com/article/manage/video?status=2&from=publish", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        manage_text = await page.locator("body").inner_text(timeout=5000)
        manage_lines = _text_lines(manage_text)
        works_count = (
            _extract_metric_from_lines(manage_lines, ["作品", "视频", "内容"])
            or _extract_metric_from_text(manage_text, ["作品", "视频", "内容"])
            or works_count
        )
    except Exception:
        pass

    for payload in api_payloads:
        url = payload.get("url", "")
        raw_data = payload.get("data") or {}
        data = raw_data.get("data") if isinstance(raw_data, dict) else {}
        if not isinstance(data, dict):
            continue
        if "/home/infoV2" in url:
            nickname = str(data.get("userName") or nickname or "").strip()
            followers = _to_int(data.get("fansCnt")) or followers
            following = _to_int(data.get("followCnt")) or following
            likes_count = _to_int(data.get("likeCnt")) if data.get("likeCnt") is not None else likes_count
            platform_user_id = str(data.get("userId") or "").strip()
        elif "/home/userInfo" in url:
            core = data.get("coreUserInfo") if isinstance(data.get("coreUserInfo"), dict) else {}
            nickname = str(core.get("userName") or nickname or "").strip()
            avatar_url = str(core.get("headUrl") or avatar_url or "").strip()
            followers = _to_int(core.get("fansNum")) or followers
            platform_user_id = str(core.get("userId") or "").strip()
        elif "/authority/account/current" in url:
            nickname = str(data.get("userName") or nickname or "").strip()
            avatar_url = str(data.get("userAvatar") or avatar_url or "").strip()
            platform_user_id = str(data.get("userId") or "").strip()
        elif "/home/photo/list" in url:
            works_count = _to_int(data.get("total")) if data.get("total") is not None else works_count

    if not nickname and not any([followers, following, works_count, likes_count]):
        return {
            "status": "connected",
            "sync_status": "success",
            "sync_message": "快手登录态有效，账号资料暂未完整识别",
            "last_profile_sync_at": _now_iso(),
        }

    return {
        "nickname": nickname,
        "avatar_url": avatar_url,
        "platform_user_id": platform_user_id,
        "profile_url": _public_url("kuaishou", platform_user_id, page.url),
        "followers": followers,
        "following": following,
        "works_count": works_count,
        "likes_count": likes_count,
        "status": "connected",
        "sync_status": "success",
        "sync_message": "账号资料已同步",
        "last_profile_sync_at": _now_iso(),
    }


def _extract_tencent_nickname(lines: list[str]) -> str:
    control_words = {
        "视频号 · 助手",
        "首页",
        "内容管理",
        "互动管理",
        "直播",
        "收入与服务",
        "带货中心",
        "数据中心",
        "设置",
        "通知中心",
        "申请认证",
    }
    for index, line in enumerate(lines):
        if line.startswith("视频号ID"):
            for candidate in reversed(lines[max(0, index - 5):index]):
                if candidate and candidate not in control_words and not candidate.isdigit():
                    return candidate
    return ""


def _extract_tencent_video_id(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        match = re.search(r"视频号ID[:：]?\s*([\w.-]+)", line)
        if match:
            return match.group(1)
        if line in {"视频号ID:", "视频号ID：", "视频号ID"} and index + 1 < len(lines):
            return lines[index + 1].strip()
    return ""


async def _sync_tencent_channels(account: dict) -> dict[str, Any]:
    session = get_desktop_browser_session().launch(
        "https://channels.weixin.qq.com/platform",
        profile_key="tencent_channels_edge",
        no_proxy=True,
    )
    if not session.ok:
        return {
            "sync_status": "failed",
            "sync_message": session.error or session.message or "视频号助手打开失败",
            "last_profile_sync_at": _now_iso(),
        }
    if not session.cdp_available:
        return {
            "status": "connected",
            "sync_status": "failed",
            "sync_message": "真实浏览器已打开，但资料同步端口不可用",
            "last_profile_sync_at": _now_iso(),
        }

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(session.cdp_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        pages = [page for page in context.pages if "channels.weixin.qq.com" in page.url]
        page = pages[0] if pages else await context.new_page()
        await page.goto("https://channels.weixin.qq.com/platform", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(4500)

        text = await page.evaluate(
            """() => Array.from(document.querySelectorAll('body')).map((body) => body.innerText || '').join('\\n')"""
        )
        if "login" in page.url.lower() or "扫码登录" in text or "登录" == text.strip():
            return {
                "status": "needs_login",
                "sync_status": "failed",
                "sync_message": "视频号登录态已失效，请重新打开助手登录",
                "last_profile_sync_at": _now_iso(),
            }

        lines = _text_lines(text)
        nickname = _extract_tencent_nickname(lines)
        platform_user_id = _extract_tencent_video_id(lines)
        avatar_url = await _first_attr(page, [
            'img.avatar[src*="wx.qlogo.cn"]',
            'img[alt*="视频号头像"]',
            'img[src*="wx.qlogo.cn/finderhead"]',
            '[class*="avatar"] img',
        ], "src")
        followers = _extract_metric_from_text(text, ["关注者", "粉丝"])
        works_count = _extract_metric_from_text(text, ["视频", "作品", "图文"])
        likes_count = _extract_metric_from_text(text, ["获赞", "点赞"])

        if not nickname and not any([followers, works_count, likes_count]):
            return {
                "status": "connected",
                "sync_status": "failed",
                "sync_message": "视频号助手已打开，但未识别到账号资料",
                "last_profile_sync_at": _now_iso(),
            }

        return {
            "nickname": nickname or account.get("nickname") or account.get("label"),
            "avatar_url": avatar_url,
            "platform_user_id": platform_user_id,
            "profile_url": _public_url("tencent", platform_user_id, page.url),
            "followers": followers,
            "following": 0,
            "works_count": works_count,
            "likes_count": likes_count,
            "status": "connected",
            "sync_status": "success",
            "sync_message": "视频号资料已同步",
            "last_profile_sync_at": _now_iso(),
        }


def _sync_bilibili(account: dict) -> dict[str, Any]:
    session_path = Path(account.get("session_path", ""))
    cookie_file = session_path if session_path.exists() else _sau_cookie_file("bilibili", account)
    cookie_header = _extract_cookie_header(cookie_file)
    if not cookie_header:
        return {
            "status": "needs_login",
            "sync_status": "failed",
            "sync_message": "B站登录态不存在",
            "last_profile_sync_at": _now_iso(),
        }

    try:
        nav = _http_json("https://api.bilibili.com/x/web-interface/nav", cookie_header)
        data = nav.get("data") if isinstance(nav, dict) else {}
        if not isinstance(data, dict) or not data.get("isLogin"):
            return {
                "status": "needs_login",
                "sync_status": "failed",
                "sync_message": "B站登录态已失效",
                "last_profile_sync_at": _now_iso(),
            }

        mid = str(data.get("mid") or "").strip()
        relation = _http_json(f"https://api.bilibili.com/x/relation/stat?vmid={mid}", cookie_header).get("data") or {}
        navnum = _http_json(f"https://api.bilibili.com/x/space/navnum?mid={mid}", cookie_header).get("data") or {}
        upstat = _http_json(f"https://api.bilibili.com/x/space/upstat?mid={mid}", cookie_header).get("data") or {}
        likes = upstat.get("likes") if isinstance(upstat, dict) else 0
        archive = navnum.get("video") if isinstance(navnum, dict) else 0

        return {
            "nickname": str(data.get("uname") or "").strip(),
            "avatar_url": str(data.get("face") or "").strip(),
            "platform_user_id": mid,
            "profile_url": _public_url("bilibili", mid, "https://space.bilibili.com"),
            "followers": _to_int(relation.get("follower") if isinstance(relation, dict) else 0),
            "following": _to_int(relation.get("following") if isinstance(relation, dict) else 0),
            "works_count": _to_int(archive),
            "likes_count": _to_int(likes),
            "status": "connected",
            "sync_status": "success",
            "sync_message": "账号资料已同步",
            "last_profile_sync_at": _now_iso(),
        }
    except Exception as exc:
        return {
            "sync_status": "failed",
            "sync_message": f"B站账号资料同步失败：{exc}",
            "last_profile_sync_at": _now_iso(),
        }


def profile_sync_due(account: dict, ttl_hours: int = PROFILE_SYNC_TTL_HOURS) -> bool:
    last = account.get("last_profile_sync_at") or ""
    if not last:
        return True
    try:
        return datetime.fromisoformat(last) <= datetime.now() - timedelta(hours=ttl_hours)
    except ValueError:
        return True


async def sync_account_profile(account_id: str, force: bool = True) -> dict:
    account = get_account(account_id)
    if not account:
        raise KeyError(account_id)
    if not force and not profile_sync_due(account):
        return account

    try:
        updates = await _sync_with_page(account)
    except PlaywrightTimeoutError as exc:
        updates = {
            "sync_status": "failed",
            "sync_message": f"账号资料同步超时: {str(exc)[:160]}",
            "last_profile_sync_at": _now_iso(),
        }
    except Exception as exc:
        updates = {
            "sync_status": "failed",
            "sync_message": f"账号资料同步失败: {str(exc)[:160]}",
            "last_profile_sync_at": _now_iso(),
        }

    cleaned = {key: value for key, value in updates.items() if value not in (None, "")}
    updated = patch_account(account_id, **cleaned)
    if updated.get("sync_status") == "success":
        from szyg.account_metrics import record_account_metrics

        record_account_metrics(updated)
    return updated
