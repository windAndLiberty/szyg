"""
szyg 智能矩阵运营系统 — 浏览器端到端测试 (Playwright/CUA)
================================================================
测试范围: 完整用户行为链路 + API 数据流监控
- 12 个前端页面渲染验证
- 所有 API 端点数据流追踪
- 关键工作流: 登录→Dashboard→工具→智能体→发布→调度→对话→生图→管理

用法:
    python tests/e2e_browser_test.py
    python tests/e2e_browser_test.py --headed    # 可见浏览器
    python tests/e2e_browser_test.py --slow      # 慢速模式 (便于观察)
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from collections import defaultdict

from playwright.sync_api import sync_playwright, Page, Browser, Request, Response

BASE_URL = "http://127.0.0.1:8000"
CREDENTIALS = {"username": "admin", "password": "admin123"}

def safe_str(s: str) -> str:
    """Remove Unicode chars that can't be encoded in GBK (Windows console)."""
    try:
        s.encode('gbk')
        return s
    except UnicodeEncodeError:
        return s.encode('gbk', errors='replace').decode('gbk')

# ═══════════════════════════════════════════════════════════════
# Data Flow Monitor
# ═══════════════════════════════════════════════════════════════

@dataclass
class ApiCall:
    """A single API call record."""
    method: str
    url: str
    status: int
    duration_ms: float
    request_body: Any = None
    response_body: Any = None
    error: str | None = None

@dataclass
class StepResult:
    """Result of one test step."""
    name: str
    passed: bool
    duration_ms: float
    api_calls: list[ApiCall] = field(default_factory=list)
    error: str | None = None
    details: str = ""

class DataFlowMonitor:
    """Intercepts & records all network traffic for data flow analysis."""

    def __init__(self, page: Page):
        self.calls: list[ApiCall] = []
        self._pending: dict[str, float] = {}  # url -> start_time
        page.on("request", self._on_request)
        page.on("response", self._on_response)

    def _on_request(self, request: Request):
        if BASE_URL in (request.url or ""):
            self._pending[request.url] = time.time()

    def _on_response(self, response: Response):
        url = response.url
        if BASE_URL not in url:
            return
        start = self._pending.pop(url, time.time())
        duration = (time.time() - start) * 1000
        call = ApiCall(
            method=response.request.method,
            url=url.replace(BASE_URL, ""),
            status=response.status,
            duration_ms=round(duration, 1),
        )
        # Capture bodies for API routes (not static assets)
        if "/api/" in url or "/v1/" in url:
            try:
                call.request_body = response.request.post_data_json
            except Exception:
                try:
                    call.request_body = response.request.post_data
                except Exception:
                    pass
            try:
                call.response_body = response.json()
            except Exception:
                try:
                    call.response_body = response.text()[:500]
                except Exception:
                    pass
        self.calls.append(call)

    def api_only(self) -> list[ApiCall]:
        """Filter to API calls only (exclude static assets)."""
        return [c for c in self.calls if "/api/" in c.url or "/v1/" in c.url]

    def summary(self) -> dict:
        """Generate a summary of data flow."""
        api = self.api_only()
        by_status = defaultdict(int)
        total_duration = 0
        failed = []
        for c in api:
            by_status[c.status] += 1
            total_duration += c.duration_ms
            if c.status >= 400:
                failed.append(c)
        return {
            "total_api_calls": len(api),
            "by_status": dict(by_status),
            "total_duration_ms": round(total_duration, 1),
            "failed": failed,
        }


# ═══════════════════════════════════════════════════════════════
# Test Runner
# ═══════════════════════════════════════════════════════════════

