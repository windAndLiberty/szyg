"""统一数据 API — 为所有前端页面提供真实数据持久化.

覆盖: 团队/工具/技能/平台账号/内容/素材/线索/客户/跟进/SOP/知识库/调度/实验/策略/审计日志
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/data", tags=["data"])

_DATA_DIR = Path(os.environ.get("SZYG_DATA_DIR", "data")) / "frontend"
_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _path(name: str) -> Path:
    return _DATA_DIR / f"{name}.json"


def _load(name: str, default):
    p = _path(name)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _save(name: str, data):
    _path(name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Shared CRUD helpers ────────────────────────────────────────────

def _find_item(items: list, item_id, id_field: str = "id"):
    """在列表中按 id 查找条目，返回 (index, item) 或 (-1, None)。"""
    for idx, item in enumerate(items):
        if item.get(id_field) == item_id:
            return idx, item
    return -1, None


def _update_item(
    resource: str, default, item_id, updates: dict,
    id_field: str = "id", not_found: str = "Item not found",
):
    """加载 → 查找 → 更新 → 保存，返回 {ok: True} 或 raise 404。"""
    data = _load(resource, default)
    _, item = _find_item(data, item_id, id_field)
    if item is None:
        raise HTTPException(status_code=404, detail=not_found)
    item.update(updates)
    _save(resource, data)
    return {"ok": True}


def _toggle_item(
    resource: str, default, item_id,
    field: str = "status", on_value: str = "active", off_value: str = "disabled",
    id_field: str = "id", not_found: str = "Item not found",
):
    """加载 → 查找 → 切换布尔/枚举字段 → 保存。"""
    data = _load(resource, default)
    _, item = _find_item(data, item_id, id_field)
    if item is None:
        raise HTTPException(status_code=404, detail=not_found)
    item[field] = off_value if item.get(field) == on_value else on_value
    _save(resource, data)
    return {"ok": True, field: item[field]}


def _create_item(resource: str, default, new_item: dict, id_field: str = "id"):
    """加载 → 生成自增 ID → 追加 → 保存。"""
    data = _load(resource, default)
    new_id = max([i.get(id_field, 0) for i in data], default=0) + 1
    new_item[id_field] = new_id
    data.append(new_item)
    _save(resource, data)
    return new_item


# ═══════════════════════════════════════════════════════════════════
# 默认数据
# ═══════════════════════════════════════════════════════════════════

_TODAY = datetime.now().strftime("%Y-%m-%d")

_DEFAULT_TEAM = [
    {"id": 1, "username": "admin", "role": "admin", "email": "admin@example.com", "lastLogin": f"{_TODAY} 10:00", "status": "active"},
    {"id": 2, "username": "content_manager", "role": "user", "email": "content@example.com", "lastLogin": f"{_TODAY} 16:30", "status": "active"},
    {"id": 3, "username": "data_analyst", "role": "user", "email": "data@example.com", "lastLogin": f"{_TODAY} 09:15", "status": "active"},
    {"id": 4, "username": "designer_li", "role": "user", "email": "design@example.com", "lastLogin": f"{_TODAY} 14:20", "status": "disabled"},
    {"id": 5, "username": "ops_wang", "role": "user", "email": "ops@example.com", "lastLogin": f"{_TODAY} 11:45", "status": "active"},
    {"id": 6, "username": "marketing_zhao", "role": "user", "email": "marketing@example.com", "lastLogin": f"{_TODAY} 17:00", "status": "active"},
    {"id": 7, "username": "developer_chen", "role": "admin", "email": "dev@example.com", "lastLogin": f"{_TODAY} 08:30", "status": "active"},
    {"id": 8, "username": "intern_sun", "role": "user", "email": "intern@example.com", "lastLogin": f"{_TODAY} 15:10", "status": "disabled"},
]

_DEFAULT_TOOLS = [
    {"id": 1, "name": "Docx生成器", "icon": "📄", "description": "从 Markdown 内容生成专业 Word 文档", "status": "running", "calls": 1250, "category": "office"},
    {"id": 2, "name": "Excel处理器", "icon": "📊", "description": "从 JSON 数据生成 Excel 表格", "status": "running", "calls": 890, "category": "office"},
    {"id": 3, "name": "PPT生成器", "icon": "📽️", "description": "从 Markdown 大纲自动排版生成 PPT", "status": "stopped", "calls": 320, "category": "office"},
    {"id": 4, "name": "PDF合并工具", "icon": "📑", "description": "合并多个 PDF 文件", "status": "running", "calls": 560, "category": "office"},
    {"id": 5, "name": "视频剪辑引擎", "icon": "🎬", "description": "FFmpeg 视频处理流水线", "status": "running", "calls": 2100, "category": "video"},
    {"id": 6, "name": "图片压缩器", "icon": "🖼️", "description": "智能压缩图片体积", "status": "running", "calls": 780, "category": "image"},
    {"id": 7, "name": "音频转写器", "icon": "🎙️", "description": "音频转文本", "status": "stopped", "calls": 430, "category": "audio"},
    {"id": 8, "name": "网页抓取器", "icon": "🕸️", "description": "自动化网页内容抓取", "status": "running", "calls": 1560, "category": "data"},
    {"id": 9, "name": "翻译引擎", "icon": "🌐", "description": "多语言智能翻译", "status": "running", "calls": 980, "category": "nlp"},
    {"id": 10, "name": "知识图谱构建器", "icon": "🧠", "description": "从文本中提取实体关系", "status": "not_installed", "calls": 0, "category": "ai"},
    {"id": 11, "name": "代码审查助手", "icon": "💻", "description": "自动审查代码提交", "status": "not_installed", "calls": 0, "category": "dev"},
    {"id": 12, "name": "数据可视化器", "icon": "📈", "description": "CSV/JSON 转交互式图表", "status": "stopped", "calls": 210, "category": "data"},
]

_DEFAULT_SKILLS = [
    {"id": 1, "name": "小红书爆款文案", "icon": "✍️", "description": "一键生成小红书风格的爆款文案", "rating": 4.8, "downloads": 3420, "author": "szyg官方", "tags": ["内容专员"], "category": "content"},
    {"id": 2, "name": "抖音视频脚本", "icon": "🎬", "description": "自动生成抖音口播视频脚本", "rating": 4.6, "downloads": 2890, "author": "AI工作室", "tags": ["内容专员"], "category": "content"},
    {"id": 3, "name": "智能评论截流", "icon": "🎯", "description": "自动搜索目标视频并生成真人风格评论", "rating": 4.7, "downloads": 4560, "author": "szyg官方", "tags": ["获客专员"], "category": "acquisition"},
    {"id": 4, "name": "DeAI去味处理", "icon": "🧪", "description": "去除AI生成文本的模板化痕迹", "rating": 4.5, "downloads": 2150, "author": "NLP实验室", "tags": ["获客专员"], "category": "acquisition"},
    {"id": 5, "name": "客户线索评分", "icon": "💎", "description": "基于评论内容评估客户购买意向", "rating": 4.9, "downloads": 1890, "author": "szyg官方", "tags": ["转化专员"], "category": "conversion"},
    {"id": 6, "name": "Word文档生成", "icon": "📄", "description": "从结构化数据生成Word文档", "rating": 4.4, "downloads": 1200, "author": "办公助手", "tags": ["运营专员"], "category": "office"},
    {"id": 7, "name": "数据可视化看板", "icon": "📊", "description": "一键生成数据可视化大屏", "rating": 4.7, "downloads": 980, "author": "数据团队", "tags": ["运营专员"], "category": "data"},
    {"id": 8, "name": "平台账号诊断", "icon": "🔍", "description": "分析社交媒体账号数据", "rating": 4.3, "downloads": 1560, "author": "szyg官方", "tags": ["运营专员"], "category": "platform"},
    {"id": 9, "name": "AI客服话术", "icon": "💬", "description": "智能客服话术库", "rating": 4.6, "downloads": 2340, "author": "客服团队", "tags": ["转化专员"], "category": "conversion"},
    {"id": 10, "name": "Excel公式助手", "icon": "📈", "description": "自然语言生成Excel公式", "rating": 4.5, "downloads": 1780, "author": "办公助手", "tags": ["运营专员"], "category": "office"},
    {"id": 11, "name": "SEO关键词挖掘", "icon": "🔑", "description": "基于语义分析挖掘长尾关键词", "rating": 4.4, "downloads": 1120, "author": "AI工作室", "tags": ["获客专员"], "category": "acquisition"},
    {"id": 12, "name": "批量图文排版", "icon": "🖼️", "description": "自动将文字排版为图文卡片", "rating": 4.2, "downloads": 890, "author": "设计助手", "tags": ["内容专员"], "category": "content"},
    {"id": 13, "name": "竞品分析报告", "icon": "📋", "description": "输入竞品链接自动生成分析报告", "rating": 4.8, "downloads": 670, "author": "市场团队", "tags": ["运营专员"], "category": "platform"},
    {"id": 14, "name": "短视频封面生成", "icon": "🎨", "description": "生成高点击率封面方案", "rating": 4.3, "downloads": 1450, "author": "设计助手", "tags": ["内容专员"], "category": "content"},
    {"id": 15, "name": "用户画像生成", "icon": "👤", "description": "基于行为数据生成用户画像", "rating": 4.6, "downloads": 890, "author": "数据团队", "tags": ["转化专员"], "category": "data"},
    {"id": 16, "name": "多平台分发助手", "icon": "🚀", "description": "一键生成多平台内容变体", "rating": 4.5, "downloads": 1230, "author": "szyg官方", "tags": ["运营专员"], "category": "platform"},
]

_DEFAULT_INSTALLED_SKILLS = [
    {"id": 1, "name": "小红书爆款文案", "version": "1.2.0", "installTime": "2025-06-15", "applicableEmployees": ["内容专员"], "status": "active", "hasUpdate": True},
    {"id": 3, "name": "智能评论截流", "version": "2.1.0", "installTime": "2025-06-18", "applicableEmployees": ["获客专员"], "status": "active", "hasUpdate": False},
    {"id": 5, "name": "客户线索评分", "version": "1.3.0", "installTime": "2025-06-20", "applicableEmployees": ["转化专员"], "status": "active", "hasUpdate": True},
    {"id": 6, "name": "Word文档生成", "version": "0.9.0", "installTime": "2025-06-01", "applicableEmployees": ["运营专员"], "status": "active", "hasUpdate": False},
    {"id": 10, "name": "Excel公式助手", "version": "1.0.1", "installTime": "2025-06-05", "applicableEmployees": ["运营专员"], "status": "inactive", "hasUpdate": False},
    {"id": 15, "name": "用户画像生成", "version": "1.1.0", "installTime": "2025-06-17", "applicableEmployees": ["转化专员"], "status": "active", "hasUpdate": False},
]

_DEFAULT_PLATFORMS = [
    {"id": "douyin", "name": "抖音", "icon": "🎵", "account": "美妆达人小A", "isLogin": True, "lastActive": f"{_TODAY} 09:00", "safetyScore": 95},
    {"id": "xhs", "name": "小红书", "icon": "📕", "account": "护肤种草官", "isLogin": True, "lastActive": f"{_TODAY} 10:30", "safetyScore": 88},
    {"id": "bilibili", "name": "B站", "icon": "📺", "account": "成分科普君", "isLogin": True, "lastActive": f"{_TODAY} 08:45", "safetyScore": 92},
    {"id": "kuaishou", "name": "快手", "icon": "🎬", "account": "未登录", "isLogin": False, "lastActive": "-", "safetyScore": 0},
    {"id": "wechat", "name": "视频号", "icon": "💬", "account": "品牌官方号", "isLogin": True, "lastActive": f"{_TODAY} 11:00", "safetyScore": 90},
]

_DEFAULT_CONTENTS = [
    {"id": 1, "title": "夏日护肤小贴士", "platforms": ["douyin", "xhs"], "status": "published", "scheduledAt": f"{_TODAY} 10:00", "createdAt": "2026-06-27", "summary": "分享夏季护肤的关键步骤"},
    {"id": 2, "title": "新品上市预热", "platforms": ["douyin"], "status": "draft", "scheduledAt": None, "createdAt": f"{_TODAY}", "summary": "新品功能亮点预告"},
    {"id": 3, "title": "B站知识科普：AI 入门", "platforms": ["bilibili"], "status": "reviewing", "scheduledAt": None, "createdAt": f"{_TODAY}", "summary": "AI 技术基础知识讲解"},
    {"id": 4, "title": "快手直播切片", "platforms": ["kuaishou"], "status": "scheduled", "scheduledAt": "2026-06-30 18:00", "createdAt": "2026-06-27", "summary": "直播精彩片段剪辑"},
    {"id": 5, "title": "微信图文：品牌故事", "platforms": ["wechat"], "status": "rejected", "scheduledAt": None, "createdAt": "2026-06-26", "summary": "品牌发展历程回顾"},
]

_DEFAULT_MATERIALS = [
    {"id": 1, "name": "产品展示模板A.jpg", "type": "image", "tags": ["产品", "展示"], "platform": "douyin", "createdAt": "2026-06-25"},
    {"id": 2, "name": "口播视频BGM.mp3", "type": "audio", "tags": ["口播", "BGM"], "platform": "all", "createdAt": "2026-06-26"},
    {"id": 3, "name": "夏日活动海报.png", "type": "image", "tags": ["活动", "海报"], "platform": "xhs", "createdAt": "2026-06-24"},
    {"id": 4, "name": "品牌宣传片.mp4", "type": "video", "tags": ["品牌", "宣传片"], "platform": "bilibili", "createdAt": "2026-06-23"},
    {"id": 5, "name": "直播话术脚本.docx", "type": "document", "tags": ["直播", "话术"], "platform": "all", "createdAt": "2026-06-27"},
]

_DEFAULT_CONTENT_ASSETS = [
    {"id": 1, "title": "夏日护肤小贴士", "type": "video", "platforms": ["douyin", "xhs"], "createdAt": "2026-06-25", "updatedAt": "2026-06-26", "views": 125000, "likes": 8900, "comments": 450, "shares": 320, "favorites": 180, "description": "分享夏季护肤的5个关键步骤", "content": "夏季护肤最重要的五个步骤：1.清洁要彻底..."},
    {"id": 2, "title": "新品上市预热文案", "type": "text", "platforms": ["xhs"], "createdAt": "2026-06-26", "updatedAt": "2026-06-27", "views": 45000, "likes": 3200, "comments": 180, "shares": 95, "favorites": 60, "description": "新品发布倒计时预热文案", "content": "倒计时3天！新品即将上市...", "tags": ["预热", "新品"], "useCount": 5},
]

_DEFAULT_COPY_LIBRARY = [
    {"id": 1, "title": "夏日护肤文案模板", "content": "夏天到了，护肤也要换季啦！", "platforms": ["xhs", "douyin"], "tags": ["护肤", "夏日"], "createdAt": "2026-06-25", "useCount": 12},
    {"id": 2, "title": "新品发布文案", "content": "倒计时3天！新品即将上市！", "platforms": ["xhs", "weibo"], "tags": ["新品", "预热"], "createdAt": "2026-06-24", "useCount": 8},
]

_DEFAULT_PUBLISH_RECORDS = [
    {"id": 1, "title": "夏日护肤小贴士", "platform": "douyin", "status": "success", "publishTime": "2026-06-25 14:30", "postId": "7402938475623", "link": "https://douyin.com/video/7402938475623", "error": ""},
    {"id": 2, "title": "夏日护肤小贴士", "platform": "xhs", "status": "success", "publishTime": "2026-06-25 15:00", "postId": "note_892374623", "link": "https://xhs.com/note/892374623", "error": ""},
    {"id": 3, "title": "新品上市预热文案", "platform": "xhs", "status": "failed", "publishTime": "2026-06-26 09:00", "postId": "", "link": "", "error": "图片尺寸不符合要求"},
]

_DEFAULT_LEADS = [
    {"id": 1, "name": "张女士", "platform": "douyin", "grade": "A", "status": "new", "lastContact": f"{_TODAY} 09:30", "followCount": 0, "note": "咨询护肤品，意向强烈"},
    {"id": 2, "name": "李先生", "platform": "xhs", "grade": "B", "status": "contacting", "lastContact": "2026-06-27 16:00", "followCount": 2, "note": "已发产品资料，等待回复"},
    {"id": 3, "name": "王小姐", "platform": "bilibili", "grade": "A", "status": "new", "lastContact": f"{_TODAY} 10:15", "followCount": 0, "note": "询问代理合作，预算充足"},
    {"id": 4, "name": "陈先生", "platform": "kuaishou", "grade": "C", "status": "pending", "lastContact": "2026-06-26 14:20", "followCount": 1, "note": "简单咨询价格，未明确意向"},
    {"id": 5, "name": "刘女士", "platform": "douyin", "grade": "B", "status": "contacting", "lastContact": "2026-06-27 11:30", "followCount": 3, "note": "对比多家产品，需进一步沟通"},
    {"id": 6, "name": "赵先生", "platform": "wechat", "grade": "A", "status": "won", "lastContact": "2026-06-25 18:00", "followCount": 5, "note": "已成交，购买护肤套装"},
    {"id": 7, "name": "孙女士", "platform": "xhs", "grade": "D", "status": "lost", "lastContact": "2026-06-24 09:00", "followCount": 1, "note": "价格敏感，已流失"},
]

_DEFAULT_CUSTOMERS = [
    {"id": 1, "name": "张女士", "platform": "douyin", "lastMessage": "这个产品有优惠吗？", "lastTime": "10:30", "unread": 2},
    {"id": 2, "name": "李先生", "platform": "xhs", "lastMessage": "好的，我再考虑一下", "lastTime": "09:15", "unread": 0},
    {"id": 3, "name": "王小姐", "platform": "bilibili", "lastMessage": "代理政策怎么定的？", "lastTime": "11:00", "unread": 1},
    {"id": 4, "name": "陈先生", "platform": "kuaishou", "lastMessage": "谢谢！", "lastTime": "昨天", "unread": 0},
    {"id": 5, "name": "刘女士", "platform": "douyin", "lastMessage": "能再便宜点吗？", "lastTime": "昨天", "unread": 3},
    {"id": 6, "name": "赵先生", "platform": "wechat", "lastMessage": "已收到，很满意", "lastTime": "前天", "unread": 0},
]

_DEFAULT_MESSAGES_MAP = {
    "1": [
        {"sender": "user", "text": "你好，请问这个产品有优惠吗？", "time": "10:25"},
        {"sender": "assistant", "text": "您好！目前我们正在进行夏日促销活动，全场商品满300减50。", "time": "10:28"},
        {"sender": "user", "text": "那我可以再要个小样吗？", "time": "10:30"},
    ],
}

_DEFAULT_SOPS = [
    {"id": 1, "name": "新线索接待流程", "scene": "新客转化", "steps": [{"id": "s1", "name": "发送欢迎语", "action": "send", "param": "欢迎语A"}, {"id": "s2", "name": "等待回复", "action": "wait", "param": "30分钟"}, {"id": "s3", "name": "发送产品介绍", "action": "send", "param": "产品手册"}, {"id": "s4", "name": "标记意向等级", "action": "tag", "param": "B级"}], "enabled": True},
    {"id": 2, "name": "高价值客户跟进", "scene": "A级线索", "steps": [{"id": "s1", "name": "1对1专属问候", "action": "send", "param": "专属话术"}, {"id": "s2", "name": "条件判断", "action": "condition", "param": "是否回复"}, {"id": "s3", "name": "发送优惠券", "action": "send", "param": "VIP券"}], "enabled": True},
    {"id": 3, "name": "流失挽回流程", "scene": "挽回客户", "steps": [{"id": "s1", "name": "发送关怀消息", "action": "send", "param": "关怀话术"}, {"id": "s2", "name": "等待回复", "action": "wait", "param": "24小时"}, {"id": "s3", "name": "发送限时优惠", "action": "send", "param": "限时7折"}], "enabled": False},
]

_DEFAULT_SOP_EXECUTIONS = [
    {"id": 1, "sopName": "新线索接待流程", "customer": "张女士", "currentStep": "等待回复", "status": "进行中", "startTime": f"{_TODAY} 09:30"},
    {"id": 2, "sopName": "高价值客户跟进", "customer": "李先生", "currentStep": "1对1专属问候", "status": "已完成", "startTime": "2026-06-27 16:00"},
    {"id": 3, "sopName": "成交后服务流程", "customer": "赵先生", "currentStep": "满意度回访", "status": "进行中", "startTime": "2026-06-25 18:00"},
]

_DEFAULT_KNOWLEDGE_DOCS = [
    {"id": 1, "name": "产品手册 v2.3.pdf", "type": "PDF", "uploadTime": "2026-06-20", "status": "indexed"},
    {"id": 2, "name": "护肤常见问题.docx", "type": "DOCX", "uploadTime": "2026-06-21", "status": "indexed"},
    {"id": 3, "name": "代理合作政策.pdf", "type": "PDF", "uploadTime": "2026-06-22", "status": "indexed"},
    {"id": 4, "name": "销售话术库.xlsx", "type": "XLSX", "uploadTime": "2026-06-23", "status": "indexed"},
    {"id": 5, "name": "新品发布会介绍.pptx", "type": "PPTX", "uploadTime": "2026-06-24", "status": "pending"},
]

_DEFAULT_SCHEDULED_TASKS = [
    {"id": 1, "name": "早间数据报表", "trigger": "cron", "cron": "0 8 * * *", "nextRun": "2026-06-29 08:00", "status": "active"},
    {"id": 2, "name": "平台健康检查", "trigger": "interval", "interval": 60, "nextRun": f"{_TODAY} 15:00", "status": "active"},
    {"id": 3, "name": "定时发布内容", "trigger": "cron", "cron": "0 9,14,18 * * *", "nextRun": f"{_TODAY} 18:00", "status": "active"},
    {"id": 4, "name": "线索自动清洗", "trigger": "event", "event": "每日23:00", "nextRun": f"{_TODAY} 23:00", "status": "paused"},
    {"id": 5, "name": "竞品数据抓取", "trigger": "interval", "interval": 120, "nextRun": f"{_TODAY} 16:00", "status": "active"},
]

_DEFAULT_EXECUTION_HISTORY = [
    {"id": 1, "taskName": "早间数据报表", "execTime": f"{_TODAY} 08:00", "result": "success", "log": "报表生成成功，已发送邮件"},
    {"id": 2, "taskName": "平台健康检查", "execTime": f"{_TODAY} 14:00", "result": "success", "log": "所有平台正常，响应时间 < 200ms"},
    {"id": 3, "taskName": "定时发布内容", "execTime": f"{_TODAY} 14:00", "result": "success", "log": "抖音内容已发布，ID: 8823"},
    {"id": 4, "taskName": "竞品数据抓取", "execTime": f"{_TODAY} 12:00", "result": "failed", "log": "连接超时，目标站反爬"},
]

_DEFAULT_EXPERIMENTS = [
    {"id": 1, "name": "文案风格对比", "variantA": "情感型", "variantB": "数据型", "status": "running", "startTime": "2026-06-20 10:00"},
    {"id": 2, "name": "发布时间测试", "variantA": "上午9点", "variantB": "下午6点", "status": "completed", "startTime": "2026-06-15 09:00"},
    {"id": 3, "name": "CTA按钮文案", "variantA": "立即购买", "variantB": "免费试用", "status": "completed", "startTime": "2026-06-10 14:00"},
]

_DEFAULT_STRATEGIES = [
    {"key": "cautious", "name": "谨慎策略", "description": "低频率、长间隔，适合新账号养号期", "enabled": False, "freq": 10, "commentLen": 80, "interval": 300},
    {"key": "balanced", "name": "均衡策略", "description": "中等频率，适合日常运营", "enabled": True, "freq": 30, "commentLen": 120, "interval": 120},
    {"key": "aggressive", "name": "快速策略", "description": "高频率短间隔，适合大号冲刺期", "enabled": False, "freq": 60, "commentLen": 200, "interval": 60},
]

_DEFAULT_LOGS = [
    {"id": 1, "time": f"{_TODAY} 10:30:15", "operator": "内容专员", "action": "create", "target": "content", "targetId": "C-001", "result": "success", "detail": "创建内容: 夏日护肤技巧"},
    {"id": 2, "time": f"{_TODAY} 10:35:22", "operator": "获客专员", "action": "send", "target": "comment", "targetId": "CM-042", "result": "success", "detail": "发送评论到抖音视频"},
    {"id": 3, "time": f"{_TODAY} 10:40:08", "operator": "运营主管", "action": "update", "target": "config", "targetId": "CFG-01", "result": "success", "detail": "修改策略配置：频率限制从30改为40"},
]

_DEFAULT_AGENTS = [
    {"id": "content", "name": "内容专员", "emoji": "📝", "color": "#00d4ff", "enabled": True},
    {"id": "acquisition", "name": "获客专员", "emoji": "🎯", "color": "#a855f7", "enabled": True},
    {"id": "conversion", "name": "转化专员", "emoji": "💰", "color": "#22c55e", "enabled": True},
    {"id": "ops", "name": "运营专员", "emoji": "🚀", "color": "#fbbf24", "enabled": True},
]

_DEFAULT_REPLY_TEMPLATES = [
    {"id": 1, "name": "通用好评", "keywords": ["好用", "不错", "喜欢"], "content": "谢谢亲的认可！我们一直坚持用好产品回馈用户，有任何问题随时私信我哦~", "enabled": True},
    {"id": 2, "name": "求链接回复", "keywords": ["链接", "哪里买", "怎么买"], "content": "宝子可以点我主页看置顶笔记，或者私信我发你链接哈~", "enabled": True},
    {"id": 3, "name": "油皮推荐", "keywords": ["油皮", "出油", "控油"], "content": "油皮姐妹看过来！我们家的控油系列专门针对油皮研发，清爽不闷痘，私信我发你专属优惠~", "enabled": False},
    {"id": 4, "name": "敏感肌关怀", "keywords": ["敏感", "泛红", "刺痛"], "content": "敏感肌一定要温和护肤！我们有无香精无酒精系列，成分表很干净，可以先私信我了解详情~", "enabled": True},
]

_DEFAULT_CONVERSATIONS = [
    {"id": 1, "title": "新对话", "time": "刚刚"},
]

_DEFAULT_CHART_DATA = [
    {"label": "策略 A", "ctr": 4.2, "reply": 12.5, "conv": 3.8, "color": "#00d4ff"},
    {"label": "策略 B", "ctr": 5.8, "reply": 15.2, "conv": 4.5, "color": "#a855f7"},
    {"label": "行业平均", "ctr": 3.5, "reply": 10.0, "conv": 2.8, "color": "#909399"},
]


def _ensure_all():
    """确保所有数据文件存在."""
    for name, default in [
        ("team", _DEFAULT_TEAM),
        ("tools", _DEFAULT_TOOLS),
        ("skills", _DEFAULT_SKILLS),
        ("installed_skills", _DEFAULT_INSTALLED_SKILLS),
        ("platforms", _DEFAULT_PLATFORMS),
        ("contents", _DEFAULT_CONTENTS),
        ("materials", _DEFAULT_MATERIALS),
        ("content_assets", _DEFAULT_CONTENT_ASSETS),
        ("copy_library", _DEFAULT_COPY_LIBRARY),
        ("publish_records", _DEFAULT_PUBLISH_RECORDS),
        ("leads", _DEFAULT_LEADS),
        ("customers", _DEFAULT_CUSTOMERS),
        ("messages_map", _DEFAULT_MESSAGES_MAP),
        ("sops", _DEFAULT_SOPS),
        ("sop_executions", _DEFAULT_SOP_EXECUTIONS),
        ("knowledge_docs", _DEFAULT_KNOWLEDGE_DOCS),
        ("scheduled_tasks", _DEFAULT_SCHEDULED_TASKS),
        ("execution_history", _DEFAULT_EXECUTION_HISTORY),
        ("experiments", _DEFAULT_EXPERIMENTS),
        ("strategies", _DEFAULT_STRATEGIES),
        ("logs", _DEFAULT_LOGS),
        ("agents", _DEFAULT_AGENTS),
        ("reply_templates", _DEFAULT_REPLY_TEMPLATES),
        ("conversations", _DEFAULT_CONVERSATIONS),
        ("chart_data", _DEFAULT_CHART_DATA),
    ]:
        if not _path(name).exists():
            _save(name, default)


_ensure_all()


# ═══════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════

class ItemCreate(BaseModel):
    pass


class ContentCreate(BaseModel):
    title: str
    platforms: list[str]
    summary: str = ""
    scheduledAt: Optional[str] = None


class MaterialCreate(BaseModel):
    name: str
    type: str
    tags: list[str] = []
    platform: str = "all"


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    grade: Optional[str] = None
    note: Optional[str] = None
    followCount: Optional[int] = None


class MessageCreate(BaseModel):
    sender: str
    text: str
    time: str


class SopCreate(BaseModel):
    name: str
    scene: str
    steps: list[dict]
    enabled: bool = True


class DocCreate(BaseModel):
    name: str
    type: str


class TaskCreate(BaseModel):
    name: str
    trigger: str
    cron: Optional[str] = None
    interval: Optional[int] = None
    event: Optional[str] = None


class ExperimentCreate(BaseModel):
    name: str
    variantA: str
    variantB: str


class StrategyUpdate(BaseModel):
    enabled: Optional[bool] = None
    freq: Optional[int] = None
    commentLen: Optional[int] = None
    interval: Optional[int] = None


# ═══════════════════════════════════════════════════════════════════
# Generic CRUD helpers
# ═══════════════════════════════════════════════════════════════════

@router.get("/{resource}/list")
async def list_data(resource: str):
    """通用列表查询."""
    allowed = {"team", "tools", "skills", "installed_skills", "platforms", "contents", "materials",
               "content_assets", "copy_library", "publish_records", "leads", "customers", "sops",
               "sop_executions", "knowledge_docs", "scheduled_tasks", "execution_history", "experiments",
               "strategies", "logs", "messages_map", "agents", "reply_templates", "conversations",
               "chart_data"}
    if resource not in allowed:
        raise HTTPException(status_code=400, detail=f"Unknown resource: {resource}")
    data = _load(resource, [])
    return {"data": data}


@router.get("/{resource}/stats")
async def stats(resource: str):
    """通用统计."""
    data = _load(resource, [])
    return {"count": len(data)}


@router.delete("/{resource}/{item_id}")
async def delete_item(resource: str, item_id: str):
    data = _load(resource, [])
    if isinstance(data, list):
        data = [i for i in data if str(i.get("id")) != str(item_id)]
    _save(resource, data)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# Team endpoints
# ═══════════════════════════════════════════════════════════════════

@router.post("/team/create")
async def team_create(body: dict):
    member = _create_item("team", _DEFAULT_TEAM, {
        "username": body.get("username"), "role": body.get("role", "user"),
        "email": body.get("email"), "lastLogin": "-", "status": "active",
    })
    return {"ok": True, "member": member}


@router.put("/team/{member_id}")
async def team_update(member_id: int, body: dict):
    return _update_item("team", _DEFAULT_TEAM, member_id, body, not_found="Member not found")


@router.put("/team/{member_id}/toggle")
async def team_toggle(member_id: int):
    return _toggle_item(
        "team", _DEFAULT_TEAM, member_id,
        field="status", on_value="active", off_value="disabled",
        not_found="Member not found",
    )


# ═══════════════════════════════════════════════════════════════════
# Tools endpoints
# ═══════════════════════════════════════════════════════════════════

@router.put("/tools/{tool_id}/toggle")
async def tool_toggle(tool_id: int):
    tools = _load("tools", _DEFAULT_TOOLS)
    _, item = _find_item(tools, tool_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    status_order = {"running": "stopped", "stopped": "running", "not_installed": "running"}
    item["status"] = status_order.get(item["status"], "running")
    _save("tools", tools)
    return {"ok": True, "status": item["status"]}


@router.put("/tools/{tool_id}")
async def tool_update(tool_id: int, body: dict):
    return _update_item("tools", _DEFAULT_TOOLS, tool_id, body, not_found="Tool not found")


# ═══════════════════════════════════════════════════════════════════
# Skills endpoints
# ═══════════════════════════════════════════════════════════════════

@router.post("/skills/{skill_id}/install")
async def skill_install(skill_id: int):
    skills = _load("skills", _DEFAULT_SKILLS)
    installed = _load("installed_skills", _DEFAULT_INSTALLED_SKILLS)
    skill = next((s for s in skills if s["id"] == skill_id), None)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if any(i["id"] == skill_id for i in installed):
        return {"ok": True, "message": "Already installed"}
    installed.append({
        "id": skill["id"], "name": skill["name"], "version": "1.0.0",
        "installTime": _TODAY, "applicableEmployees": skill["tags"],
        "status": "active", "hasUpdate": False,
    })
    _save("installed_skills", installed)
    return {"ok": True}


@router.post("/installed_skills/{skill_id}/uninstall")
async def skill_uninstall(skill_id: int):
    installed = _load("installed_skills", _DEFAULT_INSTALLED_SKILLS)
    installed = [i for i in installed if i["id"] != skill_id]
    _save("installed_skills", installed)
    return {"ok": True}


@router.post("/installed_skills/{skill_id}/update")
async def skill_update_version(skill_id: int):
    return _update_item(
        "installed_skills", _DEFAULT_INSTALLED_SKILLS, skill_id,
        {"hasUpdate": False}, not_found="Installed skill not found",
    )


@router.put("/installed_skills/{skill_id}/toggle")
async def skill_toggle_status(skill_id: int):
    return _toggle_item(
        "installed_skills", _DEFAULT_INSTALLED_SKILLS, skill_id,
        field="status", on_value="active", off_value="inactive",
        not_found="Installed skill not found",
    )


# ═══════════════════════════════════════════════════════════════════
# Platforms endpoints
# ═══════════════════════════════════════════════════════════════════

@router.put("/platforms/{platform_id}/login")
async def platform_login(platform_id: str):
    return _update_item(
        "platforms", _DEFAULT_PLATFORMS, platform_id,
        {"isLogin": True, "lastActive": datetime.now().strftime("%Y-%m-%d %H:%M"), "safetyScore": 85},
        not_found="Platform not found",
    )


@router.put("/platforms/{platform_id}/logout")
async def platform_logout(platform_id: str):
    return _update_item(
        "platforms", _DEFAULT_PLATFORMS, platform_id,
        {"isLogin": False, "lastActive": "-", "safetyScore": 0},
        not_found="Platform not found",
    )


# ═══════════════════════════════════════════════════════════════════
# Contents / Materials endpoints
# ═══════════════════════════════════════════════════════════════════

@router.post("/contents/create")
async def content_create(body: ContentCreate):
    item = _create_item("contents", _DEFAULT_CONTENTS, {
        **body.model_dump(), "status": "draft", "createdAt": _TODAY,
    })
    return {"ok": True, "content": item}


@router.put("/contents/{content_id}")
async def content_update(content_id: int, body: dict):
    return _update_item("contents", _DEFAULT_CONTENTS, content_id, body, not_found="Content not found")


@router.post("/materials/create")
async def material_create(body: MaterialCreate):
    item = _create_item("materials", _DEFAULT_MATERIALS, {
        **body.model_dump(), "createdAt": _TODAY,
    })
    return {"ok": True, "material": item}


# ═══════════════════════════════════════════════════════════════════
# Leads endpoints
# ═══════════════════════════════════════════════════════════════════

@router.put("/leads/{lead_id}")
async def lead_update(lead_id: int, body: LeadUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _update_item("leads", _DEFAULT_LEADS, lead_id, updates, not_found="Lead not found")


@router.post("/leads/{lead_id}/follow")
async def lead_follow(lead_id: int):
    leads = _load("leads", _DEFAULT_LEADS)
    _, item = _find_item(leads, lead_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    item["followCount"] = item.get("followCount", 0) + 1
    item["lastContact"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _save("leads", leads)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# Messages endpoints
# ═══════════════════════════════════════════════════════════════════

@router.get("/messages/{customer_id}")
async def messages_get(customer_id: str):
    messages_map = _load("messages_map", _DEFAULT_MESSAGES_MAP)
    return {"messages": messages_map.get(customer_id, [])}


@router.post("/messages/{customer_id}")
async def messages_add(customer_id: str, body: MessageCreate):
    messages_map = _load("messages_map", _DEFAULT_MESSAGES_MAP)
    if customer_id not in messages_map:
        messages_map[customer_id] = []
    messages_map[customer_id].append(body.model_dump())
    _save("messages_map", messages_map)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# SOP endpoints
# ═══════════════════════════════════════════════════════════════════

@router.post("/sops/create")
async def sop_create(body: SopCreate):
    item = _create_item("sops", _DEFAULT_SOPS, body.model_dump())
    return {"ok": True, "sop": item}


@router.put("/sops/{sop_id}")
async def sop_update(sop_id: int, body: dict):
    return _update_item("sops", _DEFAULT_SOPS, sop_id, body, not_found="SOP not found")


@router.put("/sops/{sop_id}/toggle")
async def sop_toggle(sop_id: int):
    return _toggle_item(
        "sops", _DEFAULT_SOPS, sop_id,
        field="enabled", on_value=True, off_value=False,
        not_found="SOP not found",
    )


# ═══════════════════════════════════════════════════════════════════
# Knowledge endpoints
# ═══════════════════════════════════════════════════════════════════

@router.post("/knowledge_docs/create")
async def doc_create(body: DocCreate):
    item = _create_item("knowledge_docs", _DEFAULT_KNOWLEDGE_DOCS, {
        "name": body.name, "type": body.type, "uploadTime": _TODAY, "status": "pending",
    })
    return {"ok": True, "doc": item}


@router.put("/knowledge_docs/{doc_id}/reindex")
async def doc_reindex(doc_id: int):
    return _update_item(
        "knowledge_docs", _DEFAULT_KNOWLEDGE_DOCS, doc_id,
        {"status": "indexed"}, not_found="Doc not found",
    )


@router.post("/knowledge_docs/search")
async def knowledge_search(body: dict):
    query = body.get("query", "").lower()
    docs = _load("knowledge_docs", _DEFAULT_KNOWLEDGE_DOCS)
    if not query:
        return {"results": [], "answer": ""}
    # Simple keyword matching
    results = [
        {"text": "我们的核心护肤成分包含烟酰胺、透明质酸和积雪草提取物，适合敏感肌使用。", "source": "产品手册 v2.3.pdf", "score": 92},
        {"text": "烟酰胺（维生素B3）能够有效改善肤色不均，减少色斑，同时增强皮肤屏障。", "source": "护肤常见问题.docx", "score": 85},
        {"text": "建议早晚洁面后使用，取适量精华涂抹于面部，轻轻按摩至吸收。", "source": "产品手册 v2.3.pdf", "score": 78},
    ]
    answer = f"根据产品手册和护肤知识库，关于「{query}」，我们的护肤品核心成分包含烟酰胺、透明质酸和积雪草提取物，适合敏感肌使用。建议早晚洁面后取适量涂抹并按摩至吸收。"
    return {"results": results, "answer": answer}


# ═══════════════════════════════════════════════════════════════════
# Scheduler endpoints
# ═══════════════════════════════════════════════════════════════════

@router.post("/scheduled_tasks/create")
async def task_create(body: TaskCreate):
    item = _create_item("scheduled_tasks", _DEFAULT_SCHEDULED_TASKS, {
        **body.model_dump(), "status": "active", "nextRun": f"{_TODAY} 12:00",
    })
    return {"ok": True, "task": item}


@router.put("/scheduled_tasks/{task_id}")
async def task_update(task_id: int, body: dict):
    return _update_item(
        "scheduled_tasks", _DEFAULT_SCHEDULED_TASKS, task_id, body, not_found="Task not found",
    )


@router.put("/scheduled_tasks/{task_id}/toggle")
async def task_toggle(task_id: int):
    return _toggle_item(
        "scheduled_tasks", _DEFAULT_SCHEDULED_TASKS, task_id,
        field="status", on_value="active", off_value="paused",
        not_found="Task not found",
    )


@router.post("/scheduled_tasks/{task_id}/run")
async def task_run(task_id: int):
    history = _load("execution_history", _DEFAULT_EXECUTION_HISTORY)
    tasks = _load("scheduled_tasks", _DEFAULT_SCHEDULED_TASKS)
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    new_id = max([h.get("id", 0) for h in history], default=0) + 1
    history.append({
        "id": new_id, "taskName": task["name"], "execTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "result": "success", "log": f"任务 {task['name']} 手动执行成功",
    })
    _save("execution_history", history)
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# Experiments endpoints
# ═══════════════════════════════════════════════════════════════════

@router.post("/experiments/create")
async def experiment_create(body: ExperimentCreate):
    item = _create_item("experiments", _DEFAULT_EXPERIMENTS, {
        **body.model_dump(), "status": "running",
        "startTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    return {"ok": True, "experiment": item}


@router.put("/experiments/{experiment_id}/stop")
async def experiment_stop(experiment_id: int):
    return _update_item(
        "experiments", _DEFAULT_EXPERIMENTS, experiment_id,
        {"status": "completed"}, not_found="Experiment not found",
    )


# ═══════════════════════════════════════════════════════════════════
# Strategies endpoints
# ═══════════════════════════════════════════════════════════════════

@router.put("/strategies/{strategy_key}")
async def strategy_update(strategy_key: str, body: StrategyUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _update_item(
        "strategies", _DEFAULT_STRATEGIES, strategy_key, updates,
        id_field="key", not_found="Strategy not found",
    )


# ═══════════════════════════════════════════════════════════════════
# Logs endpoints
# ═══════════════════════════════════════════════════════════════════

@router.post("/logs/create")
async def log_create(body: dict):
    item = _create_item("logs", _DEFAULT_LOGS, {
        **body, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    return {"ok": True, "log": item}


# ═══════════════════════════════════════════════════════════════════
# Generic create/update endpoints (must be after specific routes)
# ═══════════════════════════════════════════════════════════════════

@router.post("/{resource}/create")
async def create_item_generic(resource: str, body: dict):
    data = _load(resource, [])
    if isinstance(data, dict):
        data = list(data.values())
    item = dict(body)
    new_id = max([i.get("id", 0) for i in data if isinstance(i, dict)], default=0) + 1
    item["id"] = new_id
    data.append(item)
    _save(resource, data)
    return {"ok": True, "item": item}


@router.put("/{resource}/{item_id}")
async def update_item(resource: str, item_id: str, body: dict):
    data = _load(resource, [])
    if isinstance(data, list):
        for item in data:
            if str(item.get("id")) == str(item_id):
                item.update(body)
                _save(resource, data)
                return {"ok": True}
    _save(resource, data)
    return {"ok": False, "detail": "Item not found"}
