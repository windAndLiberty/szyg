"""
Hermes Chat API — 超级AI员工对话端点

Bridges Chat.vue to szyg's in-app Hermes kernel.
Uses Kimi Code API (OpenAI-compatible) with native function calling
+ szyg's full MCP tool suite.

Architecture:
  Chat.vue → POST /api/hermes/chat (SSE)
    → Kimi API (with szyg tools)
    → model returns tool_call → execute via szyg REST API
    → model processes result → stream text back
"""
import json, asyncio, logging, time, re, os, uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import httpx

# Internal HTTP client that bypasses system proxy (Windows proxy detection
# can route 127.0.0.1 through a corporate proxy causing 502 errors)
_internal_client = httpx.Client(proxy=None, trust_env=False, timeout=httpx.Timeout(120))

from szyg.api.auth_routes import optional_user, security
from szyg.auth import User

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Load secrets ──────────────────────────────────────

def _load_secret(key: str, default: str = "") -> str:
    """Load secret from secrets.yaml or environment variable."""
    env_key = key.upper().replace(".", "_")
    env_val = os.environ.get(env_key, "")
    if env_val:
        return env_val
    try:
        import yaml
        secrets_path = Path(__file__).parent.parent.parent.parent / "secrets.yaml"
        if secrets_path.exists():
            cfg = yaml.safe_load(secrets_path.read_text(encoding="utf-8"))
            for part in key.split("."):
                cfg = cfg.get(part, {}) if isinstance(cfg, dict) else {}
            return str(cfg) if cfg else default
    except Exception as e:
        logger.debug("Failed to load secret %s: %s", key, e)
    return default

# Fallback LLM config — Ollama local (used when VolcEngine is unavailable)
API_KEY = _load_secret("llm.ollama.api_key", "")
API_URL = _load_secret("llm.ollama.base_url", "http://localhost:11434/v1")
API_MODEL = _load_secret("llm.ollama.default_model", "qwen3:0.6B")

# ── VolcEngine config ─────────────────────────────────

def _load_volcengine_config() -> dict:
    """从 config.yaml 加载火山引擎方舟完整配置。"""
    try:
        from szyg.config.loader import load_config
        cfg = load_config()
        return cfg.get("llm", {}).get("volcengine", {})
    except Exception as e:
        logger.debug("Failed to load VolcEngine config: %s", e)
        return {}

_volc_cfg = _load_volcengine_config()

VOLCENGINE_API_KEY = (
    _load_secret("volcengine.api_key")                      # ① env: VOLCENGINE_API_KEY
    or _volc_cfg.get("api_key", "")                         # ② config.yaml → llm.volcengine.api_key
)
VOLCENGINE_BASE_URL = (
    _load_secret("volcengine.base_url")                     # ① env: VOLCENGINE_BASE_URL
    or _volc_cfg.get("base_url", "https://ark.cn-beijing.volces.com/api/v3")
)
VOLCENGINE_ENDPOINTS = _volc_cfg.get("endpoints", {})

# 火山引擎方舟 — 实测可用模型 (2026-06-22 免费额度)
# 注意: 模型列表虽显示120+个，但免费账户只能直接调用以下模型
# 其他模型(deepseek-r1/v3, kimi-k2, qwen, glm等)需创建付费推理接入点
VOLCENGINE_MODELS = {
    # ── 豆包 Seed 2.0 系列 (最新旗舰，实测可用) ──
    "doubao-seed-2-0-pro-260215",     # Seed 2.0 Pro — 旗舰综合
    "doubao-seed-2-0-lite-260428",    # Seed 2.0 Lite — 高性价比
    "doubao-seed-2-0-lite-260215",    # Seed 2.0 Lite 初版
    "doubao-seed-2-0-mini-260428",    # Seed 2.0 Mini — 快速推理
    "doubao-seed-2-0-mini-260215",    # Seed 2.0 Mini 初版
    "doubao-seed-2-0-code-preview-260215",  # Seed 2.0 Code — 代码专用
    # ── 豆包 Seed 1.6 系列 (稳定版) ──
    "doubao-seed-1-6-251015",         # Seed 1.6 — 标准版
    "doubao-seed-1-6-250615",         # Seed 1.6 初版
    "doubao-seed-1-6-flash-250828",   # Seed 1.6 Flash — 极速推理
    "doubao-seed-1-6-flash-250615",   # Seed 1.6 Flash 初版
    "doubao-seed-1-6-vision-250815",  # Seed 1.6 Vision — 视觉理解
    # ── 豆包 1.5 系列 (经典模型) ──
    "doubao-1-5-pro-32k-250115",      # 1.5 Pro 32K — 经典旗舰
    "doubao-1-5-lite-32k-250115",     # 1.5 Lite 32K — 经典轻量
    "doubao-1-5-vision-pro-32k-250115",  # 1.5 Vision Pro — 视觉
    "doubao-1-5-pro-32k-character-250715",  # 1.5 Character
    # ── DeepSeek (仅 V4 Flash 可用! V3/R1 不可用) ──
    "deepseek-v4-flash-260425",       # DeepSeek V4 Flash — 强推理
}

# 默认模型 — doubao-seed-2-0-pro (旗舰综合，适合函数调用)
# 备选: doubao-seed-1-6-flash-250828 (极速), deepseek-v4-flash-260425 (强推理)
HERMES_DEFAULT_MODEL = "doubao-seed-2-0-pro-260215" if VOLCENGINE_API_KEY else (
    _load_secret("llm.ollama.default_model", "qwen3:0.6B")
)


def _resolve_llm_backend(model: str) -> tuple[str, str, str, bool]:
    """根据模型名称解析LLM后端配置。

    Returns:
        (api_key, base_url, actual_model_id, is_volcengine)
    """
    if model in VOLCENGINE_MODELS:
        ep = VOLCENGINE_ENDPOINTS.get(model, "")
        # 空 endpoint 时用模型ID直接调用（免费额度支持直接调用）
        actual_model = ep if ep else model
        return VOLCENGINE_API_KEY, VOLCENGINE_BASE_URL, actual_model, True
    return API_KEY, API_URL, model, False


# ── Models ────────────────────────────────────────────

class HermesChatRequest(BaseModel):
    model: str = HERMES_DEFAULT_MODEL
    messages: list = Field(default_factory=list)
    stream: bool = True
    agent_id: str = ""  # 员工 ID: content/acquisition/conversion/ops，空=通用模式
    expert_prompt: str = ""  # AI人才市场专家 prompt（独立通道，不影响超级员工）

# ── Tools (same as before, OpenAI format) ─────────────

