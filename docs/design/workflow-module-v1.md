# SZYG 工作流模块 v1 功能设计

## 1. 产品定位

工作流模块不是通用拖拽式自动化搭建器，而是面向中小企业岗位任务的自动化运营中心。
用户选择可直接使用的自动化方案，配置业务目标、账号、素材、执行时间和人工接管策略，系统负责稳定运行并反馈结果。

```text
自动化方案（做什么）
→ 运行计划（什么时候做）
→ 标准流程（按什么规范做）
→ Execution Kernel（执行、验证、风控、审计）
```

## 2. 信息架构

### 2.1 自动化方案

路由：`/workflow/pipeline`

面向普通用户展示预置岗位任务，不展示 DAG、节点、模型名称或执行器术语。

v1 内置场景：

- 内容定时发布：按选定渠道和时间发布已采纳素材。
- 渠道账号巡检：检查登录状态、账号异常和需要处理事项。
- 客户跟进提醒：整理待跟进客户并生成今日行动清单。
- 线索整理日报：汇总新增线索、高意向线索和来源分布。

核心操作：

- 搜索与按岗位分类筛选。
- 查看方案目标、预计步骤、需要准备的内容和人工确认点。
- 配置方案：名称、业务目标、频率、目标渠道、人工接管策略。
- 启用、暂停、继续、停用方案。
- 查看最近运行状态与结果。

### 2.2 运行计划

路由：`/workflow/scheduler`

只负责“什么时候运行”，不重复展示方案的业务配置。

核心能力：

- 计划列表：下次运行、最近结果、状态、所属方案。
- 创建计划：立即执行、每天、每周、固定间隔、指定时间。
- 暂停、继续、立即运行、删除。
- 执行记录：触发时间、结果、耗时、失败原因、需人工状态。

### 2.3 标准流程

路由：`/workflow/sop`

用于查看和维护“这项工作应该怎样做”，不承担调度职责。

核心能力：

- 按内容运营、渠道运营、客户运营分类展示 SOP。
- 查看有序步骤、步骤说明、失败处理和人工确认点。
- 复制内置模板后有限编辑名称、说明和步骤。
- 查看由该 SOP 产生的最近执行记录。

## 3. 统一状态

### 3.1 自动化方案状态

```text
draft | active | paused | disabled
```

### 3.2 执行状态

直接复用 Execution Kernel：

```text
queued | running | success | failed | paused | needs_human | cancelled
```

页面不新增同义状态。`needs_human` 始终显示为“需处理”。

## 4. v1 数据模型

### WorkflowTemplate

```json
{
  "id": "account_health_check",
  "name": "渠道账号巡检",
  "category": "channel_operations",
  "description": "检查已连接渠道的登录与账号状态",
  "outcome": "生成账号健康清单和需处理事项",
  "steps": [],
  "config_schema": {},
  "risk_level": "low"
}
```

### WorkflowInstance

```json
{
  "id": "wf_xxxxxxxx",
  "template_id": "account_health_check",
  "name": "每天账号巡检",
  "status": "active",
  "schedule": {"type": "daily", "time": "09:00"},
  "config": {},
  "human_policy": "pause_on_risk",
  "created_at": "",
  "updated_at": ""
}
```

### WorkflowSop

```json
{
  "id": "sop_xxxxxxxx",
  "name": "渠道账号巡检标准流程",
  "category": "channel_operations",
  "source": "builtin",
  "steps": [
    {
      "id": "check_login",
      "name": "检查登录状态",
      "description": "读取账号当前状态",
      "on_failure": "needs_human",
      "requires_confirmation": false
    }
  ]
}
```

## 5. API 契约

统一前缀：`/api/workflows`

- `GET /overview`：方案、运行、需处理统计。
- `GET /templates`：预置自动化方案。
- `GET /templates/{template_id}`：方案详情。
- `GET /instances`：已配置方案列表。
- `POST /instances`：从模板创建方案。
- `PUT /instances/{instance_id}`：修改配置或状态。
- `DELETE /instances/{instance_id}`：停用并移除方案。
- `POST /instances/{instance_id}/run`：立即执行。
- `GET /runs`：读取 ExecutionRun 映射后的运行记录。
- `POST /runs/{run_id}/pause|resume|retry|cancel`：委托 Execution Kernel。
- `GET /sops`：标准流程列表。
- `POST /sops/{sop_id}/clone`：复制内置流程。
- `PUT /sops/{sop_id}`：编辑用户流程。
- `GET /sops/{sop_id}/executions`：流程执行记录。

## 6. 执行边界

v1 首先真实支持低风险、可验证任务：

- 渠道账号巡检。
- 客户跟进提醒清单。
- 线索整理日报。

内容定时发布只配置和调度已有发布能力，不在工作流模块重新实现发布器。

任何评论发送、私信发送、内容发布等外部动作继续遵循原模块确认和风控规则。工作流模块不能绕过确认，也不能把 `needs_human` 自动改成成功。

## 7. 验收标准

- 三个页面不再是占位页。
- 用户不需要理解节点、模型、执行器或 DAG。
- 能从预置模板创建自动化方案，并配置运行时间。
- 能暂停、继续、立即运行和查看结果。
- 能查看 SOP 步骤和人工确认点。
- 所有运行状态来源于 Execution Kernel。
- 页面空态、加载失败和后端无数据时均可解释，不展示演示任务冒充真实结果。
