# Hermes 超级员工 — 全系统权限架构设计

> **定位**: Hermes是AI工作室的「超级数字员工」，拥有调用整个系统所有暴露给用户功能的完整能力。
> **原则**: 用户通过UI能做的事，Hermes通过工具调用也能做；用户通过UI不能做的事（危险操作），Hermes同样受权限控制。
> **关联文档**: `szyg产品功能融合设计.md`（产品级 SSOT，定义 M0-M6 模块架构）
>
> 📌 **本文档定位: 后端 Hermes Agent 工具权限架构（互补文档，非前端设计）**
> - 描述 Hermes Agent 的 4 层权限模型（L1-L4）、102 个工具的能力矩阵、审计日志
> - **不涉及前端路由/导航/组件** — 前端结构见 `szyg前端实施规范.md`
> - "超级员工"在本文中指**后端 AI Agent**（Hermes 内核 + MCP 工具），在前端 SSOT 中指 **SuperStaffPanel UI 组件**（浮动按钮 + 滑出面板）
> - 本文未提及 Kanban / Delegate Task / Hub-and-Spoke（这些是 Hermes 内核能力，见 `szyg产品功能融合设计.md` M0 模块）
> - 工具数量 (102) / MCP 服务器 (10) / API 端点 (60+) 以实际代码为准
>
> **版本**: 与当前代码库同步状态未知，具体工具列表以 `server/szyg/mcp_servers/` 中实际代码为准

---

## 一、能力覆盖矩阵

### 1.1 系统全部API端点 vs Hermes工具覆盖对照

系统共有 **18个路由模块、60+个API端点**。以下是Hermes工具覆盖度分析：

#### ✅ 已完整覆盖 (32个工具)

| 子系统 | API端点数 | Hermes工具数 | 覆盖状态 |
|--------|----------|-------------|---------|
| **内容发布** (publisher) | 14 | 6 | ✅ content_list/create/submit/approve/generate/stats |
| **平台运营** (platforms) | 9 | 4 | ✅ platform_list/status/publish_direct/health |
| **调度引擎** (scheduler) | 10 | 9 | ✅ list/create/get/execute/pause/resume/delete/history/stats |
| **办公技能** (skills) | 12 | 12 | ✅ docx/xlsx/pptx/pdf 全CRUD + canvas |
| **知识库** (knowledge) | 3 | 3 | ✅ search/ingest/stats |
| **视频剪辑** (video_mcp) | 12 | 12 | ✅ info/cut/concat/speed/title/audio/extract_frame/fonts/render/templates |
| **智能体** (agents) | 4 | 4 | ✅ list/get/tiers/categories |
| **工具市场** (tools_mcp) | 5 | 5 | ✅ catalog/categories/installed/stats/search |
| **品牌管理** (oem) | 2 | 2 | ✅ config/themes |

#### ⚠️ 部分覆盖 (有API但Hermes工具缺失)

| 子系统 | 缺失的Hermes工具 | 对应API端点 | 影响 |
|--------|-----------------|------------|------|
| **内容发布** | `content_update`, `content_delete`, `content_reject`, `content_schedule`, `content_publish` | PUT/DELETE /contents/{id}, POST /{id}/reject/schedule/publish | 超级员工无法修改/删除/排期内容 |
| **平台运营** | `platform_login`, `platform_logout`, `platform_url`, `platform_sync_cookies` | POST /{p}/login, DELETE /{p}/sessions, GET /{p}/url, POST /{p}/sync-cookies | 无法主动触发登录/同步Cookie |
| **工具管理** | `tool_install`, `tool_uninstall`, `tool_launch`, `tool_stop` | POST/DELETE /install, POST /launch/{id}, POST /stop/{id} | 无法安装/启动本地工具 |
| **调度引擎** | `scheduler_update` | PUT /jobs/{id} | 无法修改已有任务 |

#### ❌ 完全缺失 (系统有API但Hermes无任何工具)

