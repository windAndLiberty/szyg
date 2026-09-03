# 🎯 域灵系统 — 当前阶段目标 (Phase 1)

> 版本：v1.3
> 日期：2026-07-05
> 状态：C1 ✅ 中文修复完成 (超额交付) / C2-C5 ⏳
> 下一步：进入 P0 端到端测试 批次B

---

## 一、C1 中文修复 QA审阅

### 结论：✅ 通过 — 翻译覆盖率 ~90%，14个待补全

| 验收项 | v1.2状态 | v1.3结果 |
|--------|----------|----------|
| F1 专家名称翻译 | ❌ | ✅ ~140/155准确，「Douyin Strategist」→「抖音策略师」等 |
| F2 Division标签翻译 | ❌ | ✅ 11/11全中文：「营销增长」「付费投放」「创意设计」等 |
| F3 描述翻译 | ❌ | ✅ 300+词条关键词替换，英文描述转中文营销术语 |
| F4 空激活状态引导 | ❌ | ✅ 「💡 选择一位领域专家，让超级员工拥有专业技能」 |
| 构建通过 | — | ✅ npm run build (969KB JS) |

### 🆕 超额交付

编码Agent在修复中文问题的同时，为AI人才市场添加了**内置聊天系统**：

| 功能 | 说明 |
|------|------|
| 双视图切换 | 市场浏览(`market`) ↔ 专家对话(`chat`)，选择专家后自动切入对话 |
| SSE流式对话 | 集成`streamHermesChat`，与超级员工相同的实时流式体验 |
| 对话历史管理 | 创建/选择/删除对话，对话与专家绑定 |
| 专家信息栏 | 对话页顶部显示当前专家name/emoji/description/division标签 |
| 一键恢复 | 对话页顶部「恢复默认」按钮 + 市场页「恢复默认」横幅 |
| 长生命周期 | 对话持久化到`data/agency_conversations/`，刷新不丢失 |

### ⚠️ 翻译待补全项 (14个)

翻译覆盖约90%，以下专家名称仍含英文词需手动补入`_NAME_OVERRIDE`：
- `AEOFoundations` → 「AEO基础设施专家」
- `CarouselGrowthEngine` → 「轮播增长引擎师」
- `ChinaMarketLocalizationStrategist` → 「中国市场本地化策略师」
- `ShortVideoEditingCoach` → 「短视频剪辑教练」(当前已部分翻译)
- `GlobalPodcastStrategist` → 「全球播客策略师」
- `ChinaEcommerceOperator` → 「中国电商运营师」
- `CrossBorderEcommerce` → 「跨境电商专家」
- `VideoOptimizationSpecialist` → 「视频优化专家」
- `WeChatOfficialAccount` → 「微信公众号运营师」
- `MultiPlatformPublisher` → 「多平台发布师」
- `LivestreamCommerceCoach` → 「直播电商教练」
- `PrivateDomainOperator` → 「私域运营师」
- `TwitterEngager` / `XTwitterIntelligenceAnalyst` → 「Twitter运营师」/「X情报分析师」
- `BaiduSEOSpecialist` → 「百度SEO专家」

> 这些在`agency_routes.py`的`_ROLE_ZH`和`_NAME_OVERRIDE`中追加条目即可。

---

## 二、建议下一步：进入P0端到端测试

### 理由

1. C1+Agency+聊天系统依赖SSE基础设施，端到端测试可验证整条链路
2. SuperAgent.tsx 是用户高频入口，确保稳固有最高优先级
3. 4大已有页面(SuperAgent/Dashboard/DigitalHuman/Settings)已对接真实API，可通过

### 批次B — P0端到端测试

| B# | 测试链 | 链路覆盖 | 优先级 |
|-----|--------|----------|--------|
| **B1** 🔴 | SSE对话全链路 | 用户输入 → POST /api/hermes/chat → LLM推理 → 工具调用 → SSE事件(text/tool_call/tool_result) → 对话保存 → 历史加载 | 🔴 并行 |
| **B2** 🔴 | 对话历史CRUD | 新建/选择/重命名/置顶/导出Markdown/删除 → 侧边面板刷新 | 🔴 并行 |
| **B3** 🔴 | 多平台发布 | platform_status(5平台) → platform_login → platform_publish_direct → platform_post_status | 🔴 并行 |
| **B4** 🟡 | 视频生成+卡片 | ai_video_create → video_task卡片 → ai_video_task_status轮询 → video_status更新 → video播放器 | 🟡 |
| **B5** 🟡 | 视频剪辑 | video_info → video_cut/video_concat/video_add_title → 链式操作 | 🟡 |

### 测试策略

```
B1 SSE对话链路 (最高优先级):
  ├─ 纯文本消息 → 流式Markdown渲染 + 光标闪烁
  ├─ 工具调用 → tool_call卡片(running) → tool_result(success/error)
  ├─ 图片 → image_event → 图片卡片 → Lightbox
  ├─ 视频 → video_task → video_status → video播放器+放大/全屏/下载
  ├─ 对话保存 → 流结束后自动保存 → 历史面板刷新
  ├─ 对话切换 → 加载历史消息 → 渲染混合类型
  └─ 边界 → 网络断开(SSE重连)、空消息、超长消息、特殊字符
```

---

## 三、CURRENT_GOALS.md 版本历史

| 版本 | 更新内容 |
|------|----------|
| v1.0 | Phase 1批次A骨架任务定义 |
| v1.1 | QA审阅通过 ✅ + AI人才市场集成计划(155专家) |
| v1.2 | C1 QA阻塞发现(中文缺失) + 翻译方案设计 |
| v1.3 | C1中文修复完成 ✅ + 超额交付内置聊天 + 建议进入P0测试 |

---

## 四、关键文档速查

| 用途 | 文档 |
|------|------|
| 翻译对照表 | `server\szyg\api\agency_routes.py` (_ZH_MAP / _NAME_OVERRIDE / _DIVISION_CN) |
| AI人才市场(含聊天) | `szyg-frontend\src\pages\ai-staff\AIMarket.tsx` (585行) |
| 对话持久化 | `data\agency_conversations\` (新存储) |
| 激活状态 | `server\szyg\agency_state.py` + `data\agency_active.json` |

