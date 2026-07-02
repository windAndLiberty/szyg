# 抖音搜索集成方案 — 开源项目评估与集成规范

> 本文件评估 GitHub 上成熟的抖音爬虫开源项目，定义集成方案供 Elite_Coder 执行。
> 涉及源码：`server/szyg/integrations/acquisition_adapters.py`、`server/szyg/mcp_servers/acquisition_mcp.py`

---

## 1. 候选项目评估

### 1.0 NanmiCoder/MediaCrawler ⭐⭐⭐ 最终推荐

| 维度 | 评估 |
|------|------|
| **Stars** | 54K+（社区最大） |
| **协议** | 开源版有非商业使用限制（CC BY-NC-SA 4.0 声明），Pro 版付费 |
| **平台覆盖** | 小红书、抖音、快手、B站、微博、贴吧、知乎（7 平台全覆盖） |
| **功能** | 关键词搜索、指定帖子爬取、二级评论、创作者主页、登录态缓存、IP 代理池、词云 |
| **技术栈** | Python + Playwright + httpx + uv（与本项目技术栈高度一致） |
| **签名方案** | **无需 JS 逆向** — 利用 Playwright 浏览器上下文通过 JS 表达式获取 a_bogus |
| **CDP 模式** | ✅ 支持连接用户已有 Chrome 浏览器，复用登录态/Cookie/扩展，降低风控风险 |
| **Python 版本** | 兼容 3.12（使用 uv sync 管理依赖） |
| **活跃度** | 持续更新，2026 年仍活跃 |
| **WebUI** | 内置 FastAPI WebUI + WebSocket 实时日志 |

**核心优势**：
- **签名方案最稳健**：不依赖逆向 JS 算法，直接在 Playwright 浏览器上下文中执行 `window.bdms.init._v[2].p[42]` 获取 a_bogus，抖音更新签名算法时无需同步维护
- **7 平台全覆盖**：与本项目需要支持的抖音、小红书、快手、B站完全吻合
- **架构成熟**：工厂模式（CrawlerFactory）+ 模板方法（AbstractCrawler）+ 策略模式（StoreFactory），代码质量高
- **CDP 模式**：连接用户已有 Chrome，复用登录态，与本项目 `SessionManager` 理念一致
- **uv 包管理**：与本项目使用相同的包管理工具

**抖音搜索 API 实现**（源码 `media_platform/douyin/client.py`）：

```python
# 搜索端点
GET /aweme/v1/web/general/search/single/

# 搜索参数
query_params = {
    'search_channel': 'aweme_general',
    'enable_history': '1',
    'keyword': keyword,
    'search_source': 'tab_search',
    'query_correct_type': '1',
    'is_filter_search': '0',
    'from_group_id': '7378810571505847586',
    'offset': offset,
    'count': '15',
    'need_filter_settings': '1',
    'list_type': 'multi',
    'search_id': search_id,
}
# 排序/时间筛选
if sort_type != GENERAL or publish_time != UNLIMITED:
    query_params["filter_selected"] = json.dumps({
        "sort_type": str(sort_type.value),
        "publish_time": str(publish_time.value)
    })
    query_params["is_filter_search"] = 1

# 签名：搜索接口不需要 a_bogus（源码中 if "/v1/web/general/search" not in uri 才签名）
# 其他接口（详情、评论）需要 a_bogus
```

**签名实现**（源码 `media_platform/douyin/help.py`）：

```python
# 方式 1: execjs + libs/douyin.js（离线签名）
douyin_sign_obj = execjs.compile(open('libs/douyin.js').read())
def get_a_bogus_from_js(url, params, user_agent):
    sign_js_name = "sign_datail"  # or "sign_reply" for comments
    return douyin_sign_obj.call(sign_js_name, params, user_agent)

# 方式 2: Playwright page.evaluate（浏览器内签名，更稳健但已标注失效）
async def get_a_bogus_from_playright(params, post_data, user_agent, page):
    a_bogus = await page.evaluate(
        "([params, post_data, ua]) => window.bdms.init._v[2].p[42].apply(null, [0, 1, 8, params, post_data, ua])",
        [params, post_data, user_agent]
    )
    return a_bogus
```

