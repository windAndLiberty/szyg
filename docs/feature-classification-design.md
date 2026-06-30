# szyg 功能分类与页面设计方案

> 基于后端已实现功能 + 数字员工实现期望 + 竞品研究（炼刀AI/AI超级员工/明德数创引擎），设计一级/二级功能分类及具体页面

---

## 竞品借鉴总结

| 借鉴来源 | 借鉴功能 | 对应页面 | 优先级 |
|----------|----------|----------|--------|
| 炼刀AI | 风控策略配置（行为模拟/限额/养号/内容安全） | SettingsRiskControl.vue | P0 |
| 炼刀AI | 异常处理可视化（自动重试/策略切换/人工接管） | SuperAgent 任务面板 | P0 |
| AI超级员工 | 数字人系统（形象克隆/声音克隆/视频合成） | DigitalHuman.vue | P1 |
| AI超级员工 | AI链接仿写（输入视频链接→ASR→仿写文案） | ContentStudio 新增Tab | P1 |
| AI超级员工 | 养号功能（模拟真人浏览/随机点赞评论） | AcquisitionStudio 新增Tab | P1 |
| AI超级员工 | 企业获客（企查查/天眼查/高德LBS） | EnterpriseAcquisition.vue | P2 |
| AI超级员工 | NFC到店引流 | NfcMarketing.vue | P2 |
| 明德数创引擎 | 算力计费系统（套餐/充值/消耗统计） | SettingsBilling.vue | P2 |
| 明德数创引擎 | 商学院/用户教育内容管理 | Academy.vue | P2 |

---

## 一级功能分类

```
1. AI员工
2. 内容工厂
3. 营销拓客
4. 工作流编排
5. 数据洞察
6. 知识库
```

---

## 1. AI员工

**定位**: 用户与系统的核心交互入口，通过自然语言对话调度所有系统能力

### 1.1 超级员工 (SuperAgent)

**页面**: `SuperAgent.vue` — 全屏对话式交互界面

**功能描述**: 整个页面直接与 Hermes 内核对话，用户通过自然语言发出指令，AI 自动拆解任务并调用所有系统功能（内容生产、发布、截流、获客、客服等）。支持文本和语音两种输入方式。

**后端对接**:
- `POST /api/hermes/chat` — SSE 流式对话，支持 80+ 工具调用
- 工具白名单包含全部系统功能：内容CRUD、平台发布、调度、截流、评论、监听、转化、AIGC、流水线等

**页面布局**:
- 左侧: 对话历史列表（按日期分组）
- 中间: 对话主区域（流式消息 + 工具调用过程可视化 + 中间结果展示）
- 底部: 输入框 + 语音按钮 + 快捷指令标签
- 右侧抽屉: 当前任务执行状态面板（展开查看工具调用链、参数、结果）

**核心交互**:
- 用户输入 "帮我搜索抖音上关于AI培训的视频，筛选前10条，生成评论并发送"
- AI 自动调用: `acquisition_search` → `acquisition_generate_comments` → `acquisition_deai` → `acquisition_preflight` → `acquisition_comment_send`
- 每一步执行过程实时展示在对话中

### 1.2 员工概览 (StaffOverview)

**页面**: `StaffOverview.vue` — 已有，需重构

**功能描述**: 数字员工状态看板，展示各岗位 AI 员工的运行状态、今日任务量、完成率

**后端对接**:
- `GET /api/agents/list` — 智能体列表
- `GET /api/scheduler/stats` — 调度统计

**页面布局**:
- 顶部: 岗位卡片行（内容运营、获客专员、客服专员、数据分析），显示运行状态和今日指标
- 下方: 最近任务执行记录列表

### 1.3 任务看板 (TaskBoard)

**页面**: `TaskBoard.vue` — 已有

**功能描述**: 看板视图展示所有进行中/待执行/已完成的任务

**后端对接**:
- `GET /api/scheduler/jobs` — 任务列表
- `POST /api/scheduler/jobs/:id/execute` — 手动执行
- `POST /api/scheduler/jobs/:id/pause` / `resume` — 暂停/恢复