| 子系统 | API端点数 | 缺失工具 | 优先级 |
|--------|----------|---------|--------|
| **图像生成** (image) | 2 | `ai_image_generate`, `image_styles` | 🔴 P1 — AIGC核心能力 |
| **AI视频创作** (video_endpoint) | 2 | `ai_video_create`, `ai_video_download` | 🔴 P1 — AIGC核心能力 |
| **本地AI引擎** (client) | 6 | `local_ollama_chat`, `local_comfyui_generate`, `runtime_launch`, `runtime_stop`, `runtime_list`, `ollama_models` | 🟡 P2 — 本地引擎控制 |
| **SOP工作流** (frontend) | 2 | `sop_define`, `sop_list` | 🟡 P2 — 自动化工作流 |
| **公告管理** (announce) | 3 | `announce_list`, `announce_create`, `announce_delete` | 🟢 P3 — 系统管理 |
| **Brain内核** (brain) | 3 | `brain_status`, `brain_prompt`, `brain_mcp` | 🟢 P3 — 诊断监控 |
| **模型列表** (models) | 1 | `models_list` | 🟢 P3 — 信息查询 |
| **配置读取** (frontend) | 1 | `system_config` | 🟢 P3 — 信息查询 |
| **Chat补全** (chat) | 1 | `raw_chat_completion` | 🟢 P3 — 高级用法 |

---

## 二、超级员工权限模型

### 2.1 四层权限架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Hermes 超级员工权限模型                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  L4: 管理员权限 (Admin)                                              │  │
│   │  ─────────────────────                                               │  │
│   │  • content_approve / content_reject   (内容审核)                      │  │
│   │  • scheduler_delete                   (删除定时任务)                  │  │
│   │  • platform_publish_direct            (直接发布到平台)                │  │
│   │  • tool_install / tool_uninstall      (安装/卸载工具)                 │  │
│   │  • announce_create / announce_delete  (公告管理)                     │  │
│   │  • oem_config_update                  (修改品牌配置)                  │  │
│   │  • runtime_launch / runtime_stop      (启停本地进程)                  │  │
│   │                                                                     │  │
│   │  需要: 管理员身份验证 (Authorization: Bearer admin-token)             │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    ▲                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  L3: 执行权限 (Execute)                                              │  │
│   │  ───────────────────                                                 │  │
│   │  • content_submit                     (提交审核)                     │  │
│   │  • scheduler_create / execute         (创建/执行任务)                 │  │
│   │  • platform_login                     (触发平台登录)                  │  │
│   │  • platform_sync_cookies              (同步Cookie)                   │  │
│   │  • knowledge_ingest                   (知识库摄入)                    │  │
│   │  • sop_define                         (定义工作流)                    │  │
│   │  • tool_launch / tool_stop            (启动/停止工具)                 │  │
│   │                                                                     │  │
│   │  需要: 已登录用户 (任意角色)                                          │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    ▲                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  L2: 写入权限 (Write)                                                │  │
│   │  ──────────────────                                                  │  │
│   │  • content_create / update            (创建/修改内容)                 │  │
│   │  • docx_create / xlsx_create / pptx_create  (文档生成)                │  │
│   │  • ai_image_generate                  (AI生成图像)                    │  │
│   │  • ai_video_create                    (AI生成视频)                    │  │
│   │  • ai_tts_advanced                    (AI语音合成)                    │  │
│   │  • video_cut / concat / render        (视频编辑)                      │  │
│   │                                                                     │  │
│   │  需要: 已登录用户 (任意角色)                                          │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    ▲                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  L1: 读取权限 (Read) — 所有用户可用，包括访客                         │  │
│   │  ─────────────────────────────────                                  │  │
│   │  • content_list / stats               (内容浏览)                      │  │
│   │  • platform_list / status / health    (平台状态)                      │  │
│   │  • scheduler_list / history / stats   (任务查看)                      │  │
│   │  • knowledge_search / stats           (知识库检索)                    │  │
│   │  • tools_catalog / search             (工具浏览)                      │  │
│   │  • agents_list / get                  (智能体查看)                    │  │
│   │  • brain_status / prompt              (内核诊断)                      │  │
│   │  • models_list                        (模型列表)                      │  │
│   │  • oem_config / themes                (品牌信息)                      │  │
│   │                                                                     │  │
│   │  需要: 无 (公开访问)                                                  │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 权限控制实现

