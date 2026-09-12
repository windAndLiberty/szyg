# OmniHuman1.5 + ASR 部署指南

> 当前上线状态、凭据验证和发布限制见 [2026-09-04 部署记录](DEPLOYMENT-2026-09-04.md)。`video.presenter` 仍用于原普通视频流程，不能改为 CV req_key。

> 适用 control-plane v1.x，用于把 `video.omnihuman`（OmniHuman1.5）、`video.subject_detection`（主体检测）、`speech.asr`（录音文件识别）从火山方舟控制台开通到本地后端调用全链路。

## 1. 火山引擎控制台开通清单

| 能力 | 控制台入口 | 用途 | 必填参数 |
|---|---|---|---|
| OmniHuman1.5 | 控制台 → 人工智能 → 即梦 AI → 详情 | 数字人视频生成 | 控制台 → 我的 → 在线推理 → OmniHuman1.5 |
| 录音文件识别（大模型） | 控制台 → 语音技术 → 服务管理 | ASR 字幕提取 | 开通服务后创建 APP Key |
| （可选）主体检测 | 与 OmniHuman 同服务 | 多主体场景 mask | 无 |

CV 使用 IAM AK/SK 签名，IAM 权限与具体服务开通状态都需有效；不是每开通一项服务就生成一对密钥。Secret Access Key 按控制台原始字符串保存，不做 Base64 解码。ASR 的 X-Api-Key 授权需单独实测，不能从 TTS 可用推断。当前服务器已有凭据已通过真实调用验证。

## 2. 环境变量

在 control-plane 部署环境（Docker / 物理机 / systemd 单元）配置：

```bash
# 视觉 CV 平台（OmniHuman1.5、主体检测）
CONTROL_PROVIDER_CV_ACCESS_KEY=AKLTxxxxxxxxxxxxxx
CONTROL_PROVIDER_CV_SECRET_KEY=xxxxxxxxxxxxxxxxxxxx==
CONTROL_PROVIDER_CV_BASE_URL=https://visual.volcengineapi.com
CONTROL_PROVIDER_CV_REGION=cn-north-1

# 录音文件识别 ASR
CONTROL_PROVIDER_ASR_APP_KEY=1234567890abcdef
CONTROL_PROVIDER_ASR_RESOURCE_ID=volc.seedasr.auc
CONTROL_PROVIDER_ASR_BASE_URL=https://openspeech.bytedance.com

# 模型别名（已预置默认值）
MODEL_VIDEO_OMNIHUMAN=jimeng_realman_avatar_picture_omni_v15
MODEL_SUBJECT_DETECTION=jimeng_realman_avatar_object_detection
MODEL_SPEECH_ASR=volc.seedasr.auc
```

启动时 control-plane 会自动在 `ModelRoute` 表中补建缺失的能力映射；已有数据库路由需通过管理接口核对，不能假定环境变量会覆盖既有配置。能力映射如下：

| alias | 默认 provider_model | 行为 |
|---|---|---|
| `video.omnihuman` | jimeng_realman_avatar_picture_omni_v15 | 走 CV 平台 V4 签名 |
| `video.subject_detection` | jimeng_realman_avatar_object_detection | 同步调用，不计 UsageEvent |
| `speech.asr` | volc.seedasr.auc | 走 openspeech X-Api-Key 鉴权 |

## 3. 端到端冒烟

### 3.1 验证 control-plane 已注册能力

```bash
# 先登录拿到 access_token
TOKEN=$(curl -sS -X POST http://control.example.com/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"...","totp_code":"...","device":{...}}' | jq -r .access_token)

# 列出已注册能力
curl -sS http://control.example.com/api/v1/models/capabilities \
  -H "Authorization: Bearer $TOKEN" | jq '.items[] | select(.alias | test("video.omnihuman|speech.asr|subject_detection"))'
```

期望输出：
```json
{"alias": "video.omnihuman", "available": true}
{"alias": "video.subject_detection", "available": true}
{"alias": "speech.asr", "available": true}
```

`available: false` 表示该能力所需的凭据未配置。

### 3.2 提交 OmniHuman 任务

```bash
# 准备参考素材上传（参考素材端点不变）
REF_URL=$(curl -sS -X POST http://control.example.com/api/v1/inference/references \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/avatar.png" | jq -r .url)

AUDIO_URL=$(curl -sS -X POST http://control.example.com/api/v1/inference/references \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/speech.mp3" | jq -r .url)

# 提交任务
curl -sS -X POST http://control.example.com/api/v1/inference/omni-human/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"capability\": \"video.omnihuman\",
    \"payload\": {
      \"image_url\": \"$REF_URL\",
      \"audio_url\": \"$AUDIO_URL\",
      \"duration\": 4,
      \"output_resolution\": 720,
      \"prompt\": \"人物自然地对镜头说话\"
    },
    \"idempotency_key\": \"remix-001\",
    \"app_version\": \"1.1.4\"
  }"
```

返回 `{"task_id": "...", "status": "queued", "request_id": "..."}`

### 3.3 轮询任务状态

```bash
TASK_ID=...
curl -sS http://control.example.com/api/v1/inference/omni-human/tasks/$TASK_ID \
  -H "Authorization: Bearer $TOKEN"
```

`status: "done"` 时会带 `video_url`（1 小时有效，**请立即下载**）。

### 3.4 测试 ASR

```bash
AUDIO_URL=$(... 复用 3.2 的上传方法 ...)

curl -sS -X POST http://control.example.com/api/v1/inference/asr \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{
    \"capability\": \"speech.asr\",
    \"payload\": {
      \"audio_url\": \"$AUDIO_URL\",
      \"format\": \"mp3\",
      \"language\": \"zh-CN\",
      \"enable_punc\": true,
      \"enable_itn\": true
    },
    \"idempotency_key\": \"asr-001\",
    \"app_version\": \"1.1.4\"
  }"
```

