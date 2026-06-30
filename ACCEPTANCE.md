# szyg 智能矩阵运营系统 — 验收测试文档

> 基于对「数创引擎」完整对标重构的自托管 AI 营销平台
> 最后更新: 2026-06-06

---

## 一、项目进展总览

### 已完成功能

| 阶段 | 模块 | 状态 | 说明 |
|------|------|------|------|
| Phase 1 | 平台自动化引擎 | ✅ | 5 个适配器：抖音/小红书/微信/B站/快手 |
| Phase 2 | 前端 + 系统整合 | ✅ | Platforms.vue + REST API + MCP 工具 |
| Phase 2 | 打包系统 | ✅ | build/package.py 一键构建独立安装包 |
| Phase 3 | 技能生态移植 | ✅ | 5 个脚本型 + 5 个提示词型技能 |
| Phase 3 | 视频剪辑引擎 | ✅ | FFmpeg 引擎 + 12 模板 + 27 字体 |
| Phase 3 | 多租户数据隔离 | ✅ | TenantContext + Middleware |
| 测试 | 单元测试 | ✅ | 58 个测试，全部通过 |

### 核心数字

| 指标 | 数量 |
|------|------|
| MCP Servers | 9 |
| MCP Tools | 66 |
| REST 端点 | 77+ |
| Vue 页面 | 13 |
| 平台适配器 | 5 |
| 办公技能 | 4 (docx / xlsx / pptx / pdf) |
| 内置提示词技能 | 5 (文案 / 编辑 / 策略 / AI SEO / 深度研究) |
| 设计技能 | 1 (canvas-design, 54 fonts) |
| 视频模板 + 字体 | 12 + 27 |
| 调度动作类型 | 8 |
| 单元测试 | 58 |
| Python 包 | 90 |

### 文件统计

