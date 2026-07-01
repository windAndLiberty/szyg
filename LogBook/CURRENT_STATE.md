# 🔄 域灵系统 — 实时全局状态快照

> **最后更新**: 2026-06-30 21:55:00 | **维护者**: QA_Guardian

## 🏥 系统健康度（基于代码审计，未运行后端测试）

| 维度 | 状态 | 备注 |
|------|------|------|
| 后端服务 | ⚠️ 未审计 | 代码结构存在，但本次未进行运行时验证 |
| 前端构建 | ✅ 结构完整 | Vue 3 + Vite + Element Plus，当前保留 3 个业务页面 |
| 设计系统 | ⚠️ 部分缺陷 | 视觉变量已迁移，但 `style.css` 存在 `--shadow-md` / `--shadow-lg` 循环引用 |
| 对话功能 | ❌ 不可用 | `SuperAgent.vue` 调用错误端点 `/api/hermes/conversations/*`（应为 `/api/conversations/*`） |
| 平台解绑 | ❌ 不可用 | `SettingsPlatforms.vue` 调用不存在的 `DELETE /api/platforms/{id}/sessions` |
| 登录安全 | ⚠️ 风险 | 明文密码存储 + dev 查询参数后门 |
| API_SPECS | ❌ 缺位 | 11 份路由接口规格仍为占位文件 |
| PRD | ❌ 缺位 | 7 份业务模块需求文档仍为占位文件 |

## 🚧 当前阻碍点

- **🚨 前端运行阻塞**: `SuperAgent.vue` 对话历史与 `SettingsPlatforms.vue` 解绑功能无法工作。
- **🚨 设计系统视觉缺陷**: 阴影变量循环引用导致相关卡片阴影失效。
- **🚨 登录安全后门**: `Login.vue` 明文存储密码且存在开发模式 URL 后门。
- **⚠️ 文档缺位**: `API_SPECS/` 和 `PRD/` 仍为空白，无法作为后续编码的唯一真理源。

## 💳 技术债务

- `web/src/style.css` 中 backward-compatible alias 块与 theme 块产生 CSS 变量循环引用。
- `SuperAgent.vue` 与 `SettingsPlatforms.vue` 存在错误 API 端点调用。
- `Login.vue` 使用 `localStorage` 明文存储凭据。
- `server/szyg/app.py` 与 `server/szyg/api/app.py` 双 `create_app()` 入口尚未统一。
- `web/src/router.js` 缺少已登录用户重定向与 404 处理。

## ✅ 最近完成的工作

- [2026-06-30 21:55] **QA_Guardian 前端代码审计**: 发现 P0 缺陷 3 项、P1 安全风险 2 项、P2 设计问题 4 项
- [2026-06-30 20:59] **设计系统迁移（阶段 1-6）**: 核心变量系统、组件覆盖、布局框架、全局工具类、Solarized 移除
- [2026-06-30 16:27] **前端重构**: 页面从 44 个精简为 3 个（Login / SuperAgent / SettingsPlatforms）
- [2026-06-30 16:30] **KnowledgeBase + LogBook 初始化**: 架构/规约/数据库/ADR 文档填充

## 🔄 下一步计划

- **P0**: 修复 `style.css` 中 `--shadow-md` / `--shadow-lg` 循环引用
- **P0**: 修正 `SuperAgent.vue` 对话端点为 `/api/conversations/*` 并适配 payload schema
- **P0**: 修正 `SettingsPlatforms.vue` 解绑调用（后端补 `/sessions` 或前端改为 `/login` 重新触发）
- **P1**: 移除 `Login.vue` 明文密码存储与 `dev` 查询参数后门
- **P1**: `SuperAgent.vue` 改用 axios 并检查 `response.ok`
- **P2**: 给 `JSON.parse(localStorage...)` 加 try-catch
- **P2**: `router.js` 增加已登录用户拦截与 404 路由
- **P2**: 修复 `SettingsPlatforms.vue` 账号显示与 hover 边框硬编码