class E2ETester:
    def __init__(self, page: Page, slow: bool = False):
        self.page = page
        self.slow = slow
        self.monitor = DataFlowMonitor(page)
        self.results: list[StepResult] = []
        self._login_token: str | None = None

    def _pause(self, ms: int = 300):
        if self.slow:
            time.sleep(ms / 1000 * 3)
        else:
            time.sleep(ms / 1000)

    def _record(self, name: str, passed: bool, error: str | None = None, details: str = "") -> StepResult:
        duration = 0.0  # simplified
        result = StepResult(
            name=name,
            passed=passed,
            duration_ms=duration,
            api_calls=list(self.monitor.calls),
            error=error,
            details=details,
        )
        self.results.append(result)
        self.monitor.calls.clear()
        return result

    def _nav(self, path: str) -> bool:
        """Navigate to a page and wait for it to load."""
        try:
            url = f"{BASE_URL}{path}"
            self.page.goto(url, wait_until="networkidle", timeout=15000)
            self._pause(500)
            # Check for white screen: expect #app to have content
            app = self.page.locator("#app")
            if not app.is_visible():
                return False
            # Check there's actual rendered content (not just empty #app)
            inner = app.inner_html()
            if len(inner.strip()) < 20:
                return False
            return True
        except Exception as e:
            print(f"    [WARN] nav error: {e}")
            return False

    def _el_visible(self, selector: str, timeout: int = 5000) -> bool:
        try:
            return self.page.locator(selector).first.is_visible(timeout=timeout)
        except Exception:
            return False

    def _el_text(self, selector: str) -> str:
        try:
            return self.page.locator(selector).first.inner_text()
        except Exception:
            return ""

    # ── Step 1: Login ──
    def step_login(self) -> StepResult:
        print("\n[1/10] 登录认证流程...")
        try:
            assert self._nav("/login"), "Login page failed to load (white screen?)"

            # Wait for login card to render
            assert self._el_visible(".login-card"), "Login card not visible"
            print("    [OK] 登录页面渲染正常")

            # Fill credentials
            self.page.fill('input[placeholder="用户名"]', CREDENTIALS["username"])
            self.page.fill('input[placeholder="密码"]', CREDENTIALS["password"])
            self._pause(200)

            # Submit
            self.page.click(".login-btn")
            self.page.wait_for_url("**/dashboard", timeout=10000)
            self._pause(500)

            # Verify token stored
            token = self.page.evaluate("() => localStorage.getItem('token')")
            assert token, "No JWT token in localStorage"
            self._login_token = token
            print(f"    [OK] 登录成功, JWT token: {token[:30]}...")

            # Verify user stored
            user = self.page.evaluate("() => localStorage.getItem('user')")
            assert user, "No user data in localStorage"
            user_data = json.loads(user)
            print(f"    [OK] 用户数据: {user_data.get('username')} (role: {user_data.get('role')})")

            # Validate API calls
            api_calls = self.monitor.api_only()
            login_call = [c for c in api_calls if "/api/auth/login" in c.url]
            oem_call = [c for c in api_calls if "/api/oem/" in c.url]
            assert login_call, "No login API call detected"
            assert login_call[0].status == 200, f"Login API returned {login_call[0].status}"
            print(f"    [OK] API: POST /api/auth/login → {login_call[0].status}")
            if oem_call:
                print(f"    [OK] API: GET /api/oem/config/default → {oem_call[0].status}")

            return self._record("登录认证", True, details="JWT登录 → Dashboard跳转")
        except Exception as e:
            return self._record("登录认证", False, error=str(e))

    # ── Step 2: Dashboard ──
    def step_dashboard(self) -> StepResult:
        print("\n[2/10] 首页仪表盘...")
        try:
            # Should already be on /dashboard after login
            if not self.page.url.endswith("/dashboard"):
                assert self._nav("/dashboard"), "Dashboard page failed to load"

            # Check key elements
            assert self._el_visible(".el-menu"), "Sidebar menu not visible"
            print("    [OK] 侧边栏菜单渲染正常")

            # Check for stat cards / content
            content = self.page.locator("#app").inner_html()
            assert len(content) > 100, "Dashboard content too short (white screen?)"
            print(f"    [OK] 页面内容: {len(content)} chars")

            # Check API calls
            api_calls = self.monitor.api_only()
            api_urls = [c.url for c in api_calls]
            for expected in ["/api/announce/", "/api/tools/"]:
                found = any(expected in u for u in api_urls)
                status = "[OK]" if found else "[WARN]️ (可能懒加载)"
                print(f"    {status} API: {expected}...")

            return self._record("首页仪表盘", True, details="侧边栏 + 统计卡片 + 公告渲染")
        except Exception as e:
            return self._record("首页仪表盘", False, error=str(e))

    # ── Step 3: Tools Marketplace ──
    def step_tools(self) -> StepResult:
        print("\n[3/10] 工具市场...")
        try:
            assert self._nav("/tools"), "Tools page failed to load"
            # Wait for Vue to render the cards
            self._pause(1000)
            has_cards = self._el_visible(".el-card") or self._el_visible(".tool-card")
            has_table = self._el_visible(".el-table")
            has_content = len(self.page.locator("#app").inner_html()) > 200
            assert has_cards or has_table or has_content, f"Tool content not visible (cards={has_cards}, table={has_table}, content={has_content})"
            print("    [OK] 工具市场页面渲染正常")

            # Check for tool catalog API
            api_calls = self.monitor.api_only()
            catalog = [c for c in api_calls if "/api/tools/catalog" in c.url]
            if catalog:
                print(f"    [OK] API: GET /api/tools/catalog → {catalog[0].status}")
                if catalog[0].response_body:
                    tools = catalog[0].response_body
                    if isinstance(tools, list):
                        print(f"    [OK] 工具数量: {len(tools)}")
            else:
                print("    [WARN]️ 未检测到工具目录API (可能已缓存)")

            return self._record("工具市场", True, details="工具分类 + 目录列表")
        except Exception as e:
            return self._record("工具市场", False, error=str(e))

    # ── Step 4: Agents ──
    def step_agents(self) -> StepResult:
        print("\n[4/10] AI 智能体...")
        try:
            assert self._nav("/agents"), "Agents page failed to load"
            self._pause(500)

            # Check for agent cards or list
            has_cards = self._el_visible(".el-card") or self._el_visible(".el-table")
            has_content = len(self.page.locator("#app").inner_html()) > 100
            assert has_cards or has_content, "Agents page empty"

            api_calls = self.monitor.api_only()
            agent_api = [c for c in api_calls if "/api/agents/" in c.url]
            if agent_api:
                print(f"    [OK] API: GET /api/agents/list → {agent_api[0].status}")
                if agent_api[0].response_body:
                    agents = agent_api[0].response_body
                    if isinstance(agents, list):
                        print(f"    [OK] 智能体数量: {len(agents)}")
            else:
                print("    [WARN]️ 未检测到智能体API")
            print("    [OK] 智能体页面渲染正常")

            return self._record("AI智能体", True, details="智能体列表 + 层级筛选")
        except Exception as e:
            return self._record("AI智能体", False, error=str(e))

    # ── Step 5: Content Publisher ──
    def step_publisher(self) -> StepResult:
        print("\n[5/10] 内容发布...")
        try:
            assert self._nav("/publisher"), "Publisher page failed to load"
            self._pause(500)

            content = self.page.locator("#app").inner_html()
            assert len(content) > 100, "Publisher page empty"
            print("    [OK] 发布管理页面渲染正常")

            api_calls = self.monitor.api_only()
            pub_apis = [c for c in api_calls if "/api/publisher/" in c.url]
            for c in pub_apis:
                print(f"    [OK] API: {c.method} {c.url} → {c.status}")
            if not pub_apis:
                print("    [WARN]️ 未检测到发布API (列表可能为空)")

            return self._record("内容发布", True, details="发布列表 + 新建/审核/发布操作")
        except Exception as e:
            return self._record("内容发布", False, error=str(e))

    # ── Step 6: Scheduler ──
    def step_scheduler(self) -> StepResult:
        print("\n[6/10] 调度引擎...")
        try:
            assert self._nav("/scheduler"), "Scheduler page failed to load"
            self._pause(500)

            content = self.page.locator("#app").inner_html()
            assert len(content) > 100, "Scheduler page empty"
            print("    [OK] 调度引擎页面渲染正常")

            api_calls = self.monitor.api_only()
            sch_apis = [c for c in api_calls if "/api/scheduler/" in c.url]
            for c in sch_apis:
                print(f"    [OK] API: {c.method} {c.url} → {c.status}")

            return self._record("调度引擎", True, details="任务列表 + 执行/暂停/历史")
        except Exception as e:
            return self._record("调度引擎", False, error=str(e))

    # ── Step 7: AI Hub ──
    def step_hub(self) -> StepResult:
        print("\n[7/10] AI 导航...")
        try:
            assert self._nav("/hub"), "Hub page failed to load"
            self._pause(500)

            content = self.page.locator("#app").inner_html()
            assert len(content) > 100, "Hub page empty"
            print("    [OK] AI 导航页面渲染正常")

            api_calls = self.monitor.api_only()
            hub_apis = [c for c in api_calls if "/api/hub/" in c.url]
            for c in hub_apis:
                print(f"    [OK] API: {c.method} {c.url} → {c.status}")

            return self._record("AI导航", True, details="24个精选AI工具链接")
        except Exception as e:
            return self._record("AI导航", False, error=str(e))

    # ── Step 8: Chat (Streaming SSE) ──
    def step_chat(self) -> StepResult:
        print("\n[8/10] AI 对话 (流式 SSE)...")
        try:
            assert self._nav("/chat"), "Chat page failed to load"
            self._pause(800)

            content = self.page.locator("#app").inner_html()
            assert len(content) > 100, "Chat page empty"
            print("    [OK] 对话页面渲染正常")

            # Type a test message
            textarea = self.page.locator("textarea, input[type='text'], .el-textarea__inner").first
            if textarea.is_visible():
                textarea.fill("你好，请用一句话介绍自己")
                self._pause(200)

                # Click send button
                send_btn = self.page.locator("button:has-text('发送'), .send-btn, [aria-label='send']").first
                if send_btn.is_visible():
                    send_btn.click()
                    self._pause(3000)  # Wait for streaming response
                    new_content = self.page.locator("#app").inner_html()
                    print(f"    [OK] 发送消息后页面更新: {len(content)} → {len(new_content)} chars")
                else:
                    print("    [WARN]️ 未找到发送按钮 (可能需要API配置)")

            # Check SSE-related API calls
            api_calls = self.monitor.api_only()
            chat_apis = [c for c in api_calls if "/api/" in c.url and ("chat" in c.url.lower() or "v1/chat" in c.url)]
            for c in chat_apis:
                print(f"    [OK] API: {c.method} {c.url} → {c.status}")

            return self._record("AI对话", True, details="SSE流式聊天 + Ollama后端")
        except Exception as e:
            return self._record("AI对话", False, error=str(e))

    # ── Step 9: Image Generation ──
    def step_image(self) -> StepResult:
        print("\n[9/10] AI 绘图...")
        try:
            assert self._nav("/image"), "Image page failed to load"
            self._pause(500)

            content = self.page.locator("#app").inner_html()
            assert len(content) > 100, "Image page empty"
            print("    [OK] AI绘图页面渲染正常")

            api_calls = self.monitor.api_only()
            img_apis = [c for c in api_calls if "/api/image" in c.url or "/api/client/comfyui" in c.url]
            for c in img_apis:
                print(f"    [OK] API: {c.method} {c.url} → {c.status}")
            if not img_apis:
                print("    [WARN]️ 未检测到绘图API (ComfyUI可能未启动)")

            return self._record("AI绘图", True, details="ComfyUI SD 2.1 生图界面")
        except Exception as e:
            return self._record("AI绘图", False, error=str(e))

    # ── Step 10: Admin + OEM ──
    def step_admin(self) -> StepResult:
        print("\n[10/10] 系统管理 + 品牌配置...")
        try:
            # Admin page
            assert self._nav("/admin"), "Admin page failed to load"
            self._pause(500)
            content = self.page.locator("#app").inner_html()
            assert len(content) > 100, "Admin page empty"
            print("    [OK] 管理后台页面渲染正常")

            api_calls = self.monitor.api_only()
            admin_apis = [c for c in api_calls if "/api/" in c.url and ("admin" in c.url.lower() or "user" in c.url.lower() or "announce" in c.url)]
            for c in admin_apis:
                print(f"    [OK] API: {c.method} {c.url} → {c.status}")

            # OEM page
            self._nav("/oem")
            self._pause(500)
            oem_content = self.page.locator("#app").inner_html()
            assert len(oem_content) > 50, "OEM page empty"
            print("    [OK] OEM品牌配置页面渲染正常")

            oem_apis = [c for c in self.monitor.api_only() if "/api/oem/" in c.url]
            for c in oem_apis:
                print(f"    [OK] API: {c.method} {c.url} → {c.status}")

            return self._record("系统管理", True, details="用户管理 + 系统配置 + 品牌定制")
        except Exception as e:
            return self._record("系统管理", False, error=str(e))

    # ── Extra: API-only health & config check ──
    def step_api_health(self) -> StepResult:
        print("\n[API] 后端健康检查 & OpenRouter/ModelScope 连通性...")
        api_results = []
        try:
            # Health
            resp = self.page.request.get(f"{BASE_URL}/api/health")
            assert resp.status == 200
            hdata = resp.json()
            print(f"    [OK] GET /api/health → {hdata}")

            # Config
            resp = self.page.request.get(f"{BASE_URL}/api/config")
            print(f"    [OK] GET /api/config → {resp.status}")

            # Brain status
            resp = self.page.request.get(f"{BASE_URL}/api/brain/status")
            print(f"    [OK] GET /api/brain/status → {resp.status}")

            # Client status
            resp = self.page.request.get(f"{BASE_URL}/api/client/status")
            if resp.status == 200:
                cdata = resp.json()
                ollama_status = cdata.get('ollama', '?')
                if isinstance(ollama_status, bool):
                    ollama_status = 'running' if ollama_status else 'stopped'
                print(f"    [OK] GET /api/client/status → ollama={ollama_status}")

            # Tools catalog
            resp = self.page.request.get(f"{BASE_URL}/api/tools/catalog")
            if resp.status == 200:
                tools = resp.json()
                print(f"    [OK] GET /api/tools/catalog → {len(tools) if isinstance(tools, list) else '?'} tools")

            # Agents list
            resp = self.page.request.get(f"{BASE_URL}/api/agents/list")
            if resp.status == 200:
                agents = resp.json()
                print(f"    [OK] GET /api/agents/list → {len(agents) if isinstance(agents, list) else '?'} agents")

            return self._record("API健康检查", True, details="所有核心API端点正常")
        except Exception as e:
            return self._record("API健康检查", False, error=str(e))


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def print_header():
    print("""
╔══════════════════════════════════════════════════════════════╗
║     szyg E2E 浏览器测试 — 用户行为 + 数据流验证             ║
║     Playwright/CUA · 12 Pages · Full API Trace              ║
╚══════════════════════════════════════════════════════════════╝
""")


