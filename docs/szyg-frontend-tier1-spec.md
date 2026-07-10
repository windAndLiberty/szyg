# szyg 前端第一梯队 — 施工规格文档

> 施工队：Loop Agent v2 | 生成：2026-07-08
> 目标：4 个面向中小企业文员/老板的核心页面
> 设计原则：≤ 3 个核心操作 / 清晰数据反馈 / 一键执行 / 中文标签

---

## 通用设计约束（所有页面适用）

### 视觉规范
- 深色科技主题：背景 `#0B0F1A`，卡片 `linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)`
- 主色 `#6366F1`，成功 `#10B981`，失败 `#EF4444`，警告 `#F59E0B`
- 边框 `#1E293B`，文字主色 `#F1F5F9`，次要 `#94A3B8`
- 卡片圆角 12px，输入框圆角 10px
- 所有组件使用 Tailwind CSS，图标使用 lucide-react

### 交互规范
- 加载状态：骨架屏或 spinner（`#6366F1` 色）
- 空状态：图标 + "暂无数据" + 引导操作按钮
- 错误状态：红色提示 + 重试按钮
- 成功反馈：toast 通知（右上角滑入，3 秒消失）
- Hover：卡片边框变 `#334155`，阴影 `0 8px 24px rgba(0,0,0,0.3)`

### 组件复用
- 已有基础 UI 组件：`Button` / `Card` / `Input` / `Badge` / `Empty` / `Avatar` / `Switch` / `Label`
- 路径：`@/components/ui/`
- 已有布局组件：`Layout.tsx`（Sidebar + TopBar + Content + Footer）
- API 客户端：`@/lib/api.ts`（自动 JWT 鉴权 + 401 重试）

### 路由约定
- 所有新路由已在 `App.tsx` 中定义，使用现有 `<Route>` 路径
- 页面组件只需替换占位实现，路由不变

---

## feature: F-004 发布中心

### purpose
面向运营文员。上传视频/图片 → 写标题描述 → 勾选发布平台 → 一键发布。
后端对接 `publisher` 引擎和 `platforms/` RPA 适配器（抖音/快手/小红书/B站）。
核心价值：一个页面完成多平台发布，不需要打开 4 个 App。

### north_star
一句话指挥AI干活

### engine
claude-code

### depends_on
- feature: F-005 平台账号管理（发布前需确保账号已登录）

### relevant_files
- szyg-frontend/src/pages/publish/PublishCenter.tsx
- szyg-frontend/src/lib/api.ts
- server/szyg/publisher.py
- server/szyg/platforms/base.py
- szyg-frontend/src/components/ui/card.tsx
- szyg-frontend/src/components/ui/button.tsx
- szyg-frontend/src/components/ui/input.tsx
- szyg-frontend/src/components/ui/badge.tsx
- szyg-frontend/src/components/ui/empty.tsx
- szyg-frontend/DESIGN_SYSTEM.md

### acceptance
- [ ] AC-1: 上传区 — 点击或拖拽上传视频/图片文件，显示文件名、大小、时长。支持 MP4/MOV/JPG/PNG，最大 500MB。上传后显示缩略图预览
- [ ] AC-2: 文案区 — 标题输入框（必填，最多 100 字）+ 描述输入框（选填，最多 500 字）+ 字符计数显示
- [ ] AC-3: 平台选择 — 以开关/勾选框形式展示已登录平台（抖音/快手/小红书/B站），默认全选。未登录平台灰色不可选，提示"未登录"
- [ ] AC-4: 发布方式 — 单选：立即发布 / 定时发布。选定时发布时弹出日期时间选择器
- [ ] AC-5: 一键发布按钮 — 大按钮 `#6366F1`，点击后调用 `POST /api/publish`，按钮变为 loading 状态
- [ ] AC-6: 发布结果 — 下方列表展示最近 20 条发布记录。每条显示：平台图标+名称、状态徽章（成功绿/处理中黄/失败红）、发布时间、操作按钮（成功→查看链接，失败→查看原因+重试）
- [ ] AC-7: 空状态 — 无发布记录时显示 Send 图标 + "暂无发布记录，上传内容开始发布"
- [ ] AC-8: 错误处理 — 上传失败/发布失败显示红色 toast 提示错误原因，不崩溃
- [ ] AC-9: 响应式 — 移动端单列，桌面端上传区+文案区并排，发布记录全宽