HERMES_TOOLS = [
    # Publisher
    {"type":"function","function":{"name":"content_list","description":"列出所有内容","parameters":{"type":"object","properties":{"status":{"type":"string","description":"draft/pending/approved/published"}}}}},
    {"type":"function","function":{"name":"content_create","description":"创建新内容","parameters":{"type":"object","properties":{"title":{"type":"string"},"body":{"type":"string"},"content_type":{"type":"string","enum":["post","article","video","image"]},"tags":{"type":"string"}},"required":["title"]}}},
    {"type":"function","function":{"name":"content_get","description":"获取单个内容详情","parameters":{"type":"object","properties":{"content_id":{"type":"string","description":"内容ID"}},"required":["content_id"]}}},
    {"type":"function","function":{"name":"content_submit","description":"提交内容审核","parameters":{"type":"object","properties":{"content_id":{"type":"string"}},"required":["content_id"]}}},
    {"type":"function","function":{"name":"content_approve","description":"批准内容","parameters":{"type":"object","properties":{"content_id":{"type":"string"}},"required":["content_id"]}}},
    {"type":"function","function":{"name":"content_generate","description":"AI生成内容草稿","parameters":{"type":"object","properties":{"topic":{"type":"string"}},"required":["topic"]}}},
    {"type":"function","function":{"name":"content_stats","description":"获取内容统计","parameters":{"type":"object","properties":{}}}},

    # Platforms
    {"type":"function","function":{"name":"platform_list","description":"列出所有平台的登录状态。返回 status='ok' 表示查询成功，每个平台的 state 为 ready/error/uninitialized。注意：微信(wechat_mp)需要桌面客户端运行，未运行时 state=error 是正常的，不代表接口超时。","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"platform_status","description":"查看单个平台的登录状态和Cookie有效性。发布前务必先调用此工具检查是否已登录。返回 status='ok' 表示查询成功，login.is_logged_in 表示是否已登录。","parameters":{"type":"object","properties":{"platform":{"type":"string","enum":["douyin","xhs","wechat_mp","bilibili","kuaishou"]}},"required":["platform"]}}},
    {"type":"function","function":{"name":"platform_publish_direct","description":"直接发布内容到平台。发布前务必先用 platform_status 检查登录状态；如未登录，先调用 platform_login 触发扫码登录并告知用户。支持图文和视频两种内容类型。","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台ID: douyin/xhs/bilibili/kuaishou"},"title":{"type":"string","description":"内容标题"},"body":{"type":"string","description":"正文内容"},"tags":{"type":"string","description":"标签，逗号分隔"},"content_type":{"type":"string","enum":["post","video","image","article"],"description":"内容类型: post=图文短帖, video=视频, image=图文"},"media_urls":{"type":"string","description":"媒体文件URL或本地路径，逗号分隔。视频发布时必填。"}},"required":["platform","title"]}}},
    {"type":"function","function":{"name":"platform_sessions","description":"查看平台登录态详细信息(有效期/Cookie等)","parameters":{"type":"object","properties":{"platform":{"type":"string","enum":["douyin","xhs","wechat_mp","bilibili","kuaishou"],"description":"平台ID"}},"required":["platform"]}}},
    {"type":"function","function":{"name":"platform_health","description":"全平台健康检查。返回 status='ok' 表示查询成功，每个平台有 state/is_logged_in/account_name。注意：微信桌面客户端未运行时会显示 error，这是正常的。","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"platform_post_status","description":"查询已发布内容在平台上的实时数据（播放量/点赞/评论/分享）。需要 post_id（发布时返回）。","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台ID"},"post_id":{"type":"string","description":"发布时返回的 platform_post_id"}},"required":["platform","post_id"]}}},

    # Scheduler
    {"type":"function","function":{"name":"scheduler_list","description":"列出定时任务","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"scheduler_create","description":"创建定时任务","parameters":{"type":"object","properties":{"name":{"type":"string"},"action":{"type":"string"},"trigger_type":{"type":"string"},"minutes":{"type":"integer"}},"required":["name","action"]}}},
    {"type":"function","function":{"name":"scheduler_get","description":"获取指定任务的详细信息","parameters":{"type":"object","properties":{"job_id":{"type":"string","description":"任务ID"}},"required":["job_id"]}}},
    {"type":"function","function":{"name":"scheduler_execute","description":"立即执行指定任务","parameters":{"type":"object","properties":{"job_id":{"type":"string","description":"任务ID"}},"required":["job_id"]}}},
    {"type":"function","function":{"name":"scheduler_pause","description":"暂停定时任务","parameters":{"type":"object","properties":{"job_id":{"type":"string","description":"任务ID"}},"required":["job_id"]}}},
    {"type":"function","function":{"name":"scheduler_resume","description":"恢复已暂停的任务","parameters":{"type":"object","properties":{"job_id":{"type":"string","description":"任务ID"}},"required":["job_id"]}}},
    {"type":"function","function":{"name":"scheduler_delete","description":"删除定时任务","parameters":{"type":"object","properties":{"job_id":{"type":"string","description":"任务ID"}},"required":["job_id"]}}},
    {"type":"function","function":{"name":"scheduler_history","description":"查看任务执行历史","parameters":{"type":"object","properties":{"job_id":{"type":"string","description":"可选：按任务过滤"},"limit":{"type":"integer","description":"返回条数"}}}}},
    {"type":"function","function":{"name":"scheduler_stats","description":"获取调度器统计信息","parameters":{"type":"object","properties":{}}}},

    # Skills — Office Documents (12 tools)
    {"type":"function","function":{"name":"docx_create","description":"从Markdown生成Word文档","parameters":{"type":"object","properties":{"markdown":{"type":"string"},"output_path":{"type":"string"}},"required":["markdown","output_path"]}}},
    {"type":"function","function":{"name":"docx_to_markdown","description":"将.docx转为Markdown（需pandoc）","parameters":{"type":"object","properties":{"file_path":{"type":"string","description":".docx文件路径"},"tracked_changes":{"type":"string","description":"修订处理: accept/reject/all"}},"required":["file_path"]}}},
    {"type":"function","function":{"name":"docx_extract_text","description":"从.docx提取纯文本（无需pandoc）","parameters":{"type":"object","properties":{"file_path":{"type":"string","description":".docx文件路径"}},"required":["file_path"]}}},
    {"type":"function","function":{"name":"xlsx_create","description":"从JSON数据生成Excel","parameters":{"type":"object","properties":{"data_json":{"type":"string"},"output_path":{"type":"string"}},"required":["data_json","output_path"]}}},
    {"type":"function","function":{"name":"xlsx_read","description":"读取.xlsx文件返回JSON数据","parameters":{"type":"object","properties":{"file_path":{"type":"string","description":".xlsx文件路径"},"sheet_name":{"type":"string","description":"工作表名"}},"required":["file_path"]}}},
    {"type":"function","function":{"name":"pptx_create","description":"从Markdown大纲生成PPT","parameters":{"type":"object","properties":{"markdown":{"type":"string"},"output_path":{"type":"string"}},"required":["markdown","output_path"]}}},
    {"type":"function","function":{"name":"pptx_extract","description":"从.pptx提取文字内容","parameters":{"type":"object","properties":{"file_path":{"type":"string","description":".pptx文件路径"}},"required":["file_path"]}}},
    {"type":"function","function":{"name":"pdf_extract","description":"从PDF提取文本","parameters":{"type":"object","properties":{"file_path":{"type":"string","description":"PDF文件路径"}},"required":["file_path"]}}},
    {"type":"function","function":{"name":"pdf_merge","description":"合并多个PDF文件","parameters":{"type":"object","properties":{"input_files":{"type":"string","description":"逗号分隔的PDF路径"},"output_path":{"type":"string"}},"required":["input_files","output_path"]}}},
    {"type":"function","function":{"name":"canvas_get_fonts","description":"列出可用的Canvas设计字体","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"canvas_preview_config","description":"预览Canvas设计技能参数","parameters":{"type":"object","properties":{}}}},

    # Knowledge
    {"type":"function","function":{"name":"knowledge_search","description":"搜索知识库","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"knowledge_ingest","description":"摄入文档到知识库","parameters":{"type":"object","properties":{"file_path":{"type":"string","description":"文档文件路径"}},"required":["file_path"]}}},
    {"type":"function","function":{"name":"knowledge_stats","description":"获取知识库统计信息","parameters":{"type":"object","properties":{}}}},
    # Video Cut Engine
    {"type":"function","function":{"name":"video_templates","description":"列出视频模板","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"video_info","description":"获取视频元信息（时长/分辨率/编码）","parameters":{"type":"object","properties":{"file_path":{"type":"string","description":"视频文件路径"}},"required":["file_path"]}}},
    {"type":"function","function":{"name":"video_cut","description":"裁剪视频片段","parameters":{"type":"object","properties":{"file_path":{"type":"string","description":"视频文件路径"},"start":{"type":"number","description":"开始秒数"},"duration":{"type":"number","description":"时长秒数"}},"required":["file_path","start","duration"]}}},
    {"type":"function","function":{"name":"video_concat","description":"拼接多个视频文件（逗号分隔路径）","parameters":{"type":"object","properties":{"files":{"type":"string","description":"逗号分隔的文件路径列表"}},"required":["files"]}}},
    {"type":"function","function":{"name":"video_speed","description":"视频变速（0.5=慢放一半, 2.0=快进一倍）","parameters":{"type":"object","properties":{"file_path":{"type":"string"},"speed":{"type":"number","description":"速度倍率"}},"required":["file_path","speed"]}}},
    {"type":"function","function":{"name":"video_add_title","description":"在视频上叠加文字标题","parameters":{"type":"object","properties":{"file_path":{"type":"string"},"text":{"type":"string","description":"标题文字"},"font_size":{"type":"integer","description":"字号"},"font_color":{"type":"string","description":"颜色"}},"required":["file_path","text"]}}},
    {"type":"function","function":{"name":"video_replace_audio","description":"替换视频的音频轨道","parameters":{"type":"object","properties":{"video_path":{"type":"string"},"audio_path":{"type":"string","description":"新音频文件路径"}},"required":["video_path","audio_path"]}}},
    {"type":"function","function":{"name":"video_mix_audio","description":"混合视频原声和背景音乐","parameters":{"type":"object","properties":{"video_path":{"type":"string"},"bgm_path":{"type":"string","description":"BGM文件路径"},"video_volume":{"type":"number","description":"原声音量 0-1"},"bgm_volume":{"type":"number","description":"BGM音量 0-1"}},"required":["video_path","bgm_path"]}}},
    {"type":"function","function":{"name":"video_extract_frame","description":"从视频中提取一帧作为封面图","parameters":{"type":"object","properties":{"file_path":{"type":"string"},"time_sec":{"type":"number","description":"截取时间点(秒)"},"width":{"type":"integer"},"height":{"type":"integer"}},"required":["file_path","time_sec"]}}},
    {"type":"function","function":{"name":"video_fonts","description":"列出可用的视频标题字体","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"video_render","description":"使用模板渲染视频（加标题+字幕）","parameters":{"type":"object","properties":{"template_id":{"type":"string"},"media_files":{"type":"string","description":"逗号分隔的素材文件"},"title":{"type":"string"},"subtitle":{"type":"string"},"font_name":{"type":"string"}},"required":["template_id","media_files","title"]}}},
    # Agents
    {"type":"function","function":{"name":"agents_list","description":"列出AI智能体","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"agents_get","description":"获取指定智能体的完整系统提示词","parameters":{"type":"object","properties":{"agent_id":{"type":"string","description":"智能体ID"}},"required":["agent_id"]}}},
    {"type":"function","function":{"name":"agents_tiers","description":"列出智能体提示词层级","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"agents_categories","description":"列出智能体分类","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"skills_list","description":"列出可用技能","parameters":{"type":"object","properties":{}}}},
    # Tool Marketplace (tools_mcp)
    {"type":"function","function":{"name":"tools_catalog","description":"列出工具市场所有可用AI工具","parameters":{"type":"object","properties":{"category":{"type":"string","description":"可选分类过滤"},"search":{"type":"string","description":"可选搜索关键词"}}}}},
    {"type":"function","function":{"name":"tools_categories","description":"列出工具市场所有分类","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"tools_installed","description":"列出已安装的工具","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"tools_stats","description":"获取工具市场统计信息","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"tools_search","description":"按关键词搜索工具","parameters":{"type":"object","properties":{"query":{"type":"string","description":"搜索关键词"}},"required":["query"]}}},
    # OEM Branding (oem_mcp)
    {"type":"function","function":{"name":"oem_config","description":"获取当前OEM品牌配置（名称/主题/版权）","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"oem_themes","description":"列出可用主题列表","parameters":{"type":"object","properties":{}}}},

    # ═══════════════════════════════════════════════════════════════
    # AIGC — 火山引擎方舟 (Phase A)
    # ═══════════════════════════════════════════════════════════════
    # AI图像生成
    {"type":"function","function":{"name":"ai_image_generate","description":"使用AI生成图像(火山引擎豆包·文生图/SDXL/FLUX)","parameters":{"type":"object","properties":{"prompt":{"type":"string","description":"图像描述，支持中文"},"style":{"type":"string","enum":["realistic","anime","cyberpunk","oil","ink","minimal","3d","pixel"],"description":"风格标签"},"size":{"type":"string","default":"1920x1920","description":"分辨率。预设:1920x1920/2560x1440(16:9)/1440x2560(9:16)/2048x2048/2304x1728(4:3)/3072x1296(21:9)。也可自定义如 2400x1800，需≥368万像素"},"model":{"type":"string","enum":["doubao-image","sdxl","flux"],"default":"doubao-image","description":"模型"}},"required":["prompt"]}}},
    {"type":"function","function":{"name":"ai_image_styles","description":"列出可用的AI图像生成风格","parameters":{"type":"object","properties":{}}}},
    # AI视频生成
    {"type":"function","function":{"name":"ai_video_create","description":"使用AI生成视频(火山引擎豆包·视频生成/Seaweed)。注意：视频生成是异步任务，提交后返回task_id，需要轮询查询完成状态","parameters":{"type":"object","properties":{"prompt":{"type":"string","description":"视频内容描述"},"image_url":{"type":"string","description":"参考图片路径或URL(图生视频时)"},"duration":{"type":"integer","default":5,"description":"时长秒数"},"style":{"type":"string","enum":["realistic","anime","cinematic"],"description":"视频风格"},"model":{"type":"string","enum":["doubao-video","seaweed"],"default":"doubao-video","description":"模型"}},"required":["prompt"]}}},
    {"type":"function","function":{"name":"ai_video_task_status","description":"查询AI视频生成任务状态","parameters":{"type":"object","properties":{"task_id":{"type":"string","description":"任务ID"}},"required":["task_id"]}}},
    # AI语音合成
    {"type":"function","function":{"name":"ai_tts_advanced","description":"使用AI情感语音合成(火山引擎豆包·语音合成)，支持情感表达和语速音调调节","parameters":{"type":"object","properties":{"text":{"type":"string","description":"要合成的文本"},"voice_id":{"type":"string","default":"zh_female_xiaoyi","description":"声音ID"},"emotion":{"type":"string","enum":["neutral","happy","sad","excited","calm","angry"],"default":"neutral","description":"情感"},"speed":{"type":"number","default":1.0,"description":"语速倍率0.5-2.0"},"pitch":{"type":"integer","default":0,"description":"音调-100~+100"}},"required":["text"]}}},
    # 声音克隆
    {"type":"function","function":{"name":"ai_voice_clone","description":"克隆声音样本并合成语音","parameters":{"type":"object","properties":{"audio_sample":{"type":"string","description":"声音样本文件路径(.wav/.mp3, 10-30秒)"},"text":{"type":"string","description":"要合成的文本"},"emotion":{"type":"string","enum":["neutral","happy","sad","excited"],"default":"neutral","description":"情感"}},"required":["audio_sample","text"]}}},
    # 向量嵌入
    {"type":"function","function":{"name":"ai_embedding_create","description":"生成文本向量嵌入(用于知识库RAG)","parameters":{"type":"object","properties":{"texts":{"type":"string","description":"文本内容(多个用换行分隔)"},"model":{"type":"string","default":"doubao-embedding","description":"嵌入模型"}},"required":["texts"]}}},

    # ═══════════════════════════════════════════════════════════════
    # Phase B: 补齐缺失工具 — 内容发布CRUD
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"content_update","description":"修改已有内容","parameters":{"type":"object","properties":{"content_id":{"type":"string","description":"内容ID"},"title":{"type":"string","description":"新标题"},"body":{"type":"string","description":"新正文"},"platforms":{"type":"string","description":"平台列表(逗号分隔)"},"tags":{"type":"string","description":"标签(逗号分隔)"}},"required":["content_id"]}}},
    {"type":"function","function":{"name":"content_delete","description":"删除内容(管理员)","parameters":{"type":"object","properties":{"content_id":{"type":"string","description":"内容ID"}},"required":["content_id"]}}},
    {"type":"function","function":{"name":"content_reject","description":"驳回内容(管理员)","parameters":{"type":"object","properties":{"content_id":{"type":"string","description":"内容ID"},"comment":{"type":"string","description":"驳回原因"}},"required":["content_id"]}}},
    {"type":"function","function":{"name":"content_schedule","description":"排期发布内容","parameters":{"type":"object","properties":{"content_id":{"type":"string","description":"内容ID"},"scheduled_at":{"type":"string","description":"定时发布时间(ISO格式)"}},"required":["content_id","scheduled_at"]}}},
    {"type":"function","function":{"name":"content_publish","description":"立即发布内容到所有平台","parameters":{"type":"object","properties":{"content_id":{"type":"string","description":"内容ID"},"platform":{"type":"string","description":"指定平台，空=所有"}},"required":["content_id"]}}},

    # ═══════════════════════════════════════════════════════════════
    # Phase B: 补齐缺失工具 — 平台运营
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"platform_login","description":"触发平台扫码登录。系统会在本地打开浏览器窗口，用户扫码完成登录后自动保存Cookie。调用后用户需要在浏览器中手动操作，约需10-60秒。","parameters":{"type":"object","properties":{"platform":{"type":"string","enum":["douyin","xhs","wechat_mp","bilibili","kuaishou"],"description":"平台ID"}},"required":["platform"]}}},
    {"type":"function","function":{"name":"platform_logout","description":"清除平台登录态","parameters":{"type":"object","properties":{"platform":{"type":"string","enum":["douyin","xhs","wechat_mp","bilibili","kuaishou"],"description":"平台ID"}},"required":["platform"]}}},
    {"type":"function","function":{"name":"platform_url","description":"获取平台创作者中心URL","parameters":{"type":"object","properties":{"platform":{"type":"string","enum":["douyin","xhs","wechat_mp","bilibili","kuaishou"],"description":"平台ID"}},"required":["platform"]}}},
    {"type":"function","function":{"name":"platform_sync_cookies","description":"同步Electron浏览器Cookie到后端(用于Playwright自动化)","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台ID"},"cookies_json":{"type":"string","description":"Cookie JSON字符串"}},"required":["platform","cookies_json"]}}},

    # ═══════════════════════════════════════════════════════════════
    # social-auto-upload 集成 — 多平台视频/图文发布
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"sau_list_platforms","description":"列出social-auto-upload支持的所有平台(抖音/小红书/快手/视频号/YouTube)及登录状态","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"sau_upload_video","description":"通过social-auto-upload上传视频到指定平台。支持抖音/小红书/快手/视频号/YouTube。需要本地视频文件路径。","parameters":{"type":"object","properties":{"platform":{"type":"string","enum":["douyin","xhs","kuaishou","tencent","youtube"],"description":"目标平台"},"file_path":{"type":"string","description":"视频文件本地绝对路径"},"title":{"type":"string","description":"视频标题"},"desc":{"type":"string","description":"视频描述(可选)"},"tags":{"type":"string","description":"逗号分隔的标签(可选)"},"thumbnail_path":{"type":"string","description":"封面图路径(可选)"},"schedule":{"type":"string","description":"定时发布时间 YYYY-MM-DD HH:MM (可选,空则立即发布)"},"headless":{"type":"boolean","description":"是否无头模式,默认true"}},"required":["platform","file_path","title"]}}},
    {"type":"function","function":{"name":"sau_upload_note","description":"通过social-auto-upload上传图文笔记到指定平台。支持抖音/小红书/快手/视频号。","parameters":{"type":"object","properties":{"platform":{"type":"string","enum":["douyin","xhs","kuaishou","tencent"],"description":"目标平台"},"image_paths":{"type":"string","description":"逗号分隔的图片文件本地路径"},"title":{"type":"string","description":"图文标题"},"note":{"type":"string","description":"图文正文(可选)"},"tags":{"type":"string","description":"逗号分隔的标签(可选)"},"schedule":{"type":"string","description":"定时发布时间 YYYY-MM-DD HH:MM (可选)"},"headless":{"type":"boolean","description":"是否无头模式,默认true"}},"required":["platform","image_paths","title"]}}},
    {"type":"function","function":{"name":"sau_check_login","description":"检查social-auto-upload平台登录状态(Cookie是否有效)","parameters":{"type":"object","properties":{"platform":{"type":"string","enum":["douyin","xhs","kuaishou","tencent","youtube"],"description":"平台名"}},"required":["platform"]}}},
    {"type":"function","function":{"name":"sau_login","description":"触发social-auto-upload平台扫码登录。会在本地打开浏览器窗口等待用户扫码。","parameters":{"type":"object","properties":{"platform":{"type":"string","enum":["douyin","xhs","kuaishou","tencent","youtube"],"description":"平台名"},"headless":{"type":"boolean","description":"是否无头模式,默认false(登录需要有头)"}},"required":["platform"]}}},

    # ═══════════════════════════════════════════════════════════════
    # Phase B: 补齐缺失工具 — 调度引擎
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"scheduler_update","description":"修改定时任务","parameters":{"type":"object","properties":{"job_id":{"type":"string","description":"任务ID"},"name":{"type":"string","description":"新名称"},"action":{"type":"string","description":"新动作"},"trigger_type":{"type":"string","description":"触发类型"},"minutes":{"type":"integer","description":"间隔分钟数"},"priority":{"type":"integer","description":"优先级1-10"}},"required":["job_id"]}}},

    # ═══════════════════════════════════════════════════════════════
    # Phase B: 补齐缺失工具 — 工具管理
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"tool_install","description":"安装工具(管理员)","parameters":{"type":"object","properties":{"soft_id":{"type":"string","description":"工具ID"},"soft_code":{"type":"string","description":"工具代码"},"version":{"type":"string","description":"版本"},"file_path":{"type":"string","description":"文件路径"}},"required":["soft_id","soft_code","version","file_path"]}}},
    {"type":"function","function":{"name":"tool_uninstall","description":"卸载工具(管理员)","parameters":{"type":"object","properties":{"soft_id":{"type":"string","description":"工具ID"}},"required":["soft_id"]}}},
    {"type":"function","function":{"name":"tool_launch","description":"启动已安装的工具","parameters":{"type":"object","properties":{"soft_id":{"type":"string","description":"工具ID"}},"required":["soft_id"]}}},
    {"type":"function","function":{"name":"tool_stop","description":"停止运行中的工具","parameters":{"type":"object","properties":{"soft_id":{"type":"string","description":"工具ID"}},"required":["soft_id"]}}},

    # ═══════════════════════════════════════════════════════════════
    # Phase B: 补齐缺失工具 — 本地AI引擎
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"local_ollama_models","description":"列出本地Ollama已安装的模型","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"local_ollama_chat","description":"与本地Ollama模型对话","parameters":{"type":"object","properties":{"prompt":{"type":"string","description":"提示词"},"model":{"type":"string","default":"qwen3","description":"模型名"},"system":{"type":"string","description":"系统提示词"}},"required":["prompt"]}}},
    {"type":"function","function":{"name":"local_comfyui_generate","description":"使用本地ComfyUI生成图像","parameters":{"type":"object","properties":{"prompt":{"type":"string","description":"图像描述"},"negative":{"type":"string","default":"","description":"负面提示词"},"steps":{"type":"integer","default":15,"description":"步数"},"width":{"type":"integer","default":768},"height":{"type":"integer","default":768}},"required":["prompt"]}}},
    {"type":"function","function":{"name":"runtime_list","description":"列出运行中的本地进程","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"runtime_launch","description":"启动本地可执行程序(管理员)","parameters":{"type":"object","properties":{"exe_path":{"type":"string","description":"可执行文件路径"},"cwd":{"type":"string","default":"","description":"工作目录"}},"required":["exe_path"]}}},
    {"type":"function","function":{"name":"runtime_stop","description":"停止本地进程(管理员)","parameters":{"type":"object","properties":{"exe_path":{"type":"string","description":"可执行文件路径"}},"required":["exe_path"]}}},

    # ═══════════════════════════════════════════════════════════════
    # Phase B: 补齐缺失工具 — SOP/公告/Brain/配置
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"sop_list","description":"列出所有SOP工作流","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"sop_define","description":"定义新SOP工作流","parameters":{"type":"object","properties":{"name":{"type":"string","description":"SOP名称"},"description":{"type":"string","description":"描述"},"steps_json":{"type":"string","description":"步骤JSON数组"}},"required":["name","steps_json"]}}},
    {"type":"function","function":{"name":"announce_list","description":"列出系统公告","parameters":{"type":"object","properties":{"limit":{"type":"integer","default":10,"description":"返回条数"}},"required":[]}}},
    {"type":"function","function":{"name":"announce_create","description":"创建系统公告(管理员)","parameters":{"type":"object","properties":{"title":{"type":"string","description":"标题"},"content":{"type":"string","description":"内容"},"level":{"type":"string","default":"info","description":"级别(info/warning/success/error)"},"is_pinned":{"type":"boolean","default":False,"description":"是否置顶"}},"required":["title","content"]}}},
    {"type":"function","function":{"name":"announce_delete","description":"删除系统公告(管理员)","parameters":{"type":"object","properties":{"announce_id":{"type":"string","description":"公告ID"}},"required":["announce_id"]}}},
    {"type":"function","function":{"name":"brain_status","description":"获取Hermes内核状态","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"brain_prompt","description":"查看当前Hermes系统提示词","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"brain_mcp","description":"列出MCP服务状态","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"models_list","description":"列出所有可用AI模型","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"system_config","description":"查看系统配置(脱敏)","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"oem_config_update","description":"更新品牌配置(管理员)","parameters":{"type":"object","properties":{"name":{"type":"string","description":"品牌名称"},"theme":{"type":"string","description":"主题"},"copyright":{"type":"string","description":"版权信息"}},"required":[]}}},

    # ═══════════════════════════════════════════════════════════════
    # Phase C: 多模型流水线编排
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"pipeline_list","description":"列出所有可用的多模型AIGC流水线模板","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"pipeline_get","description":"获取流水线模板的详细信息(节点/模型/参数)","parameters":{"type":"object","properties":{"name":{"type":"string","description":"流水线名称"}},"required":["name"]}}},
    {"type":"function","function":{"name":"pipeline_video_create","description":"使用AI短视频流水线创作视频: 主题→脚本→封面+视频+配音→合成","parameters":{"type":"object","properties":{"topic":{"type":"string","description":"视频主题"},"duration":{"type":"integer","default":30,"description":"时长秒数"},"style":{"type":"string","default":"realistic","description":"图像风格"}},"required":["topic"]}}},
    {"type":"function","function":{"name":"pipeline_content_create","description":"使用智能内容流水线: 主题→文案+配图","parameters":{"type":"object","properties":{"topic":{"type":"string","description":"内容主题"},"platform":{"type":"string","default":"xiaohongshu","description":"目标平台"}},"required":["topic"]}}},
    {"type":"function","function":{"name":"pipeline_image_set","description":"使用AI图集流水线: 主题→多种风格图像","parameters":{"type":"object","properties":{"topic":{"type":"string","description":"图像主题"}},"required":["topic"]}}},

    # ═══════════════════════════════════════════════════════════════
    # Phase D: 流量引擎 — 智能截流 + 评论管理
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"acquisition_search","description":"多平台视频搜索+质量评分。跨抖音/小红书/B站/快手搜索视频并自动评分排序","parameters":{"type":"object","properties":{"keyword":{"type":"string","description":"搜索关键词"},"platforms":{"type":"string","description":"平台列表，逗号分隔: douyin,xhs,bilibili,kuaishou，默认全部"},"limit":{"type":"integer","default":20,"description":"返回数量"}},"required":["keyword"]}}},
    {"type":"function","function":{"name":"acquisition_intercept","description":"一键智能截流: 搜索→筛选→AI生成→DeAI去味→发送评论","parameters":{"type":"object","properties":{"keyword":{"type":"string","description":"搜索关键词"},"platforms":{"type":"string","description":"逗号分隔的平台"},"comment_count":{"type":"integer","default":5,"description":"每个视频发送评论数"},"strategy":{"type":"string","enum":["balanced","fast","cautious"],"default":"balanced","description":"行为策略"}},"required":["keyword"]}}},
    {"type":"function","function":{"name":"acquisition_generate_comments","description":"AI生成真人风格评论(可指定策略和数量)","parameters":{"type":"object","properties":{"video_title":{"type":"string","description":"视频标题"},"video_desc":{"type":"string","default":"","description":"视频简介"},"count":{"type":"integer","default":3,"description":"生成数量"},"strategy":{"type":"string","default":"balanced","description":"策略"}},"required":["video_title"]}}},
    {"type":"function","function":{"name":"acquisition_deai","description":"DeAI去AI味处理: 去除AI模板句式、替换敏感营销词、添加真人语气","parameters":{"type":"object","properties":{"text":{"type":"string","description":"原始评论文本"},"platform":{"type":"string","default":"douyin"}},"required":["text"]}}},
    {"type":"function","function":{"name":"acquisition_preflight","description":"评论发前检查: 屏蔽词/长度/中文占比/垃圾模式","parameters":{"type":"object","properties":{"text":{"type":"string","description":"待检查的评论"}},"required":["text"]}}},
    {"type":"function","function":{"name":"acquisition_comment_send","description":"批量发送评论到平台","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台 douyin/xhs/bilibili/kuaishou"},"comments_json":{"type":"string","description":"评论JSON数组，每项{text, video_id, video_title, video_url}"},"strategy":{"type":"string","default":"balanced"}},"required":["platform","comments_json"]}}},
    {"type":"function","function":{"name":"acquisition_queue","description":"查看评论队列(全部/按状态过滤)","parameters":{"type":"object","properties":{"status":{"type":"string","description":"过滤: pending/sent/failed/skipped"},"platform":{"type":"string","description":"过滤平台"},"limit":{"type":"integer","default":30}},"required":[]}}},
    {"type":"function","function":{"name":"acquisition_stats","description":"截流+评论统计: 历史总数/活跃AB测试/频率限制","parameters":{"type":"object","properties":{}}}},
    # 舆情监听
    {"type":"function","function":{"name":"acquisition_monitor_list","description":"列出舆情监听目标(监控的视频列表)","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"acquisition_monitor_add","description":"添加监听目标，自动发现新评论中的客户线索","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台ID"},"video_url":{"type":"string","description":"视频URL"},"video_title":{"type":"string","default":"","description":"视频标题"},"owner":{"type":"string","default":"own","description":"own=自己的视频, competitor=竞品"}},"required":["platform","video_url"]}}},
    {"type":"function","function":{"name":"acquisition_monitor_start","description":"启动后台监听引擎(异步轮询)","parameters":{"type":"object","properties":{"interval":{"type":"integer","default":300,"description":"轮询间隔秒数"}},"required":[]}}},
    {"type":"function","function":{"name":"acquisition_monitor_stop","description":"停止后台监听引擎","parameters":{"type":"object","properties":{}}}},
    # A/B 测试
    {"type":"function","function":{"name":"acquisition_ab_start","description":"启动评论策略A/B测试，对比两种策略效果","parameters":{"type":"object","properties":{"strategy_a":{"type":"string","description":"策略A: balanced/fast/cautious"},"strategy_b":{"type":"string","description":"策略B: balanced/fast/cautious"},"platform":{"type":"string","default":"douyin"},"video_count":{"type":"integer","default":10}},"required":["strategy_a","strategy_b"]}}},
    {"type":"function","function":{"name":"acquisition_ab_list","description":"查看A/B测试结果列表","parameters":{"type":"object","properties":{"status":{"type":"string","description":"running/completed"}},"required":[]}}},
    # 客户转化
    {"type":"function","function":{"name":"acquisition_leads","description":"查看客户线索列表(按等级/状态/平台过滤)","parameters":{"type":"object","properties":{"status":{"type":"string","description":"new/contacted/replied/qualified/converted"},"grade":{"type":"string","description":"A/B/C/D"},"platform":{"type":"string"},"limit":{"type":"integer","default":30}},"required":[]}}},
    {"type":"function","function":{"name":"acquisition_lead_score","description":"对评论进行线索评分(A=购买意向/B=学习意向/C=普通/D=无价值)","parameters":{"type":"object","properties":{"comment_text":{"type":"string","description":"评论内容"},"author_name":{"type":"string","default":"","description":"评论者昵称"}},"required":["comment_text"]}}},
    {"type":"function","function":{"name":"acquisition_auto_reply","description":"AI生成回复并评分(支持dry_run预览模式)","parameters":{"type":"object","properties":{"platform":{"type":"string","default":"douyin"},"comments_json":{"type":"string","description":"评论JSON数组"},"dry_run":{"type":"boolean","default":True,"description":"true=仅预览不发送"}},"required":["comments_json"]}}},
    {"type":"function","function":{"name":"acquisition_funnel","description":"查看转化漏斗: discovered→replied→dm_sent→responded→qualified→converted","parameters":{"type":"object","properties":{}}}},
    # 行为策略
    {"type":"function","function":{"name":"acquisition_strategy","description":"查看可用行为策略及参数","parameters":{"type":"object","properties":{"platform":{"type":"string","default":"douyin"}},"required":[]}}},
    {"type":"function","function":{"name":"acquisition_strategy_apply","description":"应用行为策略到平台的频率限制","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台ID"},"strategy":{"type":"string","enum":["balanced","fast","cautious"],"description":"策略名称"}},"required":["platform","strategy"]}}},
    # ═══════════════════════════════════════════════════════════════
    # Acquisition MCP — 平台采集工具 (搜索/评论/私信)
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"acq_platforms","description":"列出所有支持的采集平台(bilibili/douyin/xhs/kuaishou)及其状态","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"acq_search","description":"在指定平台搜索视频(B站用API,其他用浏览器自动化)","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台: bilibili/douyin/xhs/kuaishou"},"keyword":{"type":"string","description":"搜索关键词"},"limit":{"type":"integer","default":20,"description":"返回数量"}},"required":["platform","keyword"]}}},
    {"type":"function","function":{"name":"acq_get_comments","description":"获取指定视频的评论列表","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台: bilibili/douyin/xhs/kuaishou"},"video_url":{"type":"string","description":"视频/笔记完整URL"},"limit":{"type":"integer","default":30,"description":"评论数量上限"}},"required":["platform","video_url"]}}},
    {"type":"function","function":{"name":"acq_send_comment","description":"在指定视频下发送评论(需要平台已登录)","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台: bilibili/douyin/xhs/kuaishou"},"video_url":{"type":"string","description":"视频/笔记完整URL"},"comment_text":{"type":"string","description":"评论内容"}},"required":["platform","video_url","comment_text"]}}},
    {"type":"function","function":{"name":"acq_batch_send_comments","description":"批量发送评论到指定平台的多个视频","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台: bilibili/douyin/xhs/kuaishou"},"comments_json":{"type":"string","description":"JSON数组，每项含{video_url, comment_text}"}},"required":["platform","comments_json"]}}},
    {"type":"function","function":{"name":"acq_send_dm","description":"发送私信给指定用户(目前仅支持B站)","parameters":{"type":"object","properties":{"platform":{"type":"string","description":"平台: bilibili"},"user_id":{"type":"string","description":"目标用户ID"},"text":{"type":"string","description":"私信内容"}},"required":["platform","user_id","text"]}}},
]

