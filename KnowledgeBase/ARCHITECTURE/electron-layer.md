# 🖥️ Electron 桌面端架构

## 概述

域灵通过 Electron 封装为 Windows 桌面应用，将后端 Python 服务与前端 SPA 打包为单一可执行文件。

## 目录结构

```
electron/
├── main.js         # Electron 主进程
├── preload.js      # 预加载脚本 (上下文隔离)
├── package.json    # Electron 依赖 + electron-builder 配置
└── *.vbs           # VBS 启动辅助脚本
```

## 工作流程

```
Electron 启动 (main.js)
  → 启动后端 uvicorn (Python 子进程)
  → 等待后端就绪 (健康检查)
  → 创建 BrowserWindow
  → 加载 http://localhost:{port} (前端 SPA)
  → 用户操作 → 前端 → 后端 API
```

## 打包配置 (electron-builder)

| 配置项 | 值 |
|--------|-----|
| appId | `com.szyg.app` |
| productName | `szyg` |
| target | `win portable` (便携版，无需安装) |
| 输出目录 | `dist/` |

### 打包内容

- `main.js` + `preload.js` (Electron 入口)
- `server/**/*` (后端 Python 代码)
- `data/**/*` (数据文件)
- `config.yaml` (主配置)
- `server/szyg/storage/chromium` (Playwright 浏览器二进制)

## 依赖

- **electron**: >=33.4
- **electron-builder**: >=25.0

## 启动脚本

| 脚本 | 用途 |
|------|------|
| `start_electron.bat` | 开发模式启动 Electron |
| `restart_szyg.bat` / `restart_szyg.ps1` | 重启服务 |
| `szyg_service.bat` | Windows 服务模式 |