---

## feature: F-005 平台账号管理

### purpose
面向老板/管理员。查看和管理所有已连接的社交媒体账号。
核心操作：添加账号（扫码/Cookie登录）、查看状态、重新登录。
后端对接 `platforms/` 模块（session_manager + registry）。

### north_star
一句话指挥AI干活

### engine
claude-code

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/publish/Accounts.tsx
- szyg-frontend/src/lib/api.ts
- server/szyg/platforms/registry.py
- server/szyg/platforms/session_manager.py
- server/szyg/platforms/douyin.py
- server/szyg/platforms/xiaohongshu.py
- szyg-frontend/src/components/ui/card.tsx
- szyg-frontend/src/components/ui/button.tsx
- szyg-frontend/src/components/ui/badge.tsx
- szyg-frontend/src/components/ui/empty.tsx
- szyg-frontend/DESIGN_SYSTEM.md

### acceptance
- [ ] AC-1: 顶部 [+ 添加账号] 按钮 → 弹出模态框，选择平台（抖音/快手/小红书/B站/微信）+ 登录方式（扫码/手机号/Cookie），触发后端登录流程
- [ ] AC-2: 账号卡片网格 — 每个平台一张卡片。卡片内容：平台图标（彩色）、账号昵称、粉丝数、状态指示灯（绿=在线/黄=登录中/红=过期/灰=未连接）
- [ ] AC-3: 在线账号卡片可点击 → 展开详情：最后登录时间、Cookie 有效期、最近发布统计（本周发布数/成功率）
- [ ] AC-4: 过期/离线账号卡片显示 [重新登录] 按钮 → 触发登录流程
- [ ] AC-5: 每张卡片右上角 [...] 菜单 → 删除账号（确认弹窗）
- [ ] AC-6: 空状态 — 无账号时显示 KeyRound 图标 + "暂无平台账号，点击上方按钮添加"
- [ ] AC-7: 后端调用 `GET /api/platforms` 获取账号列表，`POST /api/platforms/{name}/login` 触发登录
- [ ] AC-8: 错误处理 — 登录失败显示具体原因（如"扫码超时"、"Cookie 已失效"）
- [ ] AC-9: 响应式 — 移动端单列卡片，桌面端 2-3 列网格

---

## feature: F-006 智能截流

### purpose
面向运营/老板。配置截流关键词和评论话术 → AI 自动搜索目标视频 → 自动评论引流。
这是 szyg 对标炼刀 AI 的核心差异化功能。后端对接 `intercept_engine.py`。
核心价值：自动在同行视频评论区挖掘潜在客户，无需人工刷视频。

### north_star
一句话指挥AI干活

### engine
claude-code

### depends_on
- feature: F-005 平台账号管理（截流需要已登录的平台账号）

### relevant_files
- szyg-frontend/src/pages/marketing/Intercept.tsx
- szyg-frontend/src/lib/api.ts
- server/szyg/intercept_engine.py
- server/szyg/platforms/browser_pool.py
- server/szyg/platforms/anti_detect.py
- szyg-frontend/src/components/ui/card.tsx
- szyg-frontend/src/components/ui/button.tsx
- szyg-frontend/src/components/ui/input.tsx
- szyg-frontend/src/components/ui/badge.tsx
- szyg-frontend/src/components/ui/switch.tsx
- szyg-frontend/DESIGN_SYSTEM.md

### acceptance
- [ ] AC-1: 配置卡片 — 一个紧凑的卡片，三行配置：
  - 关键词标签输入（支持多关键词，回车添加，× 删除，如"二手车"、"买车"）+ [+添加] 按钮
  - 目标平台勾选（抖音/快手/小红书，默认全选）
  - 评论话术预览（显示当前使用的评论模板，点击 [编辑话术] 弹出文本区编辑，最多保存 5 条话术，AI 随机选择）