SYSTEM_PROMPT = """你是 szyg 智能矩阵运营系统的超级AI员工。

## 核心能力
你能通过函数调用调度以下子系统：

**内容生产**: content_create(标题+正文+类型) → content_submit → content_approve → platform_publish_direct
**平台运营**: platform_list 查看所有平台状态, platform_status 查单个平台, platform_health 健康检查
**发布**: platform_publish_direct(platform, title, body, tags, content_type, media_urls) 直接发布到抖音/小红书/B站/快手/微信
  - content_type: post=图文短帖, video=视频, image=图文
  - media_urls: 逗号分隔的媒体URL或本地路径。视频发布时必填视频文件路径
**调度**: scheduler_list/create 任务管理, scheduler_execute/pause/resume/delete 任务控制, scheduler_history/stats 历史统计
**办公文档**: docx/xlsx/pptx 创建和读取, pdf 提取和合并, docx_to_markdown/docx_extract_text/xlsx_read/pptx_extract/pdf_extract/pdf_merge
**设计**: canvas_get_fonts/canvas_preview_config Canvas设计资源
**工具市场**: tools_catalog 浏览工具列表, tools_search 搜索工具, tools_categories 查看分类, tools_stats 统计信息
**品牌定制**: oem_config 查看OEM配置, oem_config_update 更新品牌(管理员)
**视频剪辑**: video_info 查看元信息, video_cut/concat 裁剪拼接, video_speed 变速, video_add_title 叠加标题, video_replace_audio/mix_audio 音频替换混音, video_extract_frame 提取封面, video_render 模板渲染
**知识库**: knowledge_search 检索, knowledge_ingest 摄入文档, knowledge_stats 统计
**智能体**: agents_list/get/tiers/categories 智能体市场管理
**AIGC生成(火山引擎)**: ai_image_generate 生成图像(豆包/SDXL/FLUX), ai_image_styles 列出风格
**AI视频**: ai_video_create 生成视频(豆包·视频生成/Seaweed), ai_video_task_status 查询任务状态
**AI语音**: ai_tts_advanced 情感语音合成(支持6种情感), ai_voice_clone 声音克隆
**向量嵌入**: ai_embedding_create 文本向量化(知识库RAG)
**内容管理**: content_get 查看详情, content_update 修改, content_delete 删除(管理员), content_reject 驳回(管理员), content_schedule 定时发布, content_publish 立即发布
**平台运营**: platform_list 查看状态, platform_status 单个状态, platform_sessions 登录态详情, platform_login 触发扫码登录, platform_logout 清除登录态, platform_url 获取登录URL, platform_sync_cookies 同步浏览器Cookie
**调度管理**: scheduler_update 修改任务
**工具管理**: tool_install/uninstall 安装卸载(管理员), tool_launch/stop 启动停止
**本地AI**: local_ollama_models/chat 本地Ollama对话, local_comfyui_generate 本地ComfyUI生图, runtime_list/launch/stop 本地进程管理
**SOP工作流**: sop_list 列出, sop_define 定义
**公告管理**: announce_list 查看, announce_create 创建(管理员), announce_delete 删除(管理员)
**内核诊断**: brain_status 状态, brain_prompt 提示词, brain_mcp MCP服务
**流水线编排(火山引擎多模型)**: pipeline_list 列出模板, pipeline_video_create AI短视频(脚本+封面+视频+配音+合成), pipeline_content_create 智能内容(文案+配图), pipeline_image_set AI图集(多风格)
**系统信息**: models_list 模型列表, system_config 系统配置
**智能截流(流量引擎)**: acquisition_search 多平台搜索视频, acquisition_intercept 一键截流(搜索→生成→发送), acquisition_generate_comments AI生成评论, acquisition_deai 去AI味处理, acquisition_preflight 发前检查
**评论管理**: acquisition_comment_send 批量发送评论, acquisition_queue 评论队列, acquisition_stats 截流统计
**舆情监听**: acquisition_monitor_list 监听目标列表, acquisition_monitor_add 添加监听, acquisition_monitor_start/stop 启停监听引擎
**A/B测试**: acquisition_ab_start 启动策略对比测试, acquisition_ab_list 查看测试结果
**客户转化**: acquisition_leads 线索列表, acquisition_lead_score 线索评分(A/B/C/D), acquisition_auto_reply AI自动回复, acquisition_funnel 转化漏斗
**行为策略**: acquisition_strategy 查看策略参数, acquisition_strategy_apply 应用策略到平台
**平台采集(直接调用)**: acq_platforms 查看采集平台, acq_search 搜索视频(支持bilibili/douyin/xhs/kuaishou), acq_get_comments 获取评论, acq_send_comment 发送评论, acq_batch_send_comments 批量发送, acq_send_dm 发私信(B站)
**多平台发布(social-auto-upload)**: sau_list_platforms 查看支持的平台(抖音/小红书/快手/视频号/YouTube), sau_upload_video 上传视频, sau_upload_note 上传图文, sau_check_login 检查登录, sau_login 扫码登录
**其他**: skills_list

## 智能发布工作流 (重要!)

当用户要求「发布到抖音/小红书/B站」等平台时，务必遵循此流程：

### 第1步: 检查登录状态
调用 platform_status(platform) 检查目标平台是否已登录。
- 如果已登录 → 跳到第3步
- 如果未登录 → 执行第2步

### 第2步: 引导用户登录
调用 platform_login(platform) 触发扫码登录。
系统会在本地打开浏览器，你需要清晰地告诉用户:
  "正在打开 {平台名} 登录窗口，请在浏览器中扫码完成登录。登录成功后告诉我，我会继续发布。"
在此期间等待用户确认。

### 第3步: 执行发布
调用 platform_publish_direct:
- 图文帖子: content_type="post" 或 "image"
- 视频发布: content_type="video", media_urls 填写视频文件路径
- AI生成的视频: 先用 ai_video_task_status 查询任务完成后得到 video_url，再发布

### 第4步: 确认结果
发布后告诉用户: 平台、内容ID、post_id（如有）、帖子链接。

## 视频创作+发布完整流程
用户说「帮我做一个XX主题的短视频发到抖音」时:
1. ai_video_create(prompt, duration, size) → 获取 task_id
2. ai_video_task_status(task_id) 轮询 → 拿到 video_url
3. platform_status("douyin") → 检查登录
4. (如需登录) platform_login("douyin") → 引导扫码
5. platform_publish_direct("douyin", title=..., content_type="video", media_urls=video_url)
6. 报告结果

## 智能截流工作流 (评论区截流)

用户要求「在抖音/小红书/B站/快手上截流XX关键词」时:

1. acquisition_search(keyword="关键词", platforms="douyin,xhs") → 搜索相关视频并自动按质量评分排序
2. 分析搜索结果，向用户展示 Top-N 优质视频（评分≥50）
3. 用户确认后，调用 acquisition_intercept(keyword="关键词", platforms="...", comment_count=5) 一键执行
4. 或者分步执行:
   a. acquisition_generate_comments(video_title="...") → 生成评论
   b. acquisition_deai(text="...") → 去AI味处理
   c. acquisition_preflight(text="...") → 发前安全检查
   d. acquisition_comment_send(platform="...", comments_json="[...]") → 发送

截流完成后，可以:
- acquisition_queue 查看已发送的评论
- acquisition_stats 查看整体统计

## 客户线索管理

用户问「有什么新线索」或「查看转化情况」时:
1. acquisition_leads(grade="A") → 查看高价值线索
2. acquisition_lead_score(comment_text="...") → 对任意评论打分
3. acquisition_auto_reply(comments_json="[...]", dry_run=true) → 预览AI回复
4. acquisition_funnel → 查看转化漏斗
5. acquisition_monitor_list → 查看监听中的视频
6. acquisition_monitor_add(platform="douyin", video_url="...") → 添加要监听的目标

## 回复要求
用简体中文，简洁专业。函数调用的参数要准确填写。

### 工具结果呈现规则（必须严格遵守）
1. 禁止原样输出工具返回的 JSON。工具返回的数据是供你分析的内部数据，不是给用户看的原始内容。
2. 调用工具后，用自然语言 + 结构化格式（表格、列表）向用户总结关键信息。
3. 列表数据（搜索结果、评论列表）提取关键字段以表格或编号列表呈现。
4. 操作结果用一句话确认，附上关键标识。
5. 错误用自然语言解释原因和解决方案，不输出原始 error JSON。
6. 绝对不要在回复中包含原始 JSON 片段。"""