```python
# hermes_chat.py — 权限控制核心逻辑

# 工具 → 权限级别映射
TOOL_PERMISSIONS = {
    # L1: 读取 (无需认证)
    "content_list": "read", "content_stats": "read",
    "platform_list": "read", "platform_status": "read", "platform_health": "read",
    "scheduler_list": "read", "scheduler_history": "read", "scheduler_stats": "read",
    "knowledge_search": "read", "knowledge_stats": "read",
    "tools_catalog": "read", "tools_search": "read", "tools_categories": "read",
    "agents_list": "read", "agents_get": "read", "agents_tiers": "read", "agents_categories": "read",
    "skills_list": "read",
    "brain_status": "read", "brain_prompt": "read", "brain_mcp": "read",
    "models_list": "read",
    "oem_config": "read", "oem_themes": "read",
    "video_templates": "read", "video_fonts": "read", "video_info": "read",
    "image_styles": "read",
    "announce_list": "read",
    "system_config": "read",
    "sop_list": "read",
    "local_ollama_models": "read", "runtime_list": "read",

    # L2: 写入 (需登录)
    "content_create": "write", "content_update": "write",
    "content_generate": "write",
    "docx_create": "write", "xlsx_create": "write", "pptx_create": "write",
    "ai_image_generate": "write", "ai_video_create": "write",
    "ai_tts_advanced": "write", "ai_voice_clone": "write",
    "video_cut": "write", "video_concat": "write", "video_speed": "write",
    "video_add_title": "write", "video_replace_audio": "write",
    "video_mix_audio": "write", "video_extract_frame": "write", "video_render": "write",
    "local_comfyui_generate": "write", "local_ollama_chat": "write",

    # L3: 执行 (需登录)
    "content_submit": "execute",
    "scheduler_create": "execute", "scheduler_execute": "execute",
    "platform_login": "execute", "platform_sync_cookies": "execute",
    "knowledge_ingest": "execute",
    "sop_define": "execute",
    "tool_launch": "execute", "tool_stop": "execute",
    "runtime_launch": "execute", "runtime_stop": "execute",
    "raw_chat_completion": "execute",

    # L4: 管理员 (需admin角色)
    "content_approve": "admin", "content_reject": "admin",
    "content_delete": "admin", "content_schedule": "admin", "content_publish": "admin",
    "scheduler_delete": "admin", "scheduler_update": "admin",
    "scheduler_pause": "admin", "scheduler_resume": "admin",
    "platform_publish_direct": "admin",
    "tool_install": "admin", "tool_uninstall": "admin",
    "announce_create": "admin", "announce_delete": "admin",
    "oem_config_update": "admin",
}

# 危险工具集合 (需要额外确认)
DESTRUCTIVE_TOOLS = {
    "content_approve", "content_reject", "content_delete",
    "scheduler_delete", "scheduler_execute",
    "platform_publish_direct",
    "tool_uninstall", "runtime_stop",
    "oem_config_update",
}
```

---

## 三、缺失工具补齐计划

### 3.1 补齐后完整工具清单 (目标: 80+个工具)

