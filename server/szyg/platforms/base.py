"""
Base Platform Adapter — 平台适配器抽象基类

对标数创引擎:
  - core/douyin.pyd  → DouyinAdapter
  - core/xhs.pyd     → XiaohongshuAdapter
  - wxauto/wx.pyd    → WeChatDesktopAdapter
  - core/wecom.pyd   → WeComAdapter (future)

每个平台适配器实现统一的 publish() / check_login() / login() 接口。
"""
import asyncio
import logging
import random
from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from szyg.publisher import Platform, ContentType

logger = logging.getLogger(__name__)


# ── Data Models ──────────────────────────────────────────────

class AdapterState(str, Enum):
    """适配器运行状态"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    LOGGED_OUT = "logged_out"
    PUBLISHING = "publishing"
    ERROR = "error"
    CLOSED = "closed"


class LoginStatus(BaseModel):
    """平台登录状态"""
    is_logged_in: bool = False
    account_name: str = ""
    account_avatar: str = ""
    cookie_valid_until: str = ""       # ISO datetime
    qr_code_url: str = ""              # 如需扫码登录，base64 图片
    qr_code_expires_at: str = ""       # 二维码过期时间
    message: str = ""                  # 状态描述
    need_sms: bool = False             # 是否需要短信验证码


class PublishRequest(BaseModel):
    """统一发布请求 — 从 Content 模型转换而来"""
    content_id: str = ""
    title: str = ""
    body: str = ""                     # 正文 (支持 Markdown/HTML)
    content_type: ContentType = ContentType.POST
    media_urls: list[str] = Field(default_factory=list)   # 图片/视频本地路径或URL
    tags: list[str] = Field(default_factory=list)          # 话题标签
    location: str = ""                 # 地理位置 (如有)
    scheduled_at: str = ""             # 定时发布时间 ISO format
    extra: dict = Field(default_factory=dict)              # 平台特有参数

    def to_plain_text(self) -> str:
        """将 Markdown body 转为纯文本 (适配不支持富文本的平台)"""
        import re
        text = self.body
        # Remove Markdown syntax
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)       # bold
        text = re.sub(r'\*(.+?)\*', r'\1', text)           # italic
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)    # links
        text = re.sub(r'#+\s*', '', text)                  # headings
        text = re.sub(r'`(.+?)`', r'\1', text)             # inline code
        return text.strip()

    def to_html(self) -> str:
        """将 Markdown body 转为 HTML (适配公众号等平台)"""
        try:
            import markdown
            return markdown.markdown(self.body, extensions=['extra', 'codehilite'])
        except ImportError:
            return self.body.replace('\n', '<br>')


class PublishResult(BaseModel):
    """统一发布结果"""
    success: bool = False
    platform: str = ""                 # Platform enum value
    platform_post_id: str = ""         # 平台返回的帖子 ID
    platform_post_url: str = ""        # 帖子公开链接
    error_msg: str = ""
    error_code: str = ""               # 平台错误码
    published_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    extra: dict = Field(default_factory=dict)


# ── Abstract Base Class ──────────────────────────────────────

class BasePlatformAdapter(ABC):
    """
    平台适配器基类

    每个社交平台实现此接口，提供:
      - check_login(): 验证当前登录态
      - login(): 执行登录 (扫码/密码/Cookie)
      - publish(): 发布内容
      - get_status(): 查询发布状态

    生命周期:
      1. __init__() → UNINITIALIZED
      2. initialize() → INITIALIZING → READY
      3. check_login() / login() → 确保登录
      4. publish() → 异步发布
      5. close() → CLOSED
    """

    # 子类必须设置
    platform: Platform

    def __init__(self):
        self._state = AdapterState.UNINITIALIZED
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def state(self) -> AdapterState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return self._state == AdapterState.READY

    @property
    def platform_name(self) -> str:
        """平台中文名"""
        names = {
            Platform.DOUYIN: "抖音",
            Platform.XHS: "小红书",
            Platform.WECHAT_MP: "微信公众号",
            Platform.WECOM: "企业微信",
            Platform.KUAISHOU: "快手",
            Platform.BILIBILI: "B站",
            Platform.WEIBO: "微博",
        }
        return names.get(self.platform, self.platform.value)

    # ── Lifecycle ─────────────────────────────────────────

    async def initialize(self) -> bool:
        """初始化适配器 (启动浏览器/建立连接等)"""
        self._state = AdapterState.INITIALIZING
        try:
            ok = await self._do_initialize()
            self._state = AdapterState.READY if ok else AdapterState.ERROR
            return ok
        except Exception as e:
            self._logger.error(f"初始化失败: {e}")
            self._state = AdapterState.ERROR
            return False

    @abstractmethod
    async def _do_initialize(self) -> bool:
        """子类实现：实际的初始化逻辑"""
        ...

    @abstractmethod
    async def check_login(self) -> LoginStatus:
        """检查当前登录态是否有效"""
        ...

    @abstractmethod
    async def login(self, **kwargs) -> LoginStatus:
        """执行登录操作"""
        ...

    @abstractmethod
    async def publish(self, request: PublishRequest) -> PublishResult:
        """发布内容到平台"""
        ...

    @abstractmethod
    async def get_status(self, platform_post_id: str) -> dict:
        """查询已发布内容的状态"""
        ...

    async def safe_publish(self, request: PublishRequest) -> PublishResult:
        """
        安全发布包装器：失败后自动重试一次，并保存审计截图。
        各平台适配器无需改动，调用方使用 safe_publish 替代 publish 即可。
        """
        request = await self.pre_publish(request)
        last_error = None
        for attempt in range(2):
            try:
                result = await self.publish(request)
                await self.post_publish(request, result)
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"[{self.platform_name}] 发布失败 (attempt {attempt + 1}/2): {e}")
                await self._audit_screenshot(f"publish_failed_attempt_{attempt + 1}")
                if attempt == 0:
                    await asyncio.sleep(random.uniform(2, 5))
        # 两次都失败
        logger.error(f"[{self.platform_name}] 发布重试后仍失败: {last_error}")
        return PublishResult(
            success=False, platform=self.platform.value,
            error_msg=f"发布失败（已重试1次）: {str(last_error)[:200]}",
        )

    async def _audit_screenshot(self, suffix: str = "audit") -> None:
        """保存审计截图到 data/audit/{platform}/ （不依赖外部模块）"""
        page = getattr(self, '_page', None)
        if not page:
            return
        try:
            from pathlib import Path
            from datetime import datetime
            from szyg.data_path import DATA_DIR
            audit_dir = DATA_DIR / "audit" / self.platform.value / datetime.now().strftime("%Y-%m-%d")
            audit_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
            path = audit_dir / f"{timestamp}_{suffix}.png"
            await page.screenshot(path=str(path), full_page=False)
            logger.info(f"[Audit] 截图已保存: {path}")
        except Exception as e:
            logger.debug(f"[Audit] 截图失败: {e}")

    async def close(self) -> None:
        """关闭适配器，释放资源"""
        ...

    # ── Optional Hooks ────────────────────────────────────

    async def pre_publish(self, request: PublishRequest) -> PublishRequest:
        """
        发布前处理钩子。
        子类可重写以实现:
        - 内容格式转换 (Markdown→HTML, 长度截断等)
        - 话题标签处理 (#tag)
        - 平台特有字段填充
        """
        return request

    async def post_publish(self, request: PublishRequest, result: PublishResult) -> None:
        """发布后处理钩子。默认记录日志。"""
        status = "✓" if result.success else "✗"
        self._logger.info(
            f"{status} [{self.platform_name}] 发布 {request.content_id}: "
            f"{result.platform_post_id or result.error_msg}"
        )

    async def health_check(self) -> bool:
        """快速健康检查 (默认通过 check_login 实现)"""
        try:
            status = await self.check_login()
            return status.is_logged_in
        except Exception:
            return False

    async def preflight_publish(self, request: PublishRequest) -> dict:
        """Validate publish prerequisites without clicking publish."""
        login = await self.check_login()
        return {
            "ok": False,
            "platform": self.platform.value,
            "logged_in": login.is_logged_in,
            "checks": {
                "logged_in": login.is_logged_in,
                "publish_page": False,
                "upload_input": False,
            },
            "errors": ["preflight not implemented"],
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} platform={self.platform.value} state={self._state.value}>"