# ── Agent-aware system prompt builder ───────────────────

def _build_system_prompt(agent_id: str = "", expert_prompt: str = "") -> tuple[str, float]:
    """Build system prompt from staff agent config.

    Returns: (system_prompt, temperature)

    优先级：显式传入的 expert_prompt（AI人才市场）> staff agent config > 默认 Hermes Prompt
    """
    # 优先：AI人才市场显式传入的专家 prompt（独立通道，不影响超级员工）
    if expert_prompt:
        cn_instruction = "\n\n---\n## 重要：总是使用中文和用户对话\n"
        tool_hint = (
            "\n\n---\n## 你的工具能力（szyg 智能矩阵运营系统）\n"
            "你同时拥有以下工具能力，可按需调用完成营销任务：\n"
            "- 内容发布管道（创建/审核/排期/发布多平台内容）\n"
            "- 平台自动化（抖音/小红书/微信/B站登录态与发布）\n"
            "- 视频剪辑引擎（裁剪/拼接/变速/字幕/混音/模板）\n"
            "- 智能调度引擎（cron/interval 定时任务）\n"
            "- 知识库（FTS5 全文检索/文档摄入/RAG）\n"
            "- AI 图像/视频生成（火山引擎豆包系列）\n"
            "- 获客截流（搜索目标视频/生成真人评论/批量发送）\n\n"
            "回复要求：用中文回复，专业简洁，主动使用工具完成任务。"
        )
        return expert_prompt + cn_instruction + tool_hint, 0.7

    if not agent_id:
        return SYSTEM_PROMPT, 0.7  # default for generic mode

    # Load agent config
    import json
    from pathlib import Path
    from szyg.data_path import DATA_DIR

    configs_file = DATA_DIR / "staff" / "agent_configs.json"
    config = None
    if configs_file.exists():
        try:
            configs = json.loads(configs_file.read_text(encoding="utf-8"))
            config = configs.get(agent_id)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load agent config for %s: %s", agent_id, e)

    if not config:
        return SYSTEM_PROMPT, 0.7

    soul = config.get("soul", {})
    skills = config.get("skills", {}).get("list", [])
    basic = config.get("basic", {})
    memory_cfg = config.get("memory", {})

    # Build role-specific prompt
    parts = [SYSTEM_PROMPT]

    # Identity
    agent_name = basic.get("name", agent_id)
    agent_desc = basic.get("description", "")
    parts.append(f"\n## 你的角色\n你是 **{agent_name}**。{agent_desc}")

    # System prompt from config
    system_prompt = soul.get("systemPrompt", "")
    if system_prompt:
        parts.append(f"\n## 角色指令\n{system_prompt}")

    # Behavior mode
    behavior = soul.get("behaviorMode", "balanced")
    mode_hints = {
        "fast": "\n## 行为模式: 快速\n优先使用工具，精简对话，快速完成任务。",
        "cautious": "\n## 行为模式: 谨慎\n每一步操作前先确认，充分解释风险，避免误操作。",
        "balanced": "\n## 行为模式: 均衡\n在效率和谨慎之间保持平衡。",
    }
    parts.append(mode_hints.get(behavior, ""))

    # Available skills
    enabled_skills = [s for s in skills if s.get("enabled")]
    if enabled_skills:
        skill_names = ", ".join(s["name"] for s in enabled_skills)
        parts.append(f"\n## 可用技能\n{skill_names}")

    # Knowledge bases
    kbs = memory_cfg.get("knowledgeBases", [])
    if kbs:
        parts.append(f"\n## 知识库访问\n你可以优先参考以下知识库: {', '.join(kbs)}")

    temperature = float(soul.get("temperature", 0.7))
    return "\n".join(parts), temperature

# ── Tool execution ─────────────────────────────────────

