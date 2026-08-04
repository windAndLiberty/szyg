"""Central business capability registry for the SZYG Hermes runtime.

The registry keeps product capabilities discoverable without adding every
business action to the model's top-level function list. Internal modules stay
behind their existing HTTP contracts, while Hermes gets one catalog tool and
one guarded dispatcher.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import quote

import httpx


JsonBuilder = Callable[[dict[str, Any]], dict[str, Any]]


def _json_value(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ValueError("参数不是有效的 JSON")


def _string_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if text.startswith("["):
        parsed = _json_value(text, [])
        if not isinstance(parsed, list):
            raise ValueError("参数必须是列表")
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in text.split(",") if item.strip()]


def _safe_id(value: Any, label: str = "记录 ID") -> str:
    result = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", result):
        raise ValueError(f"{label}格式不正确")
    return result


@dataclass(frozen=True)
class Capability:
    name: str
    domain: str
    title: str
    description: str
    method: str = "GET"
    path: str = ""
    risk: str = "read"
    confirmation_required: bool = False
    query_keys: tuple[str, ...] = ()
    body_builder: JsonBuilder | None = None
    path_builder: Callable[[dict[str, Any]], str] | None = None
    timeout: float = 60.0
    custom: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain,
            "title": self.title,
            "description": self.description,
            "risk": self.risk,
            "confirmation_required": self.confirmation_required,
            "parameters": self.parameters,
        }


def _body(*keys: str) -> JsonBuilder:
    return lambda args: {key: args[key] for key in keys if key in args}


def _followup_body(args: dict[str, Any]) -> dict[str, Any]:
    return {
        key: args.get(key, "")
        for key in (
            "lead_id", "customer_id", "customer_name", "platform", "action",
            "reply_text", "next_reminder_at", "notes",
        )
    }


def _publish_note_body(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": str(args.get("platform") or ""),
        "image_paths": _string_list(args.get("image_paths")),
        "title": str(args.get("title") or ""),
        "note": str(args.get("note") or ""),
        "tags": _string_list(args.get("tags")),
        "schedule": args.get("schedule") or None,
        "headless": bool(args.get("headless", True)),
        "account_id": args.get("account_id") or None,
        "target_account_ids": _string_list(args.get("target_account_ids")),
        "profile_id": args.get("profile_id") or None,
    }


def _publish_video_body(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform": str(args.get("platform") or ""),
        "file_path": str(args.get("file_path") or ""),
        "title": str(args.get("title") or ""),
        "desc": str(args.get("desc") or ""),
        "tags": _string_list(args.get("tags")),
        "thumbnail_path": args.get("thumbnail_path") or None,
        "schedule": args.get("schedule") or None,
        "headless": bool(args.get("headless", True)),
        "account_id": args.get("account_id") or None,
        "target_account_ids": _string_list(args.get("target_account_ids")),
        "profile_id": args.get("profile_id") or None,
    }


def _acquisition_search_body(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "keyword": str(args.get("keyword") or ""),
        "platforms": _string_list(args.get("platforms")) or ["douyin", "xhs", "bilibili", "kuaishou"],
        "limit": int(args.get("limit") or 20),
        "min_score": int(args.get("min_score") or 40),
    }


def _workflow_instance_body(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "template_id": str(args.get("template_id") or ""),
        "definition_id": str(args.get("definition_id") or ""),
        "name": str(args.get("name") or ""),
        "description": str(args.get("description") or ""),
        "schedule": _json_value(args.get("schedule_json"), {"type": "manual"}),
        "config": _json_value(args.get("config_json"), {}),
        "human_policy": str(args.get("human_policy") or "pause_on_risk"),
    }


def _capabilities() -> list[Capability]:
    scalar = {"type": "string"}
    return [
        Capability("content.copy.generate", "content", "生成营销文案", "根据需求生成一到十条可编辑营销文案。", method="POST", path="/api/content/copy/generate", risk="generation", body_builder=_body("prompt", "copy_type", "count", "min_words", "max_words"), timeout=180, parameters={"prompt": scalar, "copy_type": scalar, "count": {"type": "integer", "default": 5}, "min_words": {"type": "integer", "default": 80}, "max_words": {"type": "integer", "default": 160}}),
        Capability("content.image.generate", "content", "生成图片", "根据描述和视觉风格生成一到四张图片并保存到本机。", method="POST", path="/api/image/generate", risk="generation", body_builder=_body("prompt", "size", "count", "style"), timeout=240, parameters={"prompt": scalar, "size": scalar, "count": {"type": "integer", "default": 1}, "style": scalar}),
        Capability("content.video.create", "content", "创建视频生成任务", "根据最终提示、时长、比例和参考图片创建视频任务。", method="POST", path="/api/video/create", risk="generation", confirmation_required=True, body_builder=_body("prompt", "duration", "size", "ratio", "count", "native_audio", "prompt_optimize", "final_prompt", "model", "image_url"), timeout=180, parameters={"prompt": scalar, "duration": {"type": "integer", "default": 6}, "size": scalar, "ratio": scalar, "count": {"type": "integer", "default": 1}, "native_audio": {"type": "boolean", "default": False}, "final_prompt": scalar, "image_url": scalar}),
        Capability("content.video.status", "content", "查询视频生成进度", "查询视频任务状态，并在完成后返回本地素材信息。", path_builder=lambda args: f"/api/video/task/{quote(_safe_id(args.get('task_id'), '任务 ID'))}", query_keys=("model",), parameters={"task_id": scalar, "model": scalar}),

        Capability("knowledge.search", "knowledge", "检索企业知识库", "使用 RAG 从当前企业知识库返回高相关事实和来源。", path="/api/knowledge/search", query_keys=("q", "top_k", "collection"), parameters={"q": scalar, "top_k": {"type": "integer", "default": 5}, "collection": scalar}),
        Capability("knowledge.stats", "knowledge", "知识库概览", "查看文档、分块、集合和最近更新时间。", path="/api/knowledge/stats"),
        Capability("knowledge.documents", "knowledge", "知识文档列表", "按关键词、集合或处理状态查询知识文档。", path="/api/knowledge/documents", query_keys=("q", "collection", "status"), parameters={"q": scalar, "collection": scalar, "status": scalar}),
        Capability("knowledge.ingest", "knowledge", "写入知识文本", "将用户提供的文本保存并进入知识解析管线。", method="POST", path="/api/knowledge/ingest", risk="write", body_builder=_body("text", "source"), parameters={"text": scalar, "source": scalar}),
        Capability("knowledge.reparse", "knowledge", "重新解析知识文档", "重新解析磁盘中仍存在的知识源文件。", method="POST", risk="write", path_builder=lambda args: f"/api/knowledge/documents/{quote(_safe_id(args.get('document_id'), '文档 ID'))}/reparse", parameters={"document_id": scalar}),
        Capability("knowledge.delete", "knowledge", "删除知识文档", "删除指定知识文档及其索引，不删除用户原始文件。", method="DELETE", risk="destructive", confirmation_required=True, path_builder=lambda args: f"/api/knowledge/documents/{quote(_safe_id(args.get('document_id'), '文档 ID'))}", parameters={"document_id": scalar}),

        Capability("private_domain.overview", "private_domain", "私域概览", "查看待跟进、高意向和微信连接状态。", path="/api/private-domain/overview"),
        Capability("private_domain.queue", "private_domain", "私域待跟进队列", "读取待跟进线索和建议动作。", path="/api/private-domain/queue", query_keys=("limit",), parameters={"limit": {"type": "integer", "default": 50}}),
        Capability("private_domain.followup", "private_domain", "记录客户跟进", "记录跟进结果并同步线索和客户转化阶段。", method="POST", path="/api/private-domain/followups", risk="write", body_builder=_followup_body, parameters={"lead_id": scalar, "customer_id": scalar, "customer_name": scalar, "platform": scalar, "action": scalar, "reply_text": scalar, "next_reminder_at": scalar, "notes": scalar}),
        Capability("private_domain.wechat_draft", "private_domain", "生成微信跟进草稿", "在已识别微信输入区的前提下创建待人工确认的微信草稿。", method="POST", path="/api/private-domain/wechat/draft", risk="external", confirmation_required=True, body_builder=_body("lead_id", "customer_id", "customer_name", "message", "source"), parameters={"lead_id": scalar, "customer_id": scalar, "customer_name": scalar, "message": scalar, "source": scalar}),

        Capability("intelligence.query", "intelligence", "发现市场情报", "结合企业资料和发布记录执行真实情报查询。", method="POST", path="/api/intelligence/query", risk="analysis", body_builder=_body("query", "use_enterprise_context", "include_publish_records"), timeout=180, parameters={"query": scalar, "use_enterprise_context": {"type": "boolean", "default": True}, "include_publish_records": {"type": "boolean", "default": True}}),
        Capability("intelligence.reports", "intelligence", "情报报告列表", "列出最近生成的市场情报报告。", path="/api/intelligence/query-reports", query_keys=("limit",), parameters={"limit": {"type": "integer", "default": 20}}),
        Capability("intelligence.report", "intelligence", "情报报告详情", "读取指定情报报告的分析结果和证据。", path_builder=lambda args: f"/api/intelligence/query-reports/{quote(_safe_id(args.get('report_id'), '报告 ID'))}", parameters={"report_id": scalar}),
        Capability("intelligence.overview", "intelligence", "市场情报概览", "查看情报来源、采集与报告概览。", path="/api/intelligence/overview"),
        Capability("intelligence.visualization", "intelligence", "情报可视化数据", "读取词云、趋势、主题和平台分布数据。", path="/api/intelligence/visualization"),

        Capability("acquisition.search", "acquisition", "搜索公域内容", "在抖音、小红书、B站和快手检索并评分相关公开内容。", method="POST", path="/api/acquisition/search/aggregate", risk="analysis", body_builder=_acquisition_search_body, timeout=180, parameters={"keyword": scalar, "platforms": scalar, "limit": {"type": "integer", "default": 20}, "min_score": {"type": "integer", "default": 40}}),
        Capability("acquisition.comments.generate", "acquisition", "生成候选评论", "根据目标内容生成五条可编辑评论候选，不发送。", method="POST", path="/api/acquisition/comments/generate", risk="generation", body_builder=lambda args: {"video_title": str(args.get("video_title") or ""), "video_description": str(args.get("video_description") or ""), "count": int(args.get("count") or 5), "strategy": str(args.get("strategy") or "balanced"), "shared_across_targets": bool(args.get("shared_across_targets", True))}, timeout=120, parameters={"video_title": scalar, "video_description": scalar, "count": {"type": "integer", "default": 5}, "strategy": scalar, "shared_across_targets": {"type": "boolean", "default": True}}),
        Capability("acquisition.comments.preflight", "acquisition", "评论发送检查", "检查评论风险并返回可自动修复建议，不发送。", method="POST", path="/api/acquisition/comments/preflight", risk="analysis", body_builder=_body("text"), parameters={"text": scalar}),
        Capability("acquisition.comments.send_batch", "acquisition", "群发评论", "将同一条已确认评论加入最多五个目标的发送队列。", method="POST", path="/api/acquisition/comments/enqueue-batch", risk="external", confirmation_required=True, body_builder=lambda args: {"targets": _json_value(args.get("targets_json"), []), "text": str(args.get("text") or ""), "strategy": str(args.get("strategy") or "balanced"), "deai": bool(args.get("deai", False)), "confirmed": True}, timeout=120, parameters={"targets_json": scalar, "text": scalar, "strategy": scalar, "deai": {"type": "boolean", "default": False}}),
        Capability("acquisition.queue", "acquisition", "评论发送队列", "查看评论群发批次、目标状态、原视频链接和失败原因。", path="/api/acquisition/comments/queue", query_keys=("status", "platform", "archived", "limit", "offset"), parameters={"status": scalar, "platform": scalar, "archived": {"type": "boolean", "default": False}, "limit": {"type": "integer", "default": 50}, "offset": {"type": "integer", "default": 0}}),
        Capability("acquisition.leads", "acquisition", "获客线索", "查询公域与私域产生的客户线索。", path="/api/acquisition/leads", query_keys=("status", "grade", "platform", "limit"), parameters={"status": scalar, "grade": scalar, "platform": scalar, "limit": {"type": "integer", "default": 50}}),

        Capability("customers.list", "customers", "客户资产列表", "按姓名或最近互动检索客户资产。", path="/api/acquisition/customers", query_keys=("search", "limit"), parameters={"search": scalar, "limit": {"type": "integer", "default": 50}}),
        Capability("customers.create", "customers", "创建客户资产", "将用户确认的客户资料写入客户资产。", method="POST", path="/api/acquisition/customers", risk="write", body_builder=lambda args: _json_value(args.get("customer_json"), {}), parameters={"customer_json": scalar}),
        Capability("customers.messages", "customers", "客户互动记录", "读取指定客户的历史互动记录。", path="/api/acquisition/messages", query_keys=("customer_id",), parameters={"customer_id": scalar}),

        Capability("insights.overview", "insights", "全局数据洞察", "基于知识库、经营记录和外部情报生成全局洞察。", path="/api/insights/overview", query_keys=("days",), parameters={"days": {"type": "integer", "default": 30}}),
        Capability("insights.content", "insights", "内容表现洞察", "分析指定时间范围内的内容与发布表现。", path="/api/insights/content", query_keys=("days",), parameters={"days": {"type": "integer", "default": 30}}),

        Capability("materials.list", "materials", "素材列表", "读取素材管理中已采纳且磁盘可用的素材。", path="/api/publisher/materials", query_keys=("mtype", "platform"), parameters={"mtype": scalar, "platform": scalar}),
        Capability("graphic.plan", "materials", "生成图文方案", "理解最多五个素材并生成可编辑图文草稿，不自动发布。", method="POST", risk="analysis", custom="graphic_plan", timeout=240, parameters={"assets_json": {"type": "string", "description": "素材引用 JSON 数组"}, "user_instruction": scalar, "answers_json": {"type": "string", "description": "可选确认答案 JSON 数组"}}),
        Capability("graphic.save", "materials", "保存图文草稿", "将确认后的图文草稿保存到素材管理。", method="POST", path="/api/content/graphic/save", risk="write", body_builder=lambda args: {"draft": _json_value(args.get("draft_json"), {}), "used_assets": _json_value(args.get("used_assets_json"), []), "filename": str(args.get("filename") or "")}, parameters={"draft_json": scalar, "used_assets_json": scalar, "filename": scalar}),
        Capability("video_compose.plan", "materials", "生成成片方案", "理解最多五个素材并生成分镜及最终提示词，不创建视频任务。", method="POST", risk="analysis", custom="video_plan", timeout=240, parameters={"assets_json": {"type": "string", "description": "素材引用 JSON 数组"}, "answers_json": scalar, "params_json": scalar}),
        Capability("video_compose.create", "materials", "创建成片任务", "使用确认后的成片方案创建视频任务。", method="POST", path="/api/video/compose/create", risk="external", confirmation_required=True, body_builder=lambda args: {"prepared": _json_value(args.get("prepared_json"), {}), "params": _json_value(args.get("params_json"), {})}, timeout=180, parameters={"prepared_json": scalar, "params_json": scalar}),

        Capability("accounts.list", "publishing", "渠道账号列表", "读取实时渠道账号、昵称、平台和登录状态。", path="/api/platform-accounts", query_keys=("platform",), parameters={"platform": scalar}),
        Capability("accounts.sync", "publishing", "同步账号资料", "从第三方平台刷新指定账号的公开资料和登录状态。", method="POST", path_builder=lambda args: f"/api/platform-accounts/{quote(_safe_id(args.get('account_id'), '账号 ID'))}/sync-profile", query_keys=("force",), timeout=120, parameters={"account_id": scalar, "force": {"type": "boolean", "default": True}}),
        Capability("publishing_profiles.list", "publishing", "发布配置档案", "列出常用多账号发布组合。", path="/api/publishing-profiles"),
        Capability("publishing.note", "publishing", "多账号图文发布", "向一个账号、多个账号或发布档案提交图文发布任务。", method="POST", path="/api/sau/upload-note-async", risk="external", confirmation_required=True, body_builder=_publish_note_body, timeout=120, parameters={"platform": scalar, "image_paths": scalar, "title": scalar, "note": scalar, "tags": scalar, "account_id": scalar, "target_account_ids": scalar, "profile_id": scalar, "schedule": scalar, "headless": {"type": "boolean", "default": True}}),
        Capability("publishing.video", "publishing", "多账号视频发布", "向一个账号、多个账号或发布档案提交视频发布任务。", method="POST", path="/api/sau/upload-video-async", risk="external", confirmation_required=True, body_builder=_publish_video_body, timeout=120, parameters={"platform": scalar, "file_path": scalar, "title": scalar, "desc": scalar, "tags": scalar, "thumbnail_path": scalar, "account_id": scalar, "target_account_ids": scalar, "profile_id": scalar, "schedule": scalar, "headless": {"type": "boolean", "default": True}}),

        Capability("workflows.overview", "workflows", "工作流概览", "查看自动化方案、运行计划和最近执行结果。", path="/api/workflows/overview"),
        Capability("workflows.templates", "workflows", "标准流程列表", "列出可用于创建自动化方案的标准流程。", path="/api/workflows/templates"),
        Capability("workflows.instances", "workflows", "自动化方案列表", "列出已配置的自动化方案及运行时间摘要。", path="/api/workflows/instances"),
        Capability("workflows.create", "workflows", "创建自动化方案", "基于标准流程绑定业务参数并创建自动化方案。", method="POST", path="/api/workflows/instances", risk="write", body_builder=_workflow_instance_body, parameters={"template_id": scalar, "definition_id": scalar, "name": scalar, "description": scalar, "schedule_json": scalar, "config_json": scalar, "human_policy": scalar}),
        Capability("workflows.run", "workflows", "立即运行自动化方案", "立即运行指定方案，执行过程由任务内核审计和控制。", method="POST", risk="external", confirmation_required=True, path_builder=lambda args: f"/api/workflows/instances/{quote(_safe_id(args.get('instance_id'), '方案 ID'))}/run", timeout=180, parameters={"instance_id": scalar}),
        Capability("workflows.runs", "workflows", "工作流运行记录", "查询工作流运行记录和结果。", path="/api/workflows/runs", query_keys=("limit", "instance_id"), parameters={"limit": {"type": "integer", "default": 50}, "instance_id": scalar}),

        Capability("executions.list", "execution", "执行记录", "按状态、平台、任务类型或关键词查询真实执行记录。", path="/api/executions", query_keys=("limit", "status", "platform", "task_type", "keyword", "sort_by", "sort_dir", "include_archived"), parameters={"limit": {"type": "integer", "default": 50}, "status": scalar, "platform": scalar, "task_type": scalar, "keyword": scalar, "sort_by": scalar, "sort_dir": scalar, "include_archived": {"type": "boolean", "default": False}}),
        Capability("executions.detail", "execution", "执行详情", "读取执行步骤、审计日志和截图证据。", path_builder=lambda args: f"/api/executions/{quote(_safe_id(args.get('run_id'), '任务 ID'))}", parameters={"run_id": scalar}),
        Capability("executions.pause", "execution", "暂停执行", "暂停可控的运行任务。", method="POST", risk="write", path_builder=lambda args: f"/api/executions/{quote(_safe_id(args.get('run_id'), '任务 ID'))}/pause", parameters={"run_id": scalar}),
        Capability("executions.resume", "execution", "继续执行", "继续暂停的任务，可能恢复真实平台操作。", method="POST", risk="external", confirmation_required=True, path_builder=lambda args: f"/api/executions/{quote(_safe_id(args.get('run_id'), '任务 ID'))}/resume", parameters={"run_id": scalar}),
        Capability("executions.cancel", "execution", "取消执行", "取消正在运行的任务。", method="POST", risk="external", confirmation_required=True, path_builder=lambda args: f"/api/executions/{quote(_safe_id(args.get('run_id'), '任务 ID'))}/cancel", parameters={"run_id": scalar}),
        Capability("executions.retry", "execution", "重试执行", "重新执行失败任务，可能再次操作真实平台。", method="POST", risk="external", confirmation_required=True, path_builder=lambda args: f"/api/executions/{quote(_safe_id(args.get('run_id'), '任务 ID'))}/retry", parameters={"run_id": scalar}),
    ]


class HermesCapabilityRegistry:
    def __init__(self) -> None:
        self._items = {item.name: item for item in _capabilities()}

    def list(self, domain: str = "", search: str = "") -> list[dict[str, Any]]:
        domain = domain.strip().lower()
        needle = search.strip().lower()
        items = []
        for item in self._items.values():
            if domain and item.domain != domain:
                continue
            haystack = f"{item.name} {item.title} {item.description}".lower()
            if needle and needle not in haystack:
                continue
            items.append(item.public_dict())
        return sorted(items, key=lambda row: (row["domain"], row["name"]))

    async def execute(self, name: str, args: dict[str, Any], auth_headers: dict[str, str] | None = None) -> str:
        item = self._items.get(name)
        if item is None:
            return json.dumps({"ok": False, "error": "未知业务能力", "capability": name}, ensure_ascii=False)
        if item.confirmation_required and args.get("confirmed") is not True:
            return json.dumps({
                "ok": False,
                "status": "confirmation_required",
                "capability": name,
                "message": f"{item.title}会影响真实业务状态，请先取得用户明确确认后再调用，并传入 confirmed=true。",
            }, ensure_ascii=False)
        try:
            if item.custom:
                result = await self._execute_custom(item, args, auth_headers)
            else:
                result = await self._request(item, args, auth_headers)
            return json.dumps(result, ensure_ascii=False)[:12000]
        except ValueError as exc:
            return json.dumps({"ok": False, "error": str(exc), "capability": name}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok": False, "error": f"能力执行失败：{str(exc)[:300]}", "capability": name}, ensure_ascii=False)

    @staticmethod
    def _base_url() -> str:
        explicit = os.environ.get("SZYG_INTERNAL_API_URL", "").strip().rstrip("/")
        if explicit:
            return explicit
        port = os.environ.get("SZYG_BACKEND_PORT", "8000").strip() or "8000"
        return f"http://127.0.0.1:{port}"

    async def _request(self, item: Capability, args: dict[str, Any], auth_headers: dict[str, str] | None) -> dict[str, Any]:
        path = item.path_builder(args) if item.path_builder else item.path
        query = {key: args[key] for key in item.query_keys if key in args and args[key] not in (None, "")}
        body = item.body_builder(args) if item.body_builder else None
        async with httpx.AsyncClient(proxy=None, trust_env=False, timeout=item.timeout) as client:
            response = await client.request(
                item.method,
                f"{self._base_url()}{path}",
                params=query or None,
                json=body,
                headers=auth_headers or {},
            )
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail") or response.text
            except Exception:
                detail = response.text
            return {"ok": False, "status_code": response.status_code, "error": str(detail)[:500]}
        return response.json()

    async def _execute_custom(self, item: Capability, args: dict[str, Any], auth_headers: dict[str, str] | None) -> dict[str, Any]:
        assets = _json_value(args.get("assets_json"), [])
        if not isinstance(assets, list) or not assets:
            raise ValueError("请提供至少一个素材引用")
        if len(assets) > 5:
            raise ValueError("最多使用 5 个素材")
        if item.custom == "graphic_plan":
            analyze = Capability("_graphic_analyze", "materials", "", "", method="POST", path="/api/content/graphic/analyze", body_builder=lambda _: {"assets": assets, "user_instruction": str(args.get("user_instruction") or "")}, timeout=item.timeout)
            analysis = await self._request(analyze, {}, auth_headers)
            if analysis.get("ok") is False:
                return analysis
            prepare = Capability("_graphic_prepare", "materials", "", "", method="POST", path="/api/content/graphic/prepare", body_builder=lambda _: {"analysis": analysis, "answers": _json_value(args.get("answers_json"), []), "user_instruction": str(args.get("user_instruction") or "")}, timeout=item.timeout)
            return await self._request(prepare, {}, auth_headers)
        if item.custom == "video_plan":
            analyze = Capability("_video_analyze", "materials", "", "", method="POST", path="/api/video/compose/analyze", body_builder=lambda _: {"assets": assets}, timeout=item.timeout)
            analysis = await self._request(analyze, {}, auth_headers)
            if analysis.get("ok") is False:
                return analysis
            prepare = Capability("_video_prepare", "materials", "", "", method="POST", path="/api/video/compose/prepare", body_builder=lambda _: {"analysis": analysis, "answers": _json_value(args.get("answers_json"), []), "params": _json_value(args.get("params_json"), {})}, timeout=item.timeout)
            return await self._request(prepare, {}, auth_headers)
        raise ValueError("未实现的复合能力")


_REGISTRY: HermesCapabilityRegistry | None = None


def get_hermes_capability_registry() -> HermesCapabilityRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = HermesCapabilityRegistry()
    return _REGISTRY


CAPABILITY_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "capability_list",
            "description": "查询 SZYG 业务能力目录。用于发现私域营销、市场情报、数据洞察、素材组合、多账号发布和执行控制能力。",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "enum": ["content", "knowledge", "private_domain", "intelligence", "acquisition", "customers", "insights", "materials", "publishing", "workflows", "execution"]},
                    "search": {"type": "string", "description": "能力名称或业务关键词"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capability_call",
            "description": "调用能力目录中的业务能力。先用 capability_list 获取准确能力名和参数；真实外发、视频创建和任务恢复等操作必须获得用户确认。",
            "parameters": {
                "type": "object",
                "properties": {
                    "capability": {"type": "string", "description": "能力目录中的 name"},
                    "arguments_json": {"type": "string", "description": "能力参数 JSON 对象"},
                    "confirmed": {"type": "boolean", "default": False, "description": "用户是否已明确确认高风险操作"},
                },
                "required": ["capability"],
            },
        },
    },
]