- [ ] AC-2: 控制按钮 — [▶ 开始截流] 大按钮 `#10B981`（未运行时）/ [■ 停止] 大按钮 `#EF4444`（运行中）+ 运行状态文字（运行中/已停止/暂停中）
- [ ] AC-3: 运行中状态栏 — 显示实时统计：已评论数、已搜索视频数、运行时长、今日新增线索数。数据每 5 秒自动刷新（轮询 `GET /api/intercept/status`）
- [ ] AC-4: 截流记录列表 — 表格展示最近 50 条截流记录。列：时间、平台图标、目标视频标题（截断 30 字+点击展开）、评论内容（截断 50 字）、状态（已评论/已跳过/失败）。支持按平台筛选
- [ ] AC-5: 停止确认 — 点击 [停止] 弹出确认："确定要停止截流吗？当前已评论 X 条"，确认后调用 `POST /api/intercept/stop`
- [ ] AC-6: 风控保护 — 当后端检测到验证码/风控时，截流自动暂停，前端显示橙色警告横幅"检测到平台风控，截流已暂停 — 请手动处理验证码后重试"
- [ ] AC-7: 空状态 — 未配置关键词时显示 Fish 图标 + "配置截流关键词，AI 自动帮您在同行的评论区挖掘客户"
- [ ] AC-8: 错误处理 — 网络断开/后端异常时显示错误卡片+重试按钮，不影响已运行的截流任务
- [ ] AC-9: 响应式 — 移动端配置卡片全宽、列表横向滚动；桌面端标准表格

---

## feature: F-021 任务看板

### purpose
面向老板。一眼看清 AI 员工正在做什么、做完了什么、什么失败了。
后端对接 `scheduler_engine.py`。
核心价值：老板不需要懂技术，看一眼就知道 AI 今天干了多少活。

### north_star
一句话指挥AI干活

### engine
claude-code

### depends_on
无

### relevant_files
- szyg-frontend/src/pages/ai-staff/TaskBoard.tsx
- szyg-frontend/src/lib/api.ts
- server/szyg/scheduler_engine.py
- szyg-frontend/src/components/ui/card.tsx
- szyg-frontend/src/components/ui/button.tsx
- szyg-frontend/src/components/ui/badge.tsx
- szyg-frontend/src/components/ui/empty.tsx
- szyg-frontend/DESIGN_SYSTEM.md

### acceptance
- [ ] AC-1: 顶部筛选栏 — 标签切换：[全部] [⏳ 进行中] [✅ 已完成] [❌ 失败]。显示各状态计数。默认显示"全部"
- [ ] AC-2: 三栏看板布局（桌面端）— 进行中 / 已完成 / 失败。移动端变为单列，按状态分组
- [ ] AC-3: 任务卡片 — 每张卡片包含：任务类型图标+名称（如 📹 发布视频 / 💬 智能截流 / 🔍 舆情监听）、目标平台、开始时间、进度（进行中显示"已评论 342 条"类动态数据、已完成显示完成时间、失败显示错误原因）。卡片可点击 → 展开任务详情（执行日志、子任务列表）
- [ ] AC-4: 进行中卡片 — 左侧绿色边框 `#10B981`。实时更新进度数据。显示 [查看详情] 和 [取消任务] 按钮
- [ ] AC-5: 已完成卡片 — 左侧灰色边框 `#64748B`。显示完成时间和结果摘要。显示 [查看详情] 按钮
- [ ] AC-6: 失败卡片 — 左侧红色边框 `#EF4444`。显示失败原因（截断 50 字）+ [重试] 按钮 + [查看日志] 按钮
- [ ] AC-7: 重试功能 — 点击失败卡片的 [重试] → 调用 `POST /api/tasks/{id}/retry` → 任务卡片移到进行中栏
- [ ] AC-8: 自动刷新 — 页面每 10 秒自动轮询 `GET /api/tasks?status=all`，刷新卡片数据。任务数变化时卡片有短暂高亮动画
- [ ] AC-9: 空状态 — 三栏均为空时显示 ClipboardList 图标 + "暂无任务，通过超级员工对话或各功能页面创建任务"
- [ ] AC-10: 响应式 — 桌面端三栏并排等宽；平板两栏；移动端单栏 + 筛选标签
