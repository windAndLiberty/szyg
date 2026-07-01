# 🏗️ 前端目录结构与页面路由

## 1. 顶层结构

```
web/
├── index.html              # SPA 入口 HTML
├── package.json            # 依赖声明 (Vue 3 + Element Plus + Pinia + Vue Router)
├── vite.config.js          # Vite 构建配置
├── tsconfig.json           # TypeScript 配置
├── src/
│   ├── main.js             # 应用入口 (创建 Vue app + 挂载 Element Plus + Pinia + Router)
│   ├── App.vue             # 根组件
│   ├── api.js              # axios 实例 (baseURL + JWT 拦截器)
│   ├── router.js           # 路由定义 (7 大版块 + 向后兼容重定向)
│   ├── style.css           # 全局样式
│   ├── tech-theme.css      # 科技主题样式
│   ├── assets/             # 静态资源
│   ├── components/         # 公共组件 (AppLayout 等)
│   ├── pages/              # 页面组件 (43 个 .vue 文件)
│   └── stores/             # Pinia 状态管理
├── public/
│   ├── favicon.svg
│   └── icons.svg
├── e2e/                    # Playwright E2E 测试
└── dist/                   # 构建产物 (被后端 StaticFiles 挂载)
```

## 2. 路由树 — 7 大版块

### 2.1 🤖 AI员工 (`/ai-staff`)

| 路径 | 组件 | 页面标题 |
|------|------|----------|
| `/ai-staff/super-agent` | `SuperAgent.vue` | 超级员工 |
| `/ai-staff/overview` | `StaffOverview.vue` | 员工概览 |
| `/ai-staff/tasks` | `TaskBoard.vue` | 任务看板 |
| `/ai-staff/profiles` | `AgentProfiles.vue` | 员工配置 |

- **Shell**: `AiStaff.vue` → 默认重定向到 `super-agent`
- **认证**: 无需认证（自动认证模式）

### 2.2 📦 内容工厂 (`/content`)

| 路径 | 组件 | 页面标题 |
|------|------|----------|
| `/content/production` | `ContentStudio.vue` | 内容生产 |
| `/content/video-editor` | `VideoEditor.vue` | 视频剪辑 |
| `/content/video-search` | `VideoSearch.vue` | 视频搜索 |
| `/content/digital-human` | `DigitalHuman.vue` | 数字人 |
| `/content/assets` | `ContentAssets.vue` | 内容资产 |
| `/content/publish` | `PublishCenter.vue` | 多平台发布 |

- **Shell**: `ContentShell.vue` → 默认重定向到 `production`

### 2.3 🎯 营销拓客 (`/marketing`)

| 路径 | 组件 | 页面标题 |
|------|------|----------|
| `/marketing/intercept` | `AcquisitionStudio.vue` | 智能截流 |
| `/marketing/listen` | `ListenCenter.vue` | 舆情监听 |
| `/marketing/conversion` | `ConversionStudio.vue` | 客户转化 |
| `/marketing/ab-test` | `ABTestCenter.vue` | A/B测试 |
| `/marketing/customers` | `CustomerAssets.vue` | 客户资产 |
| `/marketing/enterprise` | `EnterpriseAcquisition.vue` | 企业获客 |
| `/marketing/nfc` | `NfcMarketing.vue` | 到店引流 |

- **Shell**: `MarketingShell.vue` → 默认重定向到 `intercept`

### 2.4 ⚙️ 工作流编排 (`/workflow`)

| 路径 | 组件 | 页面标题 |
|------|------|----------|
| `/workflow/pipeline` | `PipelineDesigner.vue` | 流水线编排 |
| `/workflow/scheduler` | `SchedulerEngine.vue` | 调度引擎 |
| `/workflow/sop` | `SOPManager.vue` | SOP管理 |

- **Shell**: `WorkflowShell.vue` → 默认重定向到 `pipeline`

### 2.5 📊 数据洞察 (`/insights`)

| 路径 | 组件 | 页面标题 |
|------|------|----------|
| `/insights/dashboard` | `Dashboard.vue` | 运营仪表盘 |
| `/insights/content-analytics` | `ContentAnalytics.vue` | 内容分析 |
| `/insights/acquisition-analytics` | `AcquisitionAnalytics.vue` | 截流效果 |
| `/insights/conversion-analytics` | `ConversionAnalytics.vue` | 转化分析 |

- **Shell**: `InsightsShell.vue` → 默认重定向到 `dashboard`
- **默认首页**: `/` → 重定向到 `/insights/dashboard`

### 2.6 📚 知识库 (`/knowledge`)

| 路径 | 组件 | 页面标题 |
|------|------|----------|
| `/knowledge/base` | `KnowledgeBase.vue` | 知识管理 |
| `/knowledge/memory` | `MemoryCenter.vue` | 长期记忆 |
| `/knowledge/skills` | `SettingsSkills.vue` | 技能市场 |
| `/knowledge/academy` | `Academy.vue` | 商学院 |

- **Shell**: `KnowledgeShell.vue` → 默认重定向到 `base`

### 2.7 ⚙️ 系统设置 (`/settings`)

| 路径 | 组件 | 页面标题 | 权限 |
|------|------|----------|------|
| `/settings/risk-control` | `SettingsRiskControl.vue` | 风控策略 | user |
| `/settings/tools` | `SettingsTools.vue` | 工具管理 | user |
| `/settings/system` | `SettingsSystem.vue` | 系统配置 | user |
| `/settings/brand` | `SettingsBrand.vue` | 品牌配置 | **admin** |
| `/settings/team` | `SettingsTeam.vue` | 团队管理 | **admin** |
| `/settings/billing` | `SettingsBilling.vue` | 计费管理 | **admin** |

- **Shell**: `Settings.vue` → 默认重定向到 `risk-control`

## 3. 认证守卫

```javascript
// router.js beforeEach
// 自动认证模式：不再检查 token，不重定向到 /login
router.beforeEach(async (to, from, next) => {
  next()
})
```

## 4. 向后兼容重定向

路由文件包含 5 代历史路径重定向（Gen 1-5），确保旧链接不断裂：

- `/chat` → 首页 (panel=open)
- `/agents` → `/ai-staff/overview`
- `/publisher` → `/content/publish`
- `/dashboard` → `/insights/dashboard`
- `/infra/*` → `/settings/risk-control`
- `/login` → `/` (登录页已移除，重定向到首页)
- 等共 40+ 条重定向规则

## 5. API 通信

- **axios 实例**: `web/src/api.js`
- **JWT 拦截器**: 请求头自动附加 `Authorization: Bearer {token}`
- **baseURL**: 空字符串 (同源请求，后端 StaticFiles 挂载 SPA)

## 6. 构建产物

- `web/dist/` → 被 `server/szyg/api/app.py` 中 `StaticFiles` 挂载
- `/assets/*` → 静态资源
- `/{full_path:path}` → SPA 客户端路由 fallback (返回 index.html)
