# 小妤AI Microsoft Store 发布

## 产品身份

- Package name: `YuSeTech.AI`
- Publisher: `CN=5E86A6E9-6F90-4E5A-A9DA-086C3BF2C80C`
- Publisher display name: `YuSeTech`
- Application id: `XiaoyuAI`
- Product id: `xiaoyu_public`

这些值来自 Partner Center，大小写必须保持一致。MSIX 版本使用四段格式，最后一段固定为 `0`。

## 构建

在 `electron` 目录运行：

```powershell
npm run build:store
```

该命令会完成源码隐私检查、前端构建、本地后端与 Hermes 打包、运行时完整性清单、Electron x64 布局和 MSIX 生成。Store 包输出到：

```text
electron/dist/store/XiaoyuAI-1.1.6.0-x64-Store.msix
```

提交给 Microsoft Store 的 MSIX 无需开发者自行购买 CA 代码签名证书，Store 会在认证流程中签名。直接在本机侧载时，另行生成并信任仅用于本地测试的开发证书。

## Partner Center 提交资料

- 定价与市场：应用本体免费；智能服务按 Credits 充值使用。
- 分类建议：商务或效率。
- 隐私政策 URL、支持 URL 和支持邮箱。
- 至少一张真实桌面截图、商店描述、功能要点和搜索词。
- 认证测试账号，以及从登录、充值测试页到核心功能的操作步骤。
- 在认证说明中披露：应用使用支付宝作为第三方支付服务；支付成功由服务端验签并写入用户钱包账本；`1 元人民币 = 100 Credits`。
- 受限能力说明：`runFullTrust` 用于启动随应用提供的本地服务、浏览器自动化及媒体处理运行时。

## 发布前门槛

- 在生产控制服务部署 `xiaoyu_public` 自助注册接口。
- 为公域注册增加邮箱验证和注册滥用防护后再开放大范围下载。
- 准备认证专用测试账号，且不要在认证说明中放生产管理员账号。
- 对候选包运行 Windows App Certification Kit，并完成注册、登录、支付宝充值回调、Credits 到账和数字人任务断点续跑 E2E。
