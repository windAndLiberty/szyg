# 小妤 AI（Yuna AI）

小妤 AI 是面向公域用户的桌面数字员工产品，提供 OpenClaw 数字员工工作台、内容创作和运营工具。

GitHub 的 `main` 是公域源码的主线。历史私域产品「数字员工」已冻结，后续功能与修复统一进入小妤 AI。

## 验证与构建

- 前端构建：`npm --prefix szyg-frontend ci`，然后运行 `npm --prefix szyg-frontend run build`。
- OpenClaw 测试：`npm --prefix electron run test:openclaw`。
- Windows 安装包：在配置好桌面运行时和依赖的 Windows 构建环境中，运行 `npm --prefix electron run build`；Microsoft Store 包使用 `npm --prefix electron run build:store`。

### Linux 桌面版（Debian / Ubuntu，amd64）

在 x86-64 Linux 构建机上准备 npm、uv 管理的 Python 3.12、Git、rsync、curl、unzip、zstd 和 dpkg-deb。从仓库根目录运行 `npm --prefix electron run build:linux`，安装包将写入 `electron/dist/`。首次构建需要联网下载锁定的依赖。

运行 `sudo apt install ./electron/dist/szyg_1.1.11_amd64.deb`，然后从应用菜单打开「小妤 AI」，也可以在终端运行 `szyg`。安装包包含 Electron、Python 后端、OpenClaw、Hermes 和发布用 Chromium。FFmpeg 由 apt 安装。微信桌面 UI 自动化和 Windows CUA 驱动仅适用于 Windows。
