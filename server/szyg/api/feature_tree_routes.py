"""
功能树 API

返回前端功能导航树的完整结构，支持前端动态渲染
"""

from fastapi import APIRouter

router = APIRouter(tags=["feature-tree"])


FEATURE_TREE = [
    {
        "id": "ai-studio",
        "label": "AI工作室",
        "icon": "Sparkles",
        "description": "管理/训练你的数字员工团队",
        "children": [
            {"id": "super-agent", "label": "超级员工", "icon": "Bot", "description": "创建、训练和管理全能AI助手", "path": "/studio/super-agent", "engine": "state-machine"},
            {"id": "ai-video", "label": "AI视频", "icon": "Clapperboard", "description": "脚本变视频，一键生成", "path": "/studio/ai-video", "engine": "pipeline", "badge": "hot"},
            {"id": "ai-graphic", "label": "AI图文", "icon": "FileImage", "description": "自动生成笔记、海报、长文", "path": "/studio/ai-graphic", "engine": "pipeline"},
            {"id": "doc-master", "label": "文档达人", "icon": "FileText", "description": "MD一键转PDF/DOCX", "path": "/studio/doc-master", "engine": "pipeline"},
        ],
    },
    {
        "id": "public-traffic",
        "label": "公域获客",
        "icon": "Globe",
        "description": "在全网各大平台捕获流量",
        "children": [
            {"id": "one-click-publish", "label": "一键分发", "icon": "Send", "description": "内容一键适配多平台发布", "path": "/public/one-click-publish", "engine": "pipeline"},
            {"id": "smart-comment", "label": "智能评论", "icon": "MessageSquarePlus", "description": "自动高情商互动评论", "path": "/public/smart-comment", "engine": "state-machine", "badge": "new"},
            {"id": "viral-clone", "label": "爆款复刻", "icon": "Copy", "description": "拆解竞品爆款框架", "path": "/public/viral-clone", "engine": "pipeline"},
            {"id": "hotspot-ride", "label": "热点借势", "icon": "TrendingUp", "description": "实时追踪热点", "path": "/public/hotspot-ride", "engine": "pipeline"},
        ],
    },
    {
        "id": "private-domain",
        "label": "私域营销",
        "icon": "MessageCircleHeart",
        "description": "盘活、转化你的微信/企微客户",
        "children": [
            {"id": "lead-manager", "label": "线索管家", "icon": "Tags", "description": "自动打标签、识别意向", "path": "/private/lead-manager", "engine": "state-machine", "automationLevel": "semi"},
            {"id": "moments", "label": "朋友圈经营", "icon": "Camera", "description": "周期性自动生成朋友圈", "path": "/private/moments", "engine": "pipeline", "automationLevel": "full"},
            {"id": "community", "label": "社群运营", "icon": "Users", "description": "按SOP执行社群日常", "path": "/private/community", "engine": "state-machine", "automationLevel": "semi"},
            {"id": "one-on-one", "label": "1v1触达", "icon": "UserCheck", "description": "个性化话术生成", "path": "/private/one-on-one", "engine": "pipeline", "automationLevel": "assist"},
        ],
    },
    {
        "id": "data-insight",
        "label": "数据洞察",
        "icon": "BarChart3",
        "description": "让营销效果看得见",
        "children": [
            {"id": "account-diagnosis", "label": "账号诊断", "icon": "Stethoscope", "description": "分析账号内容表现", "path": "/insight/account-diagnosis", "engine": "tool"},
            {"id": "competitor-monitor", "label": "竞品监控", "icon": "Eye", "description": "追踪竞品动态", "path": "/insight/competitor-monitor", "engine": "tool"},
            {"id": "asset-dashboard", "label": "资产看板", "icon": "LayoutDashboard", "description": "展示产出与增长", "path": "/insight/asset-dashboard", "engine": "tool"},
            {"id": "auto-report", "label": "自动周报", "icon": "Newspaper", "description": "自动生成运营周报", "path": "/insight/auto-report", "engine": "pipeline", "badge": "beta"},
        ],
    },
    {
        "id": "toolbox",
        "label": "工具箱",
        "icon": "Wrench",
        "description": "原子能力集合",
        "children": [
            {"id": "copy-gen", "label": "文案生成", "icon": "Pencil", "description": "各类短文案生成", "path": "/tools/copy-gen", "engine": "tool"},
            {"id": "image-process", "label": "图片处理", "icon": "ImagePlus", "description": "抠图、改尺寸、加水印", "path": "/tools/image-process", "engine": "tool"},
            {"id": "format-convert", "label": "格式转换", "icon": "ArrowLeftRight", "description": "视频转GIF等", "path": "/tools/format-convert", "engine": "tool"},
        ],
    },
]


@router.get("/api/feature-tree")
async def get_feature_tree():
    """返回完整功能树"""
    return {"tree": FEATURE_TREE}
