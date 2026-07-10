"""
SocialAutoUpload Adapter — 统一封装 social-auto-upload 的多平台发布能力。

直接 import sau 的 uploader 类（不调 CLI 子进程），复用 szyg 的 session 管理。
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

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
try:
    from szyg.config.settings import get_settings
    _SAU_CONFIG = get_settings().integrations.social_auto_upload
except Exception:
    _SAU_CONFIG = None

_CONFIGURED_SAU_DIR = Path(getattr(_SAU_CONFIG, "project_dir", "") or "")
if _CONFIGURED_SAU_DIR and not _CONFIGURED_SAU_DIR.is_absolute():
    _CONFIGURED_SAU_DIR = (_REPO_ROOT / _CONFIGURED_SAU_DIR).resolve()
_BUNDLED_SAU_DIR = Path(__file__).parent / "social_auto_upload"
_DEFAULT_EXTERNAL_SAU_DIR = _REPO_ROOT / "external" / "social-auto-upload-main"
_SAU_DIR = (
    _CONFIGURED_SAU_DIR
    if _CONFIGURED_SAU_DIR and _CONFIGURED_SAU_DIR.exists()
    else _DEFAULT_EXTERNAL_SAU_DIR
    if _DEFAULT_EXTERNAL_SAU_DIR.exists()
    else _BUNDLED_SAU_DIR
)
if str(_SAU_DIR) not in sys.path:
    sys.path.insert(0, str(_SAU_DIR))

# ── Session 映射 ──────────────────────────────────────────
# szyg: data/sessions/storage_state_{platform}.json
# sau:  cookies/{platform}_uploader/account.json
# 格式相同（Playwright storage_state），只需路径转换
_DATA_DIR = _REPO_ROOT / "data"
_SESSIONS_DIR = _DATA_DIR / "sessions"
_SAU_COOKIES_DIR = _SAU_DIR / "cookies"

# 平台名映射: szyg Platform enum → sau uploader 模块
_PLATFORM_MAP = {
    "douyin": {
        "module": "uploader.douyin_uploader.main",
        "video_class": "DouYinVideo",
        "note_class": "DouYinNote",
        "upload_method_video": "douyin_upload_video",
        "upload_method_note": "douyin_upload_note",
        "cookie_subdir": "douyin_uploader",
        "immediate_strategy": "DOUYIN_PUBLISH_STRATEGY_IMMEDIATE",
        "scheduled_strategy": "DOUYIN_PUBLISH_STRATEGY_SCHEDULED",
    },
    "xhs": {
        "module": "uploader.xiaohongshu_uploader.main",
        "video_class": "XiaoHongShuVideo",
        "note_class": "XiaoHongShuNote",
        "upload_method_video": "xiaohongshu_upload_video",
        "upload_method_note": "xiaohongshu_upload_note",
        "cookie_subdir": "xiaohongshu_uploader",
        "immediate_strategy": "XIAOHONGSHU_PUBLISH_STRATEGY_IMMEDIATE",
        "scheduled_strategy": "XIAOHONGSHU_PUBLISH_STRATEGY_SCHEDULED",
    },
    "kuaishou": {
        "module": "uploader.ks_uploader.main",
        "video_class": "KSVideo",
        "note_class": "KSNote",
        "upload_method_video": "ks_upload_video",
        "upload_method_note": "ks_upload_note",
        "cookie_subdir": "ks_uploader",
        "immediate_strategy": "KS_PUBLISH_STRATEGY_IMMEDIATE",
        "scheduled_strategy": "KS_PUBLISH_STRATEGY_SCHEDULED",
    },
    "tencent": {
        "module": "uploader.tencent_uploader.main",
        "video_class": "TencentVideo",
        "note_class": "TencentNote",
        "upload_method_video": "tencent_upload_video",
        "upload_method_note": "tencent_upload_note",
        "cookie_subdir": "tencent_uploader",
        "immediate_strategy": "TENCENT_PUBLISH_STRATEGY_IMMEDIATE",
        "scheduled_strategy": "TENCENT_PUBLISH_STRATEGY_SCHEDULED",
    },
    "youtube": {
        "module": "uploader.youtube_uploader.main",
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

    def _account_name(self, platform: str) -> str:
        accounts = getattr(_SAU_CONFIG, "accounts", {}) or {}
        return accounts.get(platform, platform)

    def _publish_timeout_seconds(self) -> int:
        return int(getattr(_SAU_CONFIG, "publish_timeout_seconds", 900) or 900)

    def _sync_douyin_session_to_external_sau(self) -> Path:
        account_name = self._account_name("douyin")
        source = _SESSIONS_DIR / "storage_state_douyin.json"
        target = _SAU_COOKIES_DIR / f"douyin_{account_name}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.copy2(source, target)
        return target

    def _sync_external_sau_to_douyin_session(self) -> None:
        account_name = self._account_name("douyin")
        source = _SAU_COOKIES_DIR / f"douyin_{account_name}.json"
        target = _SESSIONS_DIR / "storage_state_douyin.json"
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    async def _run_external_sau(self, args: list[str], timeout_seconds: int = 900) -> dict:
        sau_cli = _SAU_DIR / "sau_cli.py"
        if not sau_cli.exists():
            return {
                "success": False,
                "message": f"social-auto-upload CLI not found: {sau_cli}",
                "stdout": "",
                "stderr": "",
            }

        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(sau_cli),
            *args,
            cwd=str(_SAU_DIR),
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

    async def _external_douyin_upload_video(
        self,
        file_path: str,
        title: str,
        desc: str,
        tags: list[str] | None,
        thumbnail_path: str | None,
        schedule: datetime | None,
        headless: bool,
    ) -> dict:
        account_name = self._account_name("douyin")
        account_file = self._sync_douyin_session_to_external_sau()
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

        result = await self._run_external_sau(args, timeout_seconds=self._publish_timeout_seconds())
        self._sync_external_sau_to_douyin_session()
        result.update({
            "platform": "douyin",
            "title": title,
            "file_path": file_path,
            "account_file": str(account_file),
            "engine": "external-social-auto-upload",
        })
        return result

    async def _external_douyin_upload_note(
        self,
        image_paths: list[str],
        title: str,
        note: str,
        tags: list[str] | None,
        schedule: datetime | None,
        headless: bool,
    ) -> dict:
        account_name = self._account_name("douyin")
        account_file = self._sync_douyin_session_to_external_sau()
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

        result = await self._run_external_sau(args, timeout_seconds=self._publish_timeout_seconds())
        self._sync_external_sau_to_douyin_session()
        result.update({
            "platform": "douyin",
            "title": title,
            "account_file": str(account_file),
            "engine": "external-social-auto-upload",
        })
        return result

    def _get_account_file(self, platform: str) -> str:
        """获取平台 cookie 文件路径。

        优先使用 szyg session 目录的 storage_state 文件，
        如果不存在则回退到 sau cookies 目录。
        """
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
            )

        try:
            mod, cfg = self._import_uploader(platform)
            account = account_file or self._get_account_file(platform)

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
            }

        except Exception as e:
            logger.error(f"[sau] {platform} 视频上传失败: {e}", exc_info=True)
            return {
                "success": False,
                "platform": platform,
                "message": str(e),
                "title": title,
                "file_path": file_path,
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
            )

        try:
            mod, cfg = self._import_uploader(platform)
            if not cfg["note_class"]:
                raise ValueError(f"平台 {platform} 不支持图文上传")

            account = account_file or self._get_account_file(platform)
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
            }

        except Exception as e:
            logger.error(f"[sau] {platform} 图文上传失败: {e}", exc_info=True)
            return {
                "success": False,
                "platform": platform,
                "message": str(e),
                "title": title,
            }

    async def login(self, platform: str, headless: bool = False) -> dict:
        """触发平台登录（扫码）。

        Args:
            platform: 平台名
            headless: 是否无头（登录通常需要有头）

        Returns:
            {"success": bool, "platform": str, "account_file": str, "message": str}
        """
        if platform == "douyin":
            account_name = self._account_name("douyin")
            account_file = self._sync_douyin_session_to_external_sau()
            result = await self._run_external_sau([
                "douyin",
                "login",
                "--account",
                account_name,
                "--headless" if headless else "--headed",
            ], timeout_seconds=600)
            self._sync_external_sau_to_douyin_session()
            return {
                "success": result["success"],
                "platform": platform,
                "account_file": str(account_file),
                "message": result.get("message", ""),
                "engine": "external-social-auto-upload",
            }

        try:
            mod, cfg = self._import_uploader(platform)
            account = self._get_account_file(platform)

            # sau 的 setup 函数名规则: {platform}_setup
            setup_func_name = f"{platform.replace('xhs', 'xiaohongshu')}_setup"
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
                    "account_file": account,
                    "message": result.get("message", ""),
                    "qrcode": result.get("qrcode"),
                }
            elif result is True:
                return {
                    "success": True,
                    "platform": platform,
                    "account_file": account,
                    "message": "登录成功",
                }
            else:
                return {
                    "success": False,
                    "platform": platform,
                    "account_file": account,
                    "message": "登录失败",
                }

        except Exception as e:
            logger.error(f"[sau] {platform} 登录失败: {e}", exc_info=True)
            return {
                "success": False,
                "platform": platform,
                "message": str(e),
            }

    async def check_login(self, platform: str) -> dict:
        """检查平台登录状态。

        Args:
            platform: 平台名

        Returns:
            {"logged_in": bool, "platform": str, "account_file": str}
        """
        if platform == "douyin":
            account_name = self._account_name("douyin")
            account_file = self._sync_douyin_session_to_external_sau()
            result = await self._run_external_sau([
                "douyin",
                "check",
                "--account",
                account_name,
            ], timeout_seconds=120)
            return {
                "logged_in": result["success"],
                "platform": platform,
                "account_file": str(account_file),
                "message": result.get("message", ""),
                "engine": "external-social-auto-upload",
            }

        try:
            mod, cfg = self._import_uploader(platform)
            account = self._get_account_file(platform)

            if not os.path.exists(account):
                return {
                    "logged_in": False,
                    "platform": platform,
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
                    "account_file": account,
                }

            # 没有 cookie_auth 函数，检查文件是否非空
            size = os.path.getsize(account)
            return {
                "logged_in": size > 100,
                "platform": platform,
                "account_file": account,
                "message": f"cookie 文件 {size} bytes" if size > 0 else "cookie 文件为空",
            }

        except Exception as e:
            logger.error(f"[sau] {platform} 登录状态检查失败: {e}")
            return {
                "logged_in": False,
                "platform": platform,
                "message": str(e),
            }

    def list_platforms(self) -> list[dict]:
        """列出所有支持的平台及其状态。"""
        platforms = []
        for name, cfg in _PLATFORM_MAP.items():
            account = self._get_account_file(name)
            has_cookie = os.path.exists(account)
            platforms.append({
                "platform": name,
                "video_support": bool(cfg["video_class"]),
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
