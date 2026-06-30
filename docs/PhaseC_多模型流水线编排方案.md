> ⚠️ **本文档已废弃（2026-06-28）**
> 与当前 SSOT 和代码库存在以下矛盾：
> - **Volcano Engine 假设不成立**: 代码库实际使用 ModelScope 集成（`modelscope_client.py`），非火山引擎方舟平台
> - **前端引用过时**: 提及 Chat.vue / Hub.vue / VideoGen.vue 等旧页面（已被合并到 ContentStudio）
> - **Hermes Chat 作为交互入口**: 已被 SuperStaffPanel 替代
> - **ModelRouter 绕过**: 提议的 `VolcEngineClient` 直接调用 API，绕过已有的 `model_router.py` 和 `image_router.py`
> - **Pipeline 文件不存在**: 提议的 `pipelines/ai_video_creator.py` 等文件未创建
> - DAG 流水线概念本身已由 `pipeline_engine.py` 实现，采用不同的提供商架构
>
> **请使用**: `szyg产品功能融合设计.md` M1 模块（内容生产工厂）了解当前 Pipeline 架构
> **不再更新本文档。**

---

# Phase C: 火山引擎多模型流水线编排方案

> **版本**: v1.0 | **日期**: 2026-06-09
>
> 核心目标: 利用火山引擎"一个API调用多个模型"的能力，构建数字员工的端到端多模态流水线编排架构。

---

## 一、火山引擎多模型调用能力调研

### 1.1 方舟平台统一API架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     火山引擎方舟平台                              │
│                     (统一API入口)                                 │
│                                                                  │
│   一个 API Key: sk-xxx                                          │
│   一个 Base URL: https://ark.cn-beijing.volces.com/api/v3        │
│                                                                  │
│   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│   │  文本模型    │ │  图像模型    │ │  视频模型    │              │
│   │ Doubao-pro  │ │ Doubao-image│ │ Doubao-video│              │
│   │ DeepSeek-R1 │ │ SDXL        │ │ Seaweed     │              │
│   │ DeepSeek-V3 │ │ FLUX        │ │             │              │
│   └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │
│          │               │               │                      │
│   ┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐             │
│   │  语音模型    │ │  向量模型    │ │  函数调用    │             │
│   │ Doubao-tts  │ │ Doubao-emb  │ │ FC版本      │             │
│   │ Voice-clone │ │             │ │             │             │
│   └──────┬──────┘ └──────┬──────┘ └──────┬──────┘             │
│          │               │               │                      │
│          └───────────────┴───────────────┘                      │
│                          │                                       │
│                   统一OpenAI兼容接口                              │
│                   chat.completions                               │
│                   images.generate                                │
│                   audio.speech                                   │
│                   embeddings.create                              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 关键特性

| 特性 | 说明 | 对数字员工的价值 |
|------|------|----------------|
| **统一入口** | 一个API Key调用所有模型 | 简化配置，降低维护成本 |
| **推理接入点** | 每个模型独立Endpoint ID | 灵活切换模型版本 |
| **函数调用** | Doubao-pro支持FC | 让LLM直接调用89个MCP工具 |
| **多模态串联** | 文本→图像→视频→语音 | 端到端内容创作 |
| **异步任务** | 视频生成异步返回 | 支持长耗时任务编排 |
| **批量嵌入** | 批量文本向量化 | 知识库RAG优化 |

---

## 二、流水线编排架构设计

### 2.1 核心概念

```
Pipeline (流水线)
  ├── DAG (有向无环图)
  │     ├── Node (节点) → 一个AIGC任务
  │     │     ├── type: text|image|video|audio|embedding|skill
  │     │     ├── model: 模型ID
  │     │     ├── prompt_template: 提示词模板
  │     │     └── params: 执行参数
  │     │
  │     └── Edge (边) → 数据依赖关系
  │           ├── from → to
  │           └── data_mapping: 输出→输入映射
  │
  ├── Context (上下文) → 节点间数据传递
  │     ├── inputs: 用户原始输入
  │     ├── outputs: {node_id: result}
  │     └── artifacts: 生成的文件路径
  │
  └── Executor (执行器) → 实际调度
        ├── 串行/并行执行
        ├── 失败重试
        └── 超时控制
```

### 2.2 数字员工流水线类型

#### 类型1: AI短视频流水线 (短视频创作)