### 1.4 员工配置 (AgentProfiles)

**页面**: `AgentProfiles.vue` — 已有

**功能描述**: 配置各岗位 AI 员工的模型、技能、行为策略

**后端对接**:
- `GET /api/agents/list` / `GET /api/agents/:id` — 智能体详情
- `GET /api/agents/categories` — 分类列表
- `GET /api/agents/tiers` — 层级列表

---

## 2. 内容工厂

**定位**: AI 驱动的内容生产线，从选题到成片的全链路自动化

### 2.1 内容生产 (ContentProduction)

**页面**: `ContentStudio.vue` — 已有，需增强

**功能描述**: 模板化内容生产向导，支持文案、脚本、标题、SEO描述的 AI 生成

**后端对接**:
- `POST /api/publisher/ai-generate` — AI 内容生成
- `POST /api/publisher/contents` — 内容创建
- `POST /api/hermes/chat` — 通过对话调用 AIGC 工具（ai_image_generate, ai_tts_advanced, ai_video_create）

**页面布局**:
- Tab 1 内容生产: 模板选择 → 选题 → 脚本 → AI生成 → 预览（已有）
- Tab 2 AI绘图: 文本描述 → 风格选择 → 图像生成 → 图集管理
- Tab 3 AI配音: 文本输入 → 音色选择 → TTS合成 → 音频预览
- Tab 4 AI视频: 主题输入 → 流水线自动生成（脚本+封面+视频+配音+合成）
- Tab 5 链接仿写: 视频链接输入 → ASR语音识别 → 文案理解 → AI仿写（借鉴AI超级员工）

### 2.2 视频剪辑 (VideoEditor)

**页面**: `VideoEditor.vue` — 新建

**功能描述**: 视频裁剪、拼接、变速、标题叠加、音频替换/混音、封面提取

**后端对接**:
- `POST /api/video/cut` — 裁剪
- `POST /api/video/concat` — 拼接
- `POST /api/video/speed` — 变速
- `POST /api/video/add-title` — 标题叠加
- `POST /api/video/replace-audio` — 音频替换
- `POST /api/video/mix-audio` — 音频混音
- `POST /api/video/extract-frame` — 封面提取
- `GET /api/video/templates` — 视频模板列表
- `GET /api/video/fonts` — 字体列表

**页面布局**:
- 左侧: 素材库（视频/音频/图片文件列表，支持上传）
- 中间: 时间轴预览区 + 操作按钮组
- 右侧: 参数面板（根据当前操作动态切换：裁剪时间范围、变速倍率、标题文字/字体/位置、音频文件选择等）
- 底部: 模板快捷应用栏

### 2.3 数字人 (DigitalHuman)

**页面**: `DigitalHuman.vue` — 新建（借鉴AI超级员工）

**功能描述**: 数字人形象克隆、声音克隆、数字人视频合成

**后端对接**:
- `POST /api/hermes/chat` (ai_tts_advanced) — TTS 声音合成/克隆
- `POST /api/hermes/chat` (ai_video_create) — AI 视频生成
- `POST /api/hermes/chat` (ai_image_generate) — 形象图片生成
- 火山引擎 `volcengine_client.py` — TTS+视频生成 API

**页面布局**:
- Tab 1 形象管理: 已克隆形象列表 + 上传新形象（视频上传→克隆处理）
- Tab 2 音色管理: 已克隆音色列表 + 上传新音色（音频上传→TTS克隆）
- Tab 3 视频合成: 选择形象 + 输入文案 → TTS合成 → 数字人视频合成（支持1+1模式和混合模式）
- Tab 4 作品列表: 已合成数字人视频列表 + 预览/下载

### 2.4 内容资产 (ContentAssets)

**页面**: `ContentAssets.vue` — 已有

**功能描述**: 管理所有已生成的内容（文案、图片、视频、音频），支持搜索、筛选、复用