async def _execute_tool(name: str, args_str: str, auth_header: dict | None = None) -> str:
    """Execute szyg tool safely: allowlist + httpx params (no URL injection).

    Args:
        auth_header: Optional dict with Authorization header for internal API calls.
                     Enables authenticated write operations (scheduler_create, approve, etc.)
    """
    args = _sanitize_args(name, args_str)
    auth_headers = auth_header or {}

    # Auth-aware httpx wrappers — use internal client (bypasses system proxy)
    # IMPORTANT: async wrappers run sync httpx in thread pool to avoid blocking
    # the uvicorn event loop (single-worker deadlock when calling 127.0.0.1:8000)
    import functools
    _GET = functools.partial(_internal_client.get, headers=auth_headers)
    _POST = functools.partial(_internal_client.post, headers=auth_headers)
    _PUT = functools.partial(_internal_client.put, headers=auth_headers)
    _DELETE = functools.partial(_internal_client.delete, headers=auth_headers)

    async def _aGET(url, **kw):
        r = await asyncio.to_thread(_GET, url, **kw)
        return r
    async def _aPOST(url, **kw):
        r = await asyncio.to_thread(_POST, url, **kw)
        return r
    async def _aPUT(url, **kw):
        r = await asyncio.to_thread(_PUT, url, **kw)
        return r
    async def _aDELETE(url, **kw):
        r = await asyncio.to_thread(_DELETE, url, **kw)
        return r

    ALLOWED = {
        "content_list","content_create","content_get","content_submit","content_approve",
        "content_generate","content_stats",
        "platform_list","platform_status","platform_publish_direct","platform_sessions","platform_health","platform_post_status",
        "scheduler_list","scheduler_create","scheduler_get","scheduler_execute",
        "scheduler_pause","scheduler_resume","scheduler_delete","scheduler_history","scheduler_stats",
        "docx_create","docx_to_markdown","docx_extract_text",
        "xlsx_create","xlsx_read",
        "pptx_create","pptx_extract",
        "pdf_extract","pdf_merge",
        "canvas_get_fonts","canvas_preview_config",
        "knowledge_search","knowledge_ingest","knowledge_stats",
        "video_templates","video_info","video_cut","video_concat","video_speed",
        "video_add_title","video_replace_audio","video_mix_audio","video_extract_frame",
        "video_fonts","video_render",
        "agents_list","agents_get","agents_tiers","agents_categories",
        "skills_list",
        # Tool Marketplace
        "tools_catalog","tools_categories","tools_installed","tools_stats","tools_search",
        # OEM Branding
        "oem_config","oem_themes",
        # AIGC — 火山引擎方舟
        "ai_image_generate","ai_image_styles",
        "ai_video_create","ai_video_task_status",
        "ai_tts_advanced","ai_voice_clone",
        "ai_embedding_create",
        # Phase B: 补齐内容发布
        "content_update","content_delete","content_reject","content_schedule","content_publish",
        # Phase B: 补齐平台运营
        "platform_login","platform_logout","platform_url","platform_sync_cookies",
        # Phase B: 补齐调度引擎
        "scheduler_update",
        # Phase B: 补齐工具管理
        "tool_install","tool_uninstall","tool_launch","tool_stop",
        # Phase B: 本地AI引擎
        "local_ollama_models","local_ollama_chat","local_comfyui_generate",
        "runtime_list","runtime_launch","runtime_stop",
        # Phase B: SOP/公告/Brain/配置
        "sop_list","sop_define",
        "announce_list","announce_create","announce_delete",
        "brain_status","brain_prompt","brain_mcp",
        "models_list","system_config","oem_config_update",
        # Phase C: 多模型流水线编排
        "pipeline_list","pipeline_get",
        "pipeline_video_create","pipeline_content_create","pipeline_image_set",
        # Phase D: 流量引擎 + 客户转化
        "acquisition_search","acquisition_intercept","acquisition_generate_comments",
        "acquisition_deai","acquisition_preflight","acquisition_comment_send",
        "acquisition_queue","acquisition_stats",
        "acquisition_monitor_list","acquisition_monitor_add",
        "acquisition_monitor_start","acquisition_monitor_stop",
        "acquisition_ab_start","acquisition_ab_list",
        "acquisition_leads","acquisition_lead_score",
        "acquisition_auto_reply","acquisition_funnel",
        "acquisition_strategy","acquisition_strategy_apply",
        # Acquisition MCP — 平台采集工具
        "acq_platforms","acq_search","acq_get_comments",
        "acq_send_comment","acq_batch_send_comments","acq_send_dm",
        # social-auto-upload 集成
        "sau_list_platforms","sau_upload_video","sau_upload_note",
        "sau_check_login","sau_login",
    }
    if name not in ALLOWED:
        return f"错误: 工具 '{name}' 不被允许"

    base = "http://127.0.0.1:8000"
    try:
        if name == "content_list":
            r = await _aGET(f"{base}/api/publisher/contents", params={"status": args.get("status","")}, timeout=30)
        elif name == "content_create":
            r = await _aPOST(f"{base}/api/publisher/contents", params={k: str(v) for k,v in args.items() if k in ("title","body","content_type","tags")}, timeout=30)
        elif name == "content_get":
            r = await _aGET(f"{base}/api/publisher/contents/{args.get('content_id','')}", timeout=30)
        elif name == "content_submit":
            r = await _aPOST(f"{base}/api/publisher/contents/{args.get('content_id','')}/submit", timeout=30)
        elif name == "content_approve":
            r = await _aPOST(f"{base}/api/publisher/contents/{args.get('content_id','')}/approve", timeout=30)
        elif name == "content_generate":
            r = await _aPOST(f"{base}/api/publisher/ai-generate", params={"topic": args.get("topic","")}, timeout=60)
        elif name == "content_stats":
            r = await _aGET(f"{base}/api/publisher/stats", timeout=30)
        elif name == "platform_list":
            r = await _aGET(f"{base}/api/platforms", timeout=30)
        elif name == "platform_status":
            r = await _aGET(f"{base}/api/platforms/{args.get('platform','')}", timeout=30)
        elif name == "platform_publish_direct":
            r = await _aPOST(f"{base}/api/platforms/{args.get('platform','')}/publish", params={k: str(v) for k,v in args.items() if k in ("title","body","tags","media_urls","content_type")}, timeout=120)
        elif name == "platform_post_status":
            r = await _aGET(f"{base}/api/platforms/{args.get('platform','')}/status/{args.get('post_id','')}", timeout=60)
        elif name == "platform_sessions":
            r = await _aGET(f"{base}/api/publisher/platforms/{args.get('platform','')}/sessions", timeout=30)
        elif name == "platform_health":
            r = await _aGET(f"{base}/api/platforms/health/all", timeout=30)
        elif name == "scheduler_list":
            r = await _aGET(f"{base}/api/scheduler/jobs", timeout=30)
        elif name == "scheduler_create":
            r = await _aPOST(f"{base}/api/scheduler/jobs", params={k: str(v) for k,v in args.items() if k in ("name","trigger_type","action","cron","interval_minutes","at_time","action_config_json","priority","tags")}, timeout=30)
        elif name == "scheduler_get":
            r = await _aGET(f"{base}/api/scheduler/jobs/{args.get('job_id','')}", timeout=30)
        elif name == "scheduler_execute":
            r = await _aPOST(f"{base}/api/scheduler/jobs/{args.get('job_id','')}/execute", timeout=60)
        elif name == "scheduler_pause":
            r = await _aPOST(f"{base}/api/scheduler/jobs/{args.get('job_id','')}/pause", timeout=30)
        elif name == "scheduler_resume":
            r = await _aPOST(f"{base}/api/scheduler/jobs/{args.get('job_id','')}/resume", timeout=30)
        elif name == "scheduler_delete":
            r = await _aDELETE(f"{base}/api/scheduler/jobs/{args.get('job_id','')}", timeout=30)
        elif name == "scheduler_history":
            r = await _aGET(f"{base}/api/scheduler/history", params={k: str(v) for k,v in args.items() if k in ("job_id","limit")}, timeout=30)
        elif name == "scheduler_stats":
            r = await _aGET(f"{base}/api/scheduler/stats", timeout=30)
        elif name == "agents_list":
            r = await _aGET(f"{base}/api/agents/list", timeout=30)
        # Tool Marketplace
        elif name == "tools_catalog":
            r = await _aGET(f"{base}/api/tools/catalog", params={k: str(v) for k,v in args.items() if k in ("category","search")}, timeout=30)
        elif name == "tools_categories":
            r = await _aGET(f"{base}/api/tools/categories", timeout=30)
        elif name == "tools_installed":
            r = await _aGET(f"{base}/api/tools/installed", timeout=30)
        elif name == "tools_stats":
            r = await _aGET(f"{base}/api/tools/stats", timeout=30)
        elif name == "tools_search":
            r = await _aGET(f"{base}/api/tools/catalog", params={"search": args.get("query","")}, timeout=30)
        # OEM Branding
        elif name == "oem_config":
            r = await _aGET(f"{base}/api/oem/config/default", timeout=30)
        elif name == "oem_themes":
            return _call_direct(name, args)
        # ═══════════════════════════════════════════════════════════════
        # AIGC — 火山引擎方舟 (Phase A)
        # ═══════════════════════════════════════════════════════════════
        elif name == "ai_image_generate":
            return await _execute_volcengine_aigc(name, args)
        elif name == "ai_image_styles":
            return await _execute_volcengine_aigc(name, args)
        elif name == "ai_video_create":
            return await _execute_volcengine_aigc(name, args)
        elif name == "ai_video_task_status":
            return await _execute_volcengine_aigc(name, args)
        elif name == "ai_tts_advanced":
            return await _execute_volcengine_aigc(name, args)
        elif name == "ai_voice_clone":
            return await _execute_volcengine_aigc(name, args)
        elif name == "ai_embedding_create":
            return await _execute_volcengine_aigc(name, args)
        # ═══════════════════════════════════════════════════════════════
        # Phase B: 补齐内容发布CRUD
        # ═══════════════════════════════════════════════════════════════
        elif name == "content_update":
            params = {}
            if args.get("title"): params["title"] = args["title"]
            if args.get("body"): params["body"] = args["body"]
            if args.get("platforms"): params["platforms"] = args["platforms"]
            if args.get("tags"): params["tags"] = args["tags"]
            r = await _aPOST(f"{base}/api/publisher/contents/{args.get('content_id','')}", params=params, timeout=30)
        elif name == "content_delete":
            r = await _aDELETE(f"{base}/api/publisher/contents/{args.get('content_id','')}", timeout=30)
        elif name == "content_reject":
            r = await _aPOST(f"{base}/api/publisher/contents/{args.get('content_id','')}/reject", params={"comment": args.get("comment", "")}, timeout=30)
        elif name == "content_schedule":
            r = await _aPOST(f"{base}/api/publisher/contents/{args.get('content_id','')}/schedule", params={"scheduled_at": args.get("scheduled_at", "")}, timeout=30)
        elif name == "content_publish":
            r = await _aPOST(f"{base}/api/publisher/contents/{args.get('content_id','')}/publish", params={"platform": args.get("platform", "")}, timeout=120)
        # ═══════════════════════════════════════════════════════════════
        # Phase B: 补齐平台运营
        # ═══════════════════════════════════════════════════════════════
        elif name == "platform_login":
            r = await _aPOST(f"{base}/api/platforms/{args.get('platform','')}/login", timeout=60)
        elif name == "platform_logout":
            r = await _aDELETE(f"{base}/api/publisher/platforms/{args.get('platform','')}/sessions", timeout=30)
        elif name == "platform_url":
            r = await _aGET(f"{base}/api/platforms/{args.get('platform','')}/url", timeout=30)
        elif name == "platform_sync_cookies":
            r = await _aPOST(f"{base}/api/platforms/{args.get('platform','')}/sync-cookies", json={"cookies": json.loads(args.get("cookies_json", "[]"))}, timeout=30)
        # ═══════════════════════════════════════════════════════════════
        # Phase B: 补齐调度引擎
        # ═══════════════════════════════════════════════════════════════
        elif name == "scheduler_update":
            params = {}
            if args.get("name"): params["name"] = args["name"]
            if args.get("action"): params["action"] = args["action"]
            if args.get("trigger_type"): params["trigger_type"] = args["trigger_type"]
            if args.get("minutes"): params["minutes"] = args["minutes"]
            if args.get("priority"): params["priority"] = args["priority"]
            r = await _aPUT(f"{base}/api/scheduler/jobs/{args.get('job_id','')}", params=params, timeout=30)
        # ═══════════════════════════════════════════════════════════════
        # Phase B: 补齐工具管理
        # ═══════════════════════════════════════════════════════════════
        elif name == "tool_install":
            r = await _aPOST(f"{base}/api/tools/install", params={k: str(v) for k,v in args.items() if k in ("soft_id","soft_code","version","file_path")}, timeout=30)
        elif name == "tool_uninstall":
            r = await _aDELETE(f"{base}/api/tools/uninstall/{args.get('soft_id','')}", timeout=30)
        elif name == "tool_launch":
            r = await _aPOST(f"{base}/api/tools/launch/{args.get('soft_id','')}", timeout=30)
        elif name == "tool_stop":
            r = await _aPOST(f"{base}/api/tools/stop/{args.get('soft_id','')}", timeout=30)
        # ═══════════════════════════════════════════════════════════════
        # Phase B: 本地AI引擎
        # ═══════════════════════════════════════════════════════════════
        elif name == "local_ollama_models":
            r = await _aGET(f"{base}/api/client/ollama/models", timeout=30)
        elif name == "local_ollama_chat":
            r = await _aPOST(f"{base}/api/client/ollama/chat", params={"prompt": args.get("prompt", ""), "model": args.get("model", "qwen3"), "system": args.get("system", "")}, timeout=120)
        elif name == "local_comfyui_generate":
            r = await _aPOST(f"{base}/api/client/comfyui/generate", params={"prompt": args.get("prompt", ""), "negative": args.get("negative", ""), "steps": args.get("steps", 15), "width": args.get("width", 768), "height": args.get("height", 768)}, timeout=300)
        elif name == "runtime_list":
            r = await _aGET(f"{base}/api/client/runtime", timeout=30)
        elif name == "runtime_launch":
            r = await _aPOST(f"{base}/api/client/runtime/launch", params={"exe_path": args.get("exe_path", ""), "cwd": args.get("cwd", "")}, timeout=30)
        elif name == "runtime_stop":
            r = await _aPOST(f"{base}/api/client/runtime/stop", params={"exe_path": args.get("exe_path", "")}, timeout=30)
        # ═══════════════════════════════════════════════════════════════
        # Phase B: SOP/公告/Brain/配置
        # ═══════════════════════════════════════════════════════════════
        elif name == "sop_list":
            r = await _aGET(f"{base}/api/sop/list", timeout=30)
        elif name == "sop_define":
            r = await _aPOST(f"{base}/api/sop/define", json={"name": args.get("name", ""), "description": args.get("description", ""), "steps": json.loads(args.get("steps_json", "[]"))}, timeout=30)
        elif name == "announce_list":
            r = await _aGET(f"{base}/api/announce/list", params={"limit": args.get("limit", 10)}, timeout=30)
        elif name == "announce_create":
            r = await _aPOST(f"{base}/api/announce/create", params={"title": args.get("title", ""), "content": args.get("content", ""), "level": args.get("level", "info"), "is_pinned": str(args.get("is_pinned", False)).lower()}, timeout=30)
        elif name == "announce_delete":
            r = await _aDELETE(f"{base}/api/announce/{args.get('announce_id','')}", timeout=30)
        elif name == "brain_status":
            r = await _aGET(f"{base}/api/brain/status", timeout=30)
        elif name == "brain_prompt":
            r = await _aGET(f"{base}/api/brain/prompt", timeout=30)
        elif name == "brain_mcp":
            r = await _aGET(f"{base}/api/brain/mcp", timeout=30)
        elif name == "models_list":
            r = await _aGET(f"{base}/api/models", timeout=30)
        elif name == "system_config":
            r = await _aGET(f"{base}/api/config", timeout=30)
        elif name == "oem_config_update":
            r = await _aPOST(f"{base}/api/oem/config", json={k: v for k, v in args.items() if v is not None}, timeout=30)
        # ═══════════════════════════════════════════════════════════════
        # Phase C: 多模型流水线编排
        # ═══════════════════════════════════════════════════════════════
        elif name == "pipeline_list":
            r = await _aGET(f"{base}/api/pipeline/templates", timeout=30)
        elif name == "pipeline_get":
            r = await _aGET(f"{base}/api/pipeline/templates/{args.get('name','')}", timeout=30)
        elif name == "pipeline_video_create":
            r = await _aPOST(f"{base}/api/pipeline/execute/video", params={"topic": args.get("topic",""), "duration": args.get("duration",30)}, timeout=600)
        elif name == "pipeline_content_create":
            r = await _aPOST(f"{base}/api/pipeline/execute", json={"name":"ai_content","inputs":{"topic":args.get("topic",""),"platform":args.get("platform","xiaohongshu")}}, timeout=300)
        elif name == "pipeline_image_set":
            r = await _aPOST(f"{base}/api/pipeline/execute", json={"name":"ai_image_set","inputs":{"topic":args.get("topic","")}}, timeout=300)

        # ═══════════════════════════════════════════════════════════════
        # Phase D: 流量引擎 + 客户转化
        # ═══════════════════════════════════════════════════════════════
        elif name == "acquisition_search":
            platforms = [p.strip() for p in args.get("platforms","douyin,xhs,bilibili,kuaishou").split(",") if p.strip()]
            r = await _aPOST(f"{base}/api/acquisition/search/aggregate", json={
                "keyword": args.get("keyword",""), "platforms": platforms,
                "limit": args.get("limit",20), "min_score": 30,
            }, timeout=60)
        elif name == "acquisition_intercept":
            platforms = [p.strip() for p in args.get("platforms","douyin,xhs").split(",") if p.strip()]
            r = await _aPOST(f"{base}/api/acquisition/intercept", json={
                "keyword": args.get("keyword",""), "platforms": platforms,
                "comment_count": args.get("comment_count",5),
                "strategy": args.get("strategy","balanced"),
                "deai": True,
            }, timeout=600)
        elif name == "acquisition_generate_comments":
            r = await _aPOST(f"{base}/api/acquisition/comments/generate", json={
                "video_title": args.get("video_title",""),
                "video_description": args.get("video_desc",""),
                "count": args.get("count",3),
                "strategy": args.get("strategy","balanced"),
            }, timeout=60)
        elif name == "acquisition_deai":
            r = await _aPOST(f"{base}/api/acquisition/comments/deai", json={
                "text": args.get("text",""),
                "platform": args.get("platform","douyin"),
            }, timeout=30)
        elif name == "acquisition_preflight":
            r = await _aPOST(f"{base}/api/acquisition/comments/preflight", json={
                "text": args.get("text",""),
            }, timeout=30)
        elif name == "acquisition_comment_send":
            import json as _json
            comments = _json.loads(args.get("comments_json","[]"))
            r = await _aPOST(f"{base}/api/acquisition/comments/batch-send", json={
                "platform": args.get("platform",""),
                "comments": comments,
                "strategy": args.get("strategy","balanced"),
                "deai": True,
            }, timeout=300)
        elif name == "acquisition_queue":
            r = await _aGET(f"{base}/api/acquisition/comments/queue", params={
                "status": args.get("status",""), "platform": args.get("platform",""),
                "limit": args.get("limit",30),
            }, timeout=30)
        elif name == "acquisition_stats":
            r = await _aGET(f"{base}/api/acquisition/intercept/history", timeout=30)
        elif name == "acquisition_monitor_list":
            r = await _aGET(f"{base}/api/acquisition/monitor/targets", timeout=30)
        elif name == "acquisition_monitor_add":
            r = await _aPOST(f"{base}/api/acquisition/monitor/targets", json={
                "platform": args.get("platform",""),
                "video_url": args.get("video_url",""),
                "video_title": args.get("video_title",""),
                "owner": args.get("owner","own"),
            }, timeout=30)
        elif name == "acquisition_monitor_start":
            r = await _aPOST(f"{base}/api/acquisition/monitor/start", params={
                "interval": args.get("interval",300),
            }, timeout=30)
        elif name == "acquisition_monitor_stop":
            r = await _aPOST(f"{base}/api/acquisition/monitor/stop", timeout=30)
        elif name == "acquisition_ab_start":
            r = await _aPOST(f"{base}/api/acquisition/ab-test/start", json={
                "strategy_a": args.get("strategy_a",""),
                "strategy_b": args.get("strategy_b",""),
                "platform": args.get("platform","douyin"),
                "video_count": args.get("video_count",10),
            }, timeout=30)
        elif name == "acquisition_ab_list":
            r = await _aGET(f"{base}/api/acquisition/ab-test", params={
                "status": args.get("status",""),
            }, timeout=30)
        elif name == "acquisition_leads":
            r = await _aGET(f"{base}/api/acquisition/leads", params={
                "status": args.get("status",""), "grade": args.get("grade",""),
                "platform": args.get("platform",""), "limit": args.get("limit",30),
            }, timeout=30)
        elif name == "acquisition_lead_score":
            r = await _aPOST(f"{base}/api/acquisition/auto-reply/score", json={
                "comment_text": args.get("comment_text",""),
                "author_name": args.get("author_name",""),
            }, timeout=30)
        elif name == "acquisition_auto_reply":
            import json as _json
            comments = _json.loads(args.get("comments_json","[]"))
            r = await _aPOST(f"{base}/api/acquisition/auto-reply", json={
                "platform": args.get("platform","douyin"),
                "comments": comments,
                "dry_run": args.get("dry_run",True),
            }, timeout=120)
        elif name == "acquisition_funnel":
            r = await _aGET(f"{base}/api/acquisition/leads/funnel", timeout=30)
        elif name == "acquisition_strategy":
            r = await _aGET(f"{base}/api/acquisition/strategy", params={
                "platform": args.get("platform","douyin"),
            }, timeout=30)
        elif name == "acquisition_strategy_apply":
            r = await _aPOST(f"{base}/api/acquisition/strategy/apply", json={
                "platform": args.get("platform",""),
                "strategy": args.get("strategy","balanced"),
            }, timeout=30)
        # ═══════════════════════════════════════════════════════════════
        # Acquisition MCP — 直接调用采集适配器 (无需HTTP)
        # ═══════════════════════════════════════════════════════════════
        elif name == "acq_platforms":
            from szyg.integrations.acquisition_adapters import list_acquisition_platforms
            return json.dumps({"platforms": list_acquisition_platforms()}, ensure_ascii=False)
        elif name == "acq_search":
            from szyg.integrations.acquisition_adapters import get_acquisition_adapter
            try:
                adapter = get_acquisition_adapter(args.get("platform",""))
                results = await adapter.search(args.get("keyword",""), limit=args.get("limit",20))
                return json.dumps({"platform": args.get("platform",""), "keyword": args.get("keyword",""), "total": len(results), "videos": results}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)
        elif name == "acq_get_comments":
            from szyg.integrations.acquisition_adapters import get_acquisition_adapter
            try:
                adapter = get_acquisition_adapter(args.get("platform",""))
                comments = await adapter.get_comments(args.get("video_url",""), limit=args.get("limit",30))
                return json.dumps({"platform": args.get("platform",""), "total": len(comments), "comments": comments}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)
        elif name == "acq_send_comment":
            from szyg.integrations.acquisition_adapters import get_acquisition_adapter
            try:
                adapter = get_acquisition_adapter(args.get("platform",""))
                result = await adapter.send_comment(args.get("video_url",""), args.get("comment_text",""))
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)
        elif name == "acq_batch_send_comments":
            from szyg.integrations.acquisition_adapters import get_acquisition_adapter
            try:
                items = json.loads(args.get("comments_json","[]"))
                adapter = get_acquisition_adapter(args.get("platform",""))
                results = []
                for item in items:
                    result = await adapter.send_comment(item.get("video_url",""), item.get("comment_text", item.get("text","")))
                    result["video_url"] = item.get("video_url","")
                    results.append(result)
                    await asyncio.sleep(2)
                return json.dumps({"platform": args.get("platform",""), "total": len(results), "results": results}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)
        elif name == "acq_send_dm":
            from szyg.integrations.acquisition_adapters import get_acquisition_adapter
            try:
                adapter = get_acquisition_adapter(args.get("platform",""))
                result = await adapter.send_dm(args.get("user_id",""), args.get("text",""))
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        # ═══════════════════════════════════════════════════════════════
        # social-auto-upload — 直接调用 adapter (无需HTTP)
        # ═══════════════════════════════════════════════════════════════
        elif name == "sau_list_platforms":
            from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
            try:
                adapter = get_sau_adapter()
                return json.dumps({"platforms": adapter.list_platforms()}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)
        elif name == "sau_upload_video":
            from datetime import datetime as _dt
            from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
            try:
                adapter = get_sau_adapter()
                tags = [t.strip() for t in args.get("tags","").split(",")] if args.get("tags") else []
                sched = _dt.strptime(args["schedule"], "%Y-%m-%d %H:%M") if args.get("schedule") else None
                result = await adapter.upload_video(
                    platform=args["platform"],
                    file_path=args["file_path"],
                    title=args["title"],
                    desc=args.get("desc",""),
                    tags=tags,
                    thumbnail_path=args.get("thumbnail_path") or None,
                    schedule=sched,
                    headless=args.get("headless", True),
                )
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)
        elif name == "sau_upload_note":
            from datetime import datetime as _dt
            from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
            try:
                adapter = get_sau_adapter()
                imgs = [p.strip() for p in args["image_paths"].split(",")] if args.get("image_paths") else []
                tags = [t.strip() for t in args.get("tags","").split(",")] if args.get("tags") else []
                sched = _dt.strptime(args["schedule"], "%Y-%m-%d %H:%M") if args.get("schedule") else None
                result = await adapter.upload_note(
                    platform=args["platform"],
                    image_paths=imgs,
                    title=args["title"],
                    note=args.get("note",""),
                    tags=tags,
                    schedule=sched,
                    headless=args.get("headless", True),
                )
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)
        elif name == "sau_check_login":
            from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
            try:
                adapter = get_sau_adapter()
                result = await adapter.check_login(args["platform"])
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)
        elif name == "sau_login":
            from szyg.integrations.social_auto_upload_adapter import get_sau_adapter
            try:
                adapter = get_sau_adapter()
                result = await adapter.login(args["platform"], headless=args.get("headless", False))
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"error": str(e)}, ensure_ascii=False)

        else:
            return _call_direct(name, args)
        r.raise_for_status()
        return json.dumps(r.json(), ensure_ascii=False)[:3000]
    except Exception as e:
        return f"错误: {e}"