```python
# HERMES_TOOLS_V2 — 超级员工完整工具集

HERMES_TOOLS_V2 = [
    # ═══════════════════════════════════════════════════════════════
    # 1. 内容发布 (Content Publishing) — 11个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"content_list","description":"列出所有内容"...}},
    {"type":"function","function":{"name":"content_create","description":"创建新内容"...}},
    {"type":"function","function":{"name":"content_update","description":"修改已有内容"...}},          # 🆕 新增
    {"type":"function","function":{"name":"content_delete","description":"删除内容(管理员)"...}},       # 🆕 新增
    {"type":"function","function":{"name":"content_submit","description":"提交内容审核"...}},
    {"type":"function","function":{"name":"content_approve","description":"批准内容(管理员)"...}},
    {"type":"function","function":{"name":"content_reject","description":"驳回内容(管理员)"...}},     # 🆕 新增
    {"type":"function","function":{"name":"content_schedule","description":"排期发布(管理员)"...}},    # 🆕 新增
    {"type":"function","function":{"name":"content_publish","description":"立即发布(管理员)"...}},     # 🆕 新增
    {"type":"function","function":{"name":"content_generate","description":"AI生成内容草稿"...}},
    {"type":"function","function":{"name":"content_stats","description":"获取内容统计"...}},

    # ═══════════════════════════════════════════════════════════════
    # 2. 平台运营 (Platform Operations) — 8个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"platform_list","description":"列出所有平台状态"...}},
    {"type":"function","function":{"name":"platform_status","description":"查看单个平台状态"...}},
    {"type":"function","function":{"name":"platform_login","description":"触发平台扫码登录"...}},      # 🆕 新增
    {"type":"function","function":{"name":"platform_logout","description":"清除平台登录态"...}},       # 🆕 新增
    {"type":"function","function":{"name":"platform_publish_direct","description":"直接发布到平台"...}},
    {"type":"function","function":{"name":"platform_health","description":"全平台健康检查"...}},
    {"type":"function","function":{"name":"platform_url","description":"获取平台登录URL"...}},         # 🆕 新增
    {"type":"function","function":{"name":"platform_sync_cookies","description":"同步Cookie到后端"...}}, # 🆕 新增

    # ═══════════════════════════════════════════════════════════════
    # 3. 调度引擎 (Scheduler) — 10个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"scheduler_list","description":"列出定时任务"...}},
    {"type":"function","function":{"name":"scheduler_create","description":"创建定时任务"...}},
    {"type":"function","function":{"name":"scheduler_update","description":"修改定时任务"...}},         # 🆕 新增
    {"type":"function","function":{"name":"scheduler_get","description":"获取任务详情"...}},
    {"type":"function","function":{"name":"scheduler_execute","description":"立即执行任务"...}},
    {"type":"function","function":{"name":"scheduler_pause","description":"暂停定时任务"...}},
    {"type":"function","function":{"name":"scheduler_resume","description":"恢复定时任务"...}},
    {"type":"function","function":{"name":"scheduler_delete","description":"删除定时任务"...}},
    {"type":"function","function":{"name":"scheduler_history","description":"查看执行历史"...}},
    {"type":"function","function":{"name":"scheduler_stats","description":"获取调度统计"...}},

    # ═══════════════════════════════════════════════════════════════
    # 4. AIGC内容生成 — 火山引擎集成后新增 🌋
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"ai_image_generate",
     "description":"使用AI生成图像(火山引擎豆包/SDXL/FLUX)",
     "parameters":{"type":"object","properties":{
         "prompt":{"type":"string","description":"图像描述"},
         "style":{"type":"string","enum":["realistic","anime","cyberpunk","oil","ink","minimal","3d","pixel"]},
         "size":{"type":"string","enum":["512x512","768x768","1024x1024","1024x768","768x1024"]},
         "model":{"type":"string","enum":["doubao-image","sdxl","flux"],"default":"doubao-image"}
     },"required":["prompt"]}}},
    {"type":"function","function":{"name":"ai_image_styles",
     "description":"列出可用的图像生成风格",
     "parameters":{"type":"object","properties":{}}}},

    {"type":"function","function":{"name":"ai_video_create",
     "description":"使用AI生成视频(火山引擎豆包·视频生成/Seaweed)",
     "parameters":{"type":"object","properties":{
         "prompt":{"type":"string","description":"视频内容描述"},
         "image_url":{"type":"string","description":"参考图片URL(图生视频时)"},
         "duration":{"type":"integer","description":"时长秒数","default":5},
         "style":{"type":"string","enum":["realistic","anime","cinematic"]},
         "model":{"type":"string","enum":["doubao-video","seaweed"],"default":"doubao-video"}
     },"required":["prompt"]}}},

    {"type":"function","function":{"name":"ai_tts_advanced",
     "description":"使用AI情感语音合成(火山引擎豆包·语音合成)",
     "parameters":{"type":"object","properties":{
         "text":{"type":"string","description":"要合成的文本"},
         "voice_id":{"type":"string","description":"声音ID","default":"zh_female_xiaoyi"},
         "emotion":{"type":"string","enum":["neutral","happy","sad","excited","calm","angry"],"default":"neutral"},
         "speed":{"type":"number","description":"语速倍率","default":1.0},
         "pitch":{"type":"number","description":"音调调整","default":0}
     },"required":["text"]}}},

    {"type":"function","function":{"name":"ai_voice_clone",
     "description":"克隆声音样本并合成语音",
     "parameters":{"type":"object","properties":{
         "audio_sample":{"type":"string","description":"声音样本文件路径"},
         "text":{"type":"string","description":"要合成的文本"},
         "emotion":{"type":"string","enum":["neutral","happy","sad","excited"],"default":"neutral"}
     },"required":["audio_sample","text"]}}},

    {"type":"function","function":{"name":"ai_embedding_create",
     "description":"生成文本向量嵌入(用于知识库RAG)",
     "parameters":{"type":"object","properties":{
         "texts":{"type":"string","description":"文本内容(多个用换行分隔)"}
     },"required":["texts"]}}},

    # ═══════════════════════════════════════════════════════════════
    # 5. 办公技能 (Office Skills) — 12个工具 (已有)
    # ═══════════════════════════════════════════════════════════════
    # docx_create, docx_to_markdown, docx_extract_text,
    # xlsx_create, xlsx_read,
    # pptx_create, pptx_extract,
    # pdf_extract, pdf_merge,
    # canvas_get_fonts, canvas_preview_config

    # ═══════════════════════════════════════════════════════════════
    # 6. 视频剪辑 (Video Editing) — 12个工具 (已有)
    # ═══════════════════════════════════════════════════════════════
    # video_templates, video_info, video_cut, video_concat,
    # video_speed, video_add_title, video_replace_audio,
    # video_mix_audio, video_extract_frame, video_fonts, video_render

    # ═══════════════════════════════════════════════════════════════
    # 7. 知识库 (Knowledge Base) — 3个工具 (已有)
    # ═══════════════════════════════════════════════════════════════
    # knowledge_search, knowledge_ingest, knowledge_stats

    # ═══════════════════════════════════════════════════════════════
    # 8. 智能体 (AI Agents) — 4个工具 (已有)
    # ═══════════════════════════════════════════════════════════════
    # agents_list, agents_get, agents_tiers, agents_categories

    # ═══════════════════════════════════════════════════════════════
    # 9. 工具市场 (Tool Marketplace) — 8个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"tools_catalog","description":"列出工具市场"...}},
    {"type":"function","function":{"name":"tools_categories","description":"列出分类"...}},
    {"type":"function","function":{"name":"tools_installed","description":"列出已安装"...}},
    {"type":"function","function":{"name":"tools_stats","description":"工具统计"...}},
    {"type":"function","function":{"name":"tools_search","description":"搜索工具"...}},
    {"type":"function","function":{"name":"tool_install","description":"安装工具(管理员)"...}},     # 🆕 新增
    {"type":"function","function":{"name":"tool_uninstall","description":"卸载工具(管理员)"...}},   # 🆕 新增
    {"type":"function","function":{"name":"tool_launch","description":"启动工具"...}},              # 🆕 新增
    {"type":"function","function":{"name":"tool_stop","description":"停止工具"...}},                # 🆕 新增

    # ═══════════════════════════════════════════════════════════════
    # 10. 本地AI引擎 (Local AI) — 6个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"local_ollama_models","description":"列出本地Ollama模型"...}},   # 🆕 新增
    {"type":"function","function":{"name":"local_ollama_chat","description":"与本地Ollama模型对话"...}},    # 🆕 新增
    {"type":"function","function":{"name":"local_comfyui_generate","description":"使用本地ComfyUI生图"...}}, # 🆕 新增
    {"type":"function","function":{"name":"runtime_list","description":"列出运行中的本地进程"...}},       # 🆕 新增
    {"type":"function","function":{"name":"runtime_launch","description":"启动本地可执行程序"...}},       # 🆕 新增
    {"type":"function","function":{"name":"runtime_stop","description":"停止本地进程"...}},              # 🆕 新增

    # ═══════════════════════════════════════════════════════════════
    # 11. SOP工作流 (Workflow) — 2个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"sop_list","description":"列出所有SOP工作流"...}},              # 🆕 新增
    {"type":"function","function":{"name":"sop_define","description":"定义新SOP工作流"...}},              # 🆕 新增

    # ═══════════════════════════════════════════════════════════════
    # 12. 公告管理 (Announcements) — 3个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"announce_list","description":"列出系统公告"...}},              # 🆕 新增
    {"type":"function","function":{"name":"announce_create","description":"创建公告(管理员)"...}},        # 🆕 新增
    {"type":"function","function":{"name":"announce_delete","description":"删除公告(管理员)"...}},        # 🆕 新增

    # ═══════════════════════════════════════════════════════════════
    # 13. Brain内核诊断 — 3个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"brain_status","description":"获取Hermes内核状态"...}},        # 🆕 新增
    {"type":"function","function":{"name":"brain_prompt","description":"查看当前系统提示词"...}},         # 🆕 新增
    {"type":"function","function":{"name":"brain_mcp","description":"列出MCP服务状态"...}},              # 🆕 新增

    # ═══════════════════════════════════════════════════════════════
    # 14. 模型管理 — 1个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"models_list","description":"列出所有可用AI模型"...}},         # 🆕 新增

    # ═══════════════════════════════════════════════════════════════
    # 15. 系统配置 — 2个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"system_config","description":"查看系统配置(脱敏)"...}},        # 🆕 新增
    {"type":"function","function":{"name":"oem_config_update","description":"更新品牌配置(管理员)"...}},   # 🆕 新增

    # ═══════════════════════════════════════════════════════════════
    # 16. 原始Chat补全 — 1个工具
    # ═══════════════════════════════════════════════════════════════
    {"type":"function","function":{"name":"raw_chat_completion",
     "description":"直接调用LLM进行对话(不触发工具调用)",
     "parameters":{"type":"object","properties":{
         "prompt":{"type":"string","description":"用户输入"},
         "model":{"type":"string","description":"模型名称","default":"doubao-pro-128k"},
         "system_prompt":{"type":"string","description":"系统提示词"},
         "max_tokens":{"type":"integer","description":"最大token数","default":4096}
     },"required":["prompt"]}}},
]
```