**后端对接**:
- `GET /api/publisher/contents` — 内容列表
- `GET /api/publisher/contents/:id` — 内容详情
- `PUT /api/publisher/contents/:id` — 修改内容
- `DELETE /api/publisher/contents/:id` — 删除内容

### 2.5 多平台发布 (PublishCenter)

**页面**: `PublishCenter.vue` — 新建（从 OpsStudio 拆分）

**功能描述**: 内容审核 → 定时/即时发布 → 发布状态追踪 → 异常重试

**后端对接**:
- `POST /api/publisher/contents/:id/submit` — 提交审核
- `POST /api/publisher/contents/:id/approve` — 审批通过
- `POST /api/publisher/contents/:id/publish` — 立即发布
- `POST /api/publisher/contents/:id/schedule` — 定时发布
- `GET /api/platforms/:platform/status/:post_id` — 发布状态
- `GET /api/platforms/health/all` — 平台健康检查

**页面布局**:
- Tab 1 发布队列: 待审核 / 待发布 / 发布中 / 已发布 / 失败 五栏看板
- Tab 2 定时计划: 日历视图展示所有定时发布任务
- Tab 3 发布历史: 时间线列表，含平台、状态、截图、数据指标

---

## 3. 营销拓客

**定位**: 主动曝光 + 评论截流 + 获客转化，实现从流量到客户的全链路

### 3.1 智能截流 (InterceptStudio)

**页面**: `AcquisitionStudio.vue` — 已有，需增强

**功能描述**: 关键词搜索 → 质量评分 → AI评论生成 → DeAI去味 → 发前检查 → 批量发送

**后端对接**:
- `POST /api/acquisition/search/aggregate` — 多平台搜索 + 评分排序
- `POST /api/acquisition/intercept` — 一键截流流水线
- `POST /api/acquisition/comments/generate` — AI 生成评论
- `POST /api/acquisition/comments/deai` — DeAI 去AI味
- `POST /api/acquisition/comments/preflight` — 发前检查
- `POST /api/acquisition/comments/batch-send` — 批量发送
- `acq_search` / `acq_send_comment` / `acq_batch_send_comments` — 直接采集工具

**页面布局**:
- Tab 1 截流流水线: Step 1 搜索 → Step 2 筛选 → Step 3 生成 → Step 4 发送（已有）
- Tab 2 养号: 平台选择 + 账号选择 + 养号参数（浏览视频数、点赞概率、评论概率、停留时间）→ 启动养号（借鉴AI超级员工/炼刀AI）
- Tab 3 平台状态: 各平台在线/离线状态指示条 + 快速跳转登录

### 3.2 舆情监听 (ListenCenter)

**页面**: `ListenCenter.vue` — 新建（从 AcquisitionStudio 拆分）

**功能描述**: 监听竞品视频的新评论，自动识别高意向客户线索

**后端对接**:
- `GET /api/acquisition/monitor/list` — 监听目标列表
- `POST /api/acquisition/monitor/add` — 添加监听目标
- `POST /api/acquisition/monitor/start` — 启动监听引擎
- `POST /api/acquisition/monitor/stop` — 停止监听引擎
- `acq_get_comments` — 获取评论（采集适配器）

**页面布局**:
- 左侧: 监听目标列表（视频卡片，显示平台、标题、新评论数、线索数）
- 右侧: 选中目标的评论流（实时更新，情感标签 positive/negative/question/lead，线索高亮）
- 底部: 监听引擎状态栏（运行/停止、轮询间隔、已发现线索数）

### 3.3 客户转化 (ConversionStudio)

**页面**: `ConversionStudio.vue` — 已有，需增强

**功能描述**: 线索评分 → 自动回复 → 私信触达 → 转化漏斗

**后端对接**:
- `GET /api/acquisition/leads` — 线索列表（按等级/状态/平台过滤）
- `POST /api/acquisition/lead/score` — 线索评分
- `POST /api/acquisition/auto-reply` — AI 自动回复（支持 dry_run 预览）
- `GET /api/acquisition/leads/funnel` — 转化漏斗
- `acq_send_dm` — 发送私信（B站）

