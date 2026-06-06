# szyg 智能矩阵运营系统 — 开发状态文档

> 最后更新: 2026-06-05

## 项目概述

基于对「数创引擎」完整逆向分析，重新构建的自托管 AI 工具平台。C/S 架构：轻量服务端 + 本地算力客户端。

## 架构

```
┌─────────────────────────────────────────────┐
│  Windows 客户端 (192.168.1.105)              │
│  ┌───────────────────────────────────────┐  │
│  │ 桌面快捷方式 → VBS → Chrome App 模式   │  │
│  │ http://127.0.0.1:8000/login (D:\szyg)  │  │
│  ├───────────────────────────────────────┤  │
│  │ FastAPI 后端 (61 REST endpoints)       │  │
│  │ Vue.js SPA (内置静态文件服务)           │  │
│  ├───────────────────────────────────────┤  │
│  │ 本地 AI 引擎                            │  │
│  │   ✅ Ollama (5 models: qwen2.5:7b等)  │  │
│  │   ⬜ ComfyUI (SD 2.1 模型已部署)       │  │
│  │   ⬜ FFmpeg                             │  │
│  ├───────────────────────────────────────┤  │
│  │ Hermes Agent v0.15 (中枢 AI)          │  │
│  │ 6 个 MCP Server (35 MCP tools)         │  │
│  └───────────────────────────────────────┘  │
│  开机自启: szygServer 计划任务              │
└─────────────────────────────────────────────┘
         ↕ 源码同步 (tar + scp)
┌─────────────────────────────────────────────┐
│  Linux 开发机 (192.168.1.136)               │
│  ~/code/szyg/ — 主控源码                    │
└─────────────────────────────────────────────┘
```

## 源码位置

| 环境 | 路径 | 用途 |
|------|------|------|
| Linux | `~/code/szyg/` | 开发主控，构建 SPA，管理配置 |
| Windows | `D:\szyg\` | 运行环境 (2026-06-05 从 C 盘迁移) |

### 关联组件位置

| 组件 | 路径 | 说明 |
|------|------|------|
| szyg 主项目 | `D:\szyg\` | 含 .venv |
| ComfyUI | `D:\ComfyUI\` | `D:\szyg\ComfyUI` → junction |
| FFmpeg | `D:\tools\ffmpeg\` | 已加入 PATH |
| Playwright | 系统托管 | ms-playwright 目录 |

同步命令：
```bash
cd ~/code/szyg && tar czf /tmp/szyg-sync.tar.gz --exclude='.venv' --exclude='node_modules' \
  server/ web/ electron/ data/ tests/ config.yaml pyproject.toml hermes.yaml
scp /tmp/szyg-sync.tar.gz Administrator@192.168.1.105:D:/ && \
ssh Administrator@192.168.1.105 "cd D:\szyg && python -c \"import tarfile; tarfile.open('D:/szyg-sync.tar.gz').extractall()\""
```

## API 端点 (61 个)

### 核心业务
| 分组 | 数量 | 关键端点 |
|------|------|---------|
| Auth | 4 | login, session, users CRUD |
| Tools | 8 | catalog, categories, install, launch, stats |
| Agents | 4 | list, detail(system_prompt), tiers, categories |
| Publisher | 14 | CRUD + submit/approve/reject/schedule/publish + AI generate |
| Scheduler | 10 | CRUD + execute/pause/resume + history + stats |
| Hub | 2 | 24 个精选 AI 工具导航 |
| OEM | 2 | 品牌配置 (name/logo/copyright/theme/客服/官网) |
| Announce | 3 | 系统公告 CRUD |
| Brain | 3 | hermes-agent 状态/prompt/MCP |
| Client | 7 | 本地 Ollama/ComfyUI/FFmpeg 状态 + 执行 |
| Knowledge | 2 | FTS5 全文检索 + 文档摄入 |
| SOP | 2 | 工作流定义/列表 |
| Image | 2 | AI 图像生成 |
| V1 | 2 | OpenAI 兼容 /v1/chat/completions + /v1/models |

### 验收测试结果: **29/30 通过** (1 个 tools/stats 边缘端点 500)

## 前端页面 (12 个)

| 路由 | 页面 | 功能 |
|------|------|------|
| `/login` | 登录页 | JWT 认证，记住密码 |
| `/dashboard` | 首页 | 公告 + 统计 + 热门工具 + 更新日志 |
| `/tools` | 工具市场 | 8 个 AI 工具浏览/安装/启动 |
| `/agents` | AI 智能体 | 12 个 SME 专家，3 层级提示词 |
| `/publisher` | 内容发布 | AI 生成→审核→排期→多平台发布 |
| `/scheduler` | 调度引擎 | Cron/Interval/Manual 定时任务 |
| `/hub` | AI 导航 | 24 个精选 AI 工具链接 |
| `/chat` | AI 对话 | 本地 Ollama 流式 SSE 聊天 |
| `/image` | AI 绘图 | 本地 ComfyUI SD 2.1 生图 |
| `/video` | AI 视频 | LLM 脚本 + TTS + FFmpeg |
| `/admin` | 系统管理 | 用户管理/配置 (admin) |
| `/oem` | 品牌管理 | Logo/版权/主题/免责声明 |

## 对比数创引擎

| 数创引擎 | szyg |
|---------|------|
| Electron 桌面壳 (264MB) | Chrome App 模式 + VBS (0MB) |
| PHP 远端后端 (154.219.107.125) | FastAPI 自托管 |
| HTTP 明文 | 本地 localhost |
| 远程 JS 配置注入 (安全隐患) | 本地 config.yaml |
| DLL 注入微信/企微 (灰色) | ✅ 留白, 预留接口 |
| 插件市场 (ZIP下载安装) | 工具市场 (本地执行 + 云端) |
| OEM 多租户 | 品牌配置系统 |
| Claude Code + MCP (80+工具) | Hermes v0.15 + MCP (35工具) |
| 闭源商业软件 | MIT 开源 |

## 已删除的原版安全问题

- ❌ HTTP 明文 → ✅ localhost
- ❌ `eval()` JSON 解析 → ✅ `json.loads()`
- ❌ 远程 JS 脚本注入 → ✅ 本地配置
- ❌ 凭据弱编码 → ✅ JWT + PBKDF2
- ❌ `webSecurity: false` → ✅ 正常浏览器安全
- ❌ DLL 注入 → ✅ 留白

## 待完成

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P2 | 代码签名 | 购买证书签名 .exe |
| P3 | 微信/企微/抖音 API | 官方 API 集成 (非 DLL) |
| P3 | 多租户 | OEM ID 数据隔离 |

## 已完成

| 日期 | 事项 |
|------|------|
| 2026-06-05 | 项目从 C 盘迁移至 D 盘 |
| 2026-06-05 | ComfyUI SD 2.1 部署 + 模型修复 (4.9GB) |
| 2026-06-05 | comfy-aimdo 升级 (0.4.5→0.4.8, 修复 ModelMMAP) |
| 2026-06-05 | httpx proxy 问题修复 (trust_env=False) |
| 2026-06-05 | ImageRouter LLM fallback (无 API key 时直接生图) |
| 2026-06-05 | Electron 启动验证 — 无白屏, SPA 正常渲染 |
| 2026-06-05 | E2E Playwright 测试: 11/11 通过, 34 API 调用追踪 |
| 2026-06-05 | 生图 API: POST /api/image/generate → ComfyUI SD 2.1 ✅ |
