# 「域灵」数字员工系统 — TDD构建计划

## 项目概述
基于测试驱动开发(TDD)模式，构建「域灵」数字员工系统的核心Python框架。项目聚焦可运行的核心引擎与各组件集成接口，使用uv进行环境管理。

## 项目边界
- **构建范围**: Agent核心引擎、MCP适配层、组件封装接口、OpenAI兼容API、配置管理
- **不构建**: 外部开源项目本身（Whisper/ComfyUI/Ollama等），而是构建与它们的集成接口
- **架构模式**: 分层解耦，协议化拼装

## Stage 1: 验收测试标准设计
- 设计完整的验收测试标准文档 (acceptance_criteria.md)
- 涵盖所有核心模块的功能性、集成性、非功能性测试
- 为每个测试用例编写可执行的pytest测试代码

## Stage 2: 项目骨架搭建 (uv + Python)
- 初始化uv项目结构
- 创建pyproject.toml、目录结构
- 搭建pytest测试框架
- 配置CI-ready的测试环境

## Stage 3: 核心模块TDD实现
按依赖顺序，对每个模块执行"测试先行，再实现":

### 3.1 配置管理模块 (config)
- 验收测试 → 实现 → 测试通过

### 3.2 Agent核心引擎 (agent_core)
- Planner: 任务拆解与决策
- Memory: FTS5 + 向量检索（长期记忆）
- Skill Registry: 技能模板注册与调用
- Model Router: 多模型调度

### 3.3 MCP协议适配层 (mcp_adapter)
- MCP Server管理（注册/启动/通信）
- MCP Tool调用封装
- computer-use / browser-use 适配器

### 3.4 组件封装接口 (integrations)
- Whisper语音转文字接口
- ComfyUI图像生成接口
- FFmpeg视频处理接口
- Ollama本地LLM接口
- LiteLLM统一网关接口

### 3.5 OpenAI兼容API (api)
- /v1/chat/completions 端点
- /v1/models 端点
- 流式/非流式响应

### 3.6 私域层接口 (private_domain)
- Wechaty消息桥接接口
- 微信消息处理管道

## Stage 4: 集成测试
- 端到端流程测试
- 多模块协作测试
- 数据流验证

## Stage 5: 验收测试执行
- 运行全部测试套件
- 修复失败的测试
- 重复直到100%通过

## 技术栈
- Python 3.12+
- uv (环境管理)
- pytest + pytest-asyncio (测试)
- FastAPI (API层)
- Pydantic (数据模型)
- SQLite FTS5 (全文检索)
- httpx (HTTP客户端)
- aiohttp (异步通信)

## 交付物
- 完整Python项目代码
- 全部通过验收测试
- pyproject.toml (uv安装即用)
- README文档