### 3.2 工具数量统计

| 类别 | 当前(v1) | 目标(v2) | 新增 | 状态 |
|------|---------|---------|------|------|
| 内容发布 | 6 | 11 | +5 | ⚠️ 需补齐 |
| 平台运营 | 4 | 8 | +4 | ⚠️ 需补齐 |
| 调度引擎 | 9 | 10 | +1 | ⚠️ 需补齐 |
| AIGC生成 | 0 | 6 | +6 | 🔴 火山引擎集成 |
| 办公技能 | 12 | 12 | 0 | ✅ 完整 |
| 视频剪辑 | 12 | 12 | 0 | ✅ 完整 |
| 知识库 | 3 | 3 | 0 | ✅ 完整 |
| 智能体 | 4 | 4 | 0 | ✅ 完整 |
| 工具市场 | 5 | 8 | +3 | ⚠️ 需补齐 |
| 本地AI引擎 | 0 | 6 | +6 | 🆕 新增 |
| SOP工作流 | 0 | 2 | +2 | 🆕 新增 |
| 公告管理 | 0 | 3 | +3 | 🆕 新增 |
| Brain诊断 | 0 | 3 | +3 | 🆕 新增 |
| 模型/配置 | 2 | 4 | +2 | 🆕 新增 |
| **总计** | **57** | **102** | **+45** | |