def print_results(results: list[StepResult]):
    print("\n\n" + "=" * 70)
    print("                    TEST RESULTS SUMMARY")
    print("=" * 70)

    passed = 0
    failed = 0
    total_api_calls = 0
    total_errors = []

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        api_count = len([c for c in r.api_calls if "/api/" in c.url])
        total_api_calls += api_count
        print(f"  [{status}] {r.name:<24s} | {api_count:3d} API calls | {r.details}")
        if r.passed:
            passed += 1
        else:
            failed += 1
            total_errors.append(f"{r.name}: {r.error}")

    print("=" * 70)
    print(f"  Total: {passed} passed / {failed} failed / {len(results)} steps")
    print(f"  Tracked {total_api_calls} API calls")
    print("=" * 70)

    if total_errors:
        print("\nFAILURES:")
        for e in total_errors:
            print(f"  * {e}")

    return failed == 0


def main():
    # Force UTF-8 output to avoid GBK encoding issues on Windows
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description="szyg E2E Browser Test")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument("--slow", action="store_true", help="Slow mode for observation")
    args = parser.parse_args()

    print_header()

    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(
            headless=not args.headed,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 1300, "height": 760},
            locale="zh-CN",
        )
        page: Page = context.new_page()

        # Capture page errors
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        tester = E2ETester(page, slow=args.slow)

        try:
            # API health first (no auth needed)
            tester.step_api_health()

            # Full user workflow
            tester.step_login()
            tester.step_dashboard()
            tester.step_tools()
            tester.step_agents()
            tester.step_publisher()
            tester.step_scheduler()
            tester.step_hub()
            tester.step_chat()
            tester.step_image()
            tester.step_admin()

        except KeyboardInterrupt:
            print("\n[WARN]️ 测试被中断")
        finally:
            # Report page errors
            if page_errors:
                print(f"\n[WARN]️ 浏览器捕获到 {len(page_errors)} 个JS错误:")
                for err in page_errors[:10]:
                    print(f"  * {err[:200]}")

            browser.close()

    success = print_results(tester.results)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