**页面布局**:
- Tab 1 线索列表: 按等级(A/B/C/D)分组的客户线索卡片，含评论内容、评分、来源平台
- Tab 2 自动回复: 评论列表 + AI生成的回复预览 + 发送/跳过操作
- Tab 3 转化漏斗: discovered → replied → dm_sent → responded → qualified → converted 各阶段转化率可视化

### 3.4 A/B测试 (ABTestCenter)

**页面**: `ABTestCenter.vue` — 新建

**功能描述**: 对比不同评论策略的发送效果，数据驱动优化

**后端对接**:
- `POST /api/acquisition/ab/start` — 启动 A/B 测试
- `GET /api/acquisition/ab/list` — 测试结果列表
- `GET /api/acquisition/stats` — 截流统计
- `GET /api/acquisition/strategy` — 策略参数
- `POST /api/acquisition/strategy/apply` — 应用策略

**页面布局**:
- 上方: 进行中的 A/B 测试卡片（策略A vs 策略B，实时对比发送量/回复率/转化率）
- 下方: 历史测试结果列表 + 策略参数配置面板

### 3.5 客户资产 (CustomerAssets)

**页面**: `CustomerAssets.vue` — 已有

**功能描述**: 管理所有客户线索、画像、跟进记录、标签

**后端对接**:
- `GET /api/acquisition/leads` — 线索列表
- 线索详情含: 评论历史、回复记录、转化阶段、评分、标签

### 3.6 企业获客 (EnterpriseAcquisition)

**页面**: `EnterpriseAcquisition.vue` — 新建P2（借鉴AI超级员工）

**功能描述**: 基于企查查/天眼查的企业信息查询获客 + 高德LBS地理位置获客

**后端对接**:
- 企查查/天眼查 API（需接入第三方API Key）
- 高德地图 API（LBS获客）

**页面布局**:
- Tab 1 企业查询: 关键词 + 省份/行业筛选 → 企业列表（含联系方式、经营范围）→ 批量导出
- Tab 2 LBS获客: 地图选点 + 行业关键词 → 周边商家列表 → 批量采集联系方式

### 3.7 到店引流 (NfcMarketing)

**页面**: `NfcMarketing.vue` — 新建P2（借鉴AI超级员工）

**功能描述**: NFC碰一碰到店引流，顾客碰卡自动跳转短视频发布页面

**后端对接**:
- 店铺信息管理 API（需新增）
- NFC卡片配置 API（需新增）

**页面布局**:
- Tab 1 店铺配置: 店铺名称/简介/宣传语/产品关键词
- Tab 2 NFC卡片: 卡片ID管理 + 链接生成 + 写入指引
- Tab 3 团购挂载: 抖音/美团团购链接配置

---

## 4. 工作流编排

**定位**: 将"剪辑→发布→曝光→获客→客服"串成可配置、可定时、可复用的数字员工工作流

### 4.1 流水线编排 (PipelineDesigner)

**页面**: `PipelineDesigner.vue` — 新建

**功能描述**: 可视化 DAG 流水线设计器，拖拽节点编排多模型 AIGC 流水线

**后端对接**:
- `GET /api/pipeline/list` — 流水线模板列表
- `GET /api/pipeline/:name` — 流水线详情
- `POST /api/pipeline/video-create` — AI短视频流水线
- `POST /api/pipeline/content-create` — 智能内容流水线
- `POST /api/pipeline/image-set` — AI图集流水线

**页面布局**:
- 左侧: 节点面板（文本/图像/视频/音频/技能 节点类型，拖拽到画布）
- 中间: 画布区域（节点连线、参数配置、拓扑排序预览）
- 右侧: 节点属性面板（模型选择、提示词模板、输入参数映射）
- 底部: 模板库（预设流水线模板一键加载）

