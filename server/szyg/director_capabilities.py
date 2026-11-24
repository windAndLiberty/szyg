"""MCP catalog for the local OpenMontage production desk."""
from __future__ import annotations


def director_capabilities():
    from szyg.hermes_capabilities import Capability, _body, _safe_id
    from szyg.api.director_routes import AdvancedTool, Export, Installation, Narration, ProjectCreate, ProjectEdit, Transcription

    base = "/api/director"
    text = {"type": "string"}
    uid = {"type": "string", "format": "uuid"}
    key = {"key": text}
    project = {"project_id": uid}

    def project_path(args):
        return base + "/projects/" + _safe_id(args.get("project_id"), "项目 ID")

    def query(name, title, description, path, params=None, required=()):
        fields = params or {}
        return Capability("director." + name, "director", title, description, path=base + path,
                          query_keys=tuple(fields), parameters=fields, required=required)

    def mutation(name, title, description, body, path, *, project_scope=False, risk="write", method="POST"):
        schema = body.model_json_schema()
        fields = dict(schema.get("properties", {}))
        if "$defs" in schema and "scenes" in fields:
            fields["scenes"]["items"] = schema["$defs"]["Scene"]
        # Body validation and the tool schema share the same field names and parameter bounds.
        required = tuple(schema.get("required", []))
        return Capability("director." + name, "director", title, description, method=method,
                          path="" if project_scope else base + path,
                          path_builder=(lambda args: project_path(args) + path) if project_scope else None,
                          risk=risk, confirmation_required="confirmed" in required, body_builder=_body(*fields),
                          parameters={**(project if project_scope else {}), **fields},
                          required=(("project_id",) if project_scope else ()) + required)

    return [
        query("capabilities", "导演制作环境", "检查 OpenMontage 版本、依赖、安装状态和可用制作能力。", "/capabilities"),
        query("catalog", "检索制作能力", "发现上游流水线、风格模板、工具和导演知识。", "/catalog", {
            "query": text, "kind": {"type":"string", "enum":["all","tool","pipeline","skill","style"]},
            "limit": {"type":"integer", "minimum":1,"maximum":200}, "offset":{"type":"integer","minimum":0}}),
        query("guide", "读取制作指南", "读取目录返回的流水线、风格或知识 key；长内容按 next_offset 继续。", "/guide", {**key, "offset":{"type":"integer","minimum":0}, "limit":{"type":"integer","minimum":1,"maximum":16000}}, ("key",)),
        query("tool_info", "检查制作工具", "查看上游工具可执行性、依赖、参数和授权要求。", "/tool", key, ("key",)),
        query("projects", "导演项目列表", "列出本机保存的项目，按 id 跨对话续编。", "/projects"),
        Capability("director.project", "director", "打开导演项目", "读取简报、分镜、音轨和版本号。",
                   path_builder=project_path, parameters=project, required=("project_id",)),
        mutation("create", "创建导演项目", "依据用户简报建立可持续编辑的本机视频项目，记录返回的 id。",
                 ProjectCreate, "/projects"),
        mutation("edit", "编辑时间线", "保存完整分镜顺序、时长、字幕、取材起点、比例与音轨。source 和 audio 取导入的 /api/media/files/ 链接；无素材可用字幕卡。先读项目并带上 expected_revision。",
                 ProjectEdit, "", project_scope=True, method="PUT"),
        mutation("render", "渲染本地成片", "导出当前版本 MP4。输出 url 可交付；若返回排队/运行中，用 director.job 查询。",
                 Export, "/render", project_scope=True),
        mutation("run_tool", "执行 OpenMontage 工具", "先查 director.tool_info。requires_approval 为真时说明所选服务商、发送的素材和费用，取得同意后传 confirmed=true。新任务分配 UUID，重试沿用该值，返回 job_id 可查询。",
                 AdvancedTool, "/tools", project_scope=True, risk="external"),
        mutation("install", "安装制作环境", "下载并安装固定版本的 OpenMontage 及依赖；取得用户同意后执行并查询任务。",
                 Installation, "/install", risk="external"),
        Capability("director.job", "director", "查询制作进度", "查看制作任务状态及最终成片/素材链接，确认完成后再交付。",
                   path_builder=lambda args: base + "/jobs/" + _safe_id(args.get("job_id"), "任务 ID"),
                   parameters={"job_id":uid}, required=("job_id",)),
        Capability("director.voices", "director", "配音音色", "列出小妤可选音色与标识。", path="/api/tts/voices"),
        mutation("narrate", "生成导演配音", "确认后将指定文本发送至云端配音服务，可能计费。原请求 ID 可用于重试。返回可用于项目 audio 的本机链接或 job_id。",
                 Narration, "/narrate", risk="external"),
        mutation("transcribe", "转写素材对白", "从指定本机媒体中提取音轨，上传语音服务识别文字与时间戳，可能计费。需用户确认。",
                 Transcription, "/transcribe", risk="external"),
    ]
