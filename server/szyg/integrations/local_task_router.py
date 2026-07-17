"""Routes low-risk short tasks to the bundled local small model."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from szyg.integrations.local_small_model_client import LocalSmallModelClient

ALLOWED_LOCAL_TASKS = {
    "summarize": "请用简洁中文总结下面内容，保留关键信息。",
    "rewrite": "请把下面文字改写得自然、简洁、适合企业员工使用。",
    "classify": "请对下面内容做简单分类，只输出分类结果和一句原因。",
    "keywords": "请从下面内容提取 3 到 8 个关键词，用逗号分隔。",
    "lead_score": "请判断下面评论的线索价值，输出 A/B/C/D 和一句原因。",
    "comment_draft": "请为下面内容生成自然、简短的评论草稿，不要包含联系方式或引流内容。",
    "title": "请为下面任务生成一个 12 字以内的中文标题。",
}

BLOCKED_LOCAL_TASKS = {
    "tool_call",
    "desktop_plan",
    "computer_use",
    "payment",
    "delete",
    "login",
    "publish_final",
}


class LocalTaskRouter:
    """Uses local model only when the task is safe and easily replaceable."""

    def __init__(self, client: LocalSmallModelClient | None = None) -> None:
        self.client = client or LocalSmallModelClient()

    def can_use_local(self, task_type: str) -> bool:
        return task_type in ALLOWED_LOCAL_TASKS and task_type not in BLOCKED_LOCAL_TASKS

    async def run(
        self,
        task_type: str,
        text: str,
        *,
        fallback: Callable[[], Awaitable[str]] | None = None,
        max_tokens: int = 512,
    ) -> dict:
        if not self.can_use_local(task_type):
            if fallback:
                return {"used_local": False, "content": await fallback(), "fallback_reason": "blocked_task"}
            return {"used_local": False, "content": "", "error": "blocked_task"}
        try:
            prompt = ALLOWED_LOCAL_TASKS[task_type]
            result = await self.client.chat(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text[:6000]},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            content = (result.get("message") or {}).get("content", "").strip()
            if not content:
                raise RuntimeError("local model returned empty content")
            return {"used_local": True, "content": content, "model": result.get("model", "")}
        except Exception as exc:
            if fallback:
                return {"used_local": False, "content": await fallback(), "fallback_reason": str(exc)}
            return {"used_local": False, "content": "", "error": str(exc)}


_router: LocalTaskRouter | None = None


def get_local_task_router() -> LocalTaskRouter:
    global _router
    if _router is None:
        _router = LocalTaskRouter()
    return _router
