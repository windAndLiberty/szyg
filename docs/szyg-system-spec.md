# szyg-system-spec ─ 单一事实规格文档

> 施工队长：Architect_Agent | 施工队：Loop Agent v2
> 生成：2026-07-06 | 更新：2026-07-06 (结构修复版)
> 标记：## feature: F-XXX 供TaskDecomposer解析

---

## 施工引擎约束

当前唯一施工 engine 为 `codex`。所有 feature 均默认由 codex 承接，文档内不再为单个 feature 单独声明 engine。

---

## 系统定位

域灵(szyg)是面向中小企业的AI超级员工自动化营销平台。
后端 Python+FastAPI+SQLite，前端 React+TS+Tailwind，核心 Hermes 自然语言对话驱动30+工具。

对标竞品：炼刀AI（内容创作+多平台分发+企业岗位自动化执行）。
差异化：Hermes多专家Agent + 30+工具链 + 多智能体协作 + 企业级自动化稳定性闭环。

## 自动化执行路线

炼刀AI的关键能力不是单点聊天，而是把高频企业任务拆成多条“数据流→处理器→执行器→状态验证”的业务流水线。域灵对标炼刀AI时，优先补齐自动化执行稳定性，而不是继续堆叠单点功能。

产品边界：域灵不做扣子、Dify、百炼、n8n 类的通用拖拽式工作流搭建器。域灵面向中小企业老板和员工，核心价值是提供可直接上岗的 AI 员工、预置业务管线和稳定执行结果，而不是让用户自己设计复杂流程。

阶段1：保留现有 Playwright / social-auto-upload 路线，先把抖音、小红书等网页发布链路包装为可观测、可暂停、可回放的稳定执行闭环。

阶段2：将真实手机端执行作为一等能力，新增 MobileExecutor 抽象，面向抖音、小红书、微信等真实 App 环境，支持截图识别、触控执行、状态断言、异常暂停和人工接管。

长期目标架构：

```
用户指令 / 定时任务 / 业务事件
  │
  ▼
任务理解 + 多智能体协作
  │
  ▼
岗位型预置管线 Pipeline / SOP
  │
  ▼
统一执行内核 Execution Kernel
  ├── BrowserExecutor  浏览器/网页后台/创作者平台
  ├── DesktopExecutor  PC客户端/微信桌面版/本地软件
  ├── MobileExecutor   真实手机/模拟器/Appium/ADB/投屏控制
  └── ApiExecutor      企微/飞书/CRM/开放平台
  │
  ▼
视觉感知 + 状态断言 + 风控熔断
  │
  ▼
执行日志 / 截图证据 / 回放 / 人工接管
```

稳定性原则：
- 不确定就暂停，不继续乱执行。
- 每个关键动作必须有状态、日志、截图或可审计证据。
- 登录失效、验证码、账号异常、未知弹窗、平台风控提示必须转入 needs_human。
- 高频动作必须经过频率限制、任务上限、账号并发限制和敏感内容检查。
- 平台适配器只负责平台差异，执行状态、重试、熔断、回放应收敛到统一执行内核。

## 北星原则

1. 一句话指挥AI干活 ─ 所有功能通过对话驱动
2. 深色科技主题 #0B0F1A + #6366F1 全站统一
3. 面向中国中小企业运营人员，中文系统
4. 先骨架后血肉 ─ 路由→占位→功能→测试
5. 自动化优先稳定 ─ 可观测、可暂停、可回放、可人工接管
6. 执行器分层 ─ 浏览器、桌面、手机、API 都是一等执行通道

## 项目结构

