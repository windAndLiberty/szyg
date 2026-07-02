# 🔄 域灵系统 — 实时全局状态快照

> **最后更新**: 2026-07-02 09:42:00 | **维护者**: QA_Guardian

## 🏥 系统健康度（基于代码审计，未运行后端测试）

| 维度 | 状态 | 备注 |
|------|------|------|
| 后端服务 | ⚠️ 未审计 | 代码结构存在，但本次未进行运行时验证 |
| 前端构建 | ✅ 结构完整 | Vue 3 + Vite + Element Plus，页面已精简为 SuperAgent |
| 设计系统 | ⚠️ 部分缺陷 | `style.css` 仍存在 `--shadow-md` / `--shadow-lg` 循环引用 |
| 对话功能 | ✅ 可用 | 端点已修正为 `/api/conversations/*`，新增右键菜单（重命名/置顶/导出/删除） |
| 图片/视频生成 | ✅ 可用 | SSE image/video 事件已修复，前端渲染卡片、Lightbox/Modal 预览 |
| Vite 开发服务器 | ✅ 可用 | 代理已改为 `127.0.0.1:8000`，端口强制 `5173` |
| 应用启动 | ✅ 可用 | `restart_szyg.bat` 已重写，可清理僵尸进程并启动前后端 |
| Electron 客户端 | ⚠️ 可用 | 已支持 dev 模式加载 Vite，自动检测现有后端，ComfyUI venv 已修复 |
| 抖音搜索 | ⚠️ 未验证 | MediaCrawler 已集成，浏览器 fallback 已加调试，需实际运行验证 |
| 登录安全 | ⚠️ 风险 | 登录页已移除，改为自动认证，仍需审查 token 存储 |
| API_SPECS | ❌ 缺位 | 11 份路由接口规格仍为占位文件 |
| PRD | ❌ 缺位 | 7 份业务模块需求文档仍为占位文件 |

## 🚧 当前阻碍点

- **🚨 文档缺位**: `API_SPECS/` 和 `PRD/` 仍为空白，无法作为后续编码的唯一真理源。
- **⚠️ 抖音搜索验证**: MediaCrawler 集成完成，但需实际运行验证是否返回有效结果。
- **⚠️ 登录自动认证**: 登录页已移除，但自动认证机制的安全性和稳定性需审查。
- **⚠️ Electron 生产模式**: 生产模式 URL 仍指向 `/login`，但登录页已移除，需修正。

## 💳 技术债务

- `web/src/style.css` 中 backward-compatible alias 块与 theme 块产生 CSS 变量循环引用。
- `server/szyg/app.py` 与 `server/szyg/api/app.py` 双 `create_app()` 入口尚未统一。
- `web/src/router.js` 缺少 404 处理。
- `electron/main.js` 生产模式 URL 为 `http://127.0.0.1:8000/login`，但登录页已移除。
- `restart_szyg.ps1` 仍依赖硬编码环境变量（API key、密码）。
- 部分上下文菜单操作（export、delete）错误处理静默。

## ✅ 最近完成的工作

- [2026-07-02 09:36] **对话历史右键菜单**: 后端 `pinned` 字段 + 置顶排序，前端重命名/置顶/导出/删除
- [2026-07-01 20:53] **视频卡片渲染**: SSE video 事件 + 视频卡片 + Modal 预览
- [2026-07-01 20:37] **Vite 代理修复**: 改为 `127.0.0.1`，避免 Windows localhost 解析到 IPv6
- [2026-07-01 20:25] **图片卡片修复**: 工具名/字段不匹配修复，保存对话保留 `image_url`/`prompt`
- [2026-07-01 20:13] **图片卡片渲染**: SSE image 事件 + ImageCard + Lightbox
- [2026-07-01] **MediaCrawler 集成与修复**: 抖音搜索调试、桥接层、集成到 `acquisition_adapters`
- [2026-07-01] **启动脚本重写**: `restart_szyg.ps1` 清理僵尸进程、强制 Vite 端口、等待服务就绪
- [2026-07-01] **Electron 修复**: 开发模式加载 Vite，检测现有后端，跳过 ComfyUI 无效 venv

## 🔄 下一步计划

- **P0**: 验证抖音搜索实际可用性（MediaCrawler 模式 + fallback 模式）
- **P0**: 修正 Electron 生产模式 URL（登录页已移除）
- **P0**: 填充 `API_SPECS/` 和 `PRD/` 空白文档
- **P1**: 修复 `style.css` 中 `--shadow-md` / `--shadow-lg` 循环引用
- **P1**: 审查自动认证安全性，移除 `localStorage` 明文 token 存储
- **P1**: 统一 `server/szyg/app.py` 与 `server/szyg/api/app.py` 入口
- **P2**: `router.js` 增加 404 路由
- **P2**: 给上下文菜单操作添加错误提示
