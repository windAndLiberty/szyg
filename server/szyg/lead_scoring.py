"""Lead Scoring — AI 意向识别引擎。

对标: 探迹AI评分 / 销氪意向识别

基于规则 + Hermes AI 的混合评分系统。
规则层快速识别显性信号，AI 层处理语义理解。
"""

import re
from szyg.models.lead import (
    IntentLevel, IntentScoringRequest, IntentScoringResult, LeadSource
)

# ── 高意向关键词（问了价格、购买方式、对比竞品）────────────
HIGH_INTENT_PATTERNS = [
    r"(多少钱|价格|报价|费用|收费|怎么收费)",
    r"(怎么买|在哪买|如何购买|购买链接|下单|购买方式)",
    r"(微信|加微信|私信|联系方式|电话|咨询|了解下|聊一下)",
    r"(对比|比.*好|和.*比|哪个好|推荐|建议)",
    r"(合作|代理|加盟|批发|拿货|经销)",
    r"(有优惠|打折|活动|促销|便宜点)",
]

MEDIUM_INTENT_PATTERNS = [
    r"(不错|挺好|喜欢|想要|感兴趣|有意思|收藏)",
    r"(怎么用|使用|功能|能.*吗|可以.*吗|支持.*吗)",
    r"(在哪里|地址|门店|线下|实体店)",
    r"(质量|效果|好用|靠谱|真的假的)",
    r"(有.*吗|还有.*吗|能不能|是否)",
]

LOW_INTENT_PATTERNS = [
    r"(好看|漂亮|赞|厉害|牛|👍|太.*了)",
    r"(关注|收藏|学习了|学到了|干货|有用)",
    r"(哈哈|笑|😂|❤️|🌹)",
]

# ── 平台特定信号 ─────────────────────────────────────────

PLATFORM_SCORE_BOOST: dict[LeadSource, float] = {
    LeadSource.WECOM: 0.15,     # 企微 — 强商业意图平台
    LeadSource.WECHAT: 0.10,    # 微信 — 私域强信号
    LeadSource.DOUYIN: 0.05,    # 抖音 — 公域中等信号
    LeadSource.XIAOHONGSHU: 0.05,
    LeadSource.KUAISHOU: 0.05,
    LeadSource.SHIPINHAO: 0.05,
    LeadSource.MANUAL: 0.20,    # 手动添加 — 高信任
    LeadSource.API: 0.00,
}


def score_intent(request: IntentScoringRequest) -> IntentScoringResult:
    """对单条互动进行意向评分（规则层）。

    Hermes Agent 可通过 prompt 覆盖/增强此结果。
    """
    text = request.interaction_content
    score = 0.0
    signals: list[str] = []
    tags: list[str] = []

    # ── 规则匹配 ──────────────────────────────────────
    for pattern in HIGH_INTENT_PATTERNS:
        if re.search(pattern, text):
            score += 0.25
            signals.append(f"高意向信号: {pattern}")

    for pattern in MEDIUM_INTENT_PATTERNS:
        if re.search(pattern, text):
            score += 0.12
            signals.append(f"中意向信号: {pattern}")

    for pattern in LOW_INTENT_PATTERNS:
        if re.search(pattern, text):
            score += 0.05

    # ── 平台加成 ──────────────────────────────────────
    platform_boost = PLATFORM_SCORE_BOOST.get(request.platform, 0.0)
    score += platform_boost

    # ── 长度信号（长回复通常意向更高）──────────────────
    if len(text) > 50:
        score += 0.05
        signals.append("详细回复")
    if len(text) > 100:
        score += 0.03

    # ── 提问信号 ──────────────────────────────────────
    if "?" in text or "？" in text:
        score += 0.05
        signals.append("主动提问")

    # ── 上下文增强 ────────────────────────────────────
    if request.context:
        ctx_lower = request.context.lower()
        if any(kw in ctx_lower for kw in ["促销", "活动", "优惠", "限时", "折扣"]):
            score += 0.03
            tags.append("营销敏感")

    # ── 确定等级 ──────────────────────────────────────
    score = min(score, 1.0)
    if score >= 0.6:
        level = IntentLevel.HIGH
    elif score >= 0.35:
        level = IntentLevel.MEDIUM
    elif score >= 0.15:
        level = IntentLevel.LOW
    else:
        level = IntentLevel.COLD

    # ── 生成建议回复 ───────────────────────────────────
    suggested_reply = _generate_reply(text, level, request.platform)

    # ── 是否需要跟进 ──────────────────────────────────
    should_follow_up = level in (IntentLevel.HIGH, IntentLevel.MEDIUM)

    return IntentScoringResult(
        intent_score=round(score, 2),
        intent_level=level,
        intent_signals=signals,
        suggested_reply=suggested_reply,
        should_follow_up=should_follow_up,
        tags=tags,
    )


def _generate_reply(text: str, level: IntentLevel, platform: LeadSource) -> str:
    """生成 AI 建议回复话术（规则层模板）。

    生产环境中应由 Hermes Agent 覆盖此结果。
    """
    if level == IntentLevel.HIGH:
        if re.search(r"(价格|多少钱|报价)", text):
            return "您好！具体价格根据需求定制，方便留个联系方式吗？我让顾问给您详细介绍~"
        if re.search(r"(微信|联系方式|加.*微信)", text):
            return f"您好！可以在主页找到联系方式，或者您留下微信号我这边添加您~"
        if re.search(r"(怎么买|购买|下单)", text):
            return "感谢关注！购买方式已私信发给您，或者您点击主页链接了解详情~"
        return "非常感谢您的关注！已经私信您详细信息，期待为您服务 🙌"

    if level == IntentLevel.MEDIUM:
        if re.search(r"(不错|喜欢|想要)", text):
            return "谢谢喜欢！想看更多类似内容可以关注我们哦，有任何问题随时问~"
        if re.search(r"(在哪|地址|门店)", text):
            return "我们在全国多个城市都有服务网点，您方便说下在哪个城市吗？我帮您查最近的~"
        return "感谢您的关注！如果有什么想了解的，随时留言 ~"

    if level == IntentLevel.LOW:
        return "感谢支持！💪"

    return "🙌"  # cold — 简单互动，不需要过度回复
