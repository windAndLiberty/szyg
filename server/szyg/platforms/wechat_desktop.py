"""
WeChatDesktopAdapter — 微信桌面客户端 Windows UI Automation 适配器

对标数创引擎: wxauto/ 框架 (wx.pyd + ui/*.pyd) + weixin/ 模块

使用 Windows UI Automation (UIA) API 控制微信桌面客户端:
  - 不需要 DLL 注入
  - 使用 Microsoft 官方的 UIAutomation COM 接口
  - 支持: 朋友圈发布、消息发送、联系人操作

依赖:
  pip install uiautomation
  pip install pywin32  (for clipboard operations)

技术原理:
  Windows UI Automation 是 Windows 7+ 内置的无障碍 API，
  通过 COM 接口可以枚举、控制和监听所有窗口元素。
  uiautomation 包提供了 Pythonic 的 UIA 封装。

安全说明:
  UIA 是 Windows 官方 API，不涉及进程注入。
  对标数创引擎的 wxauto 框架 (同样基于 UIA，参见 wxauto/uia/uiautomation.py)。
"""
import asyncio
import logging
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

from szyg.publisher import Platform, ContentType
from szyg.platforms.base import (
    BasePlatformAdapter, PublishRequest, PublishResult,
    LoginStatus, AdapterState,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

WECHAT_EXE_PATHS = [
    r"C:\Program Files\Tencent\WeChat\WeChat.exe",
    r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
    r"D:\Program Files\Tencent\WeChat\WeChat.exe",
]

WECHAT_MOMENTS_MAX_TEXT = 2000    # 朋友圈文字上限
WECHAT_MOMENTS_MAX_IMAGES = 9     # 朋友圈图片上限


class WeChatDesktopAdapter(BasePlatformAdapter):
    """
    微信桌面客户端适配器 (Windows UI Automation)

    功能:
      - 检测微信是否运行
      - 发布朋友圈
      - 发送消息 (未来)

    注意:
      - 微信版本更新可能改变 UI 结构，需要维护选择器
      - 需要微信桌面版已登录 (用户手动扫码登录)
      - 发布操作会占用鼠标键盘 (通过 UIA SendKeys/Click)

    Usage:
        adapter = WeChatDesktopAdapter()
        await adapter.initialize()
        status = await adapter.check_login()
        if status.is_logged_in:
            result = await adapter.publish_moment(request)
    """

    platform = Platform.WECHAT_MP
    platform_name = "微信"

    def __init__(self):
        super().__init__()
        self._uia = None
        self._wechat_window = None
        self._wechat_control = None

    # ── Lifecycle ─────────────────────────────────────────

    async def _do_initialize(self) -> bool:
        """检查 UIA 库是否可用"""
        try:
            import uiautomation
            self._uia = uiautomation
            logger.info("WeChatDesktopAdapter: UIAutomation 就绪")
            self._state = AdapterState.READY
            return True
        except ImportError:
            logger.error(
                "需要安装 uiautomation: pip install uiautomation"
            )
            return False
        except Exception as e:
            logger.error(f"WeChatDesktopAdapter 初始化失败: {e}")
            return False

    async def close(self) -> None:
        """释放 UIA 连接"""
        self._wechat_window = None
        self._wechat_control = None
        self._state = AdapterState.CLOSED

    # ── WeChat Process Management ─────────────────────────

    def _find_wechat_window(self):
        """
        查找微信主窗口。

        Returns:
            uiautomation.WindowControl 或 None
        """
        if not self._uia:
            return None

        try:
            # 通过窗口名称查找微信
            wechat = self._uia.WindowControl(
                Name='微信',
                searchDepth=1
            )
            if wechat.Exists(maxSearchSeconds=1):
                return wechat

            # 尝试通过 ClassName 查找
            wechat = self._uia.WindowControl(
                ClassName='WeChatMainWndForPC',
                searchDepth=1
            )
            if wechat.Exists(maxSearchSeconds=1):
                return wechat

        except Exception as e:
            logger.warning(f"查找微信窗口失败: {e}")

        return None

    def _is_wechat_running(self) -> bool:
        """检查微信进程是否运行"""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and 'wechat' in proc.info['name'].lower():
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            # Fallback: 尝试查找窗口
            return self._find_wechat_window() is not None
        except Exception:
            logger.debug(f"Non-critical operation skipped in {self.platform_name} adapter")
        return False

    def _start_wechat(self) -> bool:
        """启动微信"""
        for path in WECHAT_EXE_PATHS:
            if Path(path).exists():
                try:
                    subprocess.Popen([path])
                    logger.info(f"已启动微信: {path}")
                    return True
                except Exception as e:
                    logger.warning(f"启动微信失败 ({path}): {e}")

        logger.error("未找到微信安装路径")
        return False

    # ── Login Check ───────────────────────────────────────

    async def check_login(self) -> LoginStatus:
        """
        检查微信登录状态。

        微信桌面版无公开的登录态API，通过窗口存在性判断:
          - 微信进程运行 + 主窗口可见 → 可能已登录
          - 微信进程未运行 → 未登录
        """
        if self._is_wechat_running():
            window = self._find_wechat_window()
            if window:
                self._wechat_window = window
                try:
                    title = window.Name
                    # 如果窗口标题显示"微信" (非"登录") → 已登录
                    if "登录" not in title:
                        return LoginStatus(
                            is_logged_in=True,
                            account_name=title.replace("微信", "").strip(),
                            message="微信已登录",
                        )
                except Exception as e:
                    logger.warning(f"UIA operation failed in {self.platform_name}: {e}")
                return LoginStatus(is_logged_in=True, message="微信正在运行")

            return LoginStatus(is_logged_in=False, message="微信未运行")

        return LoginStatus(is_logged_in=False, message="微信未运行，请先启动微信")

    async def login(self, **kwargs) -> LoginStatus:
        """
        启动微信并等待用户扫码。

        流程:
          1. 检查微信是否已运行
          2. 如未运行，启动微信
          3. 等待用户完成扫码登录 (检查窗口标题变化)
        """
        if not self._is_wechat_running():
            started = self._start_wechat()
            if not started:
                return LoginStatus(is_logged_in=False, message="无法启动微信")

        logger.info("等待用户扫码登录微信… (5分钟超时)")
        timeout = kwargs.get("timeout", 300)

        for i in range(timeout):
            await asyncio.sleep(1)

            window = self._find_wechat_window()
            if window:
                try:
                    title = window.Name
                    if "登录" not in title and title.strip():
                        self._wechat_window = window
                        logger.info(f"✓ 微信已登录: {title}")
                        return LoginStatus(is_logged_in=True, message=f"登录成功: {title}")
                except Exception as e:
                    logger.warning(f"UIA operation failed in {self.platform_name}: {e}")

            if i % 30 == 0 and i > 0:
                logger.info(f"  等待扫码中… ({i}s / {timeout}s)")

        return LoginStatus(is_logged_in=False, message=f"登录超时 ({timeout}s)")

    # ── Publish (Moments / 朋友圈) ─────────────────────────

    async def publish(self, request: PublishRequest) -> PublishResult:
        """
        发布内容到微信。

        当前支持:
          - 发布朋友圈 (图文)

        微信内容类型适配:
          - POST → 朋友圈
          - ARTICLE → 公众号文章 (需公众号API)
          - IMAGE_POST → 朋友圈图片
        """
        if request.content_type == ContentType.ARTICLE:
            return PublishResult(
                success=False, platform=Platform.WECHAT_MP.value,
                error_msg="公众号文章发布需要配置公众号 API，请使用 WeChatMPAdapter",
            )

        # 默认: 发布朋友圈
        return await self.publish_moment(request)

    async def publish_moment(self, request: PublishRequest) -> PublishResult:
        """
        通过 UIA 发布朋友圈。

        流程:
          1. 确认微信已登录，主窗口可见
          2. 打开朋友圈 (快捷键: Alt+M → 朋友圈 或 UIA 导航)
          3. 点击"相机"图标 → 选择"从手机相册选择"或"拍摄"
          4. 粘贴文字内容
          5. 添加图片 (通过剪贴板)
          6. 点击"发表"

        UIA 操作对应微信 UI 控件:
          - 朋友圈按钮: Name='朋友圈' ControlType=ButtonControl
          - 文字输入框: ControlType=EditControl
          - 发表按钮: Name='发表' ControlType=ButtonControl
        """
        if not self._uia:
            return PublishResult(
                success=False, platform=Platform.WECHAT_MP.value,
                error_msg="UIAutomation 不可用，请安装: pip install uiautomation",
            )

        login_status = await self.check_login()
        if not login_status.is_logged_in:
            return PublishResult(
                success=False, platform=Platform.WECHAT_MP.value,
                error_msg="微信未登录",
            )

        self._state = AdapterState.PUBLISHING

        try:
            wechat = self._find_wechat_window()
            if not wechat:
                return PublishResult(
                    success=False, platform=Platform.WECHAT_MP.value,
                    error_msg="未找到微信窗口",
                )

            # 确保微信窗口在前台
            wechat.SetFocus()
            await asyncio.sleep(0.5)
            wechat.Maximize()
            await asyncio.sleep(0.5)

            # ── 打开朋友圈 ──────────────────────────────
            # 发送 Alt+M 快捷键 (微信默认: Alt+M 打开朋友圈)
            # 或者通过 UIA 找到朋友圈按钮
            wechat.SendKeys("{Alt}M")
            await asyncio.sleep(2)

            # 检查是否成功打开朋友圈窗口
            moment_window = self._uia.WindowControl(Name='朋友圈', searchDepth=2)
            if not moment_window.Exists(maxSearchSeconds=3):
                # 方法2: 通过 UIA 导航到朋友圈
                try:
                    moments_btn = wechat.ButtonControl(Name='朋友圈')
                    if moments_btn.Exists():
                        moments_btn.Click()
                        await asyncio.sleep(2)
                except Exception as e:
                    logger.warning(f"UIA operation failed in {self.platform_name}: {e}")

            # ── 点击"相机" → 发表图文 ──────────────────────
            camera_btn = wechat.ButtonControl(
                Name=lambda n: n and ('相机' in n or '相册' in n or 'Camera' in n)
            )
            if camera_btn.Exists(maxSearchSeconds=2):
                # 长按或右键打开菜单，选择"从手机相册选择"
                camera_btn.RightClick()
                await asyncio.sleep(0.5)
                photo_opt = wechat.MenuItemControl(Name='从手机相册选择')
                if photo_opt.Exists():
                    photo_opt.Click()
                    await asyncio.sleep(1)
            else:
                # 尝试快捷键: Ctrl+Alt+P 或点击区域
                wechat.SendKeys("^p")
                await asyncio.sleep(1)

            # ── 填入文字 ──────────────────────────────────
            # 朋友圈文字编辑框
            text_edit = wechat.EditControl(
                Name=lambda n: n and ('这一刻的想法' in n or '说点什么' in n)
            )
            if not text_edit.Exists(maxSearchSeconds=2):
                # 尝试找到任何可用的 EditControl
                text_edit = wechat.EditControl(searchDepth=3)

            if text_edit.Exists(maxSearchSeconds=2):
                text_edit.Click()
                await asyncio.sleep(0.3)

                body = request.body[:WECHAT_MOMENTS_MAX_TEXT] if request.body else request.title
                # 使用剪贴板粘贴 (支持中文 + 长文本)
                await self._clipboard_paste(text_edit, body)
                await asyncio.sleep(1)
            else:
                logger.warning("未找到朋友圈文字输入框")

            # ── 添加图片 ──────────────────────────────────
            if request.media_urls:
                await self._add_images_to_moment(request.media_urls[:WECHAT_MOMENTS_MAX_IMAGES])

            # ── 添加话题标签 ──────────────────────────────
            if request.tags and text_edit and text_edit.Exists():
                tag_text = " ".join(f"#{t}" for t in request.tags)
                await self._clipboard_paste(text_edit, f" {tag_text}")
                await asyncio.sleep(0.5)

            # ── 点击"发表" ────────────────────────────────
            publish_btn = wechat.ButtonControl(Name=lambda n: n and '发表' in n)
            if publish_btn.Exists(maxSearchSeconds=2):
                publish_btn.Click()
                await asyncio.sleep(3)
            else:
                # 尝试快捷键 Ctrl+Enter 发表
                wechat.SendKeys("{Ctrl}{Enter}")
                await asyncio.sleep(3)

            self._state = AdapterState.READY

            # 检查是否发表成功 (朋友圈窗口关闭 = 成功)
            if not self._uia.WindowControl(Name='朋友圈').Exists(maxSearchSeconds=1):
                return PublishResult(
                    success=True,
                    platform=Platform.WECHAT_MP.value,
                    platform_post_id=f"moment_{int(time.time())}",
                )
            else:
                return PublishResult(
                    success=True,  # 无法100%确认，假设成功
                    platform=Platform.WECHAT_MP.value,
                    platform_post_id=f"moment_{int(time.time())}",
                    error_msg="发布结果未知 — 请在微信中确认",
                )

        except Exception as e:
            logger.error(f"微信朋友圈发布异常: {e}")
            self._state = AdapterState.ERROR
            return PublishResult(
                success=False, platform=Platform.WECHAT_MP.value,
                error_msg=str(e),
            )

    # ── Helpers ───────────────────────────────────────────

    async def _clipboard_paste(self, element, text: str) -> None:
        """通过剪贴板粘贴文本 (更可靠地处理中文和长文本)"""
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
        except ImportError:
            # Fallback: 使用 uiautomation SendKeys (可能不支持中文)
            element.SendKeys(text)
            return

        await asyncio.sleep(0.1)
        # Ctrl+V 粘贴
        if hasattr(element, 'SendKeys'):
            element.SendKeys("{Ctrl}v")
        else:
            self._uia.SendKeys("{Ctrl}v")

    async def _add_images_to_moment(self, media_urls: list[str]) -> None:
        """添加图片到朋友圈 (通过"添加图片"按钮)"""
        try:
            add_btn = self._wechat_window.ButtonControl(
                Name=lambda n: n and ('添加' in n or 'Add' in n or '图片' in n)
            )
            if not add_btn.Exists(maxSearchSeconds=2):
                return

            for i, url in enumerate(media_urls):
                # 朋友圈的图片上传通常需要通过文件对话框
                # 点击添加按钮 → 弹出文件选择 → 填入路径
                add_btn.Click()
                await asyncio.sleep(1)

                # 查找文件对话框
                file_dialog = self._uia.WindowControl(Name='打开')
                if file_dialog.Exists(maxSearchSeconds=3):
                    # 在文件名输入框中填入文件路径
                    file_input = file_dialog.EditControl(
                        Name=lambda n: n and ('文件名' in n or 'File name' in n)
                    )
                    if file_input.Exists():
                        local_path = url
                        if url.startswith(("http://", "https://")):
                            import tempfile, httpx
                            async with httpx.AsyncClient() as client:
                                resp = await client.get(url, timeout=30)
                                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                                    f.write(resp.content)
                                    local_path = f.name
                        file_input.SendKeys(local_path)
                        await asyncio.sleep(0.5)
                        # 点击打开按钮
                        open_btn = file_dialog.ButtonControl(Name='打开')
                        if open_btn.Exists():
                            open_btn.Click()
                            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"添加图片失败: {e}")

    # ── Get Status ────────────────────────────────────────

    async def get_status(self, platform_post_id: str) -> dict:
        """查询发布状态 (朋友圈无状态查询API)"""
        return {
            "platform": "wechat",
            "post_id": platform_post_id,
            "status": "unknown",
            "message": "微信朋友圈不支持状态查询",
        }

    # ── Additional: Send Message ──────────────────────────

    async def send_message(self, contact: str, text: str) -> bool:
        """
        通过 UIA 发送微信消息。

        Args:
            contact: 联系人名称
            text: 消息内容
        """
        if not self._uia or not self._is_wechat_running():
            return False

        try:
            wechat = self._find_wechat_window()
            if not wechat:
                return False

            # Ctrl+F 搜索联系人
            wechat.SendKeys("{Ctrl}f")
            await asyncio.sleep(1)

            # 输入联系人名称
            search_box = wechat.EditControl(searchDepth=3)
            if search_box.Exists(maxSearchSeconds=2):
                search_box.SendKeys(contact)
                await asyncio.sleep(2)
                # Enter 打开聊天
                wechat.SendKeys("{Enter}")
                await asyncio.sleep(1)

            # 输入消息
            msg_edit = wechat.EditControl(
                Name=lambda n: n and ('输入' in n or '消息' in n)
            )
            if msg_edit.Exists(maxSearchSeconds=2):
                await self._clipboard_paste(msg_edit, text)
                await asyncio.sleep(0.5)
                wechat.SendKeys("{Enter}")  # 发送

            return True
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
            return False