```
D:\szyg\
├── szyg-frontend\              ← React 前端
│   └── src/
│       ├── pages/              ← 30个页面组件
│       ├── components/         ← 复用组件
│       ├── lib/api.ts          ← API封装
│       └── navConfig.ts        ← 侧边栏配置
├── server\szyg\                ← Python 后端
│   ├── brain_hermes.py         ← Hermes核心引擎
│   ├── hermes_chat.py          ← SSE对话入口
│   ├── api/                    ← 34个路由模块
│   ├── agent_core/             ← Agent核心逻辑
│   ├── platforms/              ← 平台对接(抖音/小红书等)
│   ├── video_cut_engine.py     ← 视频剪辑引擎
│   ├── intercept_engine.py     ← 智能截流引擎
│   ├── listen_engine.py        ← 舆情监听引擎
│   ├── convert_engine.py       ← 客户转化引擎
│   ├── publisher.py            ← 发布引擎
│   ├── scheduler_engine.py     ← 调度引擎
│   └── pipeline_engine.py      ← 流水线引擎
├── external\                   ← 第三方 (agency-agents-main social-auto-upload)
├── data\                       ← 运行时数据 (SQLite + JSON)
├── docs\                       ← 本文档所在地
├── tests\                      ← 后端测试
└── KnowledgeBase\              ← 设计文档集合
```

## Hermes 引擎架构

```
用户输入 (文本/语音)
  │
  ▼
hermes_chat.py (SSE流)
  │
  ▼
brain_hermes.py (Hermes核心)
  ├── 系统提示构建 (_build_system_prompt)
  ├── 专家激活 (155个专家市场)
  ├── 工具注册 (30+ MCP工具)
  └── LLM推理 + 工具调用循环
      │
      ├── 工具调用 → tool_runtime.py → 执行
      │                                    │
      │   ◄── tool_result ────────────────┘
      │
      └── 最终回复 → SSE流推送到前端
```

**关键数据流**：
- 前端 `streamHermesChat()` → SSE → `hermes_chat.py`
- `brain_hermes.py` 循环调用 LLM → 工具 → 结果 → 直到最终回复
- 工具结果以 `tool_call` + `tool_result` 消息类型推送到前端
- 对话保存到 SQLite（conversation + message 表）

## 数据模型概览

```
SQLite 表:
  conversations: id, title, created_at, updated_at, pinned
  messages: id, conversation_id, role, content, tool_calls, tool_results
  users: id, username, role, api_keys
  platforms: id, name, account, cookie, status
  tasks: id, type, status, result, created_at
  knowledge: id, content, embedding, source
```

## 外部依赖

| 依赖 | 用途 | 相关 Feature |
|------|------|-------------|
| agency-agents-main | Agent框架参考 | F-001, F-003 |
| social-auto-upload | 社媒自动发布 | F-004, F-005 |
| Hermes Agent | 核心对话引擎 | F-001 |
| 30+ MCP Servers | 工具执行 | F-017 |
| ComfyUI | 图片生成 | F-009 |
| Edge TTS | 语音合成 | F-009 |

## 页面状态总览

| 类型 | 数量 | 说明 |
|------|------|------|
| 已实现(有真实功能) | 6 | SuperAgent / Dashboard / DigitalHuman / Settings / ContentProduction / AssetManagement |
| 占位(Placeholder组件) | 23 | 其余23个二级页面 |
| 超额完成 | 1 | AIMarket.tsx (含SSE聊天+155专家市场) |

## Feature 编号规则

- F-001 ~ F-023: 前端+后端功能
- TaskDecomposer 扫描 `## feature: F-XXX` 段落
- AC 格式: `- [ ] AC-X: 描述` (Default-FAIL)
- 每个 feature 包含: purpose / relevant_files / depends_on / acceptance

---

## feature: F-001 超级员工SSE对话测试与修复

### purpose
验证SSE对话全链路：文本消息→流式Markdown→工具调用卡片→对话保存→历史加载。修复发现的问题，确保核心体验稳定。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/SuperAgent.tsx
- szyg-frontend/src/components/superagent/ChatMessageView.tsx
- szyg-frontend/src/components/superagent/ConversationPanel.tsx
- szyg-frontend/src/components/superagent/WelcomeState.tsx
- server/szyg/brain_hermes.py
- server/szyg/api/hermes_chat.py