```
用户输入: "AI发展趋势"
  │
  ▼
┌─────────────────┐
│ Node-1: 脚本生成 │ ← LLM (Doubao-pro)
│ text → script   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐  ┌─────────────────┐
│ Node-2: 封面生成 │  │ Node-3: 分镜视频 │
│ image (并行)    │  │ video (并行)    │
│ Doubao-image    │  │ Doubao-video    │
└────────┬────────┘  └────────┬────────┘
         │                    │
         └────────┬───────────┘
                  ▼
         ┌─────────────────┐
         │ Node-4: 配音生成 │
         │ audio           │
         │ Doubao-tts      │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ Node-5: 合成成片 │
         │ skill (FFmpeg)  │
         └─────────────────┘
                  │
                  ▼
         输出: 完整AI短视频
```

#### 类型2: 智能内容创作流水线 (图文/公众号)

```
用户输入: "新产品发布"
  │
  ▼
┌─────────────────┐
│ Node-1: 内容策略 │ ← LLM (DeepSeek-R1)
└────────┬────────┘
         │
         ▼
┌─────────────────┐  ┌─────────────────┐
│ Node-2: 文案生成 │  │ Node-3: 配图生成 │
│ text (并行)     │  │ image (并行)    │
│ Doubao-pro      │  │ Doubao-image    │
└────────┬────────┘  └────────┬────────┘
         │                    │
         └────────┬───────────┘
                  ▼
         ┌─────────────────┐
         │ Node-4: 排版输出 │
         │ skill (docx/    │
         │   pptx)         │
         └─────────────────┘
```

#### 类型3: 智能营销流水线 (多平台分发)

```
用户输入: "618促销活动"
  │
  ▼
┌─────────────────┐
│ Node-1: 营销策略 │ ← LLM (Doubao-pro)
└────────┬────────┘
         │
         ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Node-2: 抖音文案 │  │ Node-3: 小红书  │  │ Node-4: 公众号  │
│ text (并行)     │  │ 图文 (并行)     │  │ 长文 (并行)     │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Node-5: 抖音视频 │  │ Node-6: 小红书  │  │ Node-7: 公众号  │
│ video           │  │ 封面图          │  │ 配图            │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         └────────┬───────────┴────────────┬──────┘
                  ▼                          ▼
         ┌─────────────────┐       ┌─────────────────┐
         │ Node-8: 定时发布 │       │ Node-9: 数据    │
         │ scheduler_create │       │ 分析           │
         └─────────────────┘       └─────────────────┘
```

---

## 三、实现方案

### 3.1 模块结构

```
server/szyg/
├── pipeline_engine.py          # 流水线编排引擎核心
├── pipelines/
│   ├── __init__.py
│   ├── digital_worker.py        # 数字员工多模态流水线定义
│   ├── ai_video_pipeline.py     # AI短视频流水线
│   ├── content_pipeline.py      # 智能内容创作流水线
│   └── marketing_pipeline.py    # 智能营销流水线
├── api/
│   ├── pipeline_endpoint.py     # Pipeline REST API
│   └── video_endpoint.py        # 视频API (升级)
└── mcp_servers/
    └── pipeline_mcp.py          # Pipeline MCP工具
```

### 3.2 Pipeline Engine API

```python
from szyg.pipeline_engine import Pipeline, PipelineNode, PipelineExecutor

# 定义流水线
pipeline = Pipeline(name="AI短视频", description="从主题到成片的AI视频创作")

# 添加节点
pipeline.add_node(PipelineNode(
    id="script",
    type="text",
    model="doubao-pro-128k",
    prompt_template="为主题'{topic}'创作一个{duration}秒的短视频脚本...",
))
pipeline.add_node(PipelineNode(
    id="cover",
    type="image",
    model="doubao-image",
    prompt_template="{script.cover_prompt}",
    depends_on=["script"],
    data_mapping={"script.cover_prompt": "prompt"},
))
pipeline.add_node(PipelineNode(
    id="voice",
    type="audio",
    model="doubao-tts",
    prompt_template="{script.narration}",
    depends_on=["script"],
    params={"emotion": "happy"},
))

# 执行流水线
executor = PipelineExecutor(volcengine_client)
result = await executor.run(pipeline, inputs={"topic": "AI发展趋势", "duration": 30})
```

