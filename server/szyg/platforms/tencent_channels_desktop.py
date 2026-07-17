"""Tencent Channels desktop-assisted publishing workflow.

Video Channels is sensitive to managed browser automation. This module keeps
the product workflow on a real desktop browser profile and records every handoff
through ExecutionKernel.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from szyg.execution_kernel import get_execution_kernel
from szyg.integrations.desktop_browser_session import get_desktop_browser_session

TENCENT_CHANNELS_LOGIN_URL = "https://channels.weixin.qq.com/login.html"
TENCENT_CHANNELS_VIDEO_PUBLISH_URL = "https://channels.weixin.qq.com/platform/post/create"
TENCENT_CHANNELS_NOTE_PUBLISH_URL = "https://channels.weixin.qq.com/platform/post/finderNewLifeCreate"
TENCENT_CHANNELS_MANAGE_URL = "https://channels.weixin.qq.com/platform/post/list"
TENCENT_CHANNELS_PUBLISH_URL = TENCENT_CHANNELS_VIDEO_PUBLISH_URL
TENCENT_CHANNELS_PROFILE_KEY = "tencent_channels_edge"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv"}
LINK_LOOKUP_TIMEOUT_SECONDS = 12


@dataclass
class TencentPublishPayload:
    title: str = ""
    desc: str = ""
    tags: list[str] = field(default_factory=list)
    file_path: str = ""
    asset_paths: list[str] = field(default_factory=list)
    mode: str = "video"
    auto_publish: bool = True


class TencentChannelsDesktopAssistant:
    """Business wrapper for Tencent Channels desktop handoff."""

    platform = "tencent"

    def open_login(self) -> dict[str, Any]:
        launch = get_desktop_browser_session().launch(
            TENCENT_CHANNELS_LOGIN_URL,
            profile_key=TENCENT_CHANNELS_PROFILE_KEY,
            no_proxy=True,
        )
        return {
            **launch.to_dict(),
            "login_url": TENCENT_CHANNELS_LOGIN_URL,
            "publish_url": TENCENT_CHANNELS_PUBLISH_URL,
            "desktop_assist": True,
        }

    def _publish_url(self, mode: str) -> str:
        return TENCENT_CHANNELS_NOTE_PUBLISH_URL if mode == "note" else TENCENT_CHANNELS_VIDEO_PUBLISH_URL

    def _existing_paths(self, paths: list[str], extensions: set[str]) -> list[str]:
        result: list[str] = []
        for raw_path in paths:
            path = Path(raw_path).expanduser()
            if path.exists() and path.suffix.lower() in extensions:
                result.append(str(path))
        return result

    def _note_image_paths(self, payload: TencentPublishPayload) -> list[str]:
        return self._existing_paths(payload.asset_paths, IMAGE_EXTENSIONS)

    def _video_path(self, payload: TencentPublishPayload) -> str:
        if payload.file_path:
            path = Path(payload.file_path).expanduser()
            if path.exists() and path.suffix.lower() in VIDEO_EXTENSIONS:
                return str(path)
        paths = self._existing_paths(payload.asset_paths, VIDEO_EXTENSIONS)
        return paths[0] if paths else ""

    def _publish_frame(self, page: Any, mode: str) -> Any:
        expected = "finderNewLifeCreate" if mode == "note" else "post/create"
        for frame in page.frames:
            if "channels.weixin.qq.com/micro/" in frame.url and expected in frame.url:
                return frame
        for frame in page.frames:
            if "channels.weixin.qq.com/micro/" in frame.url:
                return frame
        return page

    async def _wait_publish_target(self, page: Any, mode: str) -> Any:
        file_selector = 'input[type="file"][accept*="image"], input[type="file"]' if mode == "note" else 'input[type="file"][accept*="video"], input[type="file"]'
        for _ in range(30):
            target = self._publish_frame(page, mode)
            try:
                if await target.evaluate("(selector) => Boolean(document.querySelector(selector))", file_selector):
                    return target
            except Exception:
                pass
            await page.wait_for_timeout(500)
        return self._publish_frame(page, mode)

    async def _set_files_via_upload_area(self, target: Any, file_paths: list[str], mode: str) -> bool:
        page = getattr(target, "page", target)
        upload_selector = (
            ".ant-upload-btn, .ant-upload-drag, .upload-wrap, .post-upload-wrap"
            if mode == "note"
            else ".upload-btn, .ant-upload-btn, .ant-upload-drag, .upload-wrap, .post-upload-wrap"
        )
        point = await target.evaluate(
            """(selector) => {
              const el = document.querySelector(selector);
              if (!el) return null;
              const rect = el.getBoundingClientRect();
              if (!rect.width || !rect.height) return null;
              return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
            }""",
            upload_selector,
        )
        if not point:
            return False
        point = await self._to_page_point(target, point)
        async with page.expect_file_chooser(timeout=10000) as chooser_info:
            await page.mouse.click(float(point["x"]), float(point["y"]))
        chooser = await chooser_info.value
        await chooser.set_files(file_paths)
        return True

    async def _to_page_point(self, target: Any, point: dict[str, Any]) -> dict[str, float]:
        """Convert frame-relative DOM coordinates to page viewport coordinates."""
        x = float(point.get("x") or 0)
        y = float(point.get("y") or 0)
        frame_element = getattr(target, "frame_element", None)
        if not callable(frame_element):
            return {"x": x, "y": y}
        try:
            element = await frame_element()
            box = await element.bounding_box()
            if box:
                return {"x": float(box.get("x") or 0) + x, "y": float(box.get("y") or 0) + y}
        except Exception:
            pass
        return {"x": x, "y": y}

    def _action_ok(self, actions: list[dict[str, Any]], action: str) -> bool:
        return any(item.get("action") == action and item.get("status") == "success" for item in actions)

    async def _upload_publish_files(self, target: Any, payload: TencentPublishPayload, actions: list[dict[str, Any]]) -> None:
        if payload.mode == "note":
            image_paths = self._note_image_paths(payload)
            if not image_paths:
                actions.append({"action": "upload_images", "status": "failed", "message": "图文发布需要至少一张图片"})
                return
            uploaded = False
            try:
                uploaded = await self._set_files_via_upload_area(target, image_paths, payload.mode)
            except Exception as exc:
                actions.append({"action": "upload_images_filechooser", "status": "failed", "message": str(exc)})
            if not uploaded:
                file_input = target.locator('input[type="file"][accept*="image"], input[type="file"]').first
                await file_input.set_input_files(image_paths)
            actions.append({"action": "upload_images", "status": "success", "count": len(image_paths), "paths": image_paths})
            await target.wait_for_timeout(3500)
            return

        video_path = self._video_path(payload)
        if not video_path:
            actions.append({"action": "upload_file", "status": "failed", "message": "视频发布需要一个可用视频文件"})
            return
        uploaded = False
        try:
            uploaded = await self._set_files_via_upload_area(target, [video_path], payload.mode)
        except Exception as exc:
            actions.append({"action": "upload_file_filechooser", "status": "failed", "message": str(exc)})
        if not uploaded:
            file_input = target.locator('input[type="file"][accept*="video"], input[type="file"]').first
            await file_input.set_input_files(video_path)
        actions.append({"action": "upload_file", "status": "success", "path": video_path})
        await target.wait_for_timeout(3500)

    async def _fill_title(self, target: Any, title: str, mode: str, actions: list[dict[str, Any]]) -> None:
        title = (title or "").strip()
        if not title:
            actions.append({"action": "fill_title", "status": "failed", "message": "标题为空"})
            return
        limit = 22 if mode == "note" else 30
        title_selectors = [
            'input[placeholder*="填写标题"]',
            'input[placeholder*="短标题"]',
            'input[placeholder*="标题"]',
        ]
        try:
            result = await target.evaluate(
                """({ selectors, value }) => {
                  const setInputValue = (el, nextValue) => {
                    const prototype = Object.getPrototypeOf(el);
                    const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
                    if (descriptor && descriptor.set) {
                      descriptor.set.call(el, nextValue);
                    } else {
                      el.value = nextValue;
                    }
                    el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: nextValue }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                  };
                  for (const selector of selectors) {
                    const el = document.querySelector(selector);
                    if (!el) continue;
                    el.focus();
                    setInputValue(el, value);
                    return { ok: true, selector, value: el.value || '' };
                  }
                  return { ok: false, selector: '' };
                }""",
                {"selectors": title_selectors, "value": title[:limit]},
            )
            if result and result.get("ok"):
                actions.append({"action": "fill_title", "status": "success", "selector": result.get("selector"), "limit": limit})
                return
        except Exception as exc:
            actions.append({"action": "fill_title_dom", "status": "failed", "message": str(exc)})
        actions.append({"action": "fill_title", "status": "failed", "message": "未找到标题输入框"})

    async def _fill_description(self, target: Any, payload: TencentPublishPayload, actions: list[dict[str, Any]]) -> None:
        desc_parts = []
        if payload.desc:
            desc_parts.append(payload.desc.strip())
        if payload.tags:
            desc_parts.append(" ".join(f"#{tag.strip().lstrip('#')}" for tag in payload.tags if tag.strip()))
        desc = "\n".join(part for part in desc_parts if part).strip()
        if not desc:
            return

        desc_selectors = [
            '.post-desc-box .input-editor[contenteditable]',
            '.input-editor[contenteditable]',
            'textarea[placeholder*="描述"]',
            'textarea[placeholder*="正文"]',
            'textarea[placeholder*="说点"]',
            '[contenteditable]',
            'div[role="textbox"]',
        ]
        try:
            result = await target.evaluate(
                """({ selectors, value }) => {
                  const setInputValue = (el, nextValue) => {
                    const prototype = Object.getPrototypeOf(el);
                    const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
                    if (descriptor && descriptor.set) {
                      descriptor.set.call(el, nextValue);
                    } else {
                      el.value = nextValue;
                    }
                  };
                  for (const selector of selectors) {
                    const el = document.querySelector(selector);
                    if (!el) continue;
                    el.focus();
                    if ('value' in el) {
                      setInputValue(el, value);
                    } else {
                      el.innerText = value;
                      el.textContent = value;
                    }
                    el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    return {
                      ok: true,
                      selector,
                      text: (el.innerText || el.value || el.textContent || '').trim(),
                    };
                  }
                  return { ok: false, selector: '' };
                }""",
                {"selectors": desc_selectors, "value": desc},
            )
            if result and result.get("ok"):
                actions.append({"action": "fill_description", "status": "success", "selector": result.get("selector")})
                return
        except Exception as exc:
            actions.append({"action": "fill_description_dom", "status": "failed", "message": str(exc)})
        actions.append({"action": "fill_description", "status": "skipped", "message": "未找到可用的正文输入框"})

    async def _click_publish(self, target: Any, actions: list[dict[str, Any]]) -> bool:
        try:
            await target.wait_for_function(
                """
                () => Array.from(document.querySelectorAll('button')).some((button) => {
                  const text = (button.innerText || button.textContent || '').trim();
                  const className = String(button.className || '');
                  return text === '发表' && !button.disabled && !className.includes('disabled');
                })
                """,
                timeout=180000,
            )
            point = await target.evaluate(
                """
                () => {
                const button = Array.from(document.querySelectorAll('button')).find((button) => {
                  const text = (button.innerText || button.textContent || '').trim();
                  const className = String(button.className || '');
                  return text === '发表' && !button.disabled && !className.includes('disabled');
                });
                if (!button) return null;
                button.scrollIntoView({ block: 'center', inline: 'center' });
                const rect = button.getBoundingClientRect();
                if (!rect.width || !rect.height) return null;
                return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
                }
                """
            )
            if not point:
                actions.append({"action": "click_publish", "status": "failed", "message": "未找到可点击的发表按钮"})
                return False
            point = await self._to_page_point(target, point)
            page = getattr(target, "page", target)
            await page.mouse.click(float(point["x"]), float(point["y"]))
            actions.append({"action": "click_publish", "status": "success", "message": "已点击发表按钮"})
            await target.wait_for_timeout(2500)

            confirm_point = await target.evaluate(
                """
                () => {
                const button = Array.from(document.querySelectorAll('button')).find((button) => {
                  const text = (button.innerText || button.textContent || '').trim();
                  const className = String(button.className || '');
                  return /确认发表|确定|继续发表/.test(text) && !button.disabled && !className.includes('disabled');
                });
                if (!button) return null;
                button.scrollIntoView({ block: 'center', inline: 'center' });
                const rect = button.getBoundingClientRect();
                if (!rect.width || !rect.height) return null;
                return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
                }
                """
            )
            if confirm_point:
                confirm_point = await self._to_page_point(target, confirm_point)
                await page.mouse.click(float(confirm_point["x"]), float(confirm_point["y"]))
                actions.append({"action": "confirm_publish", "status": "success"})
                await target.wait_for_timeout(3000)
            verified = await self._verify_publish_submitted(target, page)
            actions.append({
                "action": "verify_publish_submitted",
                "status": "success" if verified else "needs_human",
                "message": "检测到发表后状态" if verified else "页面仍停留在发表表单，请人工确认是否需要点击发表",
            })
            return verified
        except Exception as exc:
            actions.append({"action": "click_publish", "status": "needs_human", "message": f"发表按钮未就绪：{exc}"})
            return False

    async def _verify_publish_submitted(self, target: Any, page: Any) -> bool:
        """Return True only when the page shows a post-submit state."""
        success_patterns = re.compile(r"(发表成功|发布成功|已发表|提交成功|审核中|发布中)")
        for _ in range(12):
            try:
                current_url = page.url or ""
                if "finderNewLifeCreate" not in current_url and "post/create" not in current_url:
                    return True
                state = await target.evaluate(
                    """
                    () => {
                      const text = document.body ? document.body.innerText : '';
                      const publishButton = Array.from(document.querySelectorAll('button')).find((button) => {
                        const value = (button.innerText || button.textContent || '').trim();
                        const className = String(button.className || '');
                        return value === '发表' && !button.disabled && !className.includes('disabled');
                      });
                      return {
                        text: text.slice(0, 8000),
                        publishButtonEnabled: Boolean(publishButton),
                      };
                    }
                    """
                )
                if success_patterns.search(str(state.get("text") or "")):
                    return True
                if not state.get("publishButtonEnabled") and "finderNewLifeCreate" not in current_url:
                    return True
            except Exception:
                pass
            await page.wait_for_timeout(1000)
        return False

    async def _lookup_published_post(self, page: Any, title: str) -> dict[str, Any]:
        title = (title or "").strip()
        try:
            await page.goto(TENCENT_CHANNELS_MANAGE_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3500)
            attempts = max(1, LINK_LOOKUP_TIMEOUT_SECONDS)
            for _ in range(attempts):
                items = await page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll('a[href], [data-url], [data-href]')).map((el) => {
                      const text = (el.innerText || el.textContent || '').trim();
                      const href = el.getAttribute('href') || el.getAttribute('data-url') || el.getAttribute('data-href') || '';
                      return { text, href };
                    }).filter((item) => item.href || item.text).slice(0, 120)
                    """
                )
                candidates = []
                for item in items or []:
                    text = str(item.get("text") or "").strip()
                    href = str(item.get("href") or "").strip()
                    if not href:
                        continue
                    if title and title not in text:
                        continue
                    absolute = urljoin("https://channels.weixin.qq.com", href)
                    if "channels.weixin.qq.com" not in absolute:
                        continue
                    candidates.append({"text": text, "url": absolute})
                if candidates:
                    first = candidates[0]
                    post_url = first["url"]
                    post_id_match = re.search(r"(?:exportkey|objectid|feedid|id)=([^&#/?]+)", post_url)
                    post_id = post_id_match.group(1) if post_id_match else ""
                    return {
                        "post_url": post_url,
                        "platform_post_id": post_id,
                        "published_title": first.get("text") or title,
                        "publish_status": "published",
                        "link_extraction": {
                            "status": "found",
                            "method": "tencent_channels_post_list",
                            "message": "已从视频号内容管理列表回查到作品链接",
                            "attempts": 1,
                        },
                    }
                await page.wait_for_timeout(1000)
            return {
                "publish_status": "published",
                "published_title": title,
                "link_extraction": {
                    "status": "not_found",
                    "method": "tencent_channels_post_list",
                    "message": f"视频号作品链接回查超过 {LINK_LOOKUP_TIMEOUT_SECONDS} 秒，未找到可打开链接。",
                    "attempts": 1,
                    "timeout_seconds": LINK_LOOKUP_TIMEOUT_SECONDS,
                },
            }
        except Exception as exc:
            return {
                "publish_status": "published",
                "published_title": title,
                "link_extraction": {
                    "status": "not_found",
                    "method": "tencent_channels_post_list",
                    "message": f"视频号作品链接回查失败：{exc}",
                    "attempts": 1,
                    "timeout_seconds": LINK_LOOKUP_TIMEOUT_SECONDS,
                },
            }

    async def _fill_publish_draft(self, cdp_url: str, payload: TencentPublishPayload) -> dict[str, Any]:
        if not cdp_url:
            return {"success": False, "message": "真实浏览器未启用接管端口", "error_code": "cdp_unavailable"}
        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            return {"success": False, "message": f"Playwright CDP 不可用：{exc}", "error_code": "cdp_unavailable"}

        browser = None
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                pages = [page for page in context.pages if "channels.weixin.qq.com" in page.url]
                page = pages[0] if pages else await context.new_page()
                publish_url = self._publish_url(payload.mode)
                await page.goto(publish_url, wait_until="domcontentloaded", timeout=60000)
                target = await self._wait_publish_target(page, payload.mode)

                actions: list[dict[str, Any]] = []
                await self._upload_publish_files(target, payload, actions)
                await self._fill_title(target, payload.title, payload.mode, actions)
                await self._fill_description(target, payload, actions)
                publish_clicked = False
                link_result: dict[str, Any] = {}
                if payload.auto_publish:
                    required_ok = self._action_ok(actions, "fill_title")
                    required_ok = required_ok and (
                        self._action_ok(actions, "upload_images") if payload.mode == "note" else self._action_ok(actions, "upload_file")
                    )
                    if payload.mode == "note" and payload.desc.strip():
                        required_ok = required_ok and self._action_ok(actions, "fill_description")
                    if required_ok:
                        publish_clicked = await self._click_publish(target, actions)
                        if publish_clicked:
                            link_result = await self._lookup_published_post(page, payload.title)
                    else:
                        actions.append({
                            "action": "pre_publish_check",
                            "status": "needs_human",
                            "message": "标题、素材或正文未完整填入，已停止自动发表",
                        })

                screenshot = await page.screenshot(full_page=False)
                screenshot_path = ""
                try:
                    from szyg.data_path import DATA_DIR

                    artifact_dir = DATA_DIR / "computer_use" / "screenshots"
                    artifact_dir.mkdir(parents=True, exist_ok=True)
                    screenshot_path = str(artifact_dir / f"tencent_draft_{run_id_safe(payload.title)}.png")
                    Path(screenshot_path).write_bytes(screenshot)
                except Exception:
                    screenshot_path = ""

                draft_filled = self._action_ok(actions, "fill_title") and (
                    self._action_ok(actions, "upload_images") if payload.mode == "note" else self._action_ok(actions, "upload_file")
                )
                success = bool(payload.auto_publish and publish_clicked)
                if not payload.auto_publish and draft_filled:
                    message = "视频号必要信息已填写，请在视频号页面补充位置、链接、音乐等可选项后手动确认发表"
                    error_code = "manual_confirmation_required"
                elif publish_clicked:
                    message = "视频号内容已提交发表"
                    error_code = ""
                else:
                    message = "视频号草稿已填写，但发表按钮未就绪"
                    error_code = "publish_button_not_clicked"
                return {
                    "success": success,
                    "draft_filled": draft_filled,
                    "auto_publish": payload.auto_publish,
                    "manual_confirmation_required": bool(not payload.auto_publish and draft_filled),
                    "publish_clicked": publish_clicked,
                    "message": message,
                    "error_code": error_code,
                    "actions": actions,
                    "url": page.url,
                    "screenshot_path": screenshot_path,
                    **link_result,
                }
        except Exception as exc:
            return {"success": False, "message": str(exc), "error_code": "draft_fill_failed", "actions": []}

    async def open_publish(self, account: dict, payload: TencentPublishPayload) -> dict[str, Any]:
        publish_url = self._publish_url(payload.mode)
        launch = get_desktop_browser_session().launch(
            publish_url,
            profile_key=TENCENT_CHANNELS_PROFILE_KEY,
            no_proxy=True,
        )
        message = "已打开视频号发布页，正在自动填写并发表。" if payload.auto_publish else "已打开视频号发布页，正在填写必要信息。"
        kernel = get_execution_kernel()
        task_type = "publish_note" if payload.mode == "note" else "publish_video"
        input_data = {
            "account_id": account.get("id", ""),
            "account_label": account.get("nickname") or account.get("label") or "视频号",
            "title": payload.title,
            "desc": payload.desc,
            "tags": payload.tags,
            "file_path": payload.file_path,
            "asset_paths": payload.asset_paths,
            "mode": payload.mode,
            "publish_url": publish_url,
            "manual_handoff": False,
            "auto_publish": payload.auto_publish,
            "desktop_browser": {
                "profile_key": TENCENT_CHANNELS_PROFILE_KEY,
                "profile_dir": launch.profile_dir,
                "cdp_url": launch.cdp_url,
                "cdp_available": launch.cdp_available,
                "no_proxy": launch.no_proxy,
                "browser": launch.browser,
            },
        }
        run = kernel.create_run(
            task_type,
            self.platform,
            "desktop",
            input_data,
            title=payload.title or "视频号桌面发布",
            source_task_id=f"desktop:tencent:{account.get('id', '')}",
        )
        step = kernel.start_step(run["id"], "manual_handoff", "视频号桌面接管", "desktop", "open_real_browser")
        kernel.add_observation(
            run["id"],
            step["id"],
            "text",
            f"已通过真实桌面浏览器打开视频号发布页；CDP 可用：{bool(launch.cdp_available)}。",
        )
        kernel.finish_step(step, "success" if launch.ok else "failed", launch.message, error_code="" if launch.ok else "browser_launch_failed")
        draft_result = {"success": False, "message": "未执行自动填草稿"}
        if launch.ok and launch.cdp_available:
            draft_step = kernel.start_step(run["id"], "fill_draft", "填写视频号草稿", "desktop", "fill_draft")
            draft_result = await self._fill_publish_draft(launch.cdp_url, payload)
            artifact = draft_result.get("screenshot_path", "")
            if artifact:
                kernel.add_observation(run["id"], draft_step["id"], "screenshot", "视频号草稿填写后截图", artifact)
            else:
                kernel.add_observation(run["id"], draft_step["id"], "text", draft_result.get("message", "草稿填写完成"))
            kernel.finish_step(
                draft_step,
                "success" if draft_result.get("success") else "needs_human",
                draft_result.get("message", "视频号草稿填写结果已记录"),
                error_code="" if draft_result.get("success") else draft_result.get("error_code", "low_confidence"),
                artifact_path=artifact,
            )
        elif launch.ok:
            draft_step = kernel.start_step(run["id"], "fill_draft", "填写视频号草稿", "desktop", "fill_draft")
            draft_result = {"success": False, "message": "真实浏览器已打开，但 CDP 不可用，请人工填写草稿", "error_code": "cdp_unavailable"}
            kernel.add_observation(run["id"], draft_step["id"], "text", draft_result["message"])
            kernel.finish_step(draft_step, "needs_human", draft_result["message"], error_code="cdp_unavailable")
        final_message = draft_result.get("message") or message
        final_status = "success" if draft_result.get("success") else "needs_human"
        final_error_code = ""
        if final_status != "success":
            final_error_code = draft_result.get("error_code") or (
                "manual_confirmation_required" if draft_result.get("manual_confirmation_required") else "needs_human"
            )
        run = kernel.complete_run(
            run["id"],
            final_status,
            result={
                "publish_url": publish_url,
                "post_list_url": TENCENT_CHANNELS_MANAGE_URL,
                "message": final_message,
                "manual_handoff": final_status != "success",
                "desktop_browser": launch.to_dict(),
                "draft": draft_result,
                **{
                    key: draft_result.get(key)
                    for key in [
                        "post_url",
                        "platform_post_id",
                        "published_title",
                        "publish_status",
                        "link_extraction",
                    ]
                    if draft_result.get(key)
                },
            },
            error_code=final_error_code,
            error_message="" if final_status == "success" else final_message,
        )
        return {
            "ok": bool(launch.ok),
            "message": final_message if launch.ok else launch.error or launch.message,
            "url": publish_url,
            "launch": launch.to_dict(),
            "draft": draft_result,
            "task_id": run["id"],
            "execution_id": run["id"],
            "run": run,
        }


_assistant: TencentChannelsDesktopAssistant | None = None


def get_tencent_channels_desktop_assistant() -> TencentChannelsDesktopAssistant:
    global _assistant
    if _assistant is None:
        _assistant = TencentChannelsDesktopAssistant()
    return _assistant


def run_id_safe(value: str) -> str:
    text = "".join(ch for ch in (value or "draft") if ch.isalnum())[:24]
    return text or "draft"