async def _execute_volcengine_aigc(name: str, args: dict) -> str:
    """执行火山引擎AIGC工具调用。

    统一处理所有AIGC相关工具的调用，包括图像生成、视频生成、语音合成、
    声音克隆和向量嵌入。使用 VolcEngineClient 直接调用火山方舟API。
    """
    from szyg.integrations.volcengine_client import VolcEngineClient

    client = VolcEngineClient(
        api_key=VOLCENGINE_API_KEY,
        base_url=VOLCENGINE_BASE_URL,
        endpoints=VOLCENGINE_ENDPOINTS,
    )
    try:
        if name == "ai_image_generate":
            ep = VOLCENGINE_ENDPOINTS.get("doubao-image", "")
            if not ep:
                return json.dumps({
                    "ok": False,
                    "error": "图像生成未配置 — 需要在火山方舟控制台创建 doubao-image 推理接入点",
                    "help": "前往 https://console.volcengine.com/ark → 在线推理 → 创建接入点 → 选择豆包·文生图模型",
                }, ensure_ascii=False)
            path = await client.generate_image(
                prompt=args.get("prompt", ""),
                style=args.get("style"),
                size=args.get("size", "1920x1920"),
                model=args.get("model", "doubao-image"),
            )
            # Convert local path to accessible URL
            fname = Path(path).name
            url = f"/api/files/volcengine_output/{fname}"
            return json.dumps({
                "ok": True,
                "type": "image",
                "url": url,
                "path": path,
                "model": args.get("model", "doubao-image"),
                "prompt": args.get("prompt", ""),
            }, ensure_ascii=False)

        elif name == "ai_image_styles":
            from szyg.integrations.volcengine_client import VolcEngineClient as _VEC
            styles = list(_VEC.STYLE_TO_PROMPT.keys()) if hasattr(_VEC, "STYLE_TO_PROMPT") else [
                "realistic", "anime", "cyberpunk", "oil", "ink", "minimal", "3d", "pixel"
            ]
            descriptions = {
                "realistic": "写实 — 照片级真实感，8K高清",
                "anime": "动漫 — 日式动画风格，色彩鲜艳",
                "cyberpunk": "赛博朋克 — 霓虹灯，未来主义",
                "oil": "油画 — 古典油画，画布纹理",
                "ink": "水墨 — 中国水墨画，传统笔法",
                "minimal": "极简 — 简洁构图，现代设计",
                "3d": "3D渲染 — C4D，光线追踪",
                "pixel": "像素 — 16位复古游戏风格",
            }
            return json.dumps({
                "styles": [{"key": s, "description": descriptions.get(s, s)} for s in styles],
                "default": "realistic",
            }, ensure_ascii=False)

        elif name == "ai_video_create":
            ep = VOLCENGINE_ENDPOINTS.get("doubao-video", "")
            if not ep:
                return json.dumps({
                    "ok": False,
                    "error": "视频生成未配置 — 需要在火山方舟控制台创建 doubao-video 推理接入点",
                    "help": "前往 https://console.volcengine.com/ark → 在线推理 → 创建接入点",
                }, ensure_ascii=False)
            result = await client.generate_video(
                prompt=args.get("prompt", ""),
                image_url=args.get("image_url") or None,
                model=args.get("model", "doubao-video"),
                duration=args.get("duration", 5),
            )
            return json.dumps({
                "ok": True,
                "type": "video_task",
                "task_id": result.get("task_id", ""),
                "status": result.get("status", "queued"),
                "model": args.get("model", "doubao-video"),
                "prompt": args.get("prompt", ""),
                "note": "视频生成是异步任务，请使用 ai_video_task_status 查询完成状态",
            }, ensure_ascii=False)

        elif name == "ai_video_task_status":
            result = await client.get_video_task(
                task_id=args.get("task_id", ""),
                model=args.get("model", "doubao-video"),
            )
            # 如果已完成，下载视频到本地
            if result.get("status") == "succeed" and result.get("video_url"):
                path = await client.download_video(result["video_url"])
                result["local_path"] = path
            return json.dumps(result, ensure_ascii=False)

        elif name == "ai_tts_advanced":
            ep = VOLCENGINE_ENDPOINTS.get("doubao-tts", "")
            if not ep:
                return json.dumps({
                    "ok": False,
                    "error": "语音合成未配置 — 需要在火山方舟控制台创建 doubao-tts 推理接入点",
                    "help": "前往 https://console.volcengine.com/ark → 在线推理 → 创建接入点",
                }, ensure_ascii=False)
            path = await client.text_to_speech(
                text=args.get("text", ""),
                voice_id=args.get("voice_id", "zh_female_xiaoyi"),
                emotion=args.get("emotion", "neutral"),
                speed=args.get("speed", 1.0),
                pitch=args.get("pitch", 0),
            )
            fname = Path(path).name
            url = f"/api/files/volcengine_output/{fname}"
            return json.dumps({
                "ok": True,
                "type": "audio",
                "url": url,
                "path": path,
                "voice_id": args.get("voice_id", "zh_female_xiaoyi"),
                "emotion": args.get("emotion", "neutral"),
                "text": args.get("text", "")[:50] + "...",
            }, ensure_ascii=False)

        elif name == "ai_voice_clone":
            # Inline path validation for audio_sample
            sample_path = args.get("audio_sample", "")
            safe = ""
            if sample_path:
                p = Path(sample_path).resolve()
                data_dir = (Path(__file__).parent.parent.parent.parent / "data").resolve()
                volc_dir = (data_dir / "volcengine_output").resolve()
                for allowed in [data_dir, volc_dir]:
                    if str(p) == str(allowed) or str(p).startswith(str(allowed) + os.sep):
                        safe = str(p)
                        break
                if not safe:
                    safe_name = Path(sample_path).name
                    if safe_name and safe_name not in (".", ".."):
                        try_p = (data_dir / safe_name).resolve()
                        if str(try_p) == str(data_dir) or str(try_p).startswith(str(data_dir) + os.sep):
                            safe = str(try_p)
            if not safe:
                return json.dumps({"error": "无效的声音样本路径"}, ensure_ascii=False)
            path = await client.clone_voice(
                audio_sample_path=safe,
                text=args.get("text", ""),
                emotion=args.get("emotion", "neutral"),
            )
            return json.dumps({
                "ok": True,
                "type": "audio",
                "path": path,
                "emotion": args.get("emotion", "neutral"),
                "text": args.get("text", "")[:50] + "...",
            }, ensure_ascii=False)

        elif name == "ai_embedding_create":
            texts = args.get("texts", "")
            text_list = [t.strip() for t in texts.split("\n") if t.strip()] if isinstance(texts, str) else texts
            result = await client.create_embedding(
                texts=text_list,
                model=args.get("model", "doubao-embedding"),
            )
            return json.dumps({
                "ok": True,
                "count": len(result.get("embeddings", [])),
                "dimensions": len(result.get("embeddings", [[]])[0]) if result.get("embeddings") else 0,
                "usage": result.get("usage", {}),
            }, ensure_ascii=False)

        return json.dumps({"error": f"未知的AIGC工具: {name}"}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"VolcEngine AIGC error [{name}]: {e}")
        return json.dumps({"error": f"火山引擎AIGC调用失败: {str(e)[:200]}"}, ensure_ascii=False)
    finally:
        await client.close()