### 3.3 与现有系统集成

```
现有系统                  Phase C新增
┌──────────────┐         ┌─────────────────────────┐
│ Hermes Chat  │ ──────→ │ Pipeline MCP工具        │
│ (89个工具)   │         │ - pipeline_list          │
└──────────────┘         │ - pipeline_create        │
                         │ - pipeline_execute       │
                         │ - pipeline_status        │
                         └─────────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
              ┌─────────────────┐   ┌─────────────────┐
              │ Pipeline Engine │   │ VolcEngineClient│
              │ (DAG编排)       │   │ (多模型调度)     │
              └────────┬────────┘   └─────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    ┌────────┐  ┌────────┐  ┌────────┐
    │ 文本   │  │ 图像   │  │ 视频   │
    │ 语音   │  │ 嵌入   │  │ 技能   │
    └────────┘  └────────┘  └────────┘
```

---

## 四、关键技术决策

### 4.1 为什么需要Pipeline引擎而不是直接调用？

| 场景 | 直接调用 | Pipeline引擎 |
|------|---------|-------------|
| 单任务 | 简单直接 | 也能做，但大材小用 |
| 多步骤依赖 | 代码硬编码 | DAG可视化配置 |
| 并行执行 | 手动async.gather | 自动依赖分析+并行调度 |
| 失败恢复 | 手动重试 | 自动重试+断点续传 |
| 进度监控 | 无 | 实时进度+中间产物 |
| 复用性 | 低 | 模板化流水线定义 |

### 4.2 并行 vs 串行策略

```python
# 自动依赖分析后并行执行
# Node-2 和 Node-3 都依赖 Node-1，但互相独立 → 并行
# Node-4 依赖 Node-2 和 Node-3 → 串行等待

async def _execute_dag(nodes):
    # 拓扑排序
    ready = [n for n in nodes if not n.dependencies]
    pending = [n for n in nodes if n.dependencies]
    done = {}

    while ready:
        # 并行执行所有就绪节点
        tasks = [self._execute_node(n, done) for n in ready]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for n, r in zip(ready, results):
            done[n.id] = r

        # 更新待执行节点
        ready, pending = self._update_ready(pending, done)

    return done
```

### 4.3 上下文传递机制

```python
# Node-1 输出: {"script": {...}, "cover_prompt": "...", "narration": "..."}
# Node-2 输入映射: {"cover_prompt": "prompt"} → prompt = "..."
# Node-3 输入映射: {"narration": "text"} → text = "..."

class PipelineContext:
    def resolve(self, node: PipelineNode) -> dict:
        """解析节点的输入参数，从上下文中提取依赖数据"""
        params = dict(node.params)
        for key, mapping in node.data_mapping.items():
            # mapping: "script.narration" → 从上下文中提取
            value = self._get_by_path(mapping)
            params[key] = value
        return params
```

---

## 五、预期效果

### 使用示例

```
用户: 帮我创作一个关于"AI改变生活"的短视频

Hermes: [pipeline_execute]
  1. 生成脚本...
  2. 生成封面图... (并行)
  3. 生成视频片段... (并行)
  4. 生成配音...
  5. 合成最终视频...

输出: 视频文件 + 脚本 + 封面 + 配音文件

用户: 再帮我写配套的小红书文案和配图

Hermes: [pipeline_execute: 内容创作流水线]
  1. 分析视频内容...
  2. 生成小红书文案... (并行)
  3. 生成配图... (并行)

输出: 小红书文案 + 配图

用户: 帮我安排发布计划

Hermes: [pipeline_execute: 营销流水线]
  1. 创建抖音发布任务...
  2. 创建小红书发布任务...
  3. 创建公众号发布任务...

输出: 3个定时发布任务已创建
```

### 效率提升

| 指标 | 之前 | Phase C后 |
|------|------|----------|
| 短视频创作 | 5-10分钟(手动分步) | 2-5分钟(一键流水线) |
| 多平台内容 | 30分钟(逐个创作) | 5分钟(并行流水线) |
| 操作步骤 | 10+次函数调用 | 1次pipeline调用 |
| 人工干预 | 每步需要确认 | 一次性输入主题 |

---

*本文档指导 Phase C 的实现。核心是利用火山引擎"一个API Key调用多个模型"的能力，通过Pipeline编排引擎实现数字员工的端到端自动化。*
