# 小妤 AI（Yuna AI）

小妤 AI 是面向公域用户的桌面数字员工产品，提供 OpenClaw 数字员工工作台、内容创作和运营工具。

GitHub 的 `main` 是公域源码的主线。历史私域产品「数字员工」已冻结，后续功能与修复统一进入小妤 AI。

## 验证与构建

- 前端构建：`npm --prefix szyg-frontend ci`，然后运行 `npm --prefix szyg-frontend run build`。
- OpenClaw 测试：`npm --prefix electron run test:openclaw`。
- Windows 安装包：在配置好桌面运行时和依赖的 Windows 构建环境中，运行 `npm --prefix electron run build`；Microsoft Store 包使用 `npm --prefix electron run build:store`。