### acceptance
- [ ] AC-1: 发送纯文本→SSE流式返回→Markdown正确渲染→光标闪烁→done后光标消失
- [ ] AC-2: 工具调用→tool_call卡片(running)→tool_result卡片(success绿/error红)→无JSON泄露
- [ ] AC-3: 图片生成→image卡片→点击Lightbox全屏查看
- [ ] AC-4: 视频生成→video_task进度→video_status更新→video播放器+放大/全屏/下载
- [ ] AC-5: 流结束后对话自动保存→左侧面板刷新→切换对话正确加载混合消息类型
- [ ] AC-6: 空消息/超长消息/断网/401重试→前端优雅处理

---

## feature: F-002 对话历史CRUD测试与修复

### purpose
验证对话管理全功能：新建/选择/重命名/置顶/导出Markdown/删除+确认。

### depends_on
- feature: F-001

### relevant_files
- szyg-frontend/src/components/superagent/ConversationPanel.tsx
- server/szyg/api/conversation_routes.py

### acceptance
- [ ] AC-1: 点击+新建→欢迎页→发送消息→自动创建对话(标题=首条消息截断50字)
- [ ] AC-2: 右键重命名→输入框预填→空标题校验→列表刷新
- [ ] AC-3: 右键置顶→pin图标出现→置顶对话排最前→取消置顶→恢复排序
- [ ] AC-4: 右键导出→浏览器下载.md→含标题/导出时间/消息数/用户-助手交替
- [ ] AC-5: 右键删除→确认弹窗→删除后列表刷新→删除当前对话→清空消息区

---

## feature: F-003 AI视频工作台

### purpose
实现AI视频工作台完整三栏布局：左工具箱→中预览+对话→右视频库。包含AI生视频弹窗、本地上传、7个剪辑工具、操作链、模板系统、发布面板。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/ai-staff/AIVideo.tsx (重写)
- szyg-frontend/src/components/video/VideoStatusHeader.tsx
- szyg-frontend/src/components/video/VideoPipeline.tsx
- szyg-frontend/src/components/video/VideoPreview.tsx
- szyg-frontend/src/components/video/VideoToolbox.tsx
- szyg-frontend/src/components/video/CreateDialog.tsx
- szyg-frontend/src/components/video/VideoLibrary.tsx
- szyg-frontend/src/components/video/TemplateSelector.tsx
- szyg-frontend/src/components/video/PublishPanel.tsx
- szyg-frontend/src/lib/api.ts
- server/szyg/api/video_endpoint.py

### acceptance
- [ ] AC-1: AI生视频弹窗：输入描述→选风格/时长→提交→流水线出现→4段节点依次完成→播放器出现
- [ ] AC-2: 剪辑操作：裁剪/拼接/变速/标题/混音/封面提取每个工具可独立使用并预览结果
- [ ] AC-3: 操作链：多步操作排队→一次性提交→预览最终结果
- [ ] AC-4: 模板：选择模板→填参数→渲染→预览
- [ ] AC-5: 视频库：AI生成+上传视频在缩略图网格展示·可预览/下载/删除
- [ ] AC-6: 发布：选择平台→填标题标签→即时/定时发送→返回post_id
- [ ] AC-7: 进度桶动画：Processing波纹脉冲+Complete弹性✅+连线渐变色+百分比闪烁
- [ ] AC-8: 深色科技主题+4断点响应式·npm run build通过

---

## feature: F-004 发布中心

### purpose
实现多平台发布中心：5平台状态总览→选择平台→填写内容→发布→查看结果。支持视频发布+图文发布+定时发布+多平台一键发布。

### depends_on
- F-001

### relevant_files
- szyg-frontend/src/pages/publish/PublishCenter.tsx (重写)
- szyg-frontend/src/components/publish/ (新建)
- server/szyg/api/publisher_routes.py
- server/szyg/publisher.py

### acceptance
- [ ] AC-1: 页面展示5平台卡片(抖音/小红书/B站/快手/微信)含登录状态+已发数量
- [ ] AC-2: 视频发布：选择平台→填标题+标签+描述+选视频文件→发布→显示结果(post_id)
- [ ] AC-3: 图文发布：选择平台→填标题+正文+选图片(最多9张)→发布
- [ ] AC-4: 定时发布：选择日期时间→提交→后端调度器接管
- [ ] AC-5: 多平台发布：勾选多个平台→一键发布→逐个报告成功/失败