| 分类 | 数量 | 说明 |
|------|------|------|
| 新建文件 | 42 | platforms/ (15) + skills/ (5 dirs) + video/ (2) + build/ (1) + 前端 (1) + API (2) + MCP (3) + tenant (1) + tests (1) + 模板/字体 |
| 修改文件 | 14 | publisher.py, scheduler_engine.py, brain_hermes.py, main.py, app.py, hermes.yaml, config.yaml, pyproject.toml, registry.py, router.js, AppLayout.vue, Publisher.vue, Dashboard.vue, data_path.py |

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                      szyg 智能矩阵运营系统                     │
│                                                               │
│  用户入口: Chrome App  │  Electron  │  http://127.0.0.1:8000  │
│                                                               │
│  前端 (13 Vue 页面)               Hermes Agent v0.15           │
│  ├─ Dashboard (平台就绪+发布日志)   ├─ 系统提示词 (5 技能内置)   │
│  ├─ Platforms ★ (5平台卡片+登录)   ├─ 9 MCP Servers (66 tools) │
│  ├─ Publisher ★ (多平台发布+状态)   │  ├─ publisher    (12)     │
│  ├─ Scheduler ★ (8种调度动作)      │  ├─ platforms ★  (8)      │
│  └─ 9 其他页面                    │  ├─ skills ★    (12)      │
│                                    │  ├─ video ★     (11)      │
│  FastAPI (77+ endpoints)           │  ├─ scheduler    (9)      │
│  ├─ /api/publisher/*  (14)        │  ├─ tools        (5)      │
│  ├─ /api/scheduler/*  (10)        │  ├─ knowledge    (3)      │
│  ├─ /api/platforms/*  (6) ★       │  ├─ agents       (4)      │
│  └─ 其他 (47+)                     │  └─ oem          (2)      │
│                                    │                           │
│  平台适配器 (5) ★★                  │  多租户隔离 ★              │
│  ├─ DouyinAdapter   (Playwright)  │  ├─ TenantMiddleware      │
│  ├─ XHSAdapter      (Playwright)  │  ├─ TenantContext         │
│  ├─ WeChatDesktop   (Windows UIA) │  └─ data/{tenant}/        │
│  ├─ BilibiliAdapter (Playwright) ★│                           │
│  └─ KuaishouAdapter (Playwright) ★│  技能系统 ★               │
│                                    │  ├─ 办公: docx/xlsx/pptx/pdf │
│  视频引擎 ★                         │  ├─ 设计: canvas-design    │
│  ├─ FFmpeg 剪辑/拼接/变速/字幕      │  └─ 提示词: copywriting/   │
│  ├─ 12 视频模板                    │    editing/strategy/       │
│  └─ 27 中文字体                    │    ai-seo/deep-research    │
│                                                               │
│  打包系统 ★                                                    │
│  └─ build/package.py → szyg-1.0.0-win64.zip (~1.8 GB)        │
└──────────────────────────────────────────────────────────────┘

★  = Phase 2 新增    ★★ = Phase 2+3 扩展
```

---

## 三、环境依赖

### 3.1 Python 包 (90 个，完整清单)

```
核心运行时:
  fastapi==0.136.3          uvicorn==0.49.0          httpx==0.28.1
  pydantic==2.13.4          pydantic-settings==2.14.1 pyyaml==6.0.3
  structlog==25.5.0         python-multipart==0.0.32  sse-starlette==3.4.4
  python-jose==3.5.0        passlib==1.7.4            python-dotenv==1.2.2
  aiofiles (未安装)

平台自动化:
  playwright==1.60.0        uiautomation==2.0.29      pywin32==312
  psutil==7.2.2             py-mini-racer==0.6.0      comtypes==1.4.16

办公技能:
  openpyxl==3.1.5           python-pptx==1.0.2         PyPDF2==3.0.1
  pdfplumber==0.11.9        pdfminer.six==20251230     pypdfium2==5.9.0
  lxml==6.1.1               Pillow==12.2.0             xlsxwriter==3.2.9

视频引擎:
  (FFmpeg 系统工具, 不通过 pip)

AI 集成:
  openai==2.41.0            edge-tts==7.2.8            aiohttp==3.14.0

测试:
  pytest==9.0.3             pytest-asyncio==1.4.0      respx==0.23.1

传递依赖: bcrypt, certifi, cffi, cryptography, greenlet, h11, httpcore, 
           idna, multidict, pycparser, rsa, six, sniffio, starlette, 
           typing-extensions, websockets, yarl, annotated-types, anyio, 
           click, colorama, distro, ecdsa, frozenlist, httptools, jiter, 
           packaging, propcache, pyasn1, pyee, pygments, setuptools, 
           tabulate, tqdm, watchfiles, websocket-client 等
```

### 3.2 外部运行时

| 组件 | 版本 | 大小 | 位置 | 打包方式 |
|------|------|------|------|---------|
| Python | 3.11.15 | ~40 MB | `.venv/` | 复制 runtime/ |
| Python 包 | — | **322 MB** | `.venv/Lib/` | 复制 runtime/Lib/ |
| Playwright Chromium | v1223 | 820 MB | `%LOCALAPPDATA%\ms-playwright\` | 复制 browsers/ |
| Playwright Headless | v1223 | 550 MB | `%LOCALAPPDATA%\ms-playwright\` | 复制 browsers/ |
| Playwright FFmpeg | — | ~5 MB | `%LOCALAPPDATA%\ms-playwright\` | 复制 browsers/ |
| Node.js | v26.2.0 | ~100 MB | 系统安装 | 可选 |
| Vue SPA | dist | 1.5 MB | `web/dist/` | 包含 |
| FFmpeg | N-124795 | ~80 MB | `D:\tools\ffmpeg\` | 可选 |
| Pandoc | — | 未安装 | — | `winget install pandoc` |
| Ollama + LLM | — | ~5 GB | 系统安装 | 单独安装 |
| ComfyUI | SD 2.1 | ~5 GB | `D:\ComfyUI\` | 单独安装 |

### 3.3 打包尺寸预估

| 级别 | 大小 | 包含内容 |
|------|------|---------|
| 最小 | **1.8 GB** | Python + 包 + Chromium + SPA dist + 源码 |
| 标准 | **2.1 GB** | 最小 + Node.js + FFmpeg + Pandoc |
| 完整 | **12 GB** | 标准 + Ollama + ComfyUI (单独安装) |

---

## 四、验收测试

### 4.1 单元测试 (58 个)

```bash
cd D:\szyg
.venv\Scripts\activate
.venv\Scripts\python -m pytest server/tests/test_platforms.py -v -c pyproject.toml
```

**测试覆盖：**

| 测试类 | 数量 | 覆盖内容 |
|--------|------|---------|
| TestPublishModels | 8 | PublishRequest/Result/LoginStatus 数据模型 |
| TestPlatformRegistry | 7 | 注册表 CRUD、单例、健康检查 |
| TestSessionManager | 8 | 登录态保存/加载/过期验证/清除 |
| TestAntiDetect | 4 | stealth config、launch config、builtin JS |
| TestDouyinSigner | 6 | msToken 生成、唯一性、签名参数注入 |
| TestPublisherV2 | 6 | async publish、mock fallback、日志、统计 |
| TestSchedulerNewActions | 4 | PLATFORM_LOGIN_CHECK/HEALTH_CHECK、后台 loop |
| TestPlatformRoutes | 5 | REST API 端点功能 |
| TestPlatformMCPServer | 6 | MCP 工具注册完整性、输入校验 |
| TestBaseAdapter | 3 | 适配器状态机、初始化成功/失败 |

**预期：** `58 passed in ~10s`

---

### 4.2 REST API 验收

#### Step 1: 启动服务

```bash
cd D:\szyg
.venv\Scripts\python -m uvicorn szyg.main:app --host 127.0.0.1 --port 8000
```

#### Step 2: 平台 API（5 个适配器）

```bash
# 列出所有平台 — 预期 5 个: douyin, xhs, wechat_mp, bilibili, kuaishou
curl http://127.0.0.1:8000/api/platforms

# 单平台详情 — B站
curl http://127.0.0.1:8000/api/platforms/bilibili

# 全平台健康检查
curl http://127.0.0.1:8000/api/platforms/health/all

# 发布日志
curl "http://127.0.0.1:8000/api/platforms/logs/all?limit=10"
```

#### Step 3: 发布管道（完整流程）

```bash
# 创建 → 提审 → 批准 → 发布到 B站
curl -X POST "http://127.0.0.1:8000/api/publisher/contents?title=测试B站发布&body=测试正文&platforms=bilibili&tags=test"
# 返回: {"id":"xxxxxxxx",...}

curl -X POST "http://127.0.0.1:8000/api/publisher/contents/{id}/submit"
curl -X POST "http://127.0.0.1:8000/api/publisher/contents/{id}/approve"
curl -X POST "http://127.0.0.1:8000/api/publisher/contents/{id}/publish?platform=bilibili"

# 查看统计
curl http://127.0.0.1:8000/api/publisher/stats
```

#### Step 4: 调度器

```bash
# 创建平台巡检任务
curl -X POST "http://127.0.0.1:8000/api/scheduler/jobs?name=平台健康巡检&trigger_type=interval&action=platform_health_check&interval_minutes=60"

# 查看所有任务
curl http://127.0.0.1:8000/api/scheduler/jobs
```

#### Step 5: 视频引擎

```bash
# 查看可用模板
.venv\Scripts\python -c "import sys; sys.path.insert(0,'server'); from szyg.video_cut_engine import list_templates, list_fonts; print(f'Templates: {len(list_templates())}'); print(f'Fonts: {len(list_fonts())}')"
# 预期: Templates: 12, Fonts: 27

# 获取视频信息
.venv\Scripts\python -c "import sys; sys.path.insert(0,'server'); from szyg.video_cut_engine import get_video_info; print(get_video_info('path/to/video.mp4'))"
```

#### Step 6: 技能系统

```python
import sys; sys.path.insert(0, 'server')

# 办公技能
from szyg.mcp_servers.skills_mcp import skills_list, skill_xlsx_create, skill_docx_extract_text
print(skills_list())
# 预期: {"skills": [...], "total": 5, "office_skills": 4, "design_skills": 1}

# 创建 Excel
r = skill_xlsx_create('[["Name","Age"],["Alice",30]]', 'd:/test.xlsx')
assert r["rows"] == 2

# 读取 docx 文本
r = skill_docx_extract_text('path/to/test.docx')
# 预期: {"text": "...", "paragraphs": N}
```

#### Step 7: 多租户

```python
import sys; sys.path.insert(0, 'server')
from szyg.tenant import TenantContext, get_current_tenant, get_tenant_data_dir

with TenantContext("oem_customer_a"):
    assert get_current_tenant() == "oem_customer_a"
    d = get_tenant_data_dir()
    assert "tenants/oem_customer_a" in str(d)
    print(f"Tenant data dir: {d}")

# 默认租户
assert get_current_tenant() == "default"
```

---

### 4.3 前端验收

启动后端后访问 `http://127.0.0.1:8000`。

| 页面 | 验证点 |
|------|--------|
| `/login` | JWT 登录，默认 admin/admin |
| `/dashboard` | 应显示 "📡 平台就绪" 统计卡片 + 最近发布记录 |
| `/publisher` | 平台选择器含 B站/快手；登录状态图标 |
| `/scheduler` | 可创建 `platform_health_check` 类型任务 |
| `/platforms` | 5 个平台卡片（抖音/小红书/微信/B站/快手）+ 登录按钮 + 发布历史 |

---

### 4.4 Hermes MCP 集成验收

```bash
# 查看 MCP 服务器列表 — 预期 9 个
curl http://127.0.0.1:8000/api/brain/mcp | python -m json.tool

# 服务器列表: publisher, scheduler, tools, knowledge, agents, oem, platforms, skills, video

# 查看系统提示词
curl http://127.0.0.1:8000/api/brain/prompt
# 预期包含: 文案写作、AI SEO、深度研究、视频剪辑引擎、平台自动化
```

---

## 五、打包部署

### 构建安装包

```bash
cd D:\szyg
.venv\Scripts\python build/package.py
```

输出: `build/dist/szyg-1.0.0-win64.zip` (~1.8 GB)

### 安装包内容

```
szyg-1.0.0/
├── start_szyg.bat         ← 双击启动
├── README.txt
├── runtime/               ← Python 3.11 + 90 包
├── browsers/              ← Chromium + Headless Shell + FFmpeg
├── server/                ← 后端源码
├── web/dist/              ← 前端 SPA
├── data/                  ← 数据模板
├── config.yaml
├── hermes.yaml
└── pyproject.toml
```

### 用户安装步骤

1. 解压 `szyg-1.0.0-win64.zip` 到目标目录
2. (可选) 安装 Pandoc: `winget install pandoc`
3. (可选) 安装 Ollama + 模型
4. 双击 `start_szyg.bat`
5. 浏览器访问 `http://127.0.0.1:8000`
6. 默认账号: `admin` / `admin`

---

## 六、已知限制

| 限制 | 说明 | 解决方案 |
|------|------|---------|
| 浏览器自动化需要桌面 | Playwright/Chromium 需要 Windows GUI | 生产环境用 headless 模式 |
| 平台扫码登录需人工 | 抖音/小红书/微信/B站/快手首次需手机扫码 | SessionManager 持久化登录态 |
| 微信 UIA 依赖微信版本 | 微信 UI 更新可能破坏选择器 | 维护 UIA 选择器版本映射 |
| PyMiniRacer 可能故障 | V8 引擎偶尔初始化失败 | fallback 到 Node.js 子进程 |
| 视频引擎依赖 FFmpeg | 需系统安装 FFmpeg | 打包到 browsers/ffmpeg/ |
| 网络受限环境 | pip/git 需要代理 | `NO_PROXY="*"` 或打包版无需网络 |

---

## 七、路线图

| 优先级 | 任务 | 状态 |
|--------|------|------|
| P1 | git 初始化 + 首次提交 | ⬜ |
| P1 | 真实账号 E2E 测试 | ⬜ |
| P2 | B站/快手适配器 | ✅ |
| P2 | 独立安装包打包 | ✅ |
| P3 | 视频剪辑引擎 | ✅ |
| P3 | 多租户数据隔离 | ✅ |
| P3 | Weibo 适配器 | ⬜ |
| P3 | 飞书适配器 | ⬜ |
| P∞ | 企业微信 DLL 注入 |   |