### 4.2 调度引擎 (SchedulerEngine)

**页面**: `SchedulerEngine.vue` — 新建（从 OpsStudio 拆分）

**功能描述**: Cron任务管理、定时触发、执行历史、失败重试

**后端对接**:
- `GET /api/scheduler/jobs` — 任务列表
- `POST /api/scheduler/jobs` — 创建任务
- `PUT /api/scheduler/jobs/:id` — 更新任务
- `DELETE /api/scheduler/jobs/:id` — 删除任务
- `POST /api/scheduler/jobs/:id/execute` — 立即执行
- `POST /api/scheduler/jobs/:id/pause` / `resume` — 暂停/恢复
- `GET /api/scheduler/history` — 执行历史
- `GET /api/scheduler/stats` — 统计

**页面布局**:
- Tab 1 任务列表: 表格展示所有调度任务（名称、触发类型、Cron/间隔、下次执行、状态、操作）
- Tab 2 执行历史: 时间线展示历史执行记录（任务名、开始/结束时间、状态、输出、错误信息）
- Tab 3 统计面板: 任务总数、成功率、平均执行时长、失败趋势图

### 4.3 SOP管理 (SOPManager)

**页面**: `SOPManager.vue` — 新建

**功能描述**: 用户自定义标准操作流程模板，将常见工作流固化为可复用的 SOP

**后端对接**:
- `GET /api/hermes/chat` (sop_list) — SOP 列表
- `POST /api/hermes/chat` (sop_define) — 定义 SOP

**页面布局**:
- 左侧: SOP 列表（卡片式，显示名称、描述、步骤数）
- 右侧: SOP 编辑器（步骤列表，每步选择技能 + 配置参数，拖拽排序）
- 底部: 执行按钮（输入参数 → 按步骤依次执行 → 实时展示每步结果）

---

## 5. 数据洞察

**定位**: 全链路数据可视化，从内容生产到客户转化的量化分析

### 5.1 运营仪表盘 (Dashboard)

**页面**: `Dashboard.vue` — 已有，需增强

**功能描述**: 全局数据概览，一眼掌握系统运行状态

**后端对接**:
- `GET /api/scheduler/stats` — 调度统计
- `GET /api/publisher/stats` — 内容统计
- `GET /api/acquisition/stats` — 截流统计
- `GET /api/platforms/health/all` — 平台健康

**页面布局**:
- 顶部: 快捷指令输入区（已有，保留）
- 第一行: 核心指标卡片（今日发布数、截流评论数、新线索数、转化率）
- 第二行: 内容生产趋势图 + 截流效果趋势图
- 第三行: 平台健康状态 + 员工运行状态
- 第四行: 最近活动时间线

### 5.2 内容分析 (ContentAnalytics)

**页面**: `ContentAnalytics.vue` — 新建

**功能描述**: 内容生产效率、发布成功率、各平台内容表现分析

**后端对接**:
- `GET /api/publisher/stats` — 内容统计
- `GET /api/platforms/:platform/status/:post_id` — 发布后数据

**页面布局**:
- 内容生产统计: 按日/周/月的生产量趋势、内容类型分布
- 发布分析: 各平台发布成功率、平均审核时长、发布失败原因分布
- 内容表现: 已发布内容的播放/点赞/评论/分享数据汇总

### 5.3 截流效果 (AcquisitionAnalytics)

**页面**: `AcquisitionAnalytics.vue` — 新建

**功能描述**: 截流评论的发送量、回复率、线索转化率分析

**后端对接**:
- `GET /api/acquisition/stats` — 截流统计
- `GET /api/acquisition/leads/funnel` — 转化漏斗
- `GET /api/acquisition/ab/list` — A/B 测试结果

**页面布局**:
- 截流概览: 评论发送总量、平均回复率、线索发现数、客户转化数
- 趋势分析: 按日/周的评论发送量和回复率趋势
- 策略对比: A/B 测试结果可视化对比
- 平台分析: 各平台截流效果对比