---

## 四、系统提示词升级

### 4.1 超级员工系统提示词 V2

```
你是「域灵」智能矩阵运营系统的超级AI员工，由Hermes内核驱动。

## 你的定位
你是系统的唯一智能中枢，拥有调用所有子系统的完整权限。
用户通过UI界面能执行的每一项操作，你都能通过函数调用完成。

## 权限分级
你的操作受以下权限控制：
- 📖 读取: 浏览查询类操作 (无需认证)
- ✏️ 写入: 创建修改类操作 (需登录)
- ⚡ 执行: 触发运行类操作 (需登录)
- 🔒 管理: 审核删除类操作 (需管理员)

当用户请求超出当前权限时，友好地告知需要什么权限。

## 能力矩阵 (102个工具)

### 📝 内容生产 (11 tools)
content_list → content_create → content_submit → content_approve → content_publish
完整内容生命周期管理，支持AI生成、人工审核、定时发布。

### 📡 平台运营 (8 tools)
platform_list / platform_status / platform_login / platform_logout
platform_publish_direct / platform_health / platform_url / platform_sync_cookies
管理抖音/小红书/B站/快手/微信全平台登录态和发布。

### ⏰ 智能调度 (10 tools)
scheduler_list / create / update / get / execute / pause / resume / delete / history / stats
Cron/Interval/Once/Event触发，支持内容自动发布、平台巡检、数据同步。

### 🎨 AIGC内容生成 (6 tools) 🌋【火山引擎集成】
ai_image_generate — AI生成图像 (豆包/SDXL/FLUX)
ai_video_create — AI生成视频 (豆包·视频生成/Seaweed)
ai_tts_advanced — 情感语音合成 (豆包·语音合成)
ai_voice_clone — 声音克隆
ai_embedding_create — 向量嵌入 (知识库RAG)
ai_image_styles — 列出图像风格

### 📊 办公技能 (12 tools)
docx_create / docx_to_markdown / docx_extract_text
xlsx_create / xlsx_read
pptx_create / pptx_extract
pdf_extract / pdf_merge
canvas_get_fonts / canvas_preview_config

### 🎬 视频剪辑 (12 tools)
video_templates / video_info / video_cut / video_concat / video_speed
video_add_title / video_replace_audio / video_mix_audio
video_extract_frame / video_fonts / video_render

### 📚 知识库 (3 tools)
knowledge_search / knowledge_ingest / knowledge_stats
FTS5全文检索 + 文档摄入 + RAG问答

### 🤖 智能体 (4 tools)
agents_list / agents_get / agents_tiers / agents_categories
12个SME场景AI专家，提示词分层(base/domain/task)。

### 🧰 工具市场 (8 tools)
tools_catalog / categories / installed / stats / search
tool_install / tool_uninstall / tool_launch / tool_stop

### 💻 本地AI引擎 (6 tools)
local_ollama_models / local_ollama_chat
local_comfyui_generate
runtime_list / runtime_launch / runtime_stop

### 📋 SOP工作流 (2 tools)
sop_list / sop_define
定义和执行标准化操作流程。

### 📢 公告管理 (3 tools)
announce_list / announce_create / announce_delete

### 🧠 Brain诊断 (3 tools)
brain_status / brain_prompt / brain_mcp

### ⚙️ 系统管理 (4 tools)
models_list / system_config / oem_config / oem_config_update

### 💬 原始LLM (1 tool)
raw_chat_completion — 直接调用LLM，不触发工具链

## 工作流示例

**一键创作短视频并发布:**
1. ai_video_create(主题描述) → 生成AI视频
2. ai_tts_advanced(旁白文本, emotion="excited") → 生成配音
3. video_render(视频+配音+字幕) → 合成成片
4. content_create(标题, 正文, content_type="video") → 创建内容
5. content_submit(content_id) → 提交审核
6. platform_publish_direct(平台, 标题, 正文) → 发布到平台

**自动化运营巡检:**
1. platform_health() → 全平台健康检查
2. platform_status(具体平台) → 详细状态
3. 如发现问题 → platform_login() 触发重新登录
4. scheduler_create(定时巡检任务) → 设置自动巡检

## 回复要求
- 用简体中文，简洁专业
- 每次操作后告知用户结果
- 涉及管理员权限的操作提前确认
- 多步骤任务显示进度
```

