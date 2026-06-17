# 「域灵」数字员工系统 - 验收测试标准文档

## 1. 概述

本文档定义了「域灵」数字员工系统（AI Agent集成平台）的完整验收测试标准，涵盖功能性、集成性、非功能性及测试覆盖率要求。所有标准均对应可执行的pytest测试用例。

---

## 2. 功能性验收标准

### 2.1 Config模块 (`yuling.config`)

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| CFG-001 | 系统应能加载内置默认配置，所有必需字段均有合理默认值 | P0 | `test_load_default_config` |
| CFG-002 | 系统应支持从YAML配置文件加载配置项 | P0 | `test_load_from_yaml` |
| CFG-003 | 环境变量应能覆盖YAML和默认配置值 | P0 | `test_env_var_override` |
| CFG-004 | 无效配置值（如错误类型、超出范围）应触发Pydantic ValidationError | P0 | `test_config_validation_error` |
| CFG-005 | 配置优先级必须为：默认值 < YAML文件 < 环境变量 | P0 | `test_config_precedence` |
| CFG-006 | 支持嵌套配置结构（如model.ollama.host, memory.sqlite.path） | P1 | `test_nested_config` |
| CFG-007 | 敏感信息（如API密钥）应通过环境变量注入，不硬编码 | P1 | `test_sensitive_from_env` |

### 2.2 Agent Core - Planner模块 (`yuling.agent_core.planner`)

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| PLN-001 | 给定instruction字符串，Planner应返回结构化的TaskPlan对象 | P0 | `test_plan_simple_task` |
| PLN-002 | 复杂instruction应被拆解为多个有序的sub-tasks | P0 | `test_plan_complex_task` |
| PLN-003 | TaskPlan应包含每个sub-task的依赖关系和执行顺序 | P0 | `test_task_dependencies` |
| PLN-004 | 空或仅空白字符的instruction应返回空TaskPlan或合理错误 | P0 | `test_plan_empty_instruction` |
| PLN-005 | 模糊instruction应返回尽力而为的plan或请求澄清 | P1 | `test_plan_ambiguous_instruction` |
| PLN-006 | 单个任务的plan应包含至少一个step | P0 | `test_plan_single_step` |

### 2.3 Agent Core - Memory模块 (`yuling.agent_core.memory`)

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| MEM-001 | 应支持存储带content和metadata的记忆条目 | P0 | `test_store_and_retrieve` |
| MEM-002 | 应支持基于内容的全文搜索（SQLite FTS5） | P0 | `test_search_by_content` |
| MEM-003 | 应支持基于metadata的过滤搜索 | P0 | `test_search_by_metadata` |
| MEM-004 | 应支持更新已有记忆条目 | P0 | `test_update_entry` |
| MEM-005 | 应支持删除记忆条目 | P0 | `test_delete_entry` |
| MEM-006 | 数据库关闭后重新打开，数据应保持不变（持久化） | P0 | `test_persistence` |
| MEM-007 | 搜索结果应按相关性排序（FTS5 rank） | P0 | `test_search_ranking` |
| MEM-008 | 并发写入操作应线程/协程安全 | P0 | `test_concurrent_access` |
| MEM-009 | 应支持向量检索存储（向量相似度搜索） | P1 | `test_vector_search` |
| MEM-010 | 空搜索应返回空列表而非异常 | P1 | `test_search_no_results` |

### 2.4 Agent Core - SkillRegistry模块 (`yuling.agent_core.skill_registry`)

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| SKL-001 | 应支持注册带名称、描述、处理函数的技能 | P0 | `test_register_skill` |
| SKL-002 | 应能列出所有已注册技能 | P0 | `test_list_skills` |
| SKL-003 | 应能通过名称执行已注册技能并返回结果 | P0 | `test_execute_skill` |
| SKL-004 | 执行不存在的技能应抛出SkillNotFoundError | P0 | `test_execute_nonexistent_skill` |
| SKL-005 | 技能参数验证失败应抛出ValidationError | P0 | `test_skill_parameter_validation` |
| SKL-006 | 应支持注销已注册技能 | P0 | `test_unregister_skill` |
| SKL-007 | 重复注册同名技能应覆盖或抛出DuplicateSkillError | P0 | `test_register_duplicate` |
| SKL-008 | 技能执行异常应被捕获并包装为SkillExecutionError | P1 | `test_skill_execution_error` |