### 5.4 客户转化分析 (ConversionAnalytics)

**页面**: `ConversionAnalytics.vue` — 新建

**功能描述**: 转化漏斗各阶段分析、线索等级分布、跟进效率

**后端对接**:
- `GET /api/acquisition/leads/funnel` — 转化漏斗
- `GET /api/acquisition/leads` — 线索列表（按等级/状态过滤）

**页面布局**:
- 转化漏斗: discovered → replied → dm_sent → responded → qualified → converted 漏斗图
- 线索分布: A/B/C/D 等级饼图 + 状态分布
- 跟进效率: 平均响应时长、首次回复率、二次回复率
- 平台对比: 各平台线索量和转化率

---

## 6. 知识库

**定位**: 企业知识管理 + RAG 检索 + 长期记忆，为 AI 员工提供专业知识背景

### 6.1 知识管理 (KnowledgeBase)

**页面**: `KnowledgeBase.vue` — 新建

**功能描述**: 文档摄入、分块管理、来源追踪、全文检索

**后端对接**:
- `POST /api/hermes/chat` (knowledge_ingest) — 文档摄入
- `POST /api/hermes/chat` (knowledge_search) — 知识搜索
- `POST /api/hermes/chat` (knowledge_stats) — 知识库统计

**页面布局**:
- Tab 1 知识列表: 已摄入文档列表（文件名、来源、分块数、摄入时间）
- Tab 2 文档摄入: 文件上传/拖拽区域 + 支持格式说明(txt/md/json/pdf/docx)
- Tab 3 知识搜索: 搜索框 + 结果列表（相关片段 + 来源文件 + 相似度评分）
- 侧边栏: 知识库统计（总文档数、总分块数、最近更新）

### 6.2 长期记忆 (MemoryCenter)

**页面**: `MemoryCenter.vue` — 新建

**功能描述**: AI 员工的长期记忆管理，支持查看、搜索、删除记忆条目

**后端对接**:
- 通过 `agent_core/memory.py` 的 Memory 类 (SQLite FTS5)
- 需新增 API: `GET /api/memory/list` / `GET /api/memory/search` / `DELETE /api/memory/:id`

**页面布局**:
- 上方: 搜索框 + 过滤器（按类型、时间范围）
- 主体: 记忆条目列表（内容摘要、创建时间、类型标签）
- 侧边栏: 记忆统计（总条目数、按类型分布、最近活跃度）

### 6.3 技能市场 (SkillMarket)

**页面**: `SettingsSkills.vue` — 已有，归入知识库分类

**功能描述**: 浏览、安装、管理 AI 技能插件

**后端对接**:
- `GET /api/tools/catalog` — 工具市场列表
- `GET /api/tools/categories` — 分类列表
- `GET /api/tools/installed` — 已安装工具
- `POST /api/hermes/chat` (skills_list) — 技能列表
- `POST /api/hermes/chat` (tool_install / tool_uninstall) — 安装/卸载

### 6.4 商学院 (Academy)

**页面**: `Academy.vue` — 新建P2（借鉴明德数创引擎）

**功能描述**: 用户教育内容管理，行业分析、营销技巧、引流策略、FAQ

**后端对接**:
- 需新增内容管理 API（CMS模块）

**页面布局**:
- Tab 1 行业分析: 行业分析文章列表 + 编辑
- Tab 2 营销技巧: 营销技巧文章列表 + 编辑
- Tab 3 引流策略: 引流策略文章列表 + 编辑
- Tab 4 一键解答: 常见问题FAQ管理

---

## 系统设置 (独立于6大分类)

### 平台账号 (SettingsPlatforms)
- 已有，管理各平台登录状态、Cookie、会话
- `GET /api/platforms` / `POST /api/platforms/:platform/login` / `GET /api/publisher/platforms/:platform/sessions`