**项目结构**：
```
MediaCrawler/
├── main.py                    # 入口 + CrawlerFactory
├── config/                    # 配置（base + per-platform）
├── base/                      # 抽象基类（Crawler, Login, Store, Client）
├── media_platform/
│   ├── douyin/
│   │   ├── client.py          # API 客户端（httpx + 签名）
│   │   ├── core.py            # 爬虫编排（Playwright + 搜索/详情/评论流程）
│   │   ├── login.py           # 登录逻辑
│   │   ├── field.py           # 枚举定义（SearchChannelType, SearchSortType 等）
│   │   └── help.py            # a_bogus 签名工具
│   ├── xhs/                   # 小红书（同构）
│   ├── kuaishou/              # 快手（同构 + graphql.py）
│   └── bilibili/              # B站
├── store/                     # 存储实现（json/csv/db/mongodb 等）
├── libs/                      # JS 签名文件（douyin.js, stealth.min.js）
├── tools/                     # 共享工具（浏览器、文件、签名）
└── api/                       # FastAPI WebUI
```

**风险**：
- 开源版声明非商业用途（需评估合规性）
- 搜索接口本身不需要 a_bogus 签名，但详情/评论接口需要
- Playwright 依赖意味着仍需浏览器（但 CDP 模式连接已有 Chrome，资源开销小）

### 1.1 hhy5562877/douyin_mcp

| 维度 | 评估 |
|------|------|
| **协议** | MIT |
| **功能** | 8 个工具：search_videos、get_video_detail、get_video_comments、get_sub_comments、get_user_info、get_user_posts、get_homefeed、check_login_status |
| **搜索能力** | ✅ 关键词搜索 + 排序(sort_type) + 数量控制(count) |
| **技术栈** | Python + py_mini_racer (V8) + httpx，纯 API 直调，无浏览器依赖 |
| **签名** | 内置 a_bogus 本地签名（py_mini_racer 加载 douyin.js），与本项目 `DouyinSigner` 机制一致 |
| **认证** | cookies.txt 文件（单行 Cookie 字符串），本项目 `SessionManager` 已有 storage_state 可提取 |
| **Python 版本** | 要求 3.14+（需确认本项目兼容性） |
| **活跃度** | 2026 年活跃开发 |
| **MCP 协议** | ✅ 原生 MCP Server，可直接作为子进程挂载 |

**优势**：
- 功能最完整，搜索/评论/用户信息/推荐流全覆盖
- 纯 API 直调，速度快（<1s），无需启动浏览器
- 签名机制与本项目已有的 `DouyinSigner` 架构一致
- 原生 MCP 协议，可无缝挂载到 Hermes 内核

**风险**：
- Python 3.14+ 要求较高，需验证本项目 Python 版本
- 签名算法依赖 JS 文件，抖音更新签名时需同步更新
- Cookie 过期需重新获取（本项目 SessionManager 已有自动管理）

### 1.2 BACH-AI-Tools/bachai-douyin-api-new

| 维度 | 评估 |
|------|------|
| **协议** | 未明确 |
| **功能** | 搜索视频、用户资料、帖子、评论、音乐、挑战、直播、热榜 |
| **安装** | `uvx --from bach-douyin_api_new bach_douyin_api_new` |
| **认证** | 需要 API_KEY（付费第三方 API 服务） |
| **MCP 协议** | ✅ 原生 MCP Server |

**结论**：❌ 不推荐。依赖付费 API_KEY，不是直接调用抖音 API，增加外部依赖和成本。

### 1.3 yzfly/douyin-mcp-server

| 维度 | 评估 |
|------|------|
| **状态** | ⚠️ 已归档（2026-04-03） |
| **功能** | 仅提取无水印视频链接和文案，无搜索功能 |

**结论**：❌ 不适用。已归档且无搜索功能。

### 1.4 kk520879/undoom-douyin-data-analysis

| 维度 | 评估 |
|------|------|
| **功能** | search_douyin_videos、search_douyin_users、互动分析、关键词分析 |
| **技术** | BeautifulSoup 解析 HTML（非 API 直调） |
| **MCP 协议** | ✅ MCP Server，可通过 uvx 安装 |

**结论**：❌ 不推荐。用 BeautifulSoup 解析 HTML，本质还是页面抓取，不够稳定。

