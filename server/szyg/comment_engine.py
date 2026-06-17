"""
智能评论状态机引擎 — 由 Hermes Cron 定时驱动

核心设计：状态流转规则用 Python 写（业务逻辑），LLM 推理委托给 Hermes。
用法:
    python -m szyg.comment_engine tick        # 单次执行
    python -m szyg.comment_engine tick --loop # 持续循环（用于调试）

Hermes Cron 注册:
    hermes cron create --schedule "*/5 * * * *" --no-agent \
        --script "python -m szyg.comment_engine tick" \
        --name "智能评论引擎"
"""

import argparse
import asyncio
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path for standalone execution
sys.path.insert(0, str(Path(__file__).parent.parent))

from szyg.comment_db import (
    init_db,
    get_active_tasks,
    transition,
    add_record,
    get_today_count,
    update_task,
)
from szyg.integrations.openrouter_client import OpenRouterClient
from szyg.config.loader import load_config


class CommentEngine:
    """智能评论状态机引擎。

    状态流转由 Python 代码驱动，每个状态的具体"思考"操作委托给 Hermes LLM。
    """

    # ── LLM Prompts ──────────────────────────────────────────────────

    PROMPT_ANALYZE = """你是智能评论引擎的内容分析师。

任务：分析目标视频/内容的上下文，找出最适合的评论切入点。

输入信息：
- 目标平台: {platform}
- 目标账号: {account}
- 触发关键词: {keywords}
- 评论人格: {persona}
- 评论风格: {style}

请用 JSON 格式返回：
{{
    "analysis": "内容分析摘要（50字以内）",
    "angle": "评论切入点（如：请教经验、表达共鸣、补充信息、制造互动）",
    "tone": "建议语气",
    "target_audience": "目标受众画像"
}}
只返回 JSON，不要其他内容。"""

    PROMPT_GENERATE = """你是智能评论引擎的文案生成师。

任务：根据分析结果，生成 {n} 条备选评论。

要求：
- 人格设定: {persona}
- 风格: {style}
- 字数限制: {max_length} 字以内
- 必须自然、真诚、像真人写的
- 避免营销感、避免重复套路
- 每条评论要有差异（角度不同）

内容分析: {analysis}
评论切入点: {angle}
建议语气: {tone}

请用 JSON 格式返回：
{{
    "comments": [
        {{"text": "评论内容1", "angle": "角度说明", "score": 95}},
        {{"text": "评论内容2", "angle": "角度说明", "score": 88}}
    ],
    "recommendation": "推荐使用的评论及理由"
}}
只返回 JSON，不要其他内容。"""

    def __init__(self):
        init_db()
        # config.yaml 在项目根目录 (server 的父目录)
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        cfg = load_config(config_path)
        llm_cfg = cfg.get("llm", {}).get("openrouter", {})
        self.llm = OpenRouterClient(
            api_key=llm_cfg.get("api_key", ""),
            base_url=llm_cfg.get("base_url", "https://openrouter.ai/api/v1"),
            default_model=llm_cfg.get("default_model", "openrouter/free"),
            timeout=llm_cfg.get("timeout", 60),
        )

    # ── Main Loop ────────────────────────────────────────────────────

    async def tick(self) -> dict:
        """执行一次状态机 tick，处理所有活跃任务。

        Returns:
            执行统计: {"processed": N, "transitions": N, "errors": N}
        """
        tasks = get_active_tasks()
        stats = {"processed": 0, "transitions": 0, "errors": 0, "details": []}

        for task in tasks:
            task_id = task["id"]
            status = task["status"]
            handler = getattr(self, f"_handle_{status}", None)

            if not handler:
                continue

            try:
                result = await handler(task)
                stats["processed"] += 1
                if result.get("transitioned"):
                    stats["transitions"] += 1
                stats["details"].append({"id": task_id, "status": status, "result": result.get("action", "noop")})
            except Exception as e:
                stats["errors"] += 1
                stats["details"].append({"id": task_id, "status": status, "error": str(e)})
                print(f"[CommentEngine] ERROR task={task_id} status={status}: {e}")

        return stats

    async def close(self):
        await self.llm.close()

    # ── State Handlers ───────────────────────────────────────────────

    async def _handle_monitoring(self, task: dict) -> dict:
        """监控中：检查触发条件。

        TODO: 真实实现需要接入平台爬虫/RPA，检测新视频或关键词。
        当前用概率模拟（演示用）。
        """
        # 模拟触发（生产环境替换为真实检测）
        triggered = random.random() < 0.3
        if triggered:
            transition(task["id"], "analyzing", "检测到新内容/触发条件满足")
            return {"transitioned": True, "action": "triggered"}
        return {"transitioned": False, "action": "noop"}

    async def _handle_analyzing(self, task: dict) -> dict:
        """分析中：调用 Hermes LLM 分析内容上下文。"""
        prompt = self.PROMPT_ANALYZE.format(
            platform=task["target_platform"],
            account=task["target_account"],
            keywords=", ".join(task.get("trigger_keywords", [])),
            persona=task["persona"],
            style=task["comment_style"],
        )

        resp = await self.llm.chat([
            {"role": "system", "content": "你是一个专业的社交媒体内容分析师。"},
            {"role": "user", "content": prompt},
        ])

        content = resp.get("message", {}).get("content", "")
        analysis = self._extract_json(content) or {"analysis": "内容分析", "angle": "互动", "tone": "友好"}

        # 保存分析结果到 metadata（通过 update_task）
        update_task(task["id"], {"status_message": json.dumps(analysis, ensure_ascii=False)})
        transition(task["id"], "generating", f"分析完成: {analysis.get('angle', '')}")
        return {"transitioned": True, "action": "analyzed", "analysis": analysis}

    async def _handle_generating(self, task: dict) -> dict:
        """生成中：调用 Hermes LLM 生成评论候选。"""
        # 读取上一步的分析结果
        analysis_text = task.get("status_message", "{}")
        try:
            analysis = json.loads(analysis_text)
        except json.JSONDecodeError:
            analysis = {"analysis": "", "angle": "", "tone": ""}

        prompt = self.PROMPT_GENERATE.format(
            n=3,
            persona=task["persona"],
            style=task["comment_style"],
            max_length=task["max_length"],
            analysis=analysis.get("analysis", ""),
            angle=analysis.get("angle", ""),
            tone=analysis.get("tone", ""),
        )

        resp = await self.llm.chat([
            {"role": "system", "content": "你是一个高情商的社交媒体文案师。"},
            {"role": "user", "content": prompt},
        ])

        content = resp.get("message", {}).get("content", "")
        result = self._extract_json(content) or {"comments": []}
        comments = result.get("comments", [])

        # 保存候选评论
        if comments:
            best = comments[0]
            add_record(
                task_id=task["id"],
                generated_text=best.get("text", ""),
                final_text=best.get("text", ""),
                status="pending",
            )

        # 决定下一步
        if task.get("require_approval"):
            transition(task["id"], "reviewing", f"生成 {len(comments)} 条候选，等待人工审核")
        else:
            transition(task["id"], "queued", f"生成 {len(comments)} 条候选，进入风控队列")

        return {"transitioned": True, "action": "generated", "candidates": len(comments)}

    async def _handle_queued(self, task: dict) -> dict:
        """排队中：风控检查，通过后提交。"""
        if not self._risk_check(task):
            return {"transitioned": False, "action": "risk_blocked"}

        # TODO: 真实实现需要调用平台 API/RPA 提交评论
        # 当前模拟提交成功
        add_record(
            task_id=task["id"],
            generated_text="[已提交]",
            final_text="[已提交]",
            status="sent",
        )

        # 更新统计
        updates = {
            "total_executed": task.get("total_executed", 0) + 1,
            "last_executed_at": datetime.now().isoformat(),
        }
        update_task(task["id"], updates)
        transition(task["id"], "executed", "风控通过，评论已提交")

        return {"transitioned": True, "action": "submitted"}

    async def _handle_follow_up(self, task: dict) -> dict:
        """需跟进：检查是否有新回复需要继续互动。"""
        # TODO: 真实实现需要轮询评论区，检测新回复
        # 如果有新回复且未超过日上限，重新进入 analyzing
        has_reply = random.random() < 0.2
        if has_reply and self._risk_check(task):
            transition(task["id"], "analyzing", "收到新回复，继续跟进")
            return {"transitioned": True, "action": "follow_up"}
        return {"transitioned": False, "action": "no_reply"}

    # ── Helpers ──────────────────────────────────────────────────────

    def _risk_check(self, task: dict) -> bool:
        """风控检查：冷却时间 + 日上限 + 连续失败熔断"""
        # 1. 冷却时间
        last = task.get("last_executed_at")
        if last:
            last_dt = datetime.fromisoformat(last)
            cooldown = timedelta(seconds=task["cooldown_seconds"])
            if datetime.now() - last_dt < cooldown:
                return False

        # 2. 日上限
        today_count = get_today_count(task["id"])
        if today_count >= task["daily_limit"]:
            return False

        # 3. 连续失败熔断
        if task.get("consecutive_failures", 0) >= 5:
            return False

        return True

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """从 LLM 响应中提取 JSON"""
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                text = parts[1]
                if text.startswith("json"):
                    text = text[4:]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return None

    # ── Intent Scoring + Auto Lead Creation ───────────────────────────

    async def score_reply_intent(
        self, platform: str, reply_content: str, task_context: str = ""
    ) -> dict | None:
        """对用户回复进行意向评分，高意向自动创建线索。

        对标: 销氪AIsales 意向识别 / 探迹AI评分
        """
        from szyg.lead_scoring import score_intent
        from szyg.lead_store import get_lead_store
        from szyg.models.lead import IntentScoringRequest, LeadProfile, LeadSource

        try:
            platform_src = LeadSource(platform)
        except ValueError:
            platform_src = LeadSource.MANUAL

        req = IntentScoringRequest(
            platform=platform_src,
            interaction_content=reply_content,
            context=task_context,
        )
        result = score_intent(req)

        # 高意向 → 自动创建线索
        if result.should_follow_up:
            store = get_lead_store()
            lead = LeadProfile(
                platform=platform_src,
                platform_account="auto-detected",
                source_content=reply_content,
                intent_score=result.intent_score,
                intent_level=result.intent_level,
                tags=["auto-generated", *result.tags],
                recommended_action=result.suggested_reply,
                notes=f"自动从智能评论引擎创建。信号: {', '.join(result.intent_signals)}",
            )
            store.create(lead)
            return {
                "lead_created": True,
                "lead_id": lead.id,
                "intent_score": result.intent_score,
                "intent_level": result.intent_level.value,
                "suggested_reply": result.suggested_reply,
            }

        return {
            "lead_created": False,
            "intent_score": result.intent_score,
            "intent_level": result.intent_level.value,
        }


