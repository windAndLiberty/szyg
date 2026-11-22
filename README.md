# 小妤 AI（Yuna AI）

小妤 AI 是面向公域用户的桌面数字员工产品，提供 OpenClaw 数字员工工作台、内容创作和运营工具。

GitHub 的 `main` 是公域源码的主线。历史私域产品「数字员工」已冻结，后续功能与修复统一进入小妤 AI。

## 验证与构建

- 前端构建：`npm --prefix szyg-frontend ci`，然后运行 `npm --prefix szyg-frontend run build`。
- OpenClaw 测试：`npm --prefix electron run test:openclaw`。
- Windows 安装包：在配置好桌面运行时和依赖的 Windows 构建环境中，运行 `npm --prefix electron run build`；Microsoft Store 包使用 `npm --prefix electron run build:store`。

### Linux 桌面版（Debian / Ubuntu，amd64）

在 x86-64 Linux 构建机上准备 npm、uv 管理的 Python 3.12、Git、rsync、curl、unzip、zstd 和 dpkg-deb。从仓库根目录运行 `npm --prefix electron run build:linux`，安装包将写入 `electron/dist/`。首次构建需要联网下载锁定的依赖。

运行 `sudo apt install ./electron/dist/szyg_1.1.12_amd64.deb`，然后从应用菜单打开「小妤 AI」，也可以在终端运行 `szyg`。安装包包含 Electron、Python 后端、OpenClaw、Hermes 和发布用 Chromium。FFmpeg 由 apt 安装。微信桌面 UI 自动化和 Windows CUA 驱动仅适用于 Windows。

### 把小妤 AI 接入本机智能体

1. 启动桌面版并登录，在「系统配置 → 智能体接入」输入客户端名称，选择允许的工具，点击「创建凭证」。每个客户端可单独撤销。
2. 从页面复制 MCP URL 和一次性显示的凭证。在客户端选择 Streamable HTTP，将凭证设为 Bearer token。桌面端口被占用时会自动更换，请使用页面显示的 URL。
3. 让客户端列出工具。例如，仅勾选「查看知识库统计」时，会看到 `knowledge_stats`，调用它即可读取本机知识库统计。知识检索、文档列表、写入知识文本和文案生成可逐项授权。生成文案可能消耗账户额度。

使用 Codex CLI 时，可将凭证放入启动 Codex 的环境变量 `XIAOYU_MCP_TOKEN`，再运行以下命令。示例使用默认端口。

```bash
codex mcp add xiaoyu --url http://127.0.0.1:8000/api/mcp/xiaoyu --bearer-token-env-var XIAOYU_MCP_TOKEN
```

小妤桌面端需保持运行，并处于对应账户的登录状态。撤销后，客户端的后续请求立即失去授权。内置 OpenClaw 继续使用自己的连接。
