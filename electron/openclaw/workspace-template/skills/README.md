# 员工技能目录

技能以独立目录中的 `SKILL.md` 为唯一执行事实源。请勿把第三方技能正文复制到身份或系统规则中。

视频号技能由管理员显式安装，不在应用启动或构建时自动下载：

```bash
npx skills add https://github.com/TeamWiseFlow/xiaobei --skill wechat-channels-publish
```

安装后应验证 `wechat-channels-publish/SKILL.md` 存在并记录 SHA-256；技能文件由外部包管理，不得手工修改。