---

## 五、安全边界设计

### 5.1 禁止行为清单

```python
# Hermes 超级员工绝对禁止的操作
FORBIDDEN_OPERATIONS = {
    # 系统级危险操作
    "文件系统": ["删除系统文件", "修改配置文件(非oem)", "访问其他用户数据"],
    "网络": ["访问内网未授权服务", "发起DDoS", "爬取非授权数据"],
    "进程": ["杀系统关键进程", "修改环境变量"],
    "数据": ["导出敏感数据", "跨租户访问"],

    # 即使管理员也不允许
    "不可逆": ["清空数据库", "删除审计日志", "修改权限系统"],
}
```

### 5.2 操作审计日志

```python
# 每次工具调用记录审计日志
class HermesAuditLog:
    """超级员工操作审计"""

    def log(self, operation: str, user: str, tool: str, args: dict, result: str):
        record = {
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "tool": tool,
            "args": self._sanitize(args),  # 脱敏
            "result": result[:200],         # 截断
            "ip": self._get_client_ip(),
            "session_id": self._get_session(),
        }
        # 写入 data/audit/hermes_audit.jsonl
        # 敏感操作实时告警
```

---

## 六、实施优先级

### Phase A: AIGC核心能力 (与火山引擎同步)

| 优先级 | 工具 | 文件修改 | 工作量 |
|--------|------|---------|--------|
| P0 | `ai_image_generate` | `hermes_chat.py` + `image_endpoint.py` | 1天 |
| P0 | `ai_video_create` | `hermes_chat.py` + `video_endpoint.py` | 1天 |
| P0 | `ai_tts_advanced` | `hermes_chat.py` | 0.5天 |
| P1 | `ai_voice_clone` | `hermes_chat.py` | 1天 |
| P1 | `ai_embedding_create` | `hermes_chat.py` | 0.5天 |