### 风控策略 (SettingsRiskControl) — 新建P0（借鉴炼刀AI）
- 行为模拟配置: 随机间隔范围、鼠标轨迹随机度、浏览停留时间
- 限额控制: 每日发布上限、每日评论上限、每日私信上限、每日加人上限
- 养号策略: 养号时段、点赞概率、评论概率、浏览视频数
- 内容安全: 敏感词库管理、合规检查开关
- 需新增 API: `GET/PUT /api/risk-control/config`
- 后端: `anti_detect.py` 已有基础，需扩展配置化

### 系统配置 (SettingsSystem)
- 已有，模型配置、系统参数
- `GET /api/hermes/chat` (models_list / system_config)

### 品牌配置 (SettingsBrand)
- 已有，OEM 白标定制
- `GET /api/oem/config/default` / `POST /api/hermes/chat` (oem_config_update)

### 团队管理 (SettingsTeam)
- 已有，用户管理、权限控制
- `auth.py` JWT 认证 + RBAC

### 工具管理 (SettingsTools)
- 已有，本地工具运行时管理
- `tool_runtime.py` 插件安装/启动/停止

### 计费管理 (SettingsBilling) — 新建P2（借鉴明德数创引擎）
- 算力套餐管理: 套餐配置、权益配置
- 充值/消耗记录: 充值历史、算力消耗统计
- 会员管理: 会员等级、续费管理
- 支付集成: 微信支付/支付宝接入
- 需新增 API: `/api/billing/*`

---

## 路由结构总览

```
/ → Dashboard                    (数据洞察 > 运营仪表盘)

/ai-staff                        (AI员工)
  /super-agent                   → SuperAgent.vue (新建P0)
  /overview                      → StaffOverview.vue (已有)
  /tasks                         → TaskBoard.vue (已有)
  /profiles                      → AgentProfiles.vue (已有)

/content                         (内容工厂)
  /production                    → ContentStudio.vue (已有，增强)
  /video-editor                  → VideoEditor.vue (新建P1)
  /digital-human                 → DigitalHuman.vue (新建P1)
  /assets                        → ContentAssets.vue (已有)
  /publish                       → PublishCenter.vue (新建P1)

/marketing                       (营销拓客)
  /intercept                     → AcquisitionStudio.vue (已有，增强)
  /listen                        → ListenCenter.vue (新建P1)
  /conversion                    → ConversionStudio.vue (已有，增强)
  /ab-test                       → ABTestCenter.vue (新建P2)
  /customers                     → CustomerAssets.vue (已有)
  /enterprise                    → EnterpriseAcquisition.vue (新建P2)
  /nfc                           → NfcMarketing.vue (新建P2)

/workflow                        (工作流编排)
  /pipeline                      → PipelineDesigner.vue (新建P1)
  /scheduler                     → SchedulerEngine.vue (新建P2)
  /sop                           → SOPManager.vue (新建P2)

/insights                        (数据洞察)
  /dashboard                     → Dashboard.vue (已有，增强)
  /content-analytics             → ContentAnalytics.vue (新建P2)
  /acquisition-analytics         → AcquisitionAnalytics.vue (新建P2)
  /conversion-analytics          → ConversionAnalytics.vue (新建P2)

/knowledge                       (知识库)
  /base                          → KnowledgeBase.vue (新建P1)
  /memory                        → MemoryCenter.vue (新建P2)
  /skills                        → SettingsSkills.vue (已有)
  /academy                       → Academy.vue (新建P2)

/settings                        (系统设置)
  /platforms                     → SettingsPlatforms.vue (已有)
  /risk-control                  → SettingsRiskControl.vue (新建P0)
  /tools                         → SettingsTools.vue (已有)
  /system                        → SettingsSystem.vue (已有)
  /brand                         → SettingsBrand.vue (已有)
  /team                          → SettingsTeam.vue (已有)
  /billing                       → SettingsBilling.vue (新建P2)
```

---

## 页面与后端功能映射矩阵

