"""
Pipeline Engine — 多模型AIGC流水线编排引擎

利用火山引擎"一个API调用多个模型"的能力，构建数字员工的端到端多模态流水线。

核心概念:
  Pipeline      → 流水线定义 (DAG)
  PipelineNode  → 节点定义 (文本/图像/视频/语音/技能)
  PipelineEdge  → 依赖边 (数据映射)
  PipelineContext → 上下文 (中间结果传递)
  PipelineExecutor → 执行器 (调度执行)

用法:
    pipeline = Pipeline(name="AI短视频", description="从主题到成片")
    pipeline.add_node(PipelineNode(id="script", type="text", model="doubao-pro-128k", ...))
    pipeline.add_node(PipelineNode(id="cover", type="image", model="doubao-image", depends_on=["script"], ...))

    executor = PipelineExecutor(client)
    result = await executor.run(pipeline, inputs={"topic": "AI发展趋势"})
"""

import asyncio
import json
import logging
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from szyg.media_storage import get_media_output_dir

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict | None:
    """Extract JSON object from LLM response (may be wrapped in markdown fences)."""
    import re
    # Strip markdown code fences
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', text.strip())
    cleaned = re.sub(r'\n?\s*```\s*$', '', cleaned)
    # Find the outermost JSON object
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass
    # Try parsing the whole text as JSON
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None


# ── Data Classes ────────────────────────────────────────────────────────

class NodeType(str, Enum):
    TEXT = "text"         # LLM文本生成
    IMAGE = "image"       # AI图像生成
    VIDEO = "video"       # AI视频生成
    AUDIO = "audio"       # AI语音合成
    EMBEDDING = "embedding"  # 向量嵌入
    SKILL = "skill"       # 系统技能调用 (现有89个工具)


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineNode:
    """流水线节点定义"""
    id: str
    type: NodeType
    model: str = ""
    name: str = ""
    description: str = ""
    prompt_template: str = ""       # 提示词模板，支持 {input.xxx} {node_id.field} 占位符
    params: dict = field(default_factory=dict)       # 固定参数
    data_mapping: dict = field(default_factory=dict)  # 输入映射: {param_name: "source.field"}
    depends_on: list[str] = field(default_factory=list)  # 依赖节点ID列表
    timeout: int = 120              # 超时秒数
    retries: int = 1                # 重试次数
    optional: bool = False          # 是否可选（失败不中断流水线）
    output_key: str = ""            # 输出存储键，空则使用节点id

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = NodeType(self.type)
        if not self.name:
            self.name = self.id
        if not self.output_key:
            self.output_key = self.id


@dataclass
class PipelineEdge:
    """依赖边 (隐式，通过depends_on定义)"""
    from_node: str
    to_node: str
    data_mapping: dict = field(default_factory=dict)