---

## feature: F-005 平台账号管理

### purpose
实现平台账号管理页面：5平台登录状态可视化列表、扫码登录操作、Cookie状态、登出操作。

### depends_on
- feature: F-004

### relevant_files
- szyg-frontend/src/pages/publish/Accounts.tsx (重写)
- server/szyg/api/platform_routes.py

### acceptance
- [ ] AC-1: 5平台列表各显示：平台名+登录状态(已登录/未登录/异常)+账号名+Cookie有效期
- [ ] AC-2: 点击登录→触发后端扫码→浏览器打开登录页→用户扫码→状态更新为已登录
- [ ] AC-3: 点击登出→清空Cookie→状态更新为未登录
- [ ] AC-4: 微信显示需桌面客户端提示(如未运行)

---

## feature: F-006 智能截流

### purpose
实现智能截流配置页面：搜索目标视频→筛选→配置截流策略→执行评论/私信→查看效果。后端引擎已就绪，前端需UI对接。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/marketing/Intercept.tsx (重写)
- szyg-frontend/src/components/marketing/ (新建)
- server/szyg/api/acquisition_routes.py
- server/szyg/intercept_engine.py

### acceptance
- [ ] AC-1: 搜索栏：关键词输入+平台选择→搜索→展示视频列表(标题/作者/互动数据/封面)
- [ ] AC-2: 策略配置：选择目标视频→设置评论模板(含变量{昵称}{产品})→预览
- [ ] AC-3: 执行截流：单条/批量发送评论→返回执行结果(成功数/失败数/失败原因)
- [ ] AC-4: 效果查看：截流后数据(评论数/回复数/私信数/转化线索)

---

## feature: F-007 舆情监听

### purpose
实现舆情监听页面：配置关键词→监听结果实时流→预警通知。后端引擎已就绪，前端需UI对接。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/marketing/Listen.tsx (重写)
- server/szyg/listen_engine.py
- server/szyg/api/acquisition_routes.py

### acceptance
- [ ] AC-1: 关键词管理：添加/删除关键词组、支持正则、设置平台范围
- [ ] AC-2: 监听结果流：时间线展示匹配到的内容(来源/时间/摘要/链接)
- [ ] AC-3: 预警：设置阈值→触发时前端Toast+可选邮件通知

---

## feature: F-008 客户转化+客户资产

### purpose
实现客户转化管理+客户资产页面。转化漏斗可视化+自动回复规则+客户列表+标签管理+互动时间线。

### depends_on
- feature: F-006

### relevant_files
- szyg-frontend/src/pages/marketing/Conversion.tsx (重写)
- szyg-frontend/src/pages/marketing/Customers.tsx (重写)
- server/szyg/convert_engine.py

### acceptance
- [ ] AC-1: 转化漏斗可视化(展示截流→评论→私信→成交各阶段数量)
- [ ] AC-2: 自动回复规则配置(关键词匹配→模板回复)
- [ ] AC-3: 客户列表：姓名/来源平台/标签/最近互动时间
- [ ] AC-4: 客户详情：互动时间线(评论/私信/备注)
- [ ] AC-5: 标签管理：创建/删除/批量打标签

---

## feature: F-009 内容生产+素材管理

### purpose
实现AI内容生产页面(AIGC入口：文生图/文生视频/文案/语音)+素材管理页面(上传/分类/搜索/删除)。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/content/ContentProduction.tsx (重写)
- szyg-frontend/src/pages/content/AssetManagement.tsx (重写)
- server/szyg/api/image_endpoint.py
- server/szyg/pipeline_engine.py

### acceptance
- [x] AC-1: 文生图：输入描述→选风格/分辨率→生成→图片卡片展示→下载
- [x] AC-2: 文生视频：输入描述→选时长→异步生成→进度→播放器
- [x] AC-3: 文案生成：输入需求→5条文案输出→可编辑/复制
- [x] AC-4: 语音合成：输入文本→选声音/语速/情感→生成→播放试听
- [x] AC-5: 素材管理：上传/拖拽文件→网格展示→搜索→筛选→删除