# ── CLI ────────────────────────────────────────────────────────────


async def main():
    parser = argparse.ArgumentParser(description="智能评论状态机引擎")
    parser.add_argument("command", choices=["tick", "init"], help="tick: 执行一次 | init: 初始化数据库")
    parser.add_argument("--loop", action="store_true", help="持续循环执行（仅调试）")
    parser.add_argument("--interval", type=int, default=60, help="循环间隔秒数")
    args = parser.parse_args()

    if args.command == "init":
        init_db()
        print("[CommentEngine] Database initialized.")
        return

    engine = CommentEngine()
    try:
        if args.loop:
            print(f"[CommentEngine] Loop mode, interval={args.interval}s. Press Ctrl+C to stop.")
            while True:
                stats = await engine.tick()
                print(f"[CommentEngine] tick → processed={stats['processed']} transitions={stats['transitions']} errors={stats['errors']}")
                await asyncio.sleep(args.interval)
        else:
            stats = await engine.tick()
            print(f"[CommentEngine] tick → processed={stats['processed']} transitions={stats['transitions']} errors={stats['errors']}")
            for d in stats["details"]:
                print(f"  - {d['id'][:16]}: {d['status']} → {d.get('result', d.get('error', '?'))}")
    finally:
        await engine.close()


if __name__ == "__main__":
    asyncio.run(main())