| 后端模块 | 对应页面 | 状态 |
|----------|----------|------|
| Hermes Agent (hermes_chat.py) | SuperAgent | 新建 |
| 内容发布 (publisher.py) | ContentProduction, PublishCenter, ContentAssets | 已有+新建 |
| 平台适配器 (platforms/) | SettingsPlatforms | 已有 |
| 采集适配器 (acquisition_adapters.py) | InterceptStudio, ListenCenter | 已有+新建 |
| 截流引擎 (intercept_engine.py) | InterceptStudio | 已有 |
| 评论引擎 (comment_engine.py) | InterceptStudio | 已有 |
| 监听引擎 (listen_engine.py) | ListenCenter | 新建 |
| 转化引擎 (convert_engine.py) | ConversionStudio | 已有 |
| 调度引擎 (scheduler_engine.py) | SchedulerEngine, TaskBoard | 已有+新建 |
| 流水线引擎 (pipeline_engine.py) | PipelineDesigner | 新建 |
| 视频剪辑 (video_cut_engine.py) | VideoEditor | 新建 |
| 火山引擎 (volcengine_client.py) | ContentProduction, DigitalHuman | 已有+新建 |
| 知识库 (agent_core/knowledge.py) | KnowledgeBase | 新建 |
| 长期记忆 (agent_core/memory.py) | MemoryCenter | 新建 |
| SOP (agent_core/sop_manager.py) | SOPManager | 新建 |
| 技能注册 (agent_core/skill_registry.py) | SkillMarket | 已有 |
| 视觉定位 (vision_grounding.py) | (后端内部使用) | — |
| JWT认证 (auth.py) | Login, SettingsTeam | 已有 |
| 多租户 (tenant.py) | (中间件层) | — |
| 工具运行时 (tool_runtime.py) | SettingsTools | 已有 |
| OEM品牌 (oem_mcp.py) | SettingsBrand | 已有 |
| 反检测 (anti_detect.py) | SettingsRiskControl | 新建P0 |

---

## 新建页面清单

| 页面 | 一级分类 | 二级分类 | 优先级 | 复杂度 | 借鉴来源 |
|------|----------|----------|--------|--------|----------|
| SuperAgent.vue | AI员工 | 超级员工 | P0 | 高 | 炼刀AI |
| SettingsRiskControl.vue | 系统设置 | 风控策略 | P0 | 中 | 炼刀AI |
| VideoEditor.vue | 内容工厂 | 视频剪辑 | P1 | 中 | AI超级员工 |
| DigitalHuman.vue | 内容工厂 | 数字人 | P1 | 中 | AI超级员工 |
| PublishCenter.vue | 内容工厂 | 多平台发布 | P1 | 中 | — |
| ListenCenter.vue | 营销拓客 | 舆情监听 | P1 | 中 | — |
| PipelineDesigner.vue | 工作流编排 | 流水线编排 | P1 | 高 | — |
| KnowledgeBase.vue | 知识库 | 知识管理 | P1 | 中 | — |
| ABTestCenter.vue | 营销拓客 | A/B测试 | P2 | 低 | — |
| SchedulerEngine.vue | 工作流编排 | 调度引擎 | P2 | 低 | — |
| SOPManager.vue | 工作流编排 | SOP管理 | P2 | 中 | — |
| ContentAnalytics.vue | 数据洞察 | 内容分析 | P2 | 中 | — |
| AcquisitionAnalytics.vue | 数据洞察 | 截流效果 | P2 | 中 | — |
| ConversionAnalytics.vue | 数据洞察 | 转化分析 | P2 | 中 | — |
| MemoryCenter.vue | 知识库 | 长期记忆 | P2 | 低 | — |
| EnterpriseAcquisition.vue | 营销拓客 | 企业获客 | P2 | 中 | AI超级员工 |
| NfcMarketing.vue | 营销拓客 | 到店引流 | P2 | 中 | AI超级员工 |
| Academy.vue | 知识库 | 商学院 | P2 | 低 | 明德数创引擎 |
| SettingsBilling.vue | 系统设置 | 计费管理 | P2 | 中 | 明德数创引擎 |