---

## feature: F-010 内容日历

### purpose
实现可视化内容日历：日历视图+发布计划编排+拖拽调整日期。

### depends_on
- feature: F-004

### relevant_files
- szyg-frontend/src/pages/publish/ContentCalendar.tsx (重写)

### acceptance
- [ ] AC-1: 月视图日历：已排期内容按日期展示(标题+平台+缩略图)
- [ ] AC-2: 拖拽内容到新日期→更新发布时间

---

## feature: F-011 岗位型预置管线

### purpose
提供面向岗位和业务场景的预置自动化管线。用户不需要拖拽节点或设计流程，只需选择场景、配置账号/素材/频率/目标，由系统按内置业务管线完成内容发布、账号巡检、客户跟进、线索整理等高频任务。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/workflow/Pipeline.tsx
- server/szyg/pipeline_engine.py

### acceptance
- [ ] AC-1: 提供预置管线列表，覆盖内容发布、账号巡检、客户跟进、线索整理等核心岗位场景。
- [ ] AC-2: 用户可为管线配置账号、素材、执行频率、目标平台和人工接管策略。
- [ ] AC-3: 管线启动后进入统一任务看板，展示执行状态、执行结果、失败原因和需人工处理事项。
- [ ] AC-4: 管线内部复用统一执行内核，不另建一套孤立的任务状态系统。
- [ ] AC-5: 前端不提供通用拖拽节点画布，产品表达以“岗位任务”“自动化方案”“SOP模板”为主。

---

## feature: F-012 调度引擎UI

### purpose
实现调度引擎UI：定时任务管理、任务队列状态、执行日志。后端scheduler_engine已就绪。

### depends_on
- feature: F-011

### relevant_files
- szyg-frontend/src/pages/workflow/Scheduler.tsx (重写)
- server/szyg/scheduler_engine.py
- server/szyg/api/scheduler_routes.py

### acceptance
- [ ] AC-1: 定时任务管理：Cron+自然语言+日历选择→创建/编辑/删除任务
- [ ] AC-2: 任务队列：待执行/执行中/已完成/失败四个状态+暂停/恢复/取消操作
- [ ] AC-3: 执行日志：每次触发的时间/结果/耗时

---

## feature: F-013 SOP管理

### purpose
实现SOP管理页面：SOP模板库+执行记录。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/workflow/Sop.tsx (重写)

### acceptance
- [ ] AC-1: SOP模板库：按分类显示+搜索+详情
- [ ] AC-2: SOP执行记录：历史执行时间线+结果

---

## feature: F-014 运营仪表盘数据验证

### purpose
验证Dashboard后端API返回真实数据，确保不依赖mock。Dashboard UI已实现。

### depends_on
- F-001

### relevant_files
- szyg-frontend/src/pages/Dashboard.tsx (已有·验证)
- server/szyg/api/dashboard_routes.py

### acceptance
- [ ] AC-1: 4个KPI卡片显示真实后端数据(数字员工数/今日交互/成功率/任务队列)
- [ ] AC-2: 交互趋势图(Recharts AreaChart)显示7D/30D/90D真实数据
- [ ] AC-3: 实时动态流展示最近5条系统事件
- [ ] AC-4: 数字员工分布环形图显示真实分类统计

---

## feature: F-015 内容+获客分析

### purpose
实现内容分析+获客分析页面：内容表现排名、最佳发布时间、标签效果、截流效果、转化归因。

### depends_on
- feature: F-014

### relevant_files
- szyg-frontend/src/pages/insights/ContentAnalytics.tsx (重写)
- szyg-frontend/src/pages/insights/AcquisitionAnalytics.tsx (重写)

### acceptance
- [ ] AC-1: 内容分析：内容表现排名、最佳发布时间热力图、标签效果分析
- [ ] AC-2: 获客分析：截流效果(评论转化率)、客户来源归因

---

## feature: F-016 知识库·知识管理+记忆