返回：
```json
{
  "text": "完整的口播文字",
  "utterances": [{"text": "完整的", "start_time": 0, "end_time": 500}, ...],
  "duration_ms": 5230,
  "duration_seconds": 6,
  "request_id": "..."
}
```

## 4. 计费规则

| 能力 | 默认上游成本口径 | 预留与结算 |
|---|---|---|
| `video.omnihuman` | 1 元/秒 | 服务端测量上传音频并向上取整预留，单段不能超过 30 秒 |
| `speech.asr` | 0.8 元/小时 | 默认估算 30 秒，可传估算时长，按返回的音频毫秒结算 |
| `speech.tts` / Seed Audio 1.0 | 1 元/分钟 | 预留最多 120 秒成本，按返回的 original_duration 毫秒结算 |
| `video.subject_detection` | 当前未接 UsageEvent | 尚未实现此接口按次扣费 |

这是默认上游成本口径，用户 Credits 还经过既有换算，路由配置可覆盖默认价格。普通 TTS 模型仍可按字符计价，不能套用 Seed Audio 分钟价格。ASR 预留依赖估算时长，不能视为覆盖任意长音频的全部费用。

Seed Audio / ASR 费率核对来源：[火山官方计费文档](https://www.volcengine.com/docs/6561/1359370?lang=zh)，日期 2026-09-04。

参考声音生成使用上传音频，经 Seed Audio 的 `references[].audio_url` 和 `@音频1` 提示词生成新台词。缺少有效参考素材时报错，实际音色效果需要试听验收。

有效 OmniHuman 音频链接必须来自本服务认证上传接口；服务器包含 ffmpeg/ffprobe，并持久化挂载 `./data:/app/data`。成功任务链接过期不退款，已确认失败释放预留。

## 5. 错误码对照

| HTTP 状态 | 含义 | 用户操作 |
|---|---|---|
| 400 `未知的智能能力` | 客户端传了不在白名单的 capability | 升级客户端 |
| 400 `image_url 和 audio_url 必填` | OmniHuman payload 缺字段 | 检查前端提交 |
| 401 `登录状态已失效` | access_token 过期 | 客户端自动重登 |
| 403 `服务授权已到期` | entitlement 过期 | 管理员续期（订阅服务） |
| 429 `Credits 余额不足` | 用户预付费额度用完 | 充值或联系管理员 |
| 429 `Request Has Reached API Concurrent Limit` | 火山侧 QPS 限流 | 等待后重试 |
| 502 `OmniHuman 数字人服务暂时不可用` | CV 平台不可达或业务错误 | 检查 CV 凭据；火山侧 5xx 时降级 |
| 503 `OmniHuman 数字人能力暂未开放` | ModelRoute 未启用或 provider_model 为空 | 管理员启用能力 |
| 504 `asr_timeout` | ASR 240 秒未完成 | 缩短音频（< 4 小时）或稍后重试 |

## 6. 运维检查清单

- [ ] `ProviderBillingDaily` worker 每天拉取昨日账单对账
- [ ] `UsageEvent.status='failed'` 比例 > 5% 时告警（可能上游限流）
- [ ] `Entitlement.valid_until < now + 7 days` 提前告警
- [ ] 火山控制台账户余额 < 100 CNY 告警
- [ ] `ModelRoute` 修改通过 admin 页面或 API 记录到 `AdminAuditLog`
- [ ] 隐式标识（aigc_meta）：参考 `req_json.aigc_meta.producer_id` 注入业务唯一 ID，便于《人工智能生成合成内容标识办法》合规追溯

## 7. 客户化计费调价

通过 admin API 调整 `ModelRoute.config.pricing`：

```bash
curl -sS -X PUT http://control.example.com/api/v1/admin/routes/video.omnihuman \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "provider_model": "jimeng_realman_avatar_picture_omni_v15",
    "enabled": true,
    "config": {
      "pricing": {"seconds_cny": "1.20"},
      "pricing_version": "internal-v1",
      "pricing_source": "https://internal.example.com/pricing"
    }
  }'
```

`settle_usage` 会优先用 `route_config.pricing`，未配置时回退到 `DEFAULT_PRICING` 或 `MODEL_PRICING`。

## 8. 测试覆盖

- `services/control-plane/tests/test_provider.py` — V4 签名、OmniHuman submit/get、主体检测、ASR submit+poll
- `services/control-plane/tests/test_usage_accounting.py` — 1 CNY/秒、ASR 按毫秒、Seed Audio 按时长
- `services/control-plane/tests/test_control_plane.py` — 端到端 `/omni-human/tasks` 端点分流
- `server/tests/unit/test_digital_human_remix.py` — `_remix_transcribe` ASR → vision fallback 链

## 9. 待办（v1.1 之后）

- [ ] 主体检测端点接 admin 控制台（当前无 UI 入口）
- [ ] ASR 限速 1 QPS 调整为可配置
- [ ] 火山 `ListBillDetail` worker 集成（按 `req_key` 维度对账）
- [ ] 隐式标识批量补打工具
- [ ] OmniHuman 失败任务自动重试（指数退避）
- [ ] 离线 license 包中预置 OmniHuman 配额估算

## 10. 桌面正式发布

1.1.4 候选目录已构建并通过隐私审计。正式发布仍须提供 Windows 代码签名证书，通过 `electron/scripts/assert-signing.cjs` 检查，验证最终安装包签名和安装后联调。当前候选包未签名，未替换线上正式下载；完整状态见部署记录。