### 1.5 Youhai020616/douyin (dy-cli)

| 维度 | 评估 |
|------|------|
| **协议** | MIT |
| **功能** | 搜索、下载、发布、热榜、直播、互动、分析 |
| **搜索** | ✅ API 直调（httpx + 逆向 API），支持排序/时间/类型筛选 |
| **技术** | 双引擎：API Client（搜索/下载）+ Playwright（发布/登录） |
| **MCP 协议** | ❌ 不是 MCP Server，是 CLI 工具 |

**结论**：⭐ 代码参考价值极高（API 参数构造、签名处理），但不能直接作为 MCP 集成。可作为代码参考来源。

---

## 2. 推荐方案：集成 MediaCrawler

> MediaCrawler 54K+ Stars，社区最大，持续更新，7 平台全覆盖，技术栈与本项目高度一致（Python + Playwright + httpx + uv）。
> 其他候选项目：`douyin_mcp`（Python 3.14+ 不兼容）、`dy-cli`（CLI 工具非 MCP）、`yzfly`（已归档）均不适用。

### 2.1 集成策略：Git Submodule + 桥接层

```
szyg/
├── server/szyg/
│   ├── integrations/
│   │   ├── acquisition_adapters.py     # 现有浏览器方案（保留为 fallback）
│   │   └── mediacrawler_bridge.py      # 新增：MediaCrawler 桥接层
│   ├── mcp_servers/
│   │   └── acquisition_mcp.py          # 现有 MCP（内部调用桥接层）
│   └── platforms/
│       └── session_manager.py          # 现有 Cookie 管理
└── vendor/
    └── MediaCrawler/                   # Git Submodule
        ├── media_platform/douyin/      # 抖音爬虫
        ├── media_platform/xhs/         # 小红书爬虫
        ├── media_platform/kuaishou/    # 快手爬虫
        ├── libs/douyin.js              # 签名 JS
        └── ...
```

### 2.2 桥接层设计

新建文件：`server/szyg/integrations/mediacrawler_bridge.py`

```
MediaCrawlerBridge 类
  ├── __init__()
  │   └── 初始化 MediaCrawler 的 DouYinClient，注入本项目 SessionManager 的 Cookie
  │
  ├── _prepare_browser_context()
  │   ├── 从 SessionManager 加载抖音 storage_state
  │   ├── 用 Playwright 创建 BrowserContext（复用已有 BrowserPool）
  │   └── 返回 (browser_context, page) — MediaCrawler 需要 page 来获取 UA
  │
  ├── async search_douyin(keyword, limit, sort_type, publish_time) → list[dict]
  │   ├── 调用 MediaCrawler DouYinClient.search_info_by_keyword()
  │   │   端点: /aweme/v1/web/general/search/single/
  │   │   参数: keyword, search_channel, sort_type, publish_time, offset, count
  │   ├── 解析响应: data[].aweme_info
  │   └── 经 _normalize_search_result() 统一格式后返回
  │
  ├── async get_douyin_detail(aweme_id) → dict
  │   └── 调用 MediaCrawler DouYinClient.get_video_by_id()
  │
  ├── async get_douyin_comments(aweme_id, count) → list[dict]
  │   └── 调用 MediaCrawler DouYinClient.get_video_comments()
  │
  ├── async search_xhs(keyword, limit) → list[dict]
  │   └── 调用 MediaCrawler XhsClient search_note_by_keyword()
  │
  ├── async search_kuaishou(keyword, limit) → list[dict]
  │   └── 调用 MediaCrawler KuaishouClient search_info_by_keyword()
  │
  └── async search_bilibili(keyword, limit) → list[dict]
      └── 调用 MediaCrawler BilibiliClient search_video_by_keyword()
```

### 2.3 搜索 API 参数（来自 MediaCrawler 源码）

**搜索端点**：
```
GET https://www.douyin.com/aweme/v1/web/general/search/single/
```

**搜索参数**（来自 `media_platform/douyin/client.py`）：