### purpose
实现知识管理+长期记忆页面：文档上传→向量化→RAG检索，Agent对话记忆管理。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/knowledge/KnowledgeBase.tsx (重写)
- szyg-frontend/src/pages/knowledge/Memory.tsx (重写)
- server/szyg/agent_core/knowledge.py
- server/szyg/api/memory_routes.py

### acceptance
- [ ] AC-1: 知识管理：文档上传(.txt/.md/.pdf)→解析分块→向量化存入SQLite
- [ ] AC-2: RAG检索：输入问题→检索相关分块→展示结果+相似度
- [ ] AC-3: 长期记忆：Agent对话记忆管理→搜索→删除

---

## feature: F-017 知识库·技能市场+商学院

### purpose
实现技能市场MCP工具管理+商学院教程系统。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/knowledge/Skills.tsx (重写)
- szyg-frontend/src/pages/knowledge/Academy.tsx (重写)
- server/szyg/api/skills_routes.py

### acceptance
- [ ] AC-1: 技能市场：MCP工具列表(名称/描述/参数/状态)→启用/禁用→参数配置
- [ ] AC-2: 商学院：教程列表(分类)+详情(Markdown)+搜索

---

## feature: F-018 系统设置·风控+工具

### purpose
实现风控设置(频率限制/屏蔽词/IP黑名单)+工具管理(工具列表/状态/调用统计)。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/settings/RiskControl.tsx (重写)
- szyg-frontend/src/pages/settings/Tools.tsx (重写)
- server/szyg/api/risk_control_routes.py
- server/szyg/api/tools_routes.py

### acceptance
- [ ] AC-1: 风控：频率限制(每分钟/每小时/每天)+屏蔽词管理+IP黑名单
- [ ] AC-2: 工具管理：工具列表→状态→调用统计→启用/禁用

---

## feature: F-019 系统设置·团队+品牌+计费

### purpose
实现团队管理(成员/角色)+品牌配置(Logo/主色/OEM)+计费(用量/套餐)。

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/settings/Team.tsx (重写)
- szyg-frontend/src/pages/settings/Brand.tsx (重写)
- szyg-frontend/src/pages/settings/Billing.tsx (重写)

### acceptance
- [ ] AC-1: 团队：成员列表→添加/删除→角色(admin/user)→搜索
- [ ] AC-2: 品牌：Logo上传+品牌名+主色配置→OEM预览
- [ ] AC-3: 计费：用量统计(API调用/存储/发布次数)→套餐管理

---

## feature: F-020 后端核心引擎单元测试

### purpose
为szyg后端核心引擎补全测试：brain_hermes, publisher, scheduler_engine, video_cut_engine, intercept_engine, listen_engine, convert_engine。使用pytest+Mock，不依赖外部API。

### depends_on
无

### relevant_files
- server/szyg/brain_hermes.py → tests/test_hermes.py
- server/szyg/publisher.py → tests/test_publisher.py
- server/szyg/scheduler_engine.py → tests/test_scheduler.py
- server/szyg/video_cut_engine.py → tests/test_video_cut.py
- server/szyg/intercept_engine.py → tests/test_intercept.py
- server/szyg/listen_engine.py → tests/test_listen.py
- server/szyg/convert_engine.py → tests/test_convert.py

### acceptance
- [ ] AC-1: brain_hermes: 测试 _build_system_prompt 默认/激活专家两种路径
- [ ] AC-2: publisher: 测试 publish_direct入参校验、platform_status返回结构
- [ ] AC-3: scheduler: 测试任务CRUD+定时触发+异常重试
- [ ] AC-4: video_cut: 测试cut/concat/speed/title/mix_audio 参数校验+输出路径
- [ ] AC-5: 全体通过 `uv run pytest tests/ -v`

---

## feature: F-021 任务看板

### purpose
实现任务看板：执行中任务列表(进度/状态/起止时间)+任务历史+简单统计。

### depends_on
- F-001

### relevant_files
- szyg-frontend/src/pages/ai-staff/TaskBoard.tsx (重写)
- server/szyg/api/scheduler_routes.py