@dataclass
class PipelineContext:
    """流水线执行上下文"""
    pipeline_id: str
    inputs: dict = field(default_factory=dict)        # 用户原始输入
    outputs: dict = field(default_factory=dict)       # 节点输出 {node_id: result}
    artifacts: dict = field(default_factory=dict)     # 文件产物 {node_id: [path]}
    status: dict = field(default_factory=dict)        # 节点状态 {node_id: status}
    errors: dict = field(default_factory=dict)        # 错误信息 {node_id: error}
    start_time: str = ""
    end_time: str = ""

    def get(self, path: str, default=None) -> Any:
        """按路径获取上下文数据，支持:
          - "inputs.topic" → self.inputs["topic"]
          - "script.title" → self.outputs["script"]["title"]
          - "cover.path" → self.outputs["cover"]["path"]
        """
        parts = path.split(".")
        if len(parts) < 2:
            return default

        source, *rest = parts
        rest_path = ".".join(rest)

        if source == "inputs":
            data = self.inputs
        elif source in self.outputs:
            data = self.outputs[source]
        elif source in self.artifacts:
            data = self.artifacts[source]
        else:
            return default

        # 递归获取嵌套字段
        current = data
        for key in rest:
            if isinstance(current, dict):
                current = current.get(key, default)
            else:
                return default
        return current

    def set_output(self, node_id: str, result: Any):
        self.outputs[node_id] = result

    def set_artifacts(self, node_id: str, paths: list[str]):
        self.artifacts[node_id] = paths

    def set_status(self, node_id: str, status: NodeStatus):
        self.status[node_id] = status.value

    def set_error(self, node_id: str, error: str):
        self.errors[node_id] = error

    def to_dict(self) -> dict:
        return {
            "pipeline_id": self.pipeline_id,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "artifacts": self.artifacts,
            "status": self.status,
            "errors": self.errors,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


@dataclass
class Pipeline:
    """流水线定义"""
    name: str
    description: str = ""
    nodes: list[PipelineNode] = field(default_factory=list)
    inputs_schema: dict = field(default_factory=dict)   # 输入参数定义
    outputs_schema: list[str] = field(default_factory=list)  # 输出键列表

    def add_node(self, node: PipelineNode) -> "Pipeline":
        self.nodes.append(node)
        return self

    def get_node(self, node_id: str) -> PipelineNode | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def topological_sort(self) -> list[list[PipelineNode]]:
        """拓扑排序，返回分层结构（每层内部节点可并行）。"""
        # Build dependency graph
        node_map = {n.id: n for n in self.nodes}
        in_degree = {n.id: len(n.depends_on) for n in self.nodes}
        dependents = {n.id: [] for n in self.nodes}
        for n in self.nodes:
            for dep in n.depends_on:
                if dep in dependents:
                    dependents[dep].append(n.id)

        # Layer-by-layer
        layers = []
        remaining = set(n.id for n in self.nodes)
        while remaining:
            layer = [node_map[nid] for nid in remaining if in_degree[nid] == 0]
            if not layer:
                # Cycle detected
                raise ValueError("Pipeline has circular dependencies")
            layers.append(layer)
            for node in layer:
                remaining.remove(node.id)
                for dep_id in dependents[node.id]:
                    in_degree[dep_id] -= 1
        return layers


# ── Pipeline Executor ───────────────────────────────────────────────────

class PipelineExecutor:
    """流水线执行器 — 实际调度Pipeline的执行。

    支持:
      - 拓扑排序后的分层并行执行
      - 节点超时控制
      - 失败重试
      - 可选节点失败不中断
      - 实时进度回调
    """

    def __init__(self, volcengine_client=None, timeout: int = 600):
        self.client = volcengine_client
        self.timeout = timeout
        self._handlers: dict[NodeType, Callable] = {
            NodeType.TEXT: self._execute_text,
            NodeType.IMAGE: self._execute_image,
            NodeType.VIDEO: self._execute_video,
            NodeType.AUDIO: self._execute_audio,
            NodeType.EMBEDDING: self._execute_embedding,
            NodeType.SKILL: self._execute_skill,
        }

    # ── Public API ──────────────────────────────────────────────────────

    async def run(
        self,
        pipeline: Pipeline,
        inputs: dict,
        progress_callback: Callable | None = None,
    ) -> PipelineContext:
        """执行流水线。

        Args:
            pipeline: 流水线定义
            inputs: 用户输入参数
            progress_callback: 进度回调函数(node_id, status, message)

        Returns:
            PipelineContext 包含所有执行结果
        """
        ctx = PipelineContext(
            pipeline_id=str(uuid.uuid4())[:8],
            inputs=deepcopy(inputs),
            start_time=datetime.now().isoformat(),
        )

        # 拓扑排序
        layers = pipeline.topological_sort()
        logger.info(f"[Pipeline:{ctx.pipeline_id}] {pipeline.name} - {len(pipeline.nodes)} nodes, {len(layers)} layers")

        # 执行每层
        for layer_idx, layer in enumerate(layers):
            logger.info(f"[Pipeline:{ctx.pipeline_id}] Layer {layer_idx + 1}/{len(layers)}: {[n.id for n in layer]}")

            # 并行执行本层所有节点
            tasks = []
            for node in layer:
                ctx.set_status(node.id, NodeStatus.PENDING)
                tasks.append(self._execute_node_with_guard(node, ctx, progress_callback))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 检查是否有致命错误
            for node, result in zip(layer, results):
                if isinstance(result, Exception) and not node.optional:
                    ctx.end_time = datetime.now().isoformat()
                    ctx.set_error(node.id, str(result))
                    logger.error(f"[Pipeline:{ctx.pipeline_id}] Fatal error at {node.id}: {result}")
                    return ctx

        ctx.end_time = datetime.now().isoformat()
        logger.info(f"[Pipeline:{ctx.pipeline_id}] Pipeline completed")
        return ctx

    # ── Node Execution ──────────────────────────────────────────────────

    async def _execute_node_with_guard(
        self,
        node: PipelineNode,
        ctx: PipelineContext,
        progress_callback: Callable | None,
    ) -> Any:
        """带超时和重试的节点执行包装。"""
        ctx.set_status(node.id, NodeStatus.RUNNING)
        if progress_callback:
            progress_callback(node.id, "running", f"开始执行: {node.name}")

        last_error = None
        for attempt in range(node.retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._execute_node(node, ctx),
                    timeout=node.timeout,
                )
                ctx.set_output(node.id, result)
                ctx.set_status(node.id, NodeStatus.SUCCESS)
                if progress_callback:
                    progress_callback(node.id, "success", f"完成: {node.name}")
                return result
            except asyncio.TimeoutError:
                last_error = f"Timeout after {node.timeout}s"
                logger.warning(f"[Pipeline] Node {node.id} timeout (attempt {attempt + 1})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[Pipeline] Node {node.id} failed (attempt {attempt + 1}): {e}")
                if attempt < node.retries:
                    await asyncio.sleep(2 ** attempt)  # 指数退避

        # All retries exhausted
        ctx.set_error(node.id, last_error)
        if node.optional:
            ctx.set_status(node.id, NodeStatus.SKIPPED)
            if progress_callback:
                progress_callback(node.id, "skipped", f"可选节点跳过: {last_error}")
            return None
        else:
            ctx.set_status(node.id, NodeStatus.FAILED)
            if progress_callback:
                progress_callback(node.id, "failed", f"失败: {last_error}")
            raise Exception(f"Node {node.id} failed after {node.retries + 1} attempts: {last_error}")

    async def _execute_node(self, node: PipelineNode, ctx: PipelineContext) -> Any:
        """执行单个节点。"""
        handler = self._handlers.get(node.type)
        if not handler:
            raise ValueError(f"Unknown node type: {node.type}")

        # 解析输入参数
        params = self._resolve_params(node, ctx)
        logger.debug(f"[Pipeline] Node {node.id} params: {params}")

        return await handler(node, params, ctx)

    def _resolve_params(self, node: PipelineNode, ctx: PipelineContext) -> dict:
        """解析节点输入参数，从上下文中提取依赖数据。"""
        params = dict(node.params)

        # 1. 应用 data_mapping
        for param_name, source_path in node.data_mapping.items():
            value = ctx.get(source_path)
            if value is not None:
                params[param_name] = value

        # 2. 解析 prompt_template 中的占位符
        if node.prompt_template:
            prompt = self._render_template(node.prompt_template, ctx)
            params["prompt"] = prompt

        return params

    def _render_template(self, template: str, ctx: PipelineContext) -> str:
        """渲染模板，替换占位符。"""
        result = template
        # 支持 {inputs.xxx} {node_id.field} 格式
        import re
        pattern = r'\{([\w.]+)\}'

        def replace(match):
            path = match.group(1)
            value = ctx.get(path, "")
            if value is None:
                return ""
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)

        # 多次替换直到稳定（处理嵌套引用）
        prev = None
        while result != prev:
            prev = result
            result = re.sub(pattern, replace, result)
        return result

    # ── Node Type Handlers ──────────────────────────────────────────────

    async def _execute_text(self, node: PipelineNode, params: dict, ctx: PipelineContext) -> dict:
        """文本生成节点 — 调用LLM。自动解析 JSON 内容并展开到输出字段。"""
        if not self.client:
            raise RuntimeError("VolcEngine client not configured")

        prompt = params.get("prompt", "")
        system = params.get("system", "")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        result = await self.client.chat(
            messages=messages,
            model=node.model or "doubao-pro-128k",
            max_tokens=params.get("max_tokens", 4096),
            temperature=params.get("temperature", 0.7),
        )
        content = result.get("message", {}).get("content", "")
        output = {
            "content": content,
            "model": result.get("model", ""),
            "usage": result.get("usage", {}),
        }
        # Auto-parse JSON content so downstream nodes can reference script.title etc.
        if content.strip():
            parsed = _extract_json(content)
            if isinstance(parsed, dict):
                output.update(parsed)
        return output

    async def _execute_image(self, node: PipelineNode, params: dict, ctx: PipelineContext) -> dict:
        """图像生成节点 — 调用文生图。"""
        if not self.client:
            raise RuntimeError("VolcEngine client not configured")

        path = await self.client.generate_image(
            prompt=params.get("prompt", ""),
            style=params.get("style"),
            size=params.get("size", "1920x1920"),
            model=node.model or "doubao-image",
        )
        ctx.set_artifacts(node.output_key, [path])
        return {"path": path, "type": "image"}

    async def _execute_video(self, node: PipelineNode, params: dict, ctx: PipelineContext) -> dict:
        """视频生成节点 — 调用文生视频（异步）。"""
        if not self.client:
            raise RuntimeError("VolcEngine client not configured")

        # 提交异步任务
        result = await self.client.generate_video(
            prompt=params.get("prompt", ""),
            image_url=params.get("image_url"),
            model=node.model or "doubao-video",
            duration=params.get("duration", 5),
        )
        task_id = result.get("task_id", "")

        # 轮询等待完成
        max_wait = params.get("max_wait", 300)  # 最多等5分钟
        poll_interval = params.get("poll_interval", 5)
        for _ in range(max_wait // poll_interval):
            await asyncio.sleep(poll_interval)
            status = await self.client.get_video_task(task_id, model=node.model or "doubao-video")
            if status.get("status") == "succeed":
                if status.get("video_url"):
                    path = await self.client.download_video(
                        status["video_url"],
                        output_name=f"pipeline_{ctx.pipeline_id}_{node.id}.mp4",
                        output_dir=str(get_media_output_dir("video")),
                    )
                    ctx.set_artifacts(node.output_key, [path])
                    return {"path": path, "task_id": task_id, "status": "succeed"}
                return {"task_id": task_id, "status": "succeed"}
            elif status.get("status") == "failed":
                raise RuntimeError(f"Video generation failed: {status.get('error', '')}")

        raise TimeoutError(f"Video generation timeout after {max_wait}s")

    async def _execute_audio(self, node: PipelineNode, params: dict, ctx: PipelineContext) -> dict:
        """语音合成节点 — 调用TTS。"""
        if not self.client:
            raise RuntimeError("VolcEngine client not configured")

        path = await self.client.text_to_speech(
            text=params.get("text", ""),
            voice_id=params.get("voice_id", "zh_female_xiaoyi"),
            emotion=params.get("emotion", "neutral"),
            speed=params.get("speed", 1.0),
            pitch=params.get("pitch", 0),
            output_name=f"pipeline_{ctx.pipeline_id}_{node.id}.mp3",
            output_dir=str(get_media_output_dir("audio")),
        )
        ctx.set_artifacts(node.output_key, [path])
        return {"path": path, "type": "audio"}

    async def _execute_embedding(self, node: PipelineNode, params: dict, ctx: PipelineContext) -> dict:
        """向量嵌入节点。"""
        if not self.client:
            raise RuntimeError("VolcEngine client not configured")

        texts = params.get("texts", [])
        if isinstance(texts, str):
            texts = [t.strip() for t in texts.split("\n") if t.strip()]

        result = await self.client.create_embedding(
            texts=texts,
            model=node.model or "doubao-embedding",
        )
        return result

    async def _execute_skill(self, node: PipelineNode, params: dict, ctx: PipelineContext) -> dict:
        """技能节点通过统一业务能力目录执行。"""
        skill_name = params.get("skill", node.id)
        from szyg.hermes_capabilities import get_hermes_capability_registry

        registry = get_hermes_capability_registry()
        names = {item["name"] for item in registry.list()}
        if skill_name not in names:
            raise RuntimeError(f"未找到可执行能力：{skill_name}")
        arguments = {key: value for key, value in params.items() if key != "skill"}
        return {"result": await registry.execute(skill_name, arguments)}


# ── Pipeline Registry ───────────────────────────────────────────────────

class PipelineRegistry:
    """流水线注册表 — 预定义流水线模板。"""

    def __init__(self):
        self._pipelines: dict[str, Callable[[], Pipeline]] = {}
        self._register_defaults()

    def register(self, name: str, factory: Callable[[], Pipeline]):
        self._pipelines[name] = factory

    def get(self, name: str) -> Pipeline | None:
        factory = self._pipelines.get(name)
        if factory:
            return factory()
        return None

    def list(self) -> list[dict]:
        return [
            {"name": name, "description": factory().__doc__ or ""}
            for name, factory in self._pipelines.items()
        ]

    def _register_defaults(self):
        """注册默认流水线模板。"""
        self.register("ai_short_video", self._ai_short_video_pipeline)
        self.register("ai_content", self._ai_content_pipeline)
        self.register("ai_marketing", self._ai_marketing_pipeline)
        self.register("ai_image_set", self._ai_image_set_pipeline)

    # ── Predefined Pipelines ──────────────────────────────────────────

    @staticmethod
    def _ai_short_video_pipeline() -> Pipeline:
        """AI短视频流水线: 主题 → 脚本 → 封面+视频+配音 → 合成"""
        p = Pipeline(
            name="ai_short_video",
            description="AI短视频创作: 从主题到成片",
            inputs_schema={"topic": "str", "duration": "int"},
            outputs_schema=["script", "cover", "video", "audio", "final"],
        )
        p.add_node(PipelineNode(
            id="script",
            type="text",
            model="doubao-pro-128k",
            name="脚本生成",
            description="为主题创作短视频脚本",
            prompt_template="""你是短视频创作专家。为主题「{inputs.topic}」创作一个约{inputs.duration}秒的短视频脚本。

请用JSON格式返回:
{{
    "title": "视频标题(吸引眼球,10字以内)",
    "cover_prompt": "封面图描述(英文,AI绘画用)",
    "narration": "旁白文本(中文,适合朗读)",
    "subtitles": "字幕文本",
    "video_prompt": "视频内容描述(英文,文生视频用)",
    "emotion": "配音情感(neutral/happy/excited)",
    "scenes": ["场景1描述", "场景2描述"]
}}
只返回JSON。""",
            timeout=60,
        ))
        p.add_node(PipelineNode(
            id="cover",
            type="image",
            model="doubao-image",
            name="封面生成",
            description="生成短视频封面图",
            data_mapping={"prompt": "script.cover_prompt"},
            depends_on=["script"],
            timeout=120,
        ))
        p.add_node(PipelineNode(
            id="video_clip",
            type="video",
            model="doubao-video",
            name="视频片段生成",
            description="生成AI视频片段",
            data_mapping={"prompt": "script.video_prompt", "duration": "inputs.duration"},
            depends_on=["script"],
            params={"duration": 5},  # default fallback if inputs.duration not set
            timeout=300,
        ))
        p.add_node(PipelineNode(
            id="audio",
            type="audio",
            model="doubao-tts",
            name="配音生成",
            description="生成情感配音",
            data_mapping={"text": "script.narration", "emotion": "script.emotion"},
            depends_on=["script"],
            timeout=60,
        ))
        p.add_node(PipelineNode(
            id="final",
            type="skill",
            name="合成成片",
            description="用FFmpeg合成最终视频",
            depends_on=["video_clip", "audio", "cover"],
            params={"skill": "video_render", "template_id": "default"},
            timeout=120,
        ))
        return p

    @staticmethod
    def _ai_content_pipeline() -> Pipeline:
        """智能内容创作流水线: 主题 → 文案+配图 → 排版"""
        p = Pipeline(
            name="ai_content",
            description="智能内容创作: 文案+配图",
            inputs_schema={"topic": "str", "platform": "str"},
            outputs_schema=["article", "images"],
        )
        p.add_node(PipelineNode(
            id="article",
            type="text",
            model="doubao-pro-128k",
            name="文案生成",
            prompt_template="为「{inputs.topic}」创作一篇适合{inputs.platform}发布的内容。包含标题、正文、话题标签。",
            timeout=60,
        ))
        p.add_node(PipelineNode(
            id="images",
            type="image",
            model="doubao-image",
            name="配图生成",
            data_mapping={"prompt": "article.title"},
            depends_on=["article"],
            params={"style": "realistic", "size": "1024x1024"},
            timeout=120,
        ))
        return p

    @staticmethod
    def _ai_marketing_pipeline() -> Pipeline:
        """智能营销流水线: 产品 → 多平台文案+配图 → 发布计划"""
        p = Pipeline(
            name="ai_marketing",
            description="智能营销: 多平台内容创作与发布",
            inputs_schema={"product": "str", "campaign": "str"},
            outputs_schema=["strategy", "contents"],
        )
        p.add_node(PipelineNode(
            id="strategy",
            type="text",
            model="deepseek-r1",
            name="营销策略",
            prompt_template="为产品「{inputs.product}」的「{inputs.campaign}」活动制定营销策略，包括目标人群、核心卖点、内容方向。",
            timeout=60,
        ))
        # 并行生成多平台内容
        for platform in ["douyin", "xhs", "wechat_mp"]:
            p.add_node(PipelineNode(
                id=f"content_{platform}",
                type="text",
                model="doubao-pro-128k",
                name=f"{platform}文案",
                data_mapping={"strategy": "strategy.content"},
                depends_on=["strategy"],
                prompt_template=f"根据营销策略，为{platform}平台创作发布内容。",
                timeout=60,
            ))
        return p

    @staticmethod
    def _ai_image_set_pipeline() -> Pipeline:
        """AI图集流水线: 主题 → 多张风格图像"""
        p = Pipeline(
            name="ai_image_set",
            description="AI图集: 同一主题多种风格",
            inputs_schema={"topic": "str", "styles": "list"},
            outputs_schema=["images"],
        )
        # 并行生成多种风格
        for style in ["realistic", "anime", "cyberpunk", "oil"]:
            p.add_node(PipelineNode(
                id=f"img_{style}",
                type="image",
                model="doubao-image",
                name=f"{style}风格",
                prompt_template="{inputs.topic}",
                params={"style": style, "size": "1024x1024"},
                timeout=120,
            ))
        return p


# ── Singleton ──────────────────────────────────────────────────────────

_registry: PipelineRegistry | None = None

def get_pipeline_registry() -> PipelineRegistry:
    global _registry
    if _registry is None:
        _registry = PipelineRegistry()
    return _registry
