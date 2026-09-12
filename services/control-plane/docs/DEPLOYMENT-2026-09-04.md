# 2026-09-04 数字人部署记录

## 已上线的云端服务

- 正式地址：https://szyg.qdtracing.com
- 主机：dolphin；目录：`/home/ubuntu/szyg-control`。
- `control-api` 和 `control-worker` 已重建并运行，API 健康检查通过。
- 独立能力 `video.omnihuman` 使用 CV 的 OmniHuman1.5；保留原有 `video.presenter` / Seedance 路由，兼容原普通创作流程。
- `speech.asr` 使用 `volc.seedasr.auc`；`speech.tts` 使用 Seed Audio 1.0，支持以上传音频为声音参考。
- `/app/data` 映射到服务器 `./data`，参考素材在重建容器后保留。
- CV/ASR 凭据已配置在服务器 `.env`，未复制到客户端或本文档。

## 正式 HTTPS 实测

测试使用仓库卡通头像和火山公开示例音频，不使用客户素材。

| 步骤 | 实测结果 |
|---|---|
| ASR | 识别 6312 毫秒音频，数据库状态 `succeeded` |
| 参考声音生成 | 生成新台词的 3.5 秒 MP3 |
| 上传素材 | 通过认证接口上传；正式 HTTPS 临时链接可读取且字节一致 |
| OmniHuman | 生成带音轨视频，960×960，时长 3.56 秒 |
| 时长校验 | 请求故意填写 1 秒，服务端 ffprobe 测量后按 4 秒预留 |
| 结算 | ASR、TTS、OmniHuman 三项均 `succeeded`，再次查询不会重复扣费 |
| 收尾 | 临时用户已停用、刷新令牌已注销、临时管理员设备已撤销 |

验证视频任务：`vid_318e3635770c41aa81a29c7aae04b49f`。

服务器验证产物：`data/release-validation/omni-result.mp4`、`result.json`。本地副本：`.local-dev/deployment-validation/`。

## 修复的上线问题

- 高仿流程读取数字人绑定的音频/有声视频，提取最多 20 秒声音参考；缺失或处理失败则报错。
- 将参考音频经云网关送入 Seed Audio `references[].audio_url`，提示词使用官方 `@音频1` 语法。
- 使用生成音频的实测时长切分视频，保留不足一秒的末尾片段。
- CV 和原 Seedance 使用独立路由，避免数据库旧路由覆盖新配置。
- OmniHuman 按已上传音频的实测时长预留费用，不信任客户端时长；无效输入导致的终态失败释放预留。已成功任务的链接过期不会退款。
- 移除 ASR 结算前覆盖未提交更新的 `db.refresh`。
- Seed Audio 按返回的 `original_duration` 结算，默认按当前官方后付费 1 元/分钟；Seed ASR 2.0 默认 0.8 元/小时，精确到毫秒。既有 Credits 换算和成本占比保持不变。费率来源：https://www.volcengine.com/docs/6561/1359370?lang=zh 。
- 语音生成最多可返回 120 秒，预付费模式先预留最大时长费用，完成后结算实际用量。
- 桌面包补齐 ffprobe，并从随包 FFmpeg 目录查找，客户无需自行安装。

## 验证范围

- 云端测试：原完整套件 47 项通过，新增 ASR 结算回归后相关 API 套件 16 项通过。
- 数字人及声音客户端测试：16 项通过，包括实际 FFmpeg/ffprobe 测试。
- 前端生产构建成功。
- Windows 1.1.4 候选目录已生成并通过发行包隐私审计。
- 随包 ffprobe 实测读取 1 秒 WAV 成功；冻结模块中已确认包含声音参考实现。
- 临时启动完整桌面后端的验证命令被自动审批拒绝，仅返回 `blocked by policy`；未完成安装后桌面界面联调。

## 桌面正式发布尚未完成

候选目录：`electron/dist/candidate-1.1.4/win-unpacked`。
打包配置：`electron/runtime/candidate-1.1.4/builder.json`。

主程序的 Authenticode 状态为 `NotSigned`。项目的 `electron/scripts/assert-signing.cjs` 要求配置 `CSC_LINK` 和 `CSC_KEY_PASSWORD` 后才能正式发布。候选包未替换线上 1.1.3 下载，也未声明为已签名商业发行包。

签名时先生成已签名的目录包，再用 `SZYG_PACKAGED_RESOURCES_DIR` 指向该包的 `resources` 重建完整性清单，确保清单记录的是签名后的二进制哈希。再生成 NSIS 安装包并验证签名及发行审计。不得关闭签名或完整性校验来绕过发布要求。

## 回滚资料

- 备份目录：`/home/ubuntu/szyg-control/backups/release-omni-20260904T104712Z`。
- 数据库：`database.dump`，已用 `pg_restore --list` 验证可读；本次无需 schema 迁移。
- 旧镜像：`szyg-control-control-api:rollback-20260904T104712Z`、`szyg-control-control-worker:rollback-20260904T104712Z`。
- 备份包含旧源码、Compose、Dockerfile、依赖、配置。数据库恢复会丢失备份后的业务数据，仅在确需数据恢复时执行；普通代码回滚使用旧镜像并保留现有数据库。

## 运行代码 SHA-256

已确认容器与本地一致：

```text
app/config.py c61d1ce79d5ee5dc4ca43c0313d84a09dfc4d2a0be8cb5080669fd29e08a7fa3
app/main.py d484c4e10bb07e3b64b0414500e740e18f40b242a3ed8c315f703d3e3df7f84a
app/provider.py 25f8fa26f4b9aee65880ca33787eb4e7d671526d8f0aa195c54a372adefb458a
app/usage_accounting.py 4357ceb936e6328123d2f546cbc9be10b81dde029436fd434531777b4a5f98c9
```