### acceptance
- [ ] AC-1: 执行中任务列表(进度/状态/起止时间)+任务历史+简单统计
- [ ] AC-2: 任务详情：创建时间/执行时长/结果摘要/日志
- [ ] AC-3: 操作：暂停/恢复/重试/取消

---

## feature: F-022 错误处理统一

### purpose
统一所有API的错误码格式 {code, message, detail}，前端统一错误展示组件。

### depends_on
- F-001

### relevant_files
- server/szyg/api/ (所有路由模块)
- szyg-frontend/src/lib/api.ts
- szyg-frontend/src/components/ (新建ErrorToast组件)

### acceptance
- [ ] AC-1: 后端所有API返回统一错误格式 {code, message, detail}
- [ ] AC-2: 前端统一错误展示组件（Toast/弹窗/页面内）
- [ ] AC-3: 401/403/500分别有对应处理逻辑

---

## feature: F-023 自动化执行稳定性底座 v1

### purpose
建立对标炼刀AI自动化水平的统一执行内核。第一阶段不重写现有抖音/小红书发布链路，继续保留 Playwright / social-auto-upload / 平台适配器能力，但将每次自动化任务包装为可观测、可暂停、可回放、可人工接管的 ExecutionRun。

### depends_on
- F-004
- F-005
- F-011
- F-018
- F-021

### relevant_files
- server/szyg/publisher.py
- server/szyg/platforms/base.py
- server/szyg/platforms/douyin.py
- server/szyg/platforms/xiaohongshu.py
- server/szyg/platforms/wechat_desktop.py
- server/szyg/integrations/social_auto_upload_adapter.py
- server/szyg/integrations/sau_task_manager.py
- server/szyg/pipeline_engine.py
- server/szyg/scheduler_engine.py
- server/szyg/vision_grounding.py
- server/szyg/api/platform_routes.py
- server/szyg/api/task_routes.py
- szyg-frontend/src/pages/ai-staff/TaskBoard.tsx
- szyg-frontend/src/pages/publish/PlatformWorkspace.tsx
- szyg-frontend/src/lib/api.ts

### architecture
统一执行内核新增概念：
- ExecutionRun：一次完整自动化任务，例如“发布一条抖音视频”。
- ExecutionStep：任务中的关键步骤，例如预检、打开发布页、上传视频、填写标题、点击发布、校验结果。
- Executor：动作执行通道，分为 BrowserExecutor / DesktopExecutor / MobileExecutor / ApiExecutor。
- Observation：执行前后观察结果，包括截图、OCR、DOM摘要、UI元素、页面/应用状态。
- Assertion：后置断言，例如“上传入口存在”“已进入发布页”“未出现登录弹窗”“发布成功”。
- RecoveryPolicy：失败后的处理策略，包括重试、暂停、熔断、转人工。
- AuditEvent：可审计日志，包括动作、输入摘要、结果、错误、截图路径、耗时。

第一阶段接入范围：
- 抖音发布流程作为试点。
- 小红书发布流程可复用同一数据模型，但不强制一次性完成全部细节。
- 微信桌面版保留 DesktopExecutor 方向，不强制改造现有 UIA 实现。
- MobileExecutor 仅定义接口与任务状态，不要求第一阶段真实接入手机。

### acceptance
- [ ] AC-1: 每次抖音发布任务都会创建一个 ExecutionRun，状态至少支持 queued / running / success / failed / paused / needs_human。
- [ ] AC-2: 每个关键动作都会创建 ExecutionStep，记录 step_id、name、executor_type、status、started_at、finished_at、duration_ms。
- [ ] AC-3: 每个关键步骤至少记录一条 AuditEvent，包含动作描述、结果、错误信息、截图路径或可解释观察结果。
- [ ] AC-4: 登录失效、验证码、账号异常、未知弹窗、上传失败、发布超时必须被分类为明确 error_code。
- [ ] AC-5: 出现验证码、账号异常、未知页面时，任务必须进入 needs_human，不允许继续点击发布或发送。
- [ ] AC-6: 连续失败达到阈值后自动暂停任务，并在任务看板展示“需人工处理”。
- [ ] AC-7: 任务看板详情页能展示步骤时间线、每步状态、错误原因、截图/调试证据入口。
- [ ] AC-8: 现有抖音发布入口、social-auto-upload 异步任务入口、平台账号状态接口保持兼容。
- [ ] AC-9: 设计中必须保留 BrowserExecutor / DesktopExecutor / MobileExecutor / ApiExecutor 四类执行器扩展点。
- [ ] AC-10: 至少提供一个抖音发布稳定性验收脚本或测试清单：同一类素材连续执行20次，统计成功率、失败分类、平均耗时、人工接管次数。

