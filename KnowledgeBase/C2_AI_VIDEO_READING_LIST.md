# 📖 AI视频工作台 — 编码Agent阅读清单 (C2)

> 目标：将 `/ai-staff/video` 从占位页面实现为完整AI视频工作站
> 前置：C1 AI人才市场已完成

---

## 📋 必读文档 (按顺序)

### 第一层：理解系统上下文

| # | 文档 | 阅读重点 |
|---|------|----------|
| 1 | `KnowledgeBase\CURRENT_GOALS.md` | 当前Phase 1阶段、C2在批次中的位置、验收标准 |
| 2 | `KnowledgeBase\ARCHITECTURE\module-tree.md` | AI员工→AI视频 在模块树中的定位，路由 `/ai-staff/video` |
| 3 | `KnowledgeBase\ARCHITECTURE\frontend-structure.md` | React项目结构、LayoutContext、navConfig共用方式 |

### 第二层：页面设计规范 (核心)

| # | 文档 | 阅读重点 |
|---|------|----------|
| 4 | `KnowledgeBase\ARCHITECTURE\specs\ai-video-page.md` | **完整页面功能设计**：三栏布局、工具箱、预览区、视频库、模板系统、状态机、15项验收标准 |

### 第三层：前端设计系统与参考模式

| # | 文档/文件 | 阅读重点 |
|---|-----------|----------|
| 5 | `szyg-frontend\DESIGN_SYSTEM.md` | 深色科技主题Token：色板 (#0B0F1A #111827 #6366F1)、字体、间距、圆角、动效、组件规范 |
| 6 | `szyg-frontend\src\lib\layout.tsx` | LayoutContext用法、`useLayout()` hook、Sidebar宽度常量 |
| 7 | `szyg-frontend\src\lib\navConfig.ts` | 路由注册方式、NavGroup/NavChild接口 |

### 第四层：进度桶-流水线 参考实现

| # | 文件 | 阅读重点 |
|---|------|----------|
| 8 | `frontend_refer\app\src\pages\Processing.tsx` | 完整Processing页面结构：StatusHeader→AgentNode流水线→AgentDetail→OutputCards |
| 9 | `frontend_refer\app\src\components\processing\StatusHeader.tsx` | 进度头部：三灯旋转动画、百分比大字、五色渐变进度条、stepText |
| 10 | `frontend_refer\app\src\components\processing\AgentNode.tsx` | 圆形进度桶节点：100px圆、波纹脉冲环(scale+opacity交替)、Complete✅弹性动画、Processing浮动+发光 |
| 11 | `frontend_refer\app\src\components\processing\PipelineConnections.tsx` | SVG渐变色连线：已完成段彩色+未完成段灰色、cubic-bezier曲线 |
| 12 | `frontend_refer\app\src\components\processing\AgentDetail.tsx` | 当前阶段详情卡片：次级进度条+预计剩余时间 |

### 第五层：后端API与数据源

| # | 文档/文件 | 阅读重点 |
|---|-----------|----------|
| 13 | `server\szyg\brain_hermes.py` | Hermes对话引擎、SSE接口 /api/hermes/chat |
| 14 | `server\szyg\api\hermes_chat.py` | SSE事件类型(text/tool_call/tool_result/video_task/video_status/video)、_build_system_prompt入口 |
| 15 | `server\szyg\video_cut_engine.py` | 视频剪辑后端能力(video_info/cut/concat/speed/add_title/mix_audio/extract_frame/templates/render) |
| 16 | `KnowledgeBase\ARCHITECTURE\specs\chat-video-card.md` | 视频卡片渲染规范(进度卡片→播放器→Modal→下载)，前端已有参考实现 |

### 第六层：参考的现有前端代码

| # | 文件 | 参考价值 |
|---|------|----------|
| 17 | `szyg-frontend\src\pages\SuperAgent.tsx` | SSE流式对话实现、消息渲染、视频卡片处理、useState结构 |
| 18 | `szyg-frontend\src\components\superagent\ChatMessageView.tsx` | 消息气泡+工具调用卡片+图片/视频卡片渲染 |
| 19 | `szyg-frontend\src\pages\ai-staff\AIMarket.tsx` | 同目录下的二级页面实现模式：view切换、SSE对话集成、状态管理、API调用 |
| 20 | `szyg-frontend\src\lib\api.ts` | 可复用函数：`streamHermesChat(SSE)`、`apiGet/apiPost/apiDel`、`getErrorMessage` |
| 21 | `szyg-frontend\src\pages\ai-staff\AIVideo.tsx` | **当前占位文件**，将被替换为此处设计的完整页面 |

---

## ⚡ 关键实现要点

### 不需要从零构建的部分

- ❌ 不需要新建路由 — `/ai-staff/video` 已在 navConfig.ts 和 App.tsx 中注册
- ❌ 不需要新建布局 — 复用现有 Layout组件(自动获得Sidebar+TopBar)
- ❌ 不需要新建SSE客户端 — 复用 `streamHermesChat()` 函数
- ❌ 不需要新建视频播放器 — 参考 SuperAgent.tsx 中的视频卡片实现
- ❌ 不需要新建API — 后端Hermes工具链已就绪

### 需要新建的部分

- ✅ `VideoPipeline.tsx` — 4段进度桶+SVG连线组件 (参考 AgentNode+PipelineConnections)
- ✅ `VideoStatusHeader.tsx` — 进度头部组件 (参考 StatusHeader)
- ✅ `VideoPreview.tsx` — 预览区容器 (播放器/进度桶切换)
- ✅ `VideoToolbox.tsx` — 左栏工具箱 (AI生成+上传+剪辑+发布)
- ✅ `VideoLibrary.tsx` — 右栏视频库 (缩略图网格)
- ✅ `CreateDialog.tsx` — AI创作弹窗
- ✅ `PublishPanel.tsx` — 发布面板
- ✅ 重构 `AIVideo.tsx` — 主页面(三栏布局+状态机)

### 进度桶组件实现速查

```
动画Token (与DESIGN_SYSTEM一致):
  ease: [0.16, 1, 0.3, 1]  // cubic-bezier ← ease-out-expo

Processing脉冲环 (来自frontend_refer AgentNode.tsx):
  <motion.div 
    className="absolute inset-0 rounded-full border-[3px] border-[#6366F1]"
    initial={{ scale: 1, opacity: 0.6 }}
    animate={{ scale: 1.8, opacity: 0 }}
    transition={{ duration: 1.5, repeat: Infinity, ease: easeOut }}
  />

Complete✅动画:
  <motion.div
    initial={{ scale: 0, rotate: -180 }}
    animate={{ scale: 1, rotate: 0 }}
    transition={{ duration: 0.4, ease: [0.34, 1.56, 0.64, 1] }}
  >
    <CheckCircle2 className="w-8 h-8 text-[#10B981]" />
  </motion.div>

渐变进度条:
  background: linear-gradient(90deg, #8B5CF6, #3B82F6, #06B6D4, #F59E0B, #10B981)
  boxShadow: 0 0 12px rgba(99,102,241,0.4)
```