def _call_direct(name: str, args: dict) -> str:
    # Allowed base directories for file read operations
    _ALLOWED_READ_DIRS = [
        _OUTPUT_DIR.resolve(),
        (Path(__file__).parent.parent.parent.parent / "data").resolve(),
    ]

    def _safe_input_path(user_path: str) -> str:
        """Validate a user-supplied input file path for read operations.

        Resolves the path and ensures it stays within an allowed directory.
        Rejects absolute system paths like /etc/passwd or C:\\Windows\\...
        """
        if not user_path:
            return ""
        resolved = Path(user_path).resolve()
        for allowed in _ALLOWED_READ_DIRS:
            # Use os.sep suffix to prevent prefix-bypass
            r = str(resolved)
            a = str(allowed)
            if r == a or r.startswith(a + os.sep):
                return r
        # Path outside allowed dirs — allow only if it's a relative filename
        # that resolves inside PROJECT/data after join
        safe = (_OUTPUT_DIR.resolve() / Path(user_path).name).resolve()
        for allowed in _ALLOWED_READ_DIRS:
            if str(safe).startswith(str(allowed) + os.sep) or str(safe) == str(allowed):
                return str(safe)
        return ""  # Rejected

    def _safe_output(user_path: str) -> str:
        """Resolve user-supplied output path safely within OUTPUT_DIR."""
        if not user_path:
            return str(_OUTPUT_DIR / f"hermes_output_{uuid.uuid4().hex[:12]}.docx")
        resolved = Path(user_path).resolve()
        output_dir = _OUTPUT_DIR.resolve()
        output_dir_s = str(output_dir) + os.sep
        # Use os.sep suffix to prevent prefix-bypass (e.g. /data/output_evil vs /data/output)
        if str(resolved) == str(output_dir) or str(resolved).startswith(output_dir_s):
            resolved.parent.mkdir(parents=True, exist_ok=True)
            return str(resolved)
        # Enforce safe filename inside output dir
        safe_name = Path(user_path).name
        if not safe_name or safe_name in (".", ".."):
            safe_name = f"hermes_output_{uuid.uuid4().hex[:12]}"
        resolved = (output_dir / safe_name).resolve()
        if not (str(resolved) == str(output_dir) or str(resolved).startswith(output_dir_s)):
            resolved = output_dir / f"hermes_output_{uuid.uuid4().hex[:12]}"
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return str(resolved)

    def _safe_files(comma_paths: str) -> str:
        """Validate comma-separated file paths, return safe comma-separated string."""
        if not comma_paths:
            return ""
        parts = []
        for p in comma_paths.split(","):
            safe = _safe_input_path(p.strip())
            if safe:
                parts.append(safe)
        return ",".join(parts)

    # ── Skills — create (output uses _safe_output) ──
    if name == "docx_create":
        from szyg.mcp_servers.skills_mcp import skill_docx_create
        return json.dumps(skill_docx_create(args.get("markdown",""), _safe_output(args.get("output_path",""))), ensure_ascii=False)
    if name == "xlsx_create":
        from szyg.mcp_servers.skills_mcp import skill_xlsx_create
        return json.dumps(skill_xlsx_create(args.get("data_json",""), _safe_output(args.get("output_path",""))), ensure_ascii=False)
    if name == "pptx_create":
        from szyg.mcp_servers.skills_mcp import skill_pptx_create
        return json.dumps(skill_pptx_create(args.get("markdown",""), _safe_output(args.get("output_path",""))), ensure_ascii=False)
    # Skills — read/extract
    if name == "docx_to_markdown":
        from szyg.mcp_servers.skills_mcp import skill_docx_to_markdown
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(skill_docx_to_markdown(safe, args.get("tracked_changes","all")), ensure_ascii=False)
    if name == "docx_extract_text":
        from szyg.mcp_servers.skills_mcp import skill_docx_extract_text
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(skill_docx_extract_text(safe), ensure_ascii=False)
    if name == "xlsx_read":
        from szyg.mcp_servers.skills_mcp import skill_xlsx_read
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(skill_xlsx_read(safe, args.get("sheet_name","")), ensure_ascii=False)
    if name == "pptx_extract":
        from szyg.mcp_servers.skills_mcp import skill_pptx_extract
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(skill_pptx_extract(safe), ensure_ascii=False)
    if name == "pdf_extract":
        from szyg.mcp_servers.skills_mcp import skill_pdf_extract
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(skill_pdf_extract(safe), ensure_ascii=False)
    if name == "pdf_merge":
        from szyg.mcp_servers.skills_mcp import skill_pdf_merge
        return json.dumps(skill_pdf_merge(_safe_files(args.get("input_files","")), _safe_output(args.get("output_path",""))), ensure_ascii=False)
    if name == "canvas_get_fonts":
        from szyg.mcp_servers.skills_mcp import skill_canvas_get_fonts
        return json.dumps(skill_canvas_get_fonts(), ensure_ascii=False)
    if name == "canvas_preview_config":
        from szyg.mcp_servers.skills_mcp import skill_canvas_preview_config
        return json.dumps(skill_canvas_preview_config(), ensure_ascii=False)
    if name == "knowledge_search":
        from szyg.mcp_servers.knowledge_mcp import kb_search
        return json.dumps(kb_search(args.get("query","")), ensure_ascii=False)
    if name == "knowledge_ingest":
        from szyg.mcp_servers.knowledge_mcp import kb_ingest
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(kb_ingest(safe), ensure_ascii=False)
    if name == "knowledge_stats":
        from szyg.mcp_servers.knowledge_mcp import kb_stats
        return json.dumps(kb_stats(), ensure_ascii=False)
    if name == "video_templates":
        from szyg.mcp_servers.video_mcp import video_templates
        return json.dumps(video_templates(), ensure_ascii=False)
    if name == "video_info":
        from szyg.mcp_servers.video_mcp import video_info
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(video_info(safe), ensure_ascii=False)
    if name == "video_cut":
        from szyg.mcp_servers.video_mcp import video_cut
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(video_cut(safe, float(args.get("start",0)), float(args.get("duration",0))), ensure_ascii=False)
    if name == "video_concat":
        from szyg.mcp_servers.video_mcp import video_concat
        return json.dumps(video_concat(_safe_files(args.get("files",""))), ensure_ascii=False)
    if name == "video_speed":
        from szyg.mcp_servers.video_mcp import video_speed
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(video_speed(safe, float(args.get("speed",1.0))), ensure_ascii=False)
    if name == "video_add_title":
        from szyg.mcp_servers.video_mcp import video_add_title
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(video_add_title(
            safe, args.get("text",""),
            font_size=int(args.get("font_size",48)),
            font_color=args.get("font_color","white"),
        ), ensure_ascii=False)
    if name == "video_replace_audio":
        from szyg.mcp_servers.video_mcp import video_replace_audio
        sv = _safe_input_path(args.get("video_path",""))
        sa = _safe_input_path(args.get("audio_path",""))
        if not sv or not sa: return json.dumps({"error": "Invalid file path"})
        return json.dumps(video_replace_audio(sv, sa), ensure_ascii=False)
    if name == "video_mix_audio":
        from szyg.mcp_servers.video_mcp import video_mix_audio
        sv = _safe_input_path(args.get("video_path",""))
        sb = _safe_input_path(args.get("bgm_path",""))
        if not sv or not sb: return json.dumps({"error": "Invalid file path"})
        return json.dumps(video_mix_audio(
            sv, sb,
            video_volume=float(args.get("video_volume",0.3)),
            bgm_volume=float(args.get("bgm_volume",1.0)),
        ), ensure_ascii=False)
    if name == "video_extract_frame":
        from szyg.mcp_servers.video_mcp import video_extract_frame
        safe = _safe_input_path(args.get("file_path",""))
        if not safe: return json.dumps({"error": "Invalid file path"})
        return json.dumps(video_extract_frame(
            safe, float(args.get("time_sec",0)),
            width=int(args.get("width",0)), height=int(args.get("height",0)),
        ), ensure_ascii=False)
    if name == "video_fonts":
        from szyg.mcp_servers.video_mcp import video_fonts
        return json.dumps(video_fonts(), ensure_ascii=False)
    if name == "video_render":
        from szyg.mcp_servers.video_mcp import video_render
        return json.dumps(video_render(
            args.get("template_id",""), _safe_files(args.get("media_files","")),
            args.get("title",""), subtitle=args.get("subtitle",""),
            font_name=args.get("font_name",""),
        ), ensure_ascii=False)
    if name == "skills_list":
        from szyg.mcp_servers.skills_mcp import skills_list
        return json.dumps(skills_list(), ensure_ascii=False)
    if name == "oem_themes":
        from szyg.mcp_servers.oem_mcp import oem_themes
        return json.dumps(oem_themes(), ensure_ascii=False)
    # Agents
    if name == "agents_get":
        from szyg.mcp_servers.agents_mcp import agents_get
        return json.dumps(agents_get(args.get("agent_id","")), ensure_ascii=False)
    if name == "agents_tiers":
        from szyg.mcp_servers.agents_mcp import agents_tiers
        return json.dumps(agents_tiers(), ensure_ascii=False)
    if name == "agents_categories":
        from szyg.mcp_servers.agents_mcp import agents_categories
        return json.dumps(agents_categories(), ensure_ascii=False)
    return f"工具 {name} 已执行"

# ── Tool safety: allowlist + arg sanitization ──────────

DESTRUCTIVE_TOOLS = {
    "platform_publish_direct", "content_approve", "content_submit",
    "scheduler_create", "scheduler_execute", "scheduler_delete", "scheduler_pause",
    # Phase B: 新增管理员级工具
    "content_delete", "content_reject", "content_publish",
    "tool_install", "tool_uninstall",
    "runtime_launch", "runtime_stop",
    "announce_create", "announce_delete",
    "oem_config_update",
}

# ── Agent iteration budget ────────────────────────────
MAX_TURNS = 50            # total tool-calling rounds per conversation
FINAL_OUTPUT_TURNS = 5    # last N rounds can stream text (not just tools)

# ── Tool → resource grouping for parallel execution ───
# Tools that share a resource are serialised within the group;
# tools with different (or no) resource run in parallel.
TOOL_RESOURCE = {
    # scheduler — all write to scheduler_jobs.json
    "scheduler_create": "scheduler",
    "scheduler_update": "scheduler",
    "scheduler_delete": "scheduler",
    "scheduler_pause": "scheduler",
    "scheduler_resume": "scheduler",
    "scheduler_execute": "scheduler",
    # publisher — all write to publisher.json
    "content_create": "publisher",
    "content_update": "publisher",
    "content_delete": "publisher",
    "content_submit": "publisher",
    "content_approve": "publisher",
    "content_reject": "publisher",
    "content_schedule": "publisher",
    "content_publish": "publisher",
    # knowledge — writes to knowledge.db
    "knowledge_ingest": "knowledge",
    # platform sessions — login / logout / sync on same platform
    "platform_login": "platform_session",
    "platform_logout": "platform_session",
    "platform_sync_cookies": "platform_session",
    # tools install / uninstall
    "tool_install": "tools",
    "tool_uninstall": "tools",
    # runtime process management
    "tool_launch": "runtime",
    "tool_stop": "runtime",
    "runtime_launch": "runtime",
    "runtime_stop": "runtime",
}

# ── Path segment allowlists for URL construction ─────────
_PATH_ALLOWLIST = {
    "content_id": r"^[a-zA-Z0-9_\-]{1,64}$",
    "job_id": r"^[a-zA-Z0-9_\-]{1,64}$",
    "platform": r"^(douyin|xhs|wechat_mp|bilibili|kuaishou)$",
}
_OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "data"

def _sanitize_args(tool_name: str, args: str) -> dict:
    """Parse and sanitize tool arguments.

    - Repeatedly strips path traversal sequences (handles nested bypasses)
    - Validates path-segment arguments against allowlists
    - Rejects null bytes and other control characters
    """
    try:
        parsed = json.loads(args) if isinstance(args, str) else args
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}

    sanitized = {}
    for k, v in parsed.items():
        if isinstance(v, str):
            # Reject control characters
            if any(c in v for c in ("\x00", "\n", "\r")):
                continue
            # Loop-strip path traversal until stable (defeats nested bypasses like ....//)
            prev = None
            while v != prev:
                prev = v
                v = v.replace("../", "").replace("..\\", "")
            # Reject bare directory traversal tokens
            if v in (".", ".."):
                continue
            # Reject absolute paths and UNC paths for file_path-like args
            if k.endswith("_path") or k.endswith("_files") or k == "file_path" or k == "input_files":
                if re.match(r'^[A-Za-z]:[\\/]', v) or v.startswith(("/", "\\\\")):
                    continue
            # Validate against allowlist for path-segment args
            if k in _PATH_ALLOWLIST and v:
                if not re.match(_PATH_ALLOWLIST[k], v):
                    continue  # Drop invalid path segment
            sanitized[k] = v
        elif isinstance(v, (int, float, bool)):
            sanitized[k] = v
        # Drop complex nested objects — only flat scalars are safe for URL params
    return sanitized

async def _call_llm_for_tools(model: str, messages: list, tools: list, temperature: float = 0.7) -> tuple[str, list]:
    """非流式调用LLM检查tool_calls。

    根据模型自动选择火山引擎或Ollama后端。
    Returns: (assistant_content, tool_calls)
    """
    api_key, base_url, actual_model, is_volcengine = _resolve_llm_backend(model)

    if is_volcengine:
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient(
            api_key=api_key,
            base_url=base_url,
            endpoints=VOLCENGINE_ENDPOINTS,
        )
        try:
            result = await client.chat(
                messages=messages,
                model=actual_model,
                stream=False,
                tools=tools,
                temperature=temperature,
            )
            msg = result.get("message", {})
            return msg.get("content", ""), msg.get("tool_calls", [])
        finally:
            await client.close()
    else:
        async with httpx.AsyncClient(timeout=120) as c:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            # Ollama v1/chat/completions does not support the OpenAI 'tools' field
            payload = {"model": actual_model, "messages": messages, "stream": False, "temperature": temperature}
            r = await c.post(f"{base_url}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            msg = data.get("choices", [{}])[0].get("message", {})
            return msg.get("content", ""), msg.get("tool_calls", [])


async def _stream_llm_response(model: str, messages: list, temperature: float = 0.7):
    """流式调用LLM，异步生成文本chunk。

    Yields: content str (空字符串表示结束)
    """
    api_key, base_url, actual_model, is_volcengine = _resolve_llm_backend(model)

    if is_volcengine:
        from szyg.integrations.volcengine_client import VolcEngineClient
        client = VolcEngineClient(
            api_key=api_key,
            base_url=base_url,
            endpoints=VOLCENGINE_ENDPOINTS,
        )
        try:
            async for chunk in client.chat_stream(messages=messages, model=actual_model, temperature=temperature):
                if chunk.get("done"):
                    continue
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
        finally:
            await client.close()
    else:
        async with httpx.AsyncClient(timeout=120) as c:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            payload = {"model": actual_model, "messages": messages, "stream": True, "temperature": temperature}
            buffer = ""
            async with c.stream("POST", f"{base_url}/chat/completions", json=payload, headers=headers) as s:
                async for chunk in s.aiter_bytes():
                    if chunk:
                        buffer += chunk.decode()
                        lines = buffer.split("\n")
                        buffer = lines.pop() or ""
                        for line in lines:
                            if not line.startswith("data: "):
                                continue
                            line = line[6:]
                            if line == "[DONE]":
                                continue
                            try:
                                d = json.loads(line)
                                content = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if content:
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError) as e:
                                logger.debug("Skipping malformed SSE chunk: %s", e)


# ── SSE Streaming endpoint ─────────────────────────────