### 2.5 Agent Core - ModelRouter模块 (`yuling.agent_core.model_router`)

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| MRT-001 | 应能根据模型名称路由请求到Ollama后端 | P0 | `test_route_to_ollama` |
| MRT-002 | 应能根据模型名称路由请求到LiteLLM后端 | P0 | `test_route_to_litellm` |
| MRT-003 | 主模型失败时应自动降级到备用模型 | P0 | `test_fallback_when_primary_fails` |
| MRT-004 | 应能获取所有可用模型列表 | P0 | `test_get_available_models` |
| MRT-005 | 无效模型请求应返回ModelNotFoundError | P0 | `test_invalid_model_request` |
| MRT-006 | 应支持流式响应（SSE） | P0 | `test_streaming_response` |
| MRT-007 | 所有后端失败时应返回明确的错误信息 | P0 | `test_all_backends_fail` |

### 2.6 MCP适配层 (`yuling.mcp`)

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| MCP-001 | 应支持添加MCP Server配置（名称、命令、参数、环境变量） | P0 | `test_add_server` |
| MCP-002 | 应支持启动和停止MCP Server进程 | P0 | `test_start_stop_server` |
| MCP-003 | 应能通过Server调用Tool并获取结果 | P0 | `test_call_tool` |
| MCP-004 | Tool调用超时应抛出TimeoutError | P0 | `test_call_tool_timeout` |
| MCP-005 | 调用不存在Server的Tool应抛出ServerNotFoundError | P0 | `test_server_not_found` |
| MCP-006 | Server进程异常退出应能被检测并报告 | P1 | `test_server_crash` |
| MCP-007 | 应支持列举Server提供的所有Tools | P1 | `test_list_tools` |

### 2.7 集成接口 (`yuling.integrations`)

#### 2.7.1 WhisperClient

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| WSP-001 | 应能发送音频文件并返回转录文本 | P0 | `test_whisper_transcribe` |
| WSP-002 | 不存在的音频文件应返回FileNotFoundError | P0 | `test_whisper_transcribe_file_not_found` |
| WSP-003 | 服务不可用时应有重试机制 | P1 | `test_whisper_retry` |

#### 2.7.2 ComfyUIClient

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| CMF-001 | 应能提交工作流到ComfyUI队列 | P0 | `test_comfyui_generate_cover` |
| CMF-002 | 应能查询队列状态和获取生成结果 | P0 | `test_comfyui_queue_and_get` |
| CMF-003 | 无效工作流应返回错误信息 | P1 | `test_comfyui_invalid_workflow` |

#### 2.7.3 FFmpegClient

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| FFM-001 | 应能执行批处理命令编辑视频 | P0 | `test_ffmpeg_batch_edit` |
| FFM-002 | 应能从视频提取音频轨道 | P0 | `test_ffmpeg_extract_audio` |
| FFM-003 | 无效输入文件应返回FFmpegError | P0 | `test_ffmpeg_invalid_input` |

#### 2.7.4 OllamaClient

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| OLL-001 | 应能发送chat请求并获取响应 | P0 | `test_ollama_chat` |
| OLL-002 | 应能发送generate请求并获取响应 | P0 | `test_ollama_generate` |
| OLL-003 | 应支持流式响应 | P0 | `test_ollama_stream` |
| OLL-004 | 服务不可用时应触发降级 | P1 | `test_ollama_unavailable` |

