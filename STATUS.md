# szyg 智能矩阵运营系统 — 开发状态文档

> 最后更新: 2026-06-28 | 版本: v1.0.0
>
> ⚠️ **本文为运行/部署状态记录。产品功能与架构的单一事实来源（SSOT）见 `docs/szyg产品功能融合设计.md`（v2.0）**。
> 如本文与 SSOT 冲突，以 SSOT 为准。

## 项目概述

面向中小企业主的自托管「数字员工」自动化营销系统，对标炼刀AI / 百应AI / IMAI.WORK。
C/S 架构：轻量 FastAPI 服务端 + 本地算力客户端 + Vue3 SPA。核心为 **Hermes 内核驱动的多流水线架构**。

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
│  │ 10 个 MCP Server (~87 MCP tools)       │  │
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

## 前端页面 (19 个 — Studio 架构)

> 旧版独立页面（pipeline/capture/conversion/security-matrix）已全部删除，统一为 Studio 架构。
> 旧路由保留 301 重定向至对应 Studio 页面，确保书签兼容。

| 路由 | 页面 | 功能 |
|------|------|------|
| `/login` | 登录页 | JWT 认证，记住密码 |
| `/dashboard` | 仪表盘 | 公告 + 统计 + 热门工具 + 更新日志 |
| `/ai-staff/overview` | 员工概览 | AI 员工矩阵总览 |
| `/ai-staff/tasks` | 任务看板 | 任务状态追踪与分配 |
| `/ai-staff/profiles` | 员工配置 | AI 员工角色与能力配置 |
| `/ai-staff/content-studio` | 内容工作室 | AI 脚本生成与批量内容生产 |
| `/ai-staff/acquisition-studio` | 获客工作室 | 多平台搜索、截流、评论互动、监听 |
| `/ai-staff/conversion-studio` | 转化工作室 | 线索管理与私域转化 |
| `/ai-staff/ops-studio` | 运营工作室 | 调度引擎与数据报告 |
| `/assets` | 内容资产 | 素材库管理 |
| `/crm` | 客户资产 | 客户关系管理 |
| `/settings/platforms` | 平台账号 | 矩阵账号安全绑定 |
| `/settings/skills` | 技能市场 | 技能浏览与安装 |
| `/settings/tools` | 工具管理 | AI 工具配置 |
| `/settings/system` | 系统配置 | 全局系统设置 |
| `/settings/brand` | 品牌配置 | Logo/版权/主题 (admin) |
| `/settings/team` | 团队管理 | 用户管理 (admin) |

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
| Claude Code + MCP (80+工具) | Hermes v0.15 + MCP (~87工具) |
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