| 参数 | 类型 | 说明 |
|------|------|------|
| `keyword` | str | 搜索关键词 |
| `search_channel` | str | 固定 `aweme_general` |
| `sort_type` | int | 0=综合, 1=最多点赞, 2=最新发布 |
| `publish_time` | int | 0=不限, 1=一天内, 7=一周内, 180=半年内 |
| `offset` | int | 分页偏移，从 0 开始 |
| `count` | int | 每页数量，建议 15-20 |
| `search_source` | str | 固定 `normal_search` |
| `is_filter_search` | int | 0=不过滤 |
| `query_correct_type` | int | 固定 1 |
| `is_filter` | int | 固定 0 |
| `device_platform` | str | 固定 `webapp` |
| `aid` | str | 固定 `6383` |
| `channel` | str | 固定 `channel_pc_web` |
| `pc_client_type` | str | 固定 `1` |
| `version_code` | str | 固定 `170400` |
| `version_name` | str | 固定 `17.4.0` |
| `cookie_enabled` | str | 固定 `true` |
| `screen_width` | str | 固定 `1920` |
| `screen_height` | str | 固定 `1080` |
| `browser_language` | str | 固定 `zh-CN` |
| `browser_platform` | str | 固定 `Win32` |
| `browser_name` | str | 固定 `Mozilla` |
| `browser_version` | str | UA 版本 |
| `browser_online` | str | 固定 `true` |
| `engine_name` | str | 固定 `Blink` |
| `engine_version` | str | 固定 `99.0.4844.84` |
| `os_name` | str | 固定 `Windows` |
| `os_version` | str | 固定 `10` |
| `cpu_core_num` | str | 固定 `8` |
| `device_memory` | str | 固定 `8` |
| `platform` | str | 固定 `PC` |
| `downlink` | str | 固定 `10` |
| `effective_type` | str | 固定 `4g` |
| `round_trip_time` | str | 固定 `100` |

签名后自动追加：`a_bogus`、`x_bogus`、`msToken`

### 2.4 响应解析

```json
{
  "status_code": 0,
  "data": [
    {
      "aweme_info": {
        "aweme_id": "7xxx",
        "desc": "视频描述",
        "author": { "nickname": "作者", "follower_count": 12345 },
        "statistics": { "digg_count": 500, "comment_count": 30, "share_count": 10 },
        "video": { "cover": { "url_list": ["https://..."] } },
        "create_time": 1719000000
      }
    }
  ]
}
```

提取逻辑与现有 `_extract_from_api_data()` 一致（已在 `_search_douyin` 中实现）。

### 2.5 双模式策略

```
搜索请求 (acquisition_adapters.py → _search_douyin)
  ├─ 优先：MediaCrawler 桥接模式 (mediacrawler_bridge.py)
  │   ├─ 从 SessionManager 加载 Cookie
  │   ├<arg_value> 用 DouyinSigner 生成签名参数
  │   ├─ httpx.AsyncClient GET 请求
  │   ├─ 解析 JSON → _normalize_search_result
  │   └─ 返回结果
  │
  └─ Fallback：浏览器拦截模式 (现有 _search_douyin 逻辑)
      └─ API 直调失败/无 Cookie/签名错误时自动降级
```

### 2.6 Cookie 桥接

MediaCrawler 的 `DouYinClient` 需要从 Playwright BrowserContext 获取 Cookie。
本项目 `SessionManager` 保存的 `storage_state` 可直接用于创建 BrowserContext：

```python
# 从 SessionManager 加载
state = session_manager.load(Platform.DOUYIN)
# 创建 BrowserContext（复用 BrowserPool）
context = await browser_pool.new_context(storage_state=state)
# MediaCrawler 从 context 提取 Cookie
cookie_str, cookie_dict = await convert_browser_context_cookies(context, urls=[
    "https://douyin.com",
    "https://www.douyin.com",
    "https://creator.douyin.com",
])
```

### 2.7 请求头（来自 MediaCrawler 源码 `core.py`）

```python
headers = {
    "User-Agent": await page.evaluate("() => navigator.userAgent"),
    "Cookie": cookie_str,
    "Host": "www.douyin.com",
    "Origin": "https://www.douyin.com/",
    "Referer": "https://www.douyin.com/",
    "Content-Type": "application/json;charset=UTF-8",
}
# 搜索时更新 Referer
headers["Referer"] = f"https://www.douyin.com/search/{keyword}?type=general"
```

### 2.8 签名说明