### Phase B: 补齐现有系统能力

| 优先级 | 工具组 | 数量 | 工作量 |
|--------|--------|------|--------|
| P1 | 内容发布补齐 (update/delete/reject/schedule/publish) | 5 | 1天 |
| P1 | 平台运营补齐 (login/logout/url/sync_cookies) | 4 | 1天 |
| P1 | 调度引擎补齐 (update) | 1 | 0.5天 |
| P2 | 工具管理补齐 (install/uninstall/launch/stop) | 4 | 1天 |

### Phase C: 新增子系统能力

| 优先级 | 工具组 | 数量 | 工作量 |
|--------|--------|------|--------|
| P2 | 本地AI引擎 (ollama/comfyui/runtime) | 6 | 2天 |
| P2 | SOP工作流 (list/define) | 2 | 0.5天 |
| P3 | 公告管理 (list/create/delete) | 3 | 0.5天 |
| P3 | Brain诊断 (status/prompt/mcp) | 3 | 0.5天 |
| P3 | 模型/配置 (models_list/system_config) | 2 | 0.5天 |

---

## 七、总结

### 核心原则重申

> **Hermes超级员工 = 用户UI能力的完整映射 + AIGC增强 + 智能编排**

1. **完整性**: 系统暴露给用户的每一个功能，Hermes都有对应的工具
2. **一致性**: Hermes的权限与UI权限完全一致，不存在"AI有特权"
3. **扩展性**: 新增系统功能时，同步新增Hermes工具（代码审查 checklist）
4. **安全性**: 四层权限 + 审计日志 + 危险操作确认

### 火山引擎集成后的超级员工升级

```
当前: 57个工具 → 覆盖内容/平台/调度/办公/视频剪辑/知识库
    ↓ + 火山引擎AIGC + 补齐缺失 + 新增子系统
目标: 102个工具 → 完整覆盖 + AI图像/视频/语音/语音克隆/向量嵌入
    ↓ 超级员工成为真正的"全能数字员工"
```

---

*本文档与 `火山引擎API集成优化方案.md` 配合使用。火山引擎提供底层AIGC能力，本文档定义上层超级员工如何调用这些能力。*