#### 2.7.5 LiteLLMClient

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| LTL-001 | 应能发送同步completion请求 | P0 | `test_litellm_completion` |
| LTL-002 | 应能发送异步acompletion请求 | P0 | `test_litellm_acompletion` |
| LTL-003 | 应支持流式响应 | P0 | `test_litellm_stream` |
| LTL-004 | API密钥无效应返回AuthenticationError | P0 | `test_litellm_auth_error` |

#### 2.7.6 通用客户端行为

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| CLN-001 | HTTP请求失败时应有指数退避重试 | P0 | `test_client_retry_on_failure` |
| CLN-002 | 请求超时应抛出TimeoutException | P0 | `test_client_timeout` |
| CLN-003 | 应有可配置的连接池和超时参数 | P1 | `test_client_configurable_timeout` |

### 2.8 OpenAI兼容API (`yuling.api`)

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| API-001 | `POST /v1/chat/completions` 应支持非流式聊天补全 | P0 | `test_chat_completion_non_stream` |
| API-002 | `POST /v1/chat/completions` 应支持SSE流式响应 | P0 | `test_chat_completion_stream` |
| API-003 | `GET /v1/models` 应返回可用模型列表 | P0 | `test_list_models` |
| API-004 | `GET /health` 应返回系统健康状态 | P0 | `test_health_check` |
| API-005 | 无效请求应返回HTTP 422 | P0 | `test_chat_completion_invalid_request` |
| API-006 | 模型服务错误应返回HTTP 502/503 | P0 | `test_chat_completion_model_error` |
| API-007 | 如配置了API密钥，无效密钥应返回HTTP 401 | P0 | `test_api_authentication` |
| API-008 | 应支持OpenAI兼容的请求/响应格式 | P0 | `test_openai_format_compatibility` |

### 2.9 私域层 - WechatyBridge (`yuling.wechaty`)

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| WCT-001 | 应能接收并解析文本消息 | P0 | `test_handle_text_message` |
| WCT-002 | 完整消息管道应：接收→解析→Agent处理→发送回复 | P0 | `test_handle_message_pipeline` |
| WCT-003 | 应能主动发送消息到指定联系人/群 | P0 | `test_send_message` |
| WCT-004 | 非文本消息（图片、语音）应被适当处理或忽略 | P1 | `test_handle_non_text_message` |

---

## 3. 集成验收标准

### 3.1 端到端集成

| ID | 验收标准 | 优先级 | 对应测试 |
|----|---------|--------|---------|
| E2E-001 | 语音指令完整链路：语音文件→Whisper转录→Planner拆解→Agent执行→返回结果 | P0 | `test_voice_to_content_pipeline` |
| E2E-002 | Agent→MCP→Integration调用链：Agent决策→MCP Tool调用→Integration Client执行 | P0 | `test_agent_to_mcp_to_integration` |
| E2E-003 | 完整聊天API流程：HTTP请求→API层→ModelRouter→Ollama/LiteLLM→流式/非流式响应 | P0 | `test_full_chat_api_flow` |

### 3.2 模块间集成

| ID | 验收标准 | 优先级 |
|----|---------|--------|
| INT-001 | Config变更应能被所有模块热加载或重启后生效 | P1 |
| INT-002 | Memory模块应能被Planner和SkillRegistry共同访问 | P0 |
| INT-003 | ModelRouter选择模型失败时，Planner应能调整策略 | P1 |
| INT-004 | MCP Server崩溃不应影响主应用和其他Server | P0 |
| INT-005 | API层请求超时应不阻塞Agent Core的其他任务 | P0 |

---

## 4. 非功能性验收标准

### 4.1 性能标准

