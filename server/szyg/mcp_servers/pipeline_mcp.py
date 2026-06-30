"""MCP Server: Pipeline — 多模型AIGC流水线编排。"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer
from szyg.pipeline_engine import PipelineExecutor, get_pipeline_registry

server = MCPServer("szyg-pipeline", "Multi-model AIGC pipeline orchestration")


@server.tool("pipeline_list", "列出所有可用的流水线模板")
def pipeline_list():
    registry = get_pipeline_registry()
    templates = registry.list()
    return {"templates": templates, "total": len(templates)}


@server.tool("pipeline_get", "获取流水线模板的详细信息")
def pipeline_get(name: str):
    registry = get_pipeline_registry()
    p = registry.get(name)
    if not p:
        return {"error": f"流水线模板不存在: {name}"}
    return {
        "name": p.name,
        "description": p.description,
        "nodes": [{"id": n.id, "type": n.type.value, "name": n.name, "model": n.model} for n in p.nodes],
        "inputs_schema": p.inputs_schema,
        "outputs_schema": p.outputs_schema,
    }


@server.tool("pipeline_execute", "执行流水线")
async def pipeline_execute(name: str, inputs_json: str = "{}"):
    import json
    try:
        inputs = json.loads(inputs_json)
    except Exception:
        return {"error": "inputs_json 必须是有效的JSON字符串"}

    registry = get_pipeline_registry()
    pipeline = registry.get(name)
    if not pipeline:
        return {"error": f"流水线模板不存在: {name}"}

    try:
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient()
        executor = PipelineExecutor(client)
        ctx = await executor.run(pipeline, inputs=inputs)
        await client.close()

        return {
            "ok": True,
            "pipeline_id": ctx.pipeline_id,
            "status": "completed" if not ctx.errors else "partial",
            "outputs": ctx.outputs,
            "artifacts": ctx.artifacts,
            "node_status": ctx.status,
            "errors": ctx.errors,
        }
    except Exception as e:
        return {"error": str(e)}


@server.tool("pipeline_video_create", "使用AI短视频流水线创作视频")
async def pipeline_video_create(topic: str, duration: int = 30):
    """快捷执行AI短视频流水线: 主题 → 脚本 → 封面+视频+配音 → 合成"""
    return await pipeline_execute("ai_short_video", json.dumps({"topic": topic, "duration": duration}))


@server.tool("pipeline_content_create", "使用智能内容流水线创作内容")
async def pipeline_content_create(topic: str, platform: str = "xiaohongshu"):
    """快捷执行智能内容创作流水线: 主题 → 文案+配图"""
    return await pipeline_execute("ai_content", json.dumps({"topic": topic, "platform": platform}))


@server.tool("pipeline_image_set", "使用AI图集流水线生成多风格图像")
async def pipeline_image_set(topic: str):
    """快捷执行AI图集流水线: 主题 → 多种风格图像"""
    return await pipeline_execute("ai_image_set", json.dumps({"topic": topic}))


if __name__ == "__main__":
    server.run()
