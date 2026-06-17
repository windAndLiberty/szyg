"""
szyg SOP驱动短视频创作 — 知识库 + SOP 完整演示。

流程:
    1. 用户上传产品知识文件 → 知识库摄入
    2. 用户定义视频创作SOP → 保存为模板
    3. 用户输入主题 → SOP引擎按步执行 → 输出视频

用法:
    python -m szyg.pipelines.sop_video_creator
"""

import asyncio
import sys
from pathlib import Path

from szyg.agent_core.knowledge import KnowledgeBase
from szyg.agent_core.skill_registry import SkillRegistry
from szyg.agent_core.sop_manager import SOPManager
from szyg.integrations.openrouter_client import OpenRouterClient
from szyg.integrations.dashscope_client import DashScopeImageClient
from szyg.pipelines.video_creator import VideoCreator


async def build_knowledge_and_sop():
    """构建知识库和 SOP 系统，然后演示完整流程。"""

    registry = SkillRegistry()
    sop_mgr = SOPManager(registry)
    kb = KnowledgeBase("./data/knowledge.db")

    # ── 注册技能 ────────────────────────────────────────────────────────
    print("🔧 注册技能...")

    llm = OpenRouterClient()
    image_client = DashScopeImageClient()
    creator = VideoCreator()

    def skill_write_script(topic: str, duration: int = 30) -> dict:
        """生成视频脚本（同步包装）。"""
        return asyncio.get_event_loop().run_until_complete(
            llm.chat(
                messages=[{
                    "role": "user",
                    "content": f"为主题「{topic}」写一个{duration}秒短视频脚本，JSON格式，包含title, narration, cover_prompt",
                }],
                max_tokens=2000,
            )
        )

    def skill_generate_cover(prompt: str) -> str:
        """生成封面图。"""
        paths = asyncio.get_event_loop().run_until_complete(
            image_client.generate(prompt=prompt, size="1024*1024", output_dir="./data/output/images")
        )
        return paths[0] if paths else ""

    def skill_synthesize_video(image: str, audio: str, output: str) -> str:
        """合成视频。"""
        import subprocess
        # 获取音频时长
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", audio], capture_output=True, text=True,
        )
        duration = float(result.stdout.strip())
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", image, "-i", audio,
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            output,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output

    registry.register("write_script", "根据主题生成视频脚本JSON", handler=skill_write_script)
    registry.register("generate_cover", "生成视频封面图", handler=skill_generate_cover)
    registry.register("synthesize_video", "合成最终视频文件", handler=skill_synthesize_video)

    # ── 知识库：摄入示例知识 ────────────────────────────────────────────
    print("📚 构建知识库...")

    product_knowledge = """
# 产品「域灵AI助手」介绍

## 核心功能
域灵AI助手是一款全能的数字员工系统，支持以下功能：
1. AI短视频自动创作：输入主题，自动生成脚本、封面、配音和成品视频
2. 多模型智能对话：支持OpenRouter、Ollama、ModelScope等多个AI后端
3. 微信私域运营：通过Wechaty接入微信，实现自动回复和客户管理
4. 知识库管理：上传文档后AI自动学习，回答问题时引用知识库内容
5. SOP工作流：用户可自定义标准操作流程，AI按流程自动执行

## 技术优势
- 全免费API驱动，零成本运行
- 模块化架构，每个组件可独立替换
- MCP协议支持，可接入任何外部工具
- SQLite FTS5全文检索，毫秒级知识查询
- FFmpeg专业级视频处理

## 适用场景
- 抖音/快手 短视频矩阵运营
- 微信私域客户自动维护
- 企业内部知识库问答
- 自动化内容创作流水线

## 定价
基础版完全免费，使用开源组件和免费API。
企业版提供私有化部署和定制开发。
"""

    kb.ingest_text(product_knowledge, source="产品介绍", source_type=".md")
    print(f"   已摄入产品知识 (约 {len(product_knowledge)} 字)")

    # ── 定义短视频创作 SOP ────────────────────────────────────────────────
    print("📋 定义 SOP: 短视频标准创作流程")

    try:
        sop_mgr.define(
            name="短视频创作SOP",
            description="从主题到成品视频的标准创作流程：脚本→封面→配音→合成",
            steps=[
                {
                    "skill": "write_script",
                    "params": {"topic": "{topic}", "duration": "{duration}"},
                    "description": "AI 生成视频脚本（标题+旁白+封面描述）",
                    "on_failure": "stop",
                },
                {
                    "skill": "generate_cover",
                    "params": {"prompt": "{cover_prompt}"},
                    "description": "AI 生成视频封面图",
                    "on_failure": "skip",  # 封面失败可跳过
                },
                {
                    "skill": "synthesize_video",
                    "params": {"image": "{cover_path}", "audio": "{audio_path}", "output": "{output_path}"},
                    "description": "FFmpeg 合成最终视频",
                    "on_failure": "stop",
                },
            ],
        )
        print(f"   ✅ SOP 已定义: {len(sop_mgr.list_sops())} 个")
    except ValueError as e:
        print(f"   ⚠️ {e} (已存在)")

    # ── 知识库检索演示 ────────────────────────────────────────────────────
    print("\n📖 知识库检索演示:")
    context = kb.query_as_context("域灵AI助手有哪些功能", top_k=3)
    print(context[:300] + "...")

    # ── SOP 执行演示 ─────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    topic = sys.argv[1] if len(sys.argv) > 1 else "域灵AI助手如何帮助企业降本增效"
    print(f"🚀 执行 SOP: 短视频创作SOP")
    print(f"   主题: {topic}")
    print("=" * 60)

    # 这里演示 SOP 执行：按步骤展示流程
    # (实际执行需要异步包装，这里展示架构)
    sop = sop_mgr.get_sop("短视频创作SOP")
    if sop:
        print(f"\n📋 SOP: {sop.name} ({len(sop.steps)} 步)")
        for step in sop.steps:
            params_preview = {k: v[:50] + "..." if isinstance(v, str) and len(v) > 50 else v for k, v in step.params.items()}
            print(f"   Step {sop.steps.index(step)+1}: {step.skill} | {step.description}")
            print(f"          参数: {params_preview}")
            print(f"          失败时: {step.on_failure}")

    # ── 总结 ──
    print("\n" + "=" * 60)
    print("✅ 系统就绪:")
    print(f"   知识库: {kb.query('产品', top_k=1)} 条相关知识")
    print(f"   SOP:    {len(sop_mgr.list_sops())} 个流程模板")
    print(f"   技能:   {len(registry.list_skills())} 个可用技能")
    print(f"   LLM:    OpenRouter (openrouter/free)")
    print(f"   生图:   DashScope (qwen-image-plus)")
    print(f"   TTS:    edge-tts (免费)")
    print(f"   视频:   FFmpeg v8")
    print("=" * 60)

    # 清理
    kb.close()
    sop_mgr.close()
    await llm.close()
    await image_client.close()


if __name__ == "__main__":
    asyncio.run(build_knowledge_and_sop())