| ID | 验收标准 | 目标值 | 测试方法 |
|----|---------|--------|---------|
| PER-001 | API响应时间（非流式） | P99 < 2s | `test_api_response_time` |
| PER-002 | 流式首token延迟 | P99 < 1s | `test_streaming_first_token_latency` |
| PER-003 | Memory搜索响应时间 | P99 < 500ms | `test_memory_search_performance` |
| PER-004 | 并发10请求吞吐量 | QPS ≥ 5 | `test_concurrent_throughput` |

### 4.2 可靠性标准

| ID | 验收标准 | 测试方法 |
|----|---------|---------|
| REL-001 | Ollama服务失败时自动降级到LiteLLM | `test_fallback_when_primary_fails` |
| REL-002 | MCP Server崩溃后被自动重启或标记为不可用 | `test_server_crash_recovery` |
| REL-003 | 数据库损坏时能优雅降级，不导致系统崩溃 | `test_database_corruption_recovery` |
| REL-004 | 内存使用在长时间运行后保持稳定（无泄漏） | `test_memory_leak` |

### 4.3 并发标准

| ID | 验收标准 | 测试方法 |
|----|---------|---------|
| CON-001 | 同时处理10个聊天请求不丢失响应 | `test_concurrent_chat_requests` |
| CON-002 | 并发Memory写入不导致数据损坏 | `test_concurrent_access` |
| CON-003 | 流式和非流式请求可同时处理 | `test_mixed_streaming_requests` |

---

## 5. 测试覆盖率要求

### 5.1 覆盖率指标

| 指标 | 最低要求 | 目标 |
|------|---------|------|
| 行覆盖率 (Line Coverage) | ≥ 90% | ≥ 95% |
| 分支覆盖率 (Branch Coverage) | ≥ 80% | ≥ 85% |
| 函数覆盖率 (Function Coverage) | ≥ 95% | 100% |

### 5.2 模块覆盖率目标

| 模块 | 行覆盖率目标 | 分支覆盖率目标 |
|------|-------------|---------------|
| `yuling.config` | 95% | 90% |
| `yuling.agent_core.planner` | 90% | 85% |
| `yuling.agent_core.memory` | 95% | 90% |
| `yuling.agent_core.skill_registry` | 95% | 90% |
| `yuling.agent_core.model_router` | 93% | 85% |
| `yuling.mcp` | 90% | 80% |
| `yuling.integrations.*` | 90% | 80% |
| `yuling.api` | 93% | 85% |
| `yuling.wechaty` | 85% | 75% |
| `yuling.main` | 80% | 70% |

---

## 6. 测试执行策略

### 6.1 测试分层

```
单元测试（test_*）
  ├── 无需外部服务，全部使用Mock
  ├── 使用pytest + pytest-asyncio
  ├── 使用respx/pytest-httpx mock HTTP
  └── 目标：< 30秒执行完成

集成测试（test_integration_*）
  ├── 可能需要本地Docker服务
  ├── 标记为 @pytest.mark.integration
  └── 目标：< 5分钟执行完成

端到端测试（test_e2e_*）
  ├── 完整链路验证
  ├── 标记为 @pytest.mark.e2e
  └── 目标：< 10分钟执行完成
```

### 6.2 CI/CD集成要求

- 每次提交自动运行单元测试
- 每日运行完整测试套件（单元+集成）
- 发布前运行端到端测试
- 覆盖率报告生成并上传

---

## 7. 测试用例统计

| 模块 | 预计测试用例数 | 文件 |
|------|---------------|------|
| Config | 5+ | `test_config.py` |
| Memory | 8+ | `test_memory.py` |
| SkillRegistry | 7+ | `test_skill_registry.py` |
| ModelRouter | 6+ | `test_model_router.py` |
| MCP | 5+ | `test_mcp.py` |
| Integrations | 12+ | `test_integrations.py` |
| API | 7+ | `test_api.py` |
| Wechaty | 3+ | `test_wechaty.py` |
| End-to-End | 3+ | `test_e2e.py` |
| **总计** | **56+** | **9个测试文件** |

---

*文档版本: v1.0*
*最后更新: 2024*
