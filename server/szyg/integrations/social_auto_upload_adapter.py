"""
SocialAutoUpload Adapter — 统一封装 social-auto-upload 的多平台发布能力。

通过 SZYG 内置的发布 provider 复用平台会话。
支持平台: 抖音、小红书、快手、视频号(腾讯)、B站、YouTube、TikTok、百家号。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from szyg.channel_accounts import get_account, get_default_account_for_platform
from szyg.data_path import DATA_DIR

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
try:
    from szyg.config.settings import get_settings
    _SAU_CONFIG = get_settings().integrations.social_auto_upload
except Exception:
    _SAU_CONFIG = None

_SERVER_ROOT = _REPO_ROOT / "server"
_PROVIDER_PACKAGE = "szyg.integrations.social_auto_upload"

# ── Session 映射 ──────────────────────────────────────────
# szyg: data/sessions/storage_state_{platform}.json
# sau:  cookies/{platform}_uploader/account.json
# 格式相同（Playwright storage_state），只需路径转换
_DATA_DIR = DATA_DIR
_SESSIONS_DIR = _DATA_DIR / "sessions"
_SAU_RUNTIME_DIR = _DATA_DIR / "social_auto_upload"
_SAU_COOKIES_DIR = _SAU_RUNTIME_DIR / "cookies"

# 平台名映射: szyg Platform enum → sau uploader 模块
_PLATFORM_MAP = {
    "douyin": {
        "module": f"{_PROVIDER_PACKAGE}.uploader.douyin_uploader.main",
        "video_class": "DouYinVideo",
        "note_class": "DouYinNote",
        "upload_method_video": "douyin_upload_video",
        "upload_method_note": "douyin_upload_note",
        "cookie_subdir": "douyin_uploader",
        "immediate_strategy": "DOUYIN_PUBLISH_STRATEGY_IMMEDIATE",
        "scheduled_strategy": "DOUYIN_PUBLISH_STRATEGY_SCHEDULED",
    },
    "xhs": {
        "module": f"{_PROVIDER_PACKAGE}.uploader.xiaohongshu_uploader.main",
        "video_class": "XiaoHongShuVideo",
        "note_class": "XiaoHongShuNote",
        "upload_method_video": "xiaohongshu_upload_video",
        "upload_method_note": "xiaohongshu_upload_note",
        "cookie_subdir": "xiaohongshu_uploader",
        "immediate_strategy": "XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE",
        "scheduled_strategy": "XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED",
    },
    "kuaishou": {
        "module": f"{_PROVIDER_PACKAGE}.uploader.ks_uploader.main",
        "video_class": "KSVideo",
        "note_class": "KSNote",
        "upload_method_video": "main",
        "upload_method_note": "main",
        "cookie_subdir": "ks_uploader",
        "immediate_strategy": "KUAISHOU_PUBLISH_STRATEGY_IMMEDIATE",
        "scheduled_strategy": "KUAISHOU_PUBLISH_STRATEGY_SCHEDULED",
    },
    "bilibili": {
        "module": "",
        "video_class": None,
        "note_class": None,
        "upload_method_video": None,
        "upload_method_note": None,
        "cookie_subdir": "bilibili_uploader",
        "immediate_strategy": None,
        "scheduled_strategy": None,
    },
    "tencent": {
        "module": f"{_PROVIDER_PACKAGE}.uploader.tencent_uploader.main",
        "video_class": "TencentVideo",
        "note_class": "TencentNote",
        "upload_method_video": "tencent_upload_video",
        "upload_method_note": "tencent_upload_note",
        "cookie_subdir": "tencent_uploader",
        "immediate_strategy": "TENCENT_PUBLISH_STRATEGY_IMMEDIATE",
        "scheduled_strategy": "TENCENT_PUBLISH_STRATEGY_SCHEDULED",
    },
    "youtube": {
        "module": f"{_PROVIDER_PACKAGE}.uploader.youtube_uploader.main",
        "video_class": "YouTubeVideo",
        "note_class": None,
        "upload_method_video": "youtube_upload_video",
        "upload_method_note": None,
        "cookie_subdir": "youtube_uploader",
        "immediate_strategy": None,
        "scheduled_strategy": None,
    },
}


class SocialAutoUploadAdapter:
    """统一封装 social-auto-upload 的多平台发布能力。

    Usage:
        adapter = SocialAutoUploadAdapter()
        result = await adapter.upload_video(
            platform="douyin",
            file_path="/path/to/video.mp4",
            title="标题",
            tags=["标签1", "标签2"],
            account_file="/path/to/account.json",  # 可选，默认从szyg session映射
        )
    """

    def __init__(self, account_name: str = "default"):
        self.account = account_name
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        _SAU_COOKIES_DIR.mkdir(parents=True, exist_ok=True)
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    def _account_name(self, platform: str, account_id: str | None = None, account_name: str | None = None) -> str:
        if account_name:
            return account_name
        if account_id:
            account = get_account(account_id)
            if account and account.get("sau_account_name"):
                return str(account["sau_account_name"])
        accounts = getattr(_SAU_CONFIG, "accounts", {}) or {}
        return accounts.get(platform, platform)

    def _publish_timeout_seconds(self) -> int:
        return int(getattr(_SAU_CONFIG, "publish_timeout_seconds", 900) or 900)

    def _external_sau_account_file(self, platform: str, account_id: str | None = None, account_name: str | None = None) -> Path:
        account_name = self._account_name(platform, account_id=account_id, account_name=account_name)
        path = _SAU_COOKIES_DIR / f"{platform}_{account_name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _sync_douyin_session_to_external_sau(
        self,
        account_id: str | None = None,
        account_file: str | None = None,
        account_name: str | None = None,
    ) -> Path:
        account_name = self._account_name("douyin", account_id=account_id, account_name=account_name)
        source = Path(account_file) if account_file else Path(self._get_account_file("douyin", account_id=account_id))
        target = _SAU_COOKIES_DIR / f"douyin_{account_name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.copy2(source, target)
        return target

    def _sync_external_sau_to_douyin_session(
        self,
        account_id: str | None = None,
        account_file: str | None = None,
        account_name: str | None = None,
    ) -> None:
        account_name = self._account_name("douyin", account_id=account_id, account_name=account_name)
        source = _SAU_COOKIES_DIR / f"douyin_{account_name}.json"
        target = Path(account_file) if account_file else Path(self._get_account_file("douyin", account_id=account_id))
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    async def _run_provider_cli(self, args: list[str], timeout_seconds: int = 900) -> dict:
        frozen_cli = Path(sys.executable).with_name("sau-cli.exe")
        frozen_cli_available = bool(getattr(sys, "frozen", False) and frozen_cli.is_file())

        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env["SZYG_SAU_RUNTIME_HOME"] = str(_SAU_RUNTIME_DIR)
        if frozen_cli_available:
            command = [str(frozen_cli), *args]
            cwd = _SAU_RUNTIME_DIR
        else:
            command = [sys.executable, "-m", f"{_PROVIDER_PACKAGE}.cli", *args]
            cwd = _SERVER_ROOT
        cwd.mkdir(parents=True, exist_ok=True)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        async def terminate_process_tree() -> None:
            if process.returncode is not None:
                return
            if os.name == "nt":
                killer = await asyncio.create_subprocess_exec(
                    "taskkill",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await killer.communicate()
            else:
                process.kill()

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            await terminate_process_tree()
            stdout_bytes, stderr_bytes = await process.communicate()
            return {
                "success": False,
                "message": f"social-auto-upload timed out after {timeout_seconds}s",
                "stdout": stdout_bytes.decode("utf-8", errors="replace"),
                "stderr": stderr_bytes.decode("utf-8", errors="replace"),
            }
        except asyncio.CancelledError:
            await terminate_process_tree()
            await process.communicate()
            raise

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        message = (stderr or stdout).strip()
        return {
            "success": process.returncode == 0,
            "returncode": process.returncode,
            "message": message,
            "stdout": stdout,
            "stderr": stderr,
        }

    async def _login_bilibili_browser(
        self,
        account_file: str,
        timeout_seconds: int = 600,
        headless: bool = False,
        force: bool = False,
    ) -> dict:
        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            return {
                "success": False,
                "login_started": False,
                "message": f"浏览器组件不可用：{exc}",
            }

        account_path = Path(account_file)
        if force and account_path.exists():
            try:
                account_path.unlink()
            except OSError:
                pass
        account_path.parent.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless, channel="chromium")
            try:
                context_kwargs: dict[str, Any] = {
                    "viewport": {"width": 1280, "height": 900},
                }
                if account_path.exists():
                    context_kwargs["storage_state"] = str(account_path)
                context = await browser.new_context(**context_kwargs)
                page = await context.new_page()
                await page.goto("https://passport.bilibili.com/login", wait_until="domcontentloaded", timeout=60000)
                login_started = True
                deadline = asyncio.get_running_loop().time() + max(timeout_seconds, 60)
                last_error = ""

                while asyncio.get_running_loop().time() < deadline:
                    try:
                        nav = await page.evaluate(
                            """async () => {
                              const response = await fetch('https://api.bilibili.com/x/web-interface/nav', { credentials: 'include' });
                              return await response.json();
                            }"""
                        )
                        data = nav.get("data") if isinstance(nav, dict) else {}
                        if isinstance(data, dict) and data.get("isLogin"):
                            await context.storage_state(path=str(account_path))
                            return {
                                "success": True,
                                "login_started": login_started,
                                "message": "B站登录成功",
                                "account_file": str(account_path),
                            }
                    except Exception as exc:
                        last_error = str(exc)
                    await page.wait_for_timeout(2500)

                return {
                    "success": False,
                    "login_started": login_started,
                    "message": f"等待 B站扫码登录超时{f'：{last_error}' if last_error else ''}",
                    "account_file": str(account_path),
                }
            finally:
                await browser.close()

    async def _lookup_douyin_published_post(self, account_file: Path, title: str) -> dict:
        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            return {
                "link_extraction": {
                    "status": "unsupported",
                    "method": "douyin_creator_work_list",
                    "message": f"Playwright unavailable: {exc}",
                }
            }

        if not account_file.exists():
            return {
                "link_extraction": {
                    "status": "not_found",
                    "method": "douyin_creator_work_list",
                    "message": f"Account storage state not found: {account_file}",
                }
            }

        work_lists: list[dict[str, Any]] = []
        browser = None
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(
                    storage_state=str(account_file),
                    viewport={"width": 1440, "height": 1000},
                )
                page = await context.new_page()

                async def capture_work_list(response) -> None:
                    if "/janus/douyin/creator/pc/work_list" not in response.url:
                        return
                    try:
                        work_lists.append(await response.json())
                    except Exception:
                        logger.debug("Failed to parse Douyin work_list response", exc_info=True)

                page.on("response", capture_work_list)
                await page.goto(
                    "https://creator.douyin.com/creator-micro/content/manage?enter_from=publish",
                    wait_until="domcontentloaded",
                    timeout=90_000,
                )
                try:
                    await page.wait_for_response(
                        lambda response: "/janus/douyin/creator/pc/work_list" in response.url,
                        timeout=15_000,
                    )
                except Exception:
                    pass
                for _ in range(16):
                    if any(title and title in json.dumps(data, ensure_ascii=False) for data in work_lists):
                        break
                    await page.wait_for_timeout(500)
                await context.close()
        except Exception as exc:
            logger.warning("Douyin post link lookup failed: %s", exc)
            return {
                "link_extraction": {
                    "status": "not_found",
                    "method": "douyin_creator_work_list",
                    "message": str(exc),
                }
            }
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

        title = (title or "").strip()
        candidates: list[dict[str, Any]] = []
        for data in work_lists:
            for item in data.get("aweme_list") or []:
                item_title = str(item.get("item_title") or "").strip()
                desc = str(item.get("desc") or "").strip()
                if title and (item_title == title or title in desc):
                    candidates.append(item)

        if not candidates:
            return {
                "link_extraction": {
                    "status": "not_found",
                    "method": "douyin_creator_work_list",
                    "message": "Post link lookup timed out; the work was not visible in the creator work list.",
                    "attempts": 1,
                    "timeout_seconds": 25,
                }
            }

        item = max(candidates, key=lambda entry: int(entry.get("create_time") or 0))
        post_id = str(item.get("aweme_id") or item.get("item_id") or "").strip()
        share_url = str(item.get("share_url") or "").strip()
        post_url = f"https://www.douyin.com/video/{post_id}" if post_id else share_url
        status = item.get("status") or {}
        in_reviewing = bool(status.get("in_reviewing")) if isinstance(status, dict) else False
        publish_status = "pending_review" if in_reviewing else "published"
        return {
            "post_id": post_id,
            "platform_post_id": post_id,
            "post_url": post_url,
            "share_url": share_url,
            "publish_status": publish_status,
            "published_title": item.get("item_title") or title,
            "published_at": datetime.fromtimestamp(int(item.get("create_time") or 0)).isoformat() if item.get("create_time") else "",
            "link_extraction": {
                "status": "found" if post_url else "not_found",
                "method": "douyin_creator_work_list",
                "message": "Post link extracted from Douyin creator work list." if post_url else "Post exists but no public link was returned before lookup timeout.",
                "attempts": 1,
                "timeout_seconds": 25,
            },
        }

    async def _external_douyin_upload_video(
        self,
        file_path: str,
        title: str,
        desc: str,
        tags: list[str] | None,
        thumbnail_path: str | None,
        schedule: datetime | None,
        headless: bool,
        account_id: str | None = None,
        account_file: str | None = None,
        account_name: str | None = None,
    ) -> dict:
        account_name = self._account_name("douyin", account_id=account_id, account_name=account_name)
        account_file_path = self._sync_douyin_session_to_external_sau(account_id=account_id, account_file=account_file, account_name=account_name)
        args = [
            "douyin",
            "upload-video",
            "--account",
            account_name,
            "--file",
            file_path,
            "--title",
            title,
            "--desc",
            desc or "",
            "--tags",
            ",".join(tags or []),
            "--debug",
            "--headless" if headless else "--headed",
        ]
        if thumbnail_path:
            args.extend(["--thumbnail", thumbnail_path])
        if schedule:
            args.extend(["--schedule", schedule.strftime("%Y-%m-%d %H:%M")])

        result = await self._run_provider_cli(args, timeout_seconds=self._publish_timeout_seconds())
        self._sync_external_sau_to_douyin_session(account_id=account_id, account_file=account_file, account_name=account_name)
        result.update({
            "platform": "douyin",
            "title": title,
            "file_path": file_path,
            "account_id": account_id or "",
            "account_file": str(account_file_path),
            "engine": "external-social-auto-upload",
        })
        if result.get("success") and not schedule:
            result.update(await self._lookup_douyin_published_post(account_file_path, title))
        return result

    async def _external_douyin_upload_note(
        self,
        image_paths: list[str],
        title: str,
        note: str,
        tags: list[str] | None,
        schedule: datetime | None,
        headless: bool,
        account_id: str | None = None,
        account_file: str | None = None,
        account_name: str | None = None,
    ) -> dict:
        account_name = self._account_name("douyin", account_id=account_id, account_name=account_name)
        account_file_path = self._sync_douyin_session_to_external_sau(account_id=account_id, account_file=account_file, account_name=account_name)
        args = [
            "douyin",
            "upload-note",
            "--account",
            account_name,
            "--images",
            *image_paths,
            "--title",
            title,
            "--note",
            note or "",
            "--tags",
            ",".join(tags or []),
            "--debug",
            "--headless" if headless else "--headed",
        ]
        if schedule:
            args.extend(["--schedule", schedule.strftime("%Y-%m-%d %H:%M")])

        result = await self._run_provider_cli(args, timeout_seconds=self._publish_timeout_seconds())
        self._sync_external_sau_to_douyin_session(account_id=account_id, account_file=account_file, account_name=account_name)
        result.update({
            "platform": "douyin",
            "title": title,
            "account_id": account_id or "",
            "account_file": str(account_file_path),
            "engine": "external-social-auto-upload",
        })
        if result.get("success") and not schedule:
            result.update(await self._lookup_douyin_published_post(account_file_path, title))
        return result

    async def _external_bilibili_upload_video(
        self,
        file_path: str,
        title: str,
        desc: str,
        tags: list[str] | None,
        schedule: datetime | None,
        account_id: str | None = None,
        account_name: str | None = None,
    ) -> dict:
        account_name = self._account_name("bilibili", account_id=account_id, account_name=account_name)
        account_file_path = self._external_sau_account_file("bilibili", account_id=account_id, account_name=account_name)
        if not account_file_path.exists():
            return {
                "success": False,
                "platform": "bilibili",
                "title": title,
                "file_path": file_path,
                "account_id": account_id or "",
                "account_file": str(account_file_path),
                "message": "B站投稿授权未完成，请先在渠道账号中完成登录。",
                "engine": "bilibili-uploader",
            }

        tid = int(getattr(_SAU_CONFIG, "bilibili_tid", 21) or 21)
        args = [
            "bilibili",
            "upload-video",
            "--account",
            account_name,
            "--file",
            file_path,
            "--title",
            title,
            "--desc",
            desc or title,
            "--tid",
            str(tid),
            "--tags",
            ",".join(tags or []),
        ]
        if schedule:
            args.extend(["--schedule", schedule.strftime("%Y-%m-%d %H:%M")])

        result = await self._run_provider_cli(args, timeout_seconds=self._publish_timeout_seconds())
        result.update({
            "platform": "bilibili",
            "title": title,
            "file_path": file_path,
            "account_id": account_id or "",
            "account_file": str(account_file_path),
            "engine": "bilibili-uploader",
        })
        return result

    def _get_account_file(self, platform: str, account_id: str | None = None) -> str:
        """获取平台 cookie 文件路径。

        优先使用 szyg session 目录的 storage_state 文件，
        如果不存在则回退到 sau cookies 目录。
        """
        if account_id:
            account = get_account(account_id)
            if account and account.get("session_path"):
                return str(account["session_path"])

        default_account = get_default_account_for_platform(platform)
        if default_account and default_account.get("session_path"):
            return str(default_account["session_path"])

        # szyg session 路径
        szyg_session = _SESSIONS_DIR / f"storage_state_{platform}.json"
        if szyg_session.exists():
            return str(szyg_session)

        # sau cookies 路径
        cfg = _PLATFORM_MAP.get(platform)
        if cfg:
            sau_cookie = _SAU_COOKIES_DIR / cfg["cookie_subdir"] / "account.json"
            if sau_cookie.exists():
                return str(sau_cookie)

        # 返回 szyg 路径（即使不存在，让 sau 报登录错误）
        return str(szyg_session)

    def _import_uploader(self, platform: str):
        """动态导入平台 uploader 模块。"""
        cfg = _PLATFORM_MAP.get(platform)
        if not cfg:
            raise ValueError(f"不支持的平台: {platform}，支持: {list(_PLATFORM_MAP.keys())}")
        if not cfg.get("module"):
            raise ValueError(f"平台 {platform} 使用外部发布引擎，不支持直接导入 uploader 模块")

        import importlib
        mod = importlib.import_module(cfg["module"])
        return mod, cfg

    async def upload_video(
        self,
        platform: str,
        file_path: str,
        title: str,
        desc: str = "",
        tags: list[str] | None = None,
        thumbnail_path: str | None = None,
        schedule: datetime | None = None,
        account_file: str | None = None,
        account_id: str | None = None,
        account_name: str | None = None,
        headless: bool = True,
    ) -> dict:
        """上传视频到指定平台。

        Args:
            platform: 平台名 (douyin/xhs/kuaishou/tencent/youtube)
            file_path: 视频文件本地路径
            title: 视频标题
            desc: 视频描述
            tags: 标签列表
            thumbnail_path: 封面图路径
            schedule: 定时发布时间，None 表示立即发布
            account_file: cookie 文件路径，None 则自动从 szyg session 映射
            headless: 是否无头模式

        Returns:
            {"success": bool, "platform": str, "message": str}
        """
        if platform == "douyin":
            return await self._external_douyin_upload_video(
                file_path=file_path,
                title=title,
                desc=desc,
                tags=tags,
                thumbnail_path=thumbnail_path,
                schedule=schedule,
                headless=headless,
                account_id=account_id,
                account_file=account_file,
                account_name=account_name,
            )
        if platform == "bilibili":
            return await self._external_bilibili_upload_video(
                file_path=file_path,
                title=title,
                desc=desc,
                tags=tags,
                schedule=schedule,
                account_id=account_id,
                account_name=account_name,
            )

        try:
            mod, cfg = self._import_uploader(platform)
            account = account_file or self._get_account_file(platform, account_id=account_id)

            # 确定发布策略
            publish_date = schedule or 0
            if cfg["immediate_strategy"]:
                strategy = cfg["scheduled_strategy"] if schedule else cfg["immediate_strategy"]
                publish_strategy = getattr(mod, strategy)
            else:
                publish_strategy = None

            # 构建 uploader 实例
            video_cls = getattr(mod, cfg["video_class"])
            kwargs: dict[str, Any] = {
                "title": title,
                "file_path": file_path,
                "tags": tags or [],
                "publish_date": publish_date,
                "account_file": account,
                "headless": headless,
            }
            if desc:
                kwargs["desc"] = desc
            if thumbnail_path:
                if platform == "douyin":
                    kwargs["thumbnail_landscape_path"] = thumbnail_path
            if publish_strategy:
                kwargs["publish_strategy"] = publish_strategy

            uploader = video_cls(**kwargs)

            # 执行上传
            upload_method = getattr(uploader, cfg["upload_method_video"])
            await upload_method()

            return {
                "success": True,
                "platform": platform,
                "message": f"视频已上传到{platform}",
                "title": title,
                "file_path": file_path,
                "account_id": account_id or "",
                "account_file": account,
                **(getattr(uploader, "publish_result", {}) or {}),
            }

        except Exception as e:
            logger.error(f"[sau] {platform} 视频上传失败: {e}", exc_info=True)
            return {
                "success": False,
                "platform": platform,
                "message": str(e),
                "title": title,
                "file_path": file_path,
                "account_id": account_id or "",
            }

    async def upload_note(
        self,
        platform: str,
        image_paths: list[str],
        title: str,
        note: str = "",
        tags: list[str] | None = None,
        schedule: datetime | None = None,
        account_file: str | None = None,
        account_id: str | None = None,
        account_name: str | None = None,
        headless: bool = True,
    ) -> dict:
        """上传图文到指定平台。

        Args:
            platform: 平台名 (douyin/xhs/kuaishou/tencent)
            image_paths: 图片文件本地路径列表
            title: 图文标题
            note: 图文正文
            tags: 标签列表
            schedule: 定时发布时间
            account_file: cookie 文件路径
            headless: 是否无头模式

        Returns:
            {"success": bool, "platform": str, "message": str}
        """
        if platform == "douyin":
            return await self._external_douyin_upload_note(
                image_paths=image_paths,
                title=title,
                note=note,
                tags=tags,
                schedule=schedule,
                headless=headless,
                account_id=account_id,
                account_file=account_file,
                account_name=account_name,
            )
        if platform == "bilibili":
            return {
                "success": False,
                "platform": platform,
                "message": "B站当前只支持视频发布，不支持图文发布",
                "title": title,
                "account_id": account_id or "",
            }

        try:
            mod, cfg = self._import_uploader(platform)
            if not cfg["note_class"]:
                raise ValueError(f"平台 {platform} 不支持图文上传")

            account = account_file or self._get_account_file(platform, account_id=account_id)
            publish_date = schedule or 0

            if cfg["immediate_strategy"]:
                strategy = cfg["scheduled_strategy"] if schedule else cfg["immediate_strategy"]
                publish_strategy = getattr(mod, strategy)
            else:
                publish_strategy = None

            note_cls = getattr(mod, cfg["note_class"])
            kwargs: dict[str, Any] = {
                "title": title,
                "image_paths": image_paths,
                "note": note,
                "tags": tags or [],
                "publish_date": publish_date,
                "account_file": account,
                "headless": headless,
            }
            if publish_strategy:
                kwargs["publish_strategy"] = publish_strategy

            uploader = note_cls(**kwargs)
            upload_method = getattr(uploader, cfg["upload_method_note"])
            await upload_method()

            return {
                "success": True,
                "platform": platform,
                "message": f"图文已上传到{platform}",
                "title": title,
                "account_id": account_id or "",
                "account_file": account,
                **(getattr(uploader, "publish_result", {}) or {}),
            }

        except Exception as e:
            logger.error(f"[sau] {platform} 图文上传失败: {e}", exc_info=True)
            return {
                "success": False,
                "platform": platform,
                "message": str(e),
                "title": title,
                "account_id": account_id or "",
            }

    async def login(
        self,
        platform: str,
        headless: bool = False,
        account_id: str | None = None,
        account_file: str | None = None,
        account_name: str | None = None,
        timeout_seconds: int = 600,
        force: bool = False,
    ) -> dict:
        """触发平台登录（扫码）。

        Args:
            platform: 平台名
            headless: 是否无头（登录通常需要有头）

        Returns:
            {"success": bool, "platform": str, "account_file": str, "message": str}
        """
        if platform == "douyin":
            account_name = self._account_name("douyin", account_id=account_id, account_name=account_name)
            account_file_path = self._sync_douyin_session_to_external_sau(account_id=account_id, account_file=account_file, account_name=account_name)
            result = await self._run_provider_cli([
                "douyin",
                "login",
                "--account",
                account_name,
                "--headless" if headless else "--headed",
            ], timeout_seconds=timeout_seconds)
            self._sync_external_sau_to_douyin_session(account_id=account_id, account_file=account_file, account_name=account_name)
            return {
                "success": result["success"],
                "platform": platform,
                "account_id": account_id or "",
                "account_file": str(account_file_path),
                "message": result.get("message", ""),
                "engine": "external-social-auto-upload",
            }
        if platform == "bilibili":
            try:
                result = await self._login_bilibili_browser(
                    account_file=account_file or self._get_account_file("bilibili", account_id=account_id),
                    timeout_seconds=timeout_seconds,
                    headless=headless,
                    force=force,
                )
            except Exception as exc:
                result = {
                    "success": False,
                    "login_started": False,
                    "message": f"B站登录失败：{exc}",
                }
            account_file_path = Path(account_file or self._get_account_file("bilibili", account_id=account_id))
            return {
                "success": result["success"],
                "login_started": bool(result.get("login_started")),
                "platform": platform,
                "account_id": account_id or "",
                "account_file": str(account_file_path),
                "message": result.get("message", ""),
                "engine": "bilibili-browser",
            }

        try:
            mod, cfg = self._import_uploader(platform)
            account = account_file or self._get_account_file(platform, account_id=account_id)
            if force and account and os.path.exists(account):
                try:
                    os.remove(account)
                except OSError:
                    pass

            setup_aliases = {
                "xhs": "xiaohongshu_setup",
                "kuaishou": "ks_setup",
            }
            setup_func_name = setup_aliases.get(platform, f"{platform}_setup")
            setup_func = getattr(mod, setup_func_name, None)

            if setup_func is None:
                # 尝试通用名称
                setup_func = getattr(mod, "setup", None)

            if setup_func is None:
                return {
                    "success": False,
                    "platform": platform,
                    "message": f"平台 {platform} 未实现登录函数",
                }

            result = await setup_func(account_file=account, handle=True, return_detail=True, headless=headless)

            if isinstance(result, dict):
                return {
                    "success": result.get("success", False),
                    "platform": platform,
                    "account_id": account_id or "",
                    "account_file": account,
                    "message": result.get("message", ""),
                    "qrcode": result.get("qrcode"),
                }
            elif result is True:
                return {
                    "success": True,
                    "platform": platform,
                    "account_id": account_id or "",
                    "account_file": account,
                    "message": "登录成功",
                }
            else:
                return {
                    "success": False,
                    "platform": platform,
                    "account_id": account_id or "",
                    "account_file": account,
                    "message": "登录失败",
                }

        except Exception as e:
            logger.error(f"[sau] {platform} 登录失败: {e}", exc_info=True)
            return {
                "success": False,
                "platform": platform,
                "account_id": account_id or "",
                "message": str(e),
            }

    async def check_login(
        self,
        platform: str,
        account_id: str | None = None,
        account_file: str | None = None,
        account_name: str | None = None,
    ) -> dict:
        """检查平台登录状态。

        Args:
            platform: 平台名

        Returns:
            {"logged_in": bool, "platform": str, "account_file": str}
        """
        if platform == "douyin":
            account_name = self._account_name("douyin", account_id=account_id, account_name=account_name)
            account_file_path = self._sync_douyin_session_to_external_sau(account_id=account_id, account_file=account_file, account_name=account_name)
            result = await self._run_provider_cli([
                "douyin",
                "check",
                "--account",
                account_name,
            ], timeout_seconds=120)
            return {
                "logged_in": result["success"],
                "platform": platform,
                "account_id": account_id or "",
                "account_file": str(account_file_path),
                "message": result.get("message", ""),
                "engine": "external-social-auto-upload",
            }
        if platform == "bilibili":
            account_name = self._account_name("bilibili", account_id=account_id, account_name=account_name)
            account_file_path = self._external_sau_account_file("bilibili", account_id=account_id, account_name=account_name)
            if not account_file_path.exists():
                return {
                    "logged_in": False,
                    "platform": platform,
                    "account_id": account_id or "",
                    "account_file": str(account_file_path),
                    "message": "B站登录态不存在",
                    "engine": "bilibili-uploader",
                }
            result = await self._run_provider_cli([
                "bilibili",
                "check",
                "--account",
                account_name,
            ], timeout_seconds=120)
            return {
                "logged_in": result["success"],
                "platform": platform,
                "account_id": account_id or "",
                "account_file": str(account_file_path),
                "message": result.get("message", ""),
                "engine": "bilibili-uploader",
            }

        try:
            mod, cfg = self._import_uploader(platform)
            account = account_file or self._get_account_file(platform, account_id=account_id)

            if not os.path.exists(account):
                return {
                    "logged_in": False,
                    "platform": platform,
                    "account_id": account_id or "",
                    "account_file": account,
                    "message": "cookie 文件不存在",
                }

            # 尝试调用 cookie_auth 函数（如果存在）
            cookie_auth = getattr(mod, "cookie_auth", None)
            if cookie_auth:
                is_valid = await cookie_auth(account)
                return {
                    "logged_in": bool(is_valid),
                    "platform": platform,
                    "account_id": account_id or "",
                    "account_file": account,
                    "message": "登录态有效" if is_valid else f"{platform} 登录态已失效，请重新登录",
                }

            # 没有 cookie_auth 函数，检查文件是否非空
            size = os.path.getsize(account)
            return {
                "logged_in": size > 100,
                "platform": platform,
                "account_id": account_id or "",
                "account_file": account,
                "message": f"cookie 文件 {size} bytes" if size > 0 else "cookie 文件为空",
            }

        except Exception as e:
            logger.error(f"[sau] {platform} 登录状态检查失败: {e}")
            return {
                "logged_in": False,
                "platform": platform,
                "account_id": account_id or "",
                "message": str(e),
            }

    def list_platforms(self) -> list[dict]:
        """列出所有支持的平台及其状态。"""
        platforms = []
        for name, cfg in _PLATFORM_MAP.items():
            account = str(self._external_sau_account_file(name)) if name == "bilibili" else self._get_account_file(name)
            has_cookie = os.path.exists(account)
            platforms.append({
                "platform": name,
                "video_support": name == "bilibili" or bool(cfg["video_class"]),
                "note_support": bool(cfg["note_class"]),
                "has_cookie": has_cookie,
                "account_file": account,
            })
        return platforms


# ── 单例 ──────────────────────────────────────────────────
_adapter: SocialAutoUploadAdapter | None = None


def get_sau_adapter() -> SocialAutoUploadAdapter:
    global _adapter
    if _adapter is None:
        _adapter = SocialAutoUploadAdapter()
    return _adapter