**关键发现**（来自 MediaCrawler 源码 `client.py`）：

```python
# 搜索接口不需要 a_bogus 签名
if "/v1/web/general/search" not in uri:
    a_bogus = await get_a_bogus(uri, query_string, post_data, headers["User-Agent"], page)
    params["a_bogus"] = a_bogus
```

- **搜索**：不需要 a_bogus，直接 httpx GET 即可
- **详情/评论**：需要 a_bogus，通过 `libs/douyin.js` + `execjs` 生成
- 这意味着搜索功能可以完全脱离浏览器签名，仅需 Cookie 即可工作

---

## 3. Elite_Coder 执行清单

### 3.1 前置准备

```bash
# 1. 添加 MediaCrawler 为 Git Submodule
git submodule add https://github.com/NanmiCoder/MediaCrawler.git vendor/MediaCrawler

# 2. 安装 MediaCrawler 依赖（在 submodule 目录内）
cd vendor/MediaCrawler
uv sync
uv run playwright install

# 3. 本项目可能需要新增依赖
uv add execjs  # MediaCrawler 签名依赖
```

### 3.2 前置验证

- [ ] 确认 `vendor/MediaCrawler` 可正常 `uv sync` 和 `uv run main.py --platform dy --type search`
- [ ] 确认 `SessionManager` 中抖音 storage_state 是否存在有效 Cookie
- [ ] 确认 `httpx` 已在依赖中（`pyproject.toml` 已声明 `httpx>=0.27.0`）
- [ ] 确认 MediaCrawler 的 `DouYinClient` 可被独立导入（不依赖 main.py 入口）

### 3.3 实现步骤

1. **新建 `server/szyg/integrations/mediacrawler_bridge.py`**
   - 实现 `MediaCrawlerBridge` 类
   - `_prepare_browser_context()`：从 SessionManager 加载 storage_state → 创建 BrowserContext
   - `search_douyin()`：调用 MediaCrawler `DouYinClient.search_info_by_keyword()` → 解析 → `_normalize_search_result`
   - `get_douyin_detail()`：调用 `DouYinClient.get_video_by_id()`
   - `get_douyin_comments()`：调用 `DouYinClient.get_video_comments()`
   - 后续可扩展 `search_xhs()`、`search_kuaishou()`、`search_bilibili()`

2. **修改 `server/szyg/integrations/acquisition_adapters.py`**
   - `_search_douyin` 开头先尝试 `MediaCrawlerBridge.search_douyin()`
   - 失败时 fallback 到现有浏览器拦截逻辑
   - 日志区分 `[MediaCrawler]` 和 `[BrowserFallback]` 两种模式

3. **可选：扩展 MCP 工具**
   - 在 `acquisition_mcp.py` 新增 `acq_get_detail`、`acq_get_comments` 工具
   - 或直接复用 `acq_search`，内部自动选择模式

### 3.4 验收标准

- [ ] MediaCrawler 模式搜索响应时间 < 3 秒（含浏览器上下文创建）
- [ ] 搜索结果包含标题、作者、点赞数、评论数、视频链接
- [ ] 无登录 Cookie 时自动 fallback 到浏览器模式
- [ ] MediaCrawler 调用异常时自动 fallback 到浏览器模式
- [ ] 浏览器模式仍作为兜底可用
- [ ] 不影响现有其他平台（小红书、B站、快手）的搜索功能
- [ ] 后续可扩展至小红书、快手、B站搜索（MediaCrawler 已支持）

---

## 4. 注意事项

- MediaCrawler 开源版声明仅供学习研究，商业使用需评估合规性或购买 MediaCrawlerPro
- MediaCrawler Pro 版已移除 Playwright 依赖，纯 API 直调，但需付费订阅
- 抖音搜索接口本身不需要 a_bogus 签名，但详情/评论接口需要
- Cookie 有效期通常为 1-2 周，需依赖 SessionManager 的自动刷新机制
- MediaCrawler 的 CDP 模式可连接用户已有 Chrome，与本项目 BrowserPool 可共存
- MediaCrawler 更新时 `git submodule update --remote vendor/MediaCrawler` 同步最新版
- 签名 JS 文件(`libs/douyin.js`)会随 MediaCrawler 更新同步，无需本项目维护
