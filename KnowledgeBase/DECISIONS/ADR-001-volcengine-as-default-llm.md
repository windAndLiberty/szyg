# ADR-001: 选择火山引擎方舟作为默认 LLM 后端

## 状态

Accepted

## 背景

域灵系统需要集成本地 LLM 和云端 LLM 两种推理后端，以平衡成本、延迟和模型质量。候选方案：

1. **火山引擎方舟** — OpenAI 兼容 API，统一多模态 AIGC (文本/图像/视频/语音/向量)
2. **Ollama** — 本地 LLM，免费但受限于硬件 (GTX 1650 4GB)
3. **LiteLLM** — 自托管网关，需额外部署

## 决策

选择**火山引擎方舟**作为默认 LLM 后端 (`default_backend: volcengine`)，Ollama 作为降级备选。

## 理由

- **统一多模态**: 一个 API Key 调用文本/图像/视频/语音/向量嵌入，减少集成成本
- **模型丰富**: doubao-seed-2-0-pro (旗舰) / lite / mini / flash / code 多档可选
- **OpenAI 兼容**: 直接使用 `openai` Python SDK，无需额外适配
- **免费额度**: 火山方舟提供免费额度，降低初期成本
- **本地降级**: Ollama 保持可用，网络中断或额度耗尽时自动降级

## 影响

- `config.yaml` 中 `llm.default_backend: volcengine`
- 依赖 `openai>=2.43.0` (OpenAI SDK 兼容调用)
- 需要火山引擎 API Key (存储在 `config.yaml` 或 `secrets.yaml`)
- 模型 ID 通过 `endpoints` 配置映射 (如 `doubao-pro-128k` → `doubao-seed-2-0-pro-260215`)
- 不可用模型: deepseek-r1/v3 系列, kimi-k2 系列, qwen/glm 开源系列 (方舟不支持)