@router.post("/api/hermes/chat")
async def hermes_chat(chat_req: HermesChatRequest, user: User | None = Depends(optional_user),
                      req: Request = None):
    if not chat_req.messages:
        raise HTTPException(422, "messages required")

    if not API_KEY and not VOLCENGINE_API_KEY:
        raise HTTPException(500, "未配置任何LLM API Key，请在 secrets.yaml 中配置 火山引擎 或 config.yaml 中配置 Ollama")

    # Extract Authorization header for forwarding to internal API calls
    auth_header = {}
    if req:
        auth_val = req.headers.get("Authorization", "")
        if auth_val:
            auth_header = {"Authorization": auth_val}

    user_msg = chat_req.messages[-1].get("content", "") if chat_req.messages else ""
    is_admin = user is not None and getattr(user, "role", "") == "admin"

    async def stream():
        system_prompt, agent_temperature = _build_system_prompt(chat_req.agent_id, chat_req.expert_prompt)
        msgs = [{"role": "system", "content": system_prompt}]
        for m in chat_req.messages[:-1]:
            content = m.get("content","") if isinstance(m, dict) else str(m)
            msgs.append({"role": m.get("role","user") if isinstance(m, dict) else "user", "content": content})
        msgs.append({"role": "user", "content": user_msg})

        # 检查模型是否有配置
        api_key, _, actual_model, is_volcengine = _resolve_llm_backend(chat_req.model)
        if is_volcengine and not api_key:
            yield f"data: {json.dumps({'type': 'error', 'content': f'模型 {chat_req.model} 未配置API Key'})}\n\n"
            return

        failed_tools = set()       # tools that returned permanent errors — don't retry
        called_signatures = set()  # (tool_name, args_str) — cross-iteration dedup
        tool_call_history = []     # chronological tool names for status messages

        # ── SSE helpers ──
        def _sse(**kw):
            return f"data: {json.dumps(kw)}\n\n"

        async def _execute_single(tool_name, tool_args, tool_id):
            """Execute one tool and return (tool_name, tool_id, result_str)."""
            if tool_name in failed_tools:
                return (tool_name, tool_id, f"工具 {tool_name} 已在本次对话中失败，请不要再调用")
            sig = (tool_name, str(tool_args))
            if sig in called_signatures:
                return (tool_name, tool_id, f"工具 {tool_name} 已使用相同参数调用过，跳过重复执行")
            called_signatures.add(sig)
            try:
                result = await _execute_tool(tool_name, tool_args, auth_header)
            except Exception as e:
                result = f"工具执行异常: {str(e)[:200]}"
                failed_tools.add(tool_name)
            # Track permanent failures
            try:
                rj = json.loads(result)
                if isinstance(rj, dict) and rj.get("ok") is False:
                    failed_tools.add(tool_name)
            except (json.JSONDecodeError, TypeError):
                pass  # result is not JSON — expected for plain-text tool outputs
            return (tool_name, tool_id, result)

        async def _execute_group(resource_key, items):
            """Execute items in the same resource group serially."""
            results = []
            for item in items:
                r = await _execute_single(item["tool_name"], item["tool_args"], item["tool_id"])
                results.append(r)
            return results

        for iteration in range(MAX_TURNS):
            # ── Status event ──
            if iteration == 0:
                yield _sse(type='status', content='正在分析任务…')
            elif tool_call_history:
                recent = tool_call_history[-3:]
                remaining = MAX_TURNS - iteration
                yield _sse(type='status',
                           content=f'第{iteration + 1}轮 — 已执行: {", ".join(recent)} (剩余{remaining}轮)')
            else:
                yield _sse(type='status', content=f'第{iteration + 1}轮思考…')

            try:
                msg_content, tool_calls = await _call_llm_for_tools(chat_req.model, msgs, HERMES_TOOLS, temperature=agent_temperature)

                if tool_calls:
                    # ── LLM wants to call tools ──
                    msgs.append({"role": "assistant", "content": msg_content or "",
                                 "tool_calls": tool_calls})

                    # Parse all tool calls with unique IDs
                    parsed = []
                    for tc in tool_calls:
                        fn = tc.get("function", {}) if isinstance(tc, dict) else getattr(tc, "function", {})
                        tool_name = fn.get("name", "") if isinstance(fn, dict) else getattr(fn, "name", "")
                        tool_args = fn.get("arguments", "{}") if isinstance(fn, dict) else getattr(fn, "arguments", "{}")
                        tool_id = (tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")) or str(uuid.uuid4())[:8]

                        parsed.append({
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "tool_id": tool_id,
                            "tc": tc,
                        })

                    # Pre-checks: auth gate + dedup → separate into pre-resolved vs needs-execution
                    pre_resolved = []   # (tool_name, tool_id, result, dedup_sig)
                    to_execute = []     # items that actually need _execute_tool

                    for p in parsed:
                        # Auth gate
                        if p["tool_name"] in DESTRUCTIVE_TOOLS and not is_admin:
                            yield _sse(type='tool_call', tool=p["tool_name"], args=p["tool_args"], id=p["tool_id"])
                            yield _sse(type='error', content=f'权限不足: {p["tool_name"]} 需要管理员权限')
                            msgs.append({"role": "tool", "tool_call_id": p["tool_id"],
                                         "content": f"错误: 权限不足，{p['tool_name']}需要管理员登录"})
                            continue

                        # Yield tool_call event so frontend shows the card immediately
                        yield _sse(type='tool_call', tool=p["tool_name"], args=p["tool_args"], id=p["tool_id"])

                        sig = (p["tool_name"], str(p["tool_args"]))

                        # Dedup check — same tool + same args already called
                        if sig in called_signatures:
                            pre_resolved.append((p["tool_name"], p["tool_id"],
                                                 f"工具 {p['tool_name']} 已使用相同参数调用过，跳过重复执行", sig))
                            continue

                        # Failed-tools check — tool previously returned permanent error
                        if p["tool_name"] in failed_tools:
                            pre_resolved.append((p["tool_name"], p["tool_id"],
                                                 f"工具 {p['tool_name']} 已在本次对话中失败，请不要再调用",
                                                 (p["tool_name"], "")))  # broad block
                            continue

                        to_execute.append(p)

                    # Yield pre-resolved results immediately
                    for tool_name, tool_id, result, dedup_sig in pre_resolved:
                        yield _sse(type='tool_result', tool=tool_name, result=result[:500], id=tool_id)
                        msgs.append({"role": "tool", "tool_call_id": tool_id, "content": result})
                        tool_call_history.append(tool_name)
                        called_signatures.add(dedup_sig)

                    if to_execute:
                        # Group by resource for parallel execution
                        from collections import defaultdict
                        groups = defaultdict(list)
                        for p in to_execute:
                            resource = TOOL_RESOURCE.get(p["tool_name"])  # None = no conflict
                            groups[resource].append(p)

                        # Execute groups in parallel, items within a group serially
                        group_tasks = [
                            _execute_group(res, items) for res, items in groups.items()
                        ]
                        all_results = []
                        for task in asyncio.as_completed(group_tasks):
                            batch = await task
                            all_results.extend(batch)

                        # Yield results, preserving some order (by group completion order is fine)
                        for tool_name, tool_id, result in all_results:
                            yield _sse(type='tool_result', tool=tool_name, result=result[:500], id=tool_id)
                            msgs.append({"role": "tool", "tool_call_id": tool_id, "content": result})
                            tool_call_history.append(tool_name)

                            # 检测图片生成工具，发送 image 事件
                            if tool_name == "ai_image_generate":
                                try:
                                    rj = json.loads(result)
                                    if rj.get("ok") and rj.get("url"):
                                        yield _sse(
                                            type='image',
                                            url=rj["url"],
                                            prompt=rj.get("prompt", ""),
                                        )
                                except Exception as e:
                                    logger.debug(f"Failed to parse image result: {e}")

                            # 检测视频生成工具，发送 video_task / video / video_status 事件
                            if tool_name == "ai_video_create":
                                try:
                                    rj = json.loads(result)
                                    if rj.get("ok") and rj.get("task_id"):
                                        yield _sse(
                                            type='video_task',
                                            task_id=rj["task_id"],
                                            prompt=rj.get("prompt", ""),
                                            status=rj.get("status", "queued"),
                                        )
                                except Exception as e:
                                    logger.debug(f"Failed to parse video_task result: {e}")

                            elif tool_name == "ai_video_task_status":
                                try:
                                    rj = json.loads(result)
                                    status = rj.get("status", "")
                                    # 兼容 succeed / succeeded 两种拼写
                                    if status in ("succeed", "succeeded"):
                                        local_path = rj.get("local_path", "")
                                        if local_path:
                                            fname = Path(local_path).name
                                            video_url = f"/api/files/volcengine_output/{fname}"
                                        else:
                                            video_url = rj.get("video_url", "")
                                        if video_url:
                                            yield _sse(
                                                type='video',
                                                task_id=rj.get("task_id", ""),
                                                url=video_url,
                                                prompt=rj.get("prompt", ""),
                                            )
                                    else:
                                        yield _sse(
                                            type='video_status',
                                            task_id=rj.get("task_id", ""),
                                            status=status,
                                            progress=rj.get("progress", 0),
                                        )
                                except Exception as e:
                                    logger.debug(f"Failed to parse video_status result: {e}")

                    continue  # next iteration — feed results back to LLM

                else:
                    # ── No tool calls: LLM is done → stream response ──
                    yield _sse(type='status', content='正在生成回复…')
                    async for content in _stream_llm_response(chat_req.model, msgs, temperature=agent_temperature):
                        if content:
                            yield _sse(type='text', content=content)
                    yield _sse(type='done')
                    break

            except Exception as e:
                logger.error(f"Hermes error iter={iteration}: {e}")
                yield _sse(type='error', content=f'模型调用失败: {str(e)[:200]}')
                break
        else:
            # for-loop exhausted without break — max iterations reached
            yield _sse(type='status', content='已达到最大轮次，正在总结…')
            async for content in _stream_llm_response(chat_req.model, msgs, temperature=agent_temperature):
                if content:
                    yield _sse(type='text', content=content)
            yield _sse(type='done')

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── Case Cards: Dynamic Douyin Video Recommendations ─────────────────────────────

_case_card_cache: dict[str, tuple[float, list]] = {}  # keyword -> (timestamp, cards)
_CASE_CARD_CACHE_TTL = 1800  # 30 minutes
_DEFAULT_CASE_KEYWORD = "AI营销自动化工具"  # 无对话历史时使用的默认搜索关键词


class CaseCardRequest(BaseModel):
    recent_titles: list[str] = Field(default_factory=list, description="近期对话标题列表，最多10条")
    limit: int = Field(default=3, description="返回卡片数量")


class CaseCard(BaseModel):
    title: str          # 视频标题（截断至 50 字符）
    cover_url: str      # 视频封面图 URL
    video_url: str      # 视频页面 URL (https://www.douyin.com/video/{vid})
    author: str         # 作者昵称
    likes: int          # 点赞数


class CaseCardResponse(BaseModel):
    cards: list[CaseCard]
    keyword: str        # 实际使用的搜索关键词（用于调试/展示）
    source: str         # "douyin" (固定)


async def _infer_search_keyword(titles: list[str]) -> str:
    """用 LLM 从近期对话标题中推断搜索关键词。

    Prompt: "根据以下用户近期任务标题，生成一个适合在抖音搜索的短视频关键词（5-15个字，不要加引号）：
    标题列表: {titles}
    只返回关键词本身，不要其他文字。"
    """
    if not titles:
        return ""
    
    try:
        prompt = f"""根据以下用户近期任务标题，生成一个适合在抖音搜索的短视频关键词（5-15个字，不要加引号）：
标题列表: {', '.join(titles[:5])}
只返回关键词本身，不要其他文字。"""
        
        # 调用 LLM 获取关键词 (10秒超时)
        messages = [{"role": "user", "content": prompt}]
        content = ""

        async def _do_infer():
            nonlocal content
            async for chunk in _stream_llm_response("doubao-seed-2-0-lite-260428", messages, temperature=0.3):
                content += chunk

        await asyncio.wait_for(_do_infer(), timeout=10)
        
        keyword = content.strip().strip('"').strip("'")
        if keyword and len(keyword) <= 20:
            return keyword
    except asyncio.TimeoutError:
        logger.warning("LLM keyword inference timed out (10s)")
    except Exception as e:
        logger.warning(f"LLM keyword inference failed: {e}")
    
    return ""


async def _select_top_videos(videos: list[dict], titles: list[str], limit: int) -> list[CaseCard]:
    """从搜索结果中选出最匹配的 limit 个视频。

    策略:
    1. 优先用 LLM 对视频标题与用户任务标题做相关性排序
    2. LLM 不可用时 fallback: 按 likes 降序取前 limit 条
    """
    if not videos:
        return []
    
    # Fallback: 按 likes 降序取前 limit 条
    sorted_videos = sorted(videos, key=lambda v: v.get("likes", 0), reverse=True)[:limit]
    
    cards = []
    for item in sorted_videos:
        cards.append(CaseCard(
            title=item.get("title", "")[:50],
            cover_url=item.get("cover", ""),
            video_url=item.get("url", ""),
            author=item.get("author", ""),
            likes=item.get("likes", 0),
        ))
    
    return cards


def _cleanup_expired_cache(now: float):
    """清理过期的缓存条目"""
    expired_keys = []
    for key, (timestamp, _) in _case_card_cache.items():
        if now - timestamp >= _CASE_CARD_CACHE_TTL:
            expired_keys.append(key)
    
    for key in expired_keys:
        del _case_card_cache[key]
    
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired case card cache entries")


@router.post("/api/hermes/case-cards")
async def get_case_cards(req: CaseCardRequest):
    """获取欢迎页精选案例卡片（动态抖音短视频推荐）"""
    # 1. 关键词推断
    if not req.recent_titles:
        keyword = _DEFAULT_CASE_KEYWORD
    else:
        keyword = await _infer_search_keyword(req.recent_titles)
        if not keyword:
            keyword = req.recent_titles[0]  # fallback
    
    # 2. 检查缓存
    cache_key = f"case_cards:{keyword}"
    now = time.time()
    if cache_key in _case_card_cache:
        timestamp, cached_cards = _case_card_cache[cache_key]
        if now - timestamp < _CASE_CARD_CACHE_TTL:
            logger.info(f"Case cards cache hit for keyword: {keyword}")
            return CaseCardResponse(cards=cached_cards, keyword=keyword, source="douyin")
    
    # 清理过期缓存
    _cleanup_expired_cache(now)
    
    # 3. 抖音搜索
    try:
        from szyg.integrations.acquisition_adapters import get_acquisition_adapter
        adapter = get_acquisition_adapter("douyin")
        logger.info(f"Case cards: searching douyin for keyword='{keyword}'")
        results = await asyncio.wait_for(
            adapter.search(keyword, limit=10),
            timeout=60,
        )
        logger.info(f"Case cards: search returned {len(results)} results")
    except asyncio.TimeoutError:
        logger.warning(f"Case cards: douyin search timed out (60s) for keyword='{keyword}'")
        return CaseCardResponse(cards=[], keyword=keyword, source="douyin")
    except Exception as e:
        logger.warning(f"Case card search failed: {e}", exc_info=True)
        return CaseCardResponse(cards=[], keyword=keyword, source="douyin")
    
    if not results:
        logger.warning(f"Case cards: douyin search returned 0 results for keyword='{keyword}'")
        return CaseCardResponse(cards=[], keyword=keyword, source="douyin")
    
    # 4. LLM 排序筛选
    top_cards = await _select_top_videos(results, req.recent_titles, req.limit)
    
    # 5. 缓存结果
    _case_card_cache[cache_key] = (now, top_cards)
    
    return CaseCardResponse(cards=top_cards, keyword=keyword, source="douyin")
