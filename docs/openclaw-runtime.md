# 小妤 OpenClaw Runtime

小妤把 OpenClaw 当作可替换的本地运行时，不修改 OpenClaw 源码，也不使用用户全局安装。

## 构建

运行 `electron/scripts/build-openclaw-runtime.ps1`。脚本下载锁定的 Node.js 24.16.0，执行完整 npm 安装并生成包含关键文件 SHA-256 的 `manifest.json`。当前 Runtime、Gateway Client 和 Protocol 均锁定为 2026.10.5，wire version 为 4。该 Node 版本满足 OpenClaw 对 SQLite WAL 安全修复的最低要求，运行时不会回退到用户全局 Node.js。

Electron 只接受版本和哈希均匹配的运行时目录。Gateway 绑定 `127.0.0.1`，令牌由 Electron 安全存储，渲染页面无法读取。

## 状态与升级

- 安装包中的 Runtime 是只读基础版本。
- 可写更新放在应用数据目录 `openclaw/runtime/versions/<version>`。
- `active.json` 是唯一切换指针，写入使用临时文件加原子替换。
- 更新包必须同时通过文件哈希与 Ed25519 签名验证；未配置发行公钥或包未签名时拒绝暂存。
- 切换前应停止新任务、等待或取消当前任务，并备份 `openclaw/state`。
- Runtime 与数据库不兼容时必须同时恢复迁移前状态备份。
- 禁止员工调用 OpenClaw 自更新；升级只能随小妤正式版本或管理员操作进行。

## 视频号技能

应用不会自动下载第三方技能。管理员先审查来源，再查看安装命令：

```powershell
powershell -File scripts/install-wechat-channels-skill.ps1 -Workspace <员工工作区>
```

确认后显式执行：

```powershell
powershell -File scripts/install-wechat-channels-skill.ps1 -Workspace <员工工作区> -Install
```

脚本实际调用且仅调用指定的安装来源：

```bash
npx skills add https://github.com/TeamWiseFlow/xiaobei --skill wechat-channels-publish
```

完成后验证 `skills/wechat-channels-publish/SKILL.md`，并把哈希写入工作区自己的 `.xiaoyu/skill-lock.json`。不修改第三方 `SKILL.md`，也不把它的正文复制进员工身份规则。

## 本地边界

应用退出或电脑关机时，例程和 webhook 不运行。Hermes 历史会话和记忆不导入；原有账号、素材、项目、发布记录及其他业务数据库保持不变。