---

## 依赖拓扑图

```
Layer 0 (无依赖·最高优先级·可并行):
  F-001 超级员工SSE对话    ← 核心·立即
  F-020 后端测试补全        ← 核心·立即
  F-003 AI视频工作台        ← 无依赖·P0
  F-006 智能截流            ← 无依赖
  F-007 舆情监听            ← 无依赖
  F-009 内容生产+素材       ← 无依赖
  F-011 岗位型预置管线      ← 无依赖
  F-013 SOP管理             ← 无依赖
  F-016 知识库·知识+记忆    ← 无依赖
  F-017 知识库·技能+学院    ← 无依赖
  F-018 风控+工具           ← 无依赖
  F-019 团队+品牌+计费     ← 无依赖

Layer 1 (依赖F-001):
  F-002 对话历史CRUD        ← depends: F-001
  F-004 发布中心            ← depends: F-001
  F-014 运营仪表盘数据      ← depends: F-001
  F-021 任务看板            ← depends: F-001
  F-022 错误处理统一        ← depends: F-001

Layer 2 (依赖Layer 1):
  F-005 平台账号管理        ← depends: F-004
  F-008 客户转化+资产       ← depends: F-006
  F-010 内容日历            ← depends: F-004
  F-012 调度引擎UI          ← depends: F-011
  F-015 内容+获客分析       ← depends: F-014

Layer 3 (自动化稳定性闭环):
  F-023 自动化执行稳定性底座 ← depends: F-004, F-005, F-011, F-018, F-021
```

## 施工路线图

```
Phase 1 ─ 立即执行 (P0·核心)
  F-001 超级员工SSE对话测试与修复
  F-020 后端核心引擎单元测试
  F-003 AI视频工作台

Phase 2 ─ 本轮施工 (P1·主要功能)
  F-004 发布中心
  F-005 平台账号管理
  F-006 智能截流
  F-007 舆情监听
  F-009 内容生产+素材管理
  F-018 风控+工具管理

Phase 3 ─ 本轮施工 (P1·辅助)
  F-002 对话历史CRUD
  F-014 运营仪表盘数据验证
  F-011 岗位型预置管线
  F-021 任务看板
  F-022 错误处理统一

Phase 4 ─ 自动化稳定性核心 (P0/P1交界·对标炼刀AI)
  F-023 自动化执行稳定性底座 v1

Phase 5 ─ 后续 (P2·完善)
  F-008 客户转化+资产
  F-010 内容日历
  F-012 调度引擎UI
  F-013 SOP管理
  F-015 内容+获客分析
  F-016 知识库·知识+记忆
  F-017 知识库·技能+学院
  F-019 团队+品牌+计费

总计: 23 Features · 107 AC · 30页面 · 7个后端测试文件
```

## 已完成的Feature (不重复施工)

```
F-000-A 前端路由骨架: 9一级+30二级全部就绪, 45条重定向
F-000-B 侧边栏+导航: 9分组可展开, navConfig真理源
F-000-C AI人才市场: AIMarket.tsx 含SSE聊天+155专家
F-000-D 设计系统迁移: 深色科技主题统一
F-000-E LayoutContext: 折叠状态共享, TopBar/Content同步
```

---

> 此文档由Architect_Agent聚合KnowledgeBase自动生成。
> TaskDecomposer将扫描 `## feature: F-XXX` 段落生成TaskPackage队列。
> 施工队长将在每次施工前据此创建TaskPackage。
