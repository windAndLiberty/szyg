"""Weibo desktop-assisted publishing workflow.

Weibo does not have a bundled social-auto-upload adapter in this project.
This module uses a real desktop browser profile and records the workflow
through ExecutionKernel so failures can be inspected and handed off.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from szyg.channel_accounts import patch_account, safe_token
from szyg.data_path import DATA_DIR
from szyg.execution_kernel import get_execution_kernel
from szyg.integrations.desktop_browser_session import get_desktop_browser_session

WEIBO_HOME_URL = "https://weibo.com"
WEIBO_ME_URL = "https://me.weibo.com"
WEIBO_PROFILE_PREFIX = "weibo_"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv"}


@dataclass
class WeiboPublishPayload:
    title: str = ""
    desc: str = ""
    tags: list[str] = field(default_factory=list)
    file_path: str = ""
    asset_paths: list[str] = field(default_factory=list)
    mode: str = "note"
    auto_publish: bool = True


def weibo_profile_key(account_id: str) -> str:
    return f"{WEIBO_PROFILE_PREFIX}{safe_token(account_id or 'default')}"


def _screenshot_path(prefix: str) -> Path:
    directory = DATA_DIR / "computer_use" / "screenshots"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{prefix}_{safe_token(str(Path().absolute().name))}_{Path(__file__).stat().st_mtime_ns}.png"


def _run_id_safe(value: str) -> str:
    text = "".join(ch for ch in (value or "weibo") if ch.isalnum())[:24]
    return text or "weibo"


class WeiboDesktopPublisher:
    platform = "weibo"

    def open_login(self, account: dict) -> dict[str, Any]:
        profile_key = weibo_profile_key(account.get("id", "weibo_default"))
        launch = get_desktop_browser_session().launch(
            WEIBO_HOME_URL,
            profile_key=profile_key,
            no_proxy=True,
        )
        return {
            **launch.to_dict(),
            "login_url": WEIBO_HOME_URL,
            "desktop_assist": True,
            "profile_key": profile_key,
        }

    def _existing_paths(self, paths: list[str], extensions: set[str]) -> list[str]:
        result: list[str] = []
        for raw_path in paths:
            path = Path(raw_path).expanduser()
            if path.exists() and path.suffix.lower() in extensions:
                result.append(str(path))
        return result

    def _image_paths(self, payload: WeiboPublishPayload) -> list[str]:
        return self._existing_paths(payload.asset_paths, IMAGE_EXTENSIONS)

    def _video_path(self, payload: WeiboPublishPayload) -> str:
        if payload.file_path:
            path = Path(payload.file_path).expanduser()
            if path.exists() and path.suffix.lower() in VIDEO_EXTENSIONS:
                return str(path)
        videos = self._existing_paths(payload.asset_paths, VIDEO_EXTENSIONS)
        return videos[0] if videos else ""

    def _compose_text(self, payload: WeiboPublishPayload) -> str:
        parts = []
        if payload.title.strip():
            parts.append(payload.title.strip())
        if payload.desc.strip():
            parts.append(payload.desc.strip())
        tag_text = " ".join(f"#{tag.strip().lstrip('#')}#" for tag in payload.tags if tag.strip())
        if tag_text:
            parts.append(tag_text)
        return "\n\n".join(parts).strip()

    async def _ensure_publish_page(self, page: Any) -> dict[str, Any]:
        candidates = [WEIBO_HOME_URL, WEIBO_ME_URL]
        for url in candidates:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3500)
            state = await page.evaluate(
                """() => {
                  const text = document.body ? document.body.innerText : '';
                  const editors = Array.from(document.querySelectorAll('textarea,[contenteditable="true"],div[role="textbox"]'));
                  const uploaders = Array.from(document.querySelectorAll('input[type="file"],button,a,div,span')).filter((el) => {
                    const value = (el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim();
                    return /图片|视频|照片|发布|发微博/.test(value);
                  });
                  return {
                    url: location.href,
                    loginRequired: /登录|扫码|验证码|安全验证/.test(text) && !/发微博|有什么新鲜事/.test(text),
                    editorCount: editors.length,
                    uploaderCount: uploaders.length,
                    text: text.slice(0, 4000),
                  };
                }"""
            )
            if state.get("loginRequired"):
                return {"ok": False, "error_code": "login_expired", "message": "需要重新登录微博", "url": state.get("url")}
            if int(state.get("editorCount") or 0) > 0:
                return {"ok": True, "url": state.get("url"), "state": state}
        return {"ok": False, "error_code": "platform_changed", "message": "未找到微博发布输入区"}

    async def _fill_text(self, page: Any, text: str, actions: list[dict[str, Any]]) -> bool:
        if not text:
            actions.append({"action": "fill_text", "status": "failed", "message": "发布正文为空"})
            return False
        result = await page.evaluate(
            """(value) => {
              const selectors = [
                'textarea[placeholder*="新鲜事"]',
                'textarea',
                '[contenteditable="true"]',
                'div[role="textbox"]'
              ];
              const setInputValue = (el, nextValue) => {
                if ('value' in el) {
                  const prototype = Object.getPrototypeOf(el);
                  const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value');
                  if (descriptor && descriptor.set) descriptor.set.call(el, nextValue);
                  else el.value = nextValue;
                } else {
                  el.innerText = nextValue;
                  el.textContent = nextValue;
                }
                el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: nextValue }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
              };
              for (const selector of selectors) {
                const el = document.querySelector(selector);
                if (!el) continue;
                el.focus();
                setInputValue(el, value);
                return { ok: true, selector };
              }
              return { ok: false };
            }""",
            text,
        )
        ok = bool(result and result.get("ok"))
        actions.append({
            "action": "fill_text",
            "status": "success" if ok else "failed",
            "selector": result.get("selector") if result else "",
            "message": "微博正文已填写" if ok else "未找到微博正文输入区",
        })
        return ok

    async def _upload_media(self, page: Any, payload: WeiboPublishPayload, actions: list[dict[str, Any]]) -> bool:
        if payload.mode == "video":
            files = [self._video_path(payload)]
            files = [item for item in files if item]
            selector_hint = "video"
            action = "upload_video"
        else:
            files = self._image_paths(payload)
            selector_hint = "image"
            action = "upload_images"
        if not files:
            actions.append({"action": action, "status": "failed", "message": "未找到可上传的媒体文件"})
            return False

        selectors = [
            'input[type="file"][accept*="image"]' if selector_hint == "image" else 'input[type="file"][accept*="video"]',
            'input[type="file"]',
        ]
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count():
                    await locator.set_input_files(files, timeout=15000)
                    actions.append({"action": action, "status": "success", "count": len(files), "selector": selector})
                    await page.wait_for_timeout(3500)
                    return True
            except Exception as exc:
                actions.append({"action": f"{action}_input", "status": "failed", "message": str(exc), "selector": selector})

        button_re = "视频" if payload.mode == "video" else "图片|照片"
        try:
            async with page.expect_file_chooser(timeout=12000) as chooser_info:
                await page.get_by_text(re.compile(button_re)).first.click(timeout=10000)
            chooser = await chooser_info.value
            await chooser.set_files(files)
            actions.append({"action": action, "status": "success", "count": len(files), "selector": "visible_upload_button"})
            await page.wait_for_timeout(3500)
            return True
        except Exception as exc:
            actions.append({"action": action, "status": "needs_human", "message": f"未找到可用上传入口：{exc}"})
            return False

    async def _click_publish(self, page: Any, actions: list[dict[str, Any]]) -> bool:
        try:
            await page.wait_for_function(
                """() => Array.from(document.querySelectorAll('button,a,div,span')).some((el) => {
                  const text = (el.innerText || el.textContent || '').trim();
                  const className = String(el.className || '');
                  return /^(发布|发表|发送)$/.test(text) && !className.includes('disabled') && !el.disabled;
                })""",
                timeout=120000,
            )
            point = await page.evaluate(
                """() => {
                  const el = Array.from(document.querySelectorAll('button,a,div,span')).find((item) => {
                    const text = (item.innerText || item.textContent || '').trim();
                    const className = String(item.className || '');
                    return /^(发布|发表|发送)$/.test(text) && !className.includes('disabled') && !item.disabled;
                  });
                  if (!el) return null;
                  el.scrollIntoView({ block: 'center', inline: 'center' });
                  const rect = el.getBoundingClientRect();
                  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, text: (el.innerText || el.textContent || '').trim() };
                }"""
            )
            if not point:
                actions.append({"action": "click_publish", "status": "needs_human", "message": "未找到发布按钮"})
                return False
            await page.mouse.click(float(point["x"]), float(point["y"]))
            actions.append({"action": "click_publish", "status": "success", "message": f"已点击{point.get('text') or '发布'}按钮"})
            await page.wait_for_timeout(3500)
            return await self._verify_submitted(page)
        except Exception as exc:
            actions.append({"action": "click_publish", "status": "needs_human", "message": f"发布按钮不可确认：{exc}"})
            return False

    async def _verify_submitted(self, page: Any) -> bool:
        patterns = re.compile(r"(发布成功|发表成功|已发布|发送成功|审核中|发布中)")
        for _ in range(10):
            try:
                state = await page.evaluate(
                    """() => {
                      const text = document.body ? document.body.innerText : '';
                      const editorText = Array.from(document.querySelectorAll('textarea,[contenteditable="true"],div[role="textbox"]'))
                        .map((el) => el.value || el.innerText || el.textContent || '')
                        .join('\\n')
                        .trim();
                      return { text: text.slice(0, 6000), editorText };
                    }"""
                )
                if patterns.search(str(state.get("text") or "")):
                    return True
                if not str(state.get("editorText") or "").strip():
                    return True
            except Exception:
                pass
            await page.wait_for_timeout(1000)
        return False

    async def _publish_with_cdp(self, cdp_url: str, payload: WeiboPublishPayload) -> dict[str, Any]:
        if not cdp_url:
            return {"success": False, "message": "真实浏览器未启用接管端口", "error_code": "cdp_unavailable"}
        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            return {"success": False, "message": f"Playwright CDP 不可用：{exc}", "error_code": "cdp_unavailable"}

        actions: list[dict[str, Any]] = []
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                pages = [page for page in context.pages if "weibo.com" in page.url]
                page = pages[0] if pages else await context.new_page()
                target = await self._ensure_publish_page(page)
                if not target.get("ok"):
                    return {"success": False, "message": target.get("message", "微博页面不可用"), "error_code": target.get("error_code", "platform_changed"), "actions": actions}
                text_ok = await self._fill_text(page, self._compose_text(payload), actions)
                media_ok = await self._upload_media(page, payload, actions)
                publish_ok = False
                if text_ok and media_ok and payload.auto_publish:
                    publish_ok = await self._click_publish(page, actions)
                screenshot_path = DATA_DIR / "computer_use" / "screenshots" / f"weibo_{_run_id_safe(payload.title)}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    await page.screenshot(path=str(screenshot_path), full_page=False)
                except Exception:
                    screenshot_path = Path("")
                if publish_ok:
                    return {
                        "success": True,
                        "message": "微博内容已提交发布",
                        "publish_status": "published",
                        "actions": actions,
                        "screenshot_path": str(screenshot_path) if screenshot_path else "",
                        "url": page.url,
                    }
                return {
                    "success": False,
                    "message": "微博内容未能确认发布，请人工检查页面",
                    "error_code": "verification_uncertain",
                    "actions": actions,
                    "screenshot_path": str(screenshot_path) if screenshot_path else "",
                    "url": page.url,
                }
        except Exception as exc:
            return {"success": False, "message": str(exc), "error_code": "weibo_desktop_publish_failed", "actions": actions}

    async def publish(self, account: dict, payload: WeiboPublishPayload) -> dict[str, Any]:
        profile_key = weibo_profile_key(account.get("id", "weibo_default"))
        launch = get_desktop_browser_session().launch(
            WEIBO_HOME_URL,
            profile_key=profile_key,
            no_proxy=True,
        )
        kernel = get_execution_kernel()
        task_type = "publish_video" if payload.mode == "video" else "publish_note"
        input_data = {
            "account_id": account.get("id", ""),
            "account_label": account.get("nickname") or account.get("label") or "微博",
            "title": payload.title,
            "desc": payload.desc,
            "tags": payload.tags,
            "file_path": payload.file_path,
            "asset_paths": payload.asset_paths,
            "image_paths": payload.asset_paths,
            "mode": payload.mode,
            "auto_publish": payload.auto_publish,
            "desktop_browser": launch.to_dict(),
        }
        run = kernel.create_run(
            task_type,
            self.platform,
            "desktop",
            input_data,
            title=payload.title or "微博桌面发布",
            source_task_id=f"desktop:weibo:{account.get('id', '')}",
        )

        step = kernel.start_step(run["id"], "open_real_browser", "打开微博真实浏览器", "desktop", "open_real_browser")
        kernel.add_observation(run["id"], step["id"], "text", launch.message)
        kernel.finish_step(step, "success" if launch.ok else "failed", launch.message, error_code="" if launch.ok else "browser_launch_failed")

        result = {"success": False, "message": launch.error or launch.message, "error_code": "browser_launch_failed"}
        if launch.ok and launch.cdp_available:
            publish_step = kernel.start_step(run["id"], "desktop_publish", "微博桌面发布", "desktop", "desktop_publish")
            result = await self._publish_with_cdp(launch.cdp_url, payload)
            artifact = result.get("screenshot_path", "")
            if artifact:
                kernel.add_observation(run["id"], publish_step["id"], "screenshot", "微博发布执行后截图", artifact)
            else:
                kernel.add_observation(run["id"], publish_step["id"], "text", result.get("message", "微博发布执行完成"))
            kernel.finish_step(
                publish_step,
                "success" if result.get("success") else "needs_human",
                result.get("message", "微博发布结果已记录"),
                error_code="" if result.get("success") else result.get("error_code", "needs_human"),
                artifact_path=artifact,
            )
        elif launch.ok:
            result = {"success": False, "message": "真实浏览器已打开，但接管端口不可用，请人工确认微博页面", "error_code": "cdp_unavailable"}

        final_status = "success" if result.get("success") else "needs_human"
        error_code = "" if final_status == "success" else result.get("error_code", "needs_human")
        completed = kernel.complete_run(
            run["id"],
            final_status,
            result={
                "message": result.get("message", ""),
                "desktop_browser": launch.to_dict(),
                "draft": result,
                "publish_status": result.get("publish_status", ""),
                "post_list_url": account.get("profile_url") or WEIBO_HOME_URL,
                "profile_url": account.get("profile_url") or WEIBO_HOME_URL,
                "published_title": payload.title,
            },
            error_code=error_code,
            error_message="" if final_status == "success" else result.get("message", ""),
        )
        if final_status == "success" and account.get("id"):
            try:
                patch_account(account["id"], last_publish_at=completed.get("finished_at", ""))
            except Exception:
                pass
        return {
            "ok": bool(launch.ok),
            "message": result.get("message", launch.message),
            "task_id": completed["id"],
            "execution_id": completed["id"],
            "run": completed,
            "draft": result,
            "launch": launch.to_dict(),
        }


_publisher: WeiboDesktopPublisher | None = None


def get_weibo_desktop_publisher() -> WeiboDesktopPublisher:
    global _publisher
    if _publisher is None:
        _publisher = WeiboDesktopPublisher()
    return _publisher
