# 🔧 Loop Agent v2 — 施工队长指导书

> 施工队长：Architect_Agent | 施工队：编码Agent (Cline)
> 日期：2026-07-06 | 施工对象：szyg 域灵系统
> 蓝图：D:\\szyg\\docs\\szyg-system-spec.md (22 Features)

---

## 一、角色划分

| 角色 | 谁 | 做什么 |
|------|-----|--------|
| 施工队长 | Architect_Agent | 设计接口·拆解任务·定义验收·审阅产出 |
| 工头 | 编码Agent | 读指导书→写代码→跑测试→写日志 |
| 施工对象 | szyg (域灵系统) | 被改写的目标项目 |
| 施工工具 | Loop Agent v2 | 编码Agent要构建的元工具 |

## 二、施工工具需要构建什么

Loop Agent v2 是一个 LangGraph StateGraph 管道，站在 D:\\loop-agent\\，
读 D:\\szyg\\docs\\szyg-system-spec.md 蓝图，拆任务，驱动编码工具写 szyg 代码。

### 2.1 组件清单及实现顺序

```
第1层 (基石·可并行):
  A. loop_agent/task_package.py       ← TaskPackage 数据类
  B. loop_agent/engines/base.py        ← CliSession 抽象基类

第2层 (引擎实现·依赖A+B):
  C. loop_agent/engines/claude_code.py ← Claude Code CLI 会话
  D. loop_agent/engines/cline.py       ← Cline CLI 会话
  E. loop_agent/task_decomposer.py     ← 蓝图解析+拓扑排序

第3层 (管道组装·依赖C+D+E):
  F. loop_agent/router.py              ← 任务→引擎 分派逻辑
  G. loop_agent/graph_v2.py            ← 组装 v2 LangGraph StateGraph

第4层 (质量·依赖F+G):
  H. loop_agent/break_early.py         ← Evaluator打断逻辑
  I. loop_agent/evaluator_v2.py        ← v2专属3层Evaluator

测试 (每层完成后):
  T1. tests/test_task_package.py
  T2. tests/test_decomposer.py (输入 szyg-system-spec.md 期望输出 TaskPackage列表)
  T3. tests/test_router.py
  T4. tests/test_graph_v2.py (Mock引擎·验证StateGraph流转)
```

### 2.2 每个组件的交界面 (Interface Contract)

```
A. TaskPackage
  输入: feature_id (F-001 etc) + blueprint_dict
  输出: TaskPackage 实例 (title/purpose/description/acceptance_criteria/relevant_files/engine/depends_on)
  关键: acceptance_criteria 全部初始化为 {"passes": false, "evidence": null} ← Default-FAIL

B. CliSession
  抽象方法:
    async start(project_dir) → session_id
    async send(task, context_files) → stdout_lines
    async await_response() → tool_calls + code_artifacts
    async stop()
  关键: stdin/stdout 管道·prompt cache 复用·超时控制

C. TaskDecomposer
  输入: szyg-system-spec.md 文件路径
  解析: 正则匹配 ## feature: F-XXX 段落 → 提取 优先级/依赖/文件范围/AC
  拓扑排序: 先安排无依赖Feature·再安排依赖链
  输出: list[TaskPackage] (按依赖拓扑排序)
  关键: 尊重模块树9级+前端路由结构作为依赖信号

D. Router
  输入: TaskPackage + 当前OrchestrationState
  规则:
    task.relevant_files 以 .tsx .css 为主 → cline (前端)
    task.relevant_files 以 .py 为主·跨5+文件 → claude-code (后端)
    task.relevant_files ≤ 2个.py 文件·非架构 → chat-nvidia (简单)
  输出: engine_name (claude-code|cline|chat-nvidia)

E. GraphV2
  复用 v1 的 6 Agent节点 (Planner/Coder/Tester/3×Reviewer/Evaluator)
  新增: TaskDecomposer 前置节点 + Router 替换 Coder 选择
  流程: TaskDecomposer→Planner→Router→Coder(多引擎)→Tester→Reviewer(×3)→Evaluator
  Evaluator裁决: continue→back to Coder | finish→next TaskPackage | rewind→从检查点恢复
```

---

## 三、施工步调

### 第一批：基石 (2个文件·预计1次编码会话)

```
编码Agent任务:
  1. 读 WORK-SUMMARY.md + loop-agent-v2-design.md
  2. 实现 loop_agent/task_package.py (TaskPackage数据类)
  3. 实现 loop_agent/engines/base.py (CliSession抽象·仅接口不实现)
  4. 写 tests/test_task_package.py (验证Default-FAIL初始状态)
  5. 跑 uv run pytest tests/test_task_package.py -v → 全绿

产出检查:
  ✅ TaskPackage.__init__ 正确设置 acceptance_criteria 全为 passes:false
  ✅ TaskPackage.depends_on 正确解析
  ✅ CliSession 抽象方法签名与设计文档一致
```

### 第二批：引擎+拆解 (3个文件)

```
编码Agent任务:
  1. 实现 loop_agent/task_decomposer.py → 输入 szyg-system-spec.md 输出 TaskPackage列表
  2. 实现 loop_agent/engines/claude_code.py (如果有claude CLI)·cline.py (如果有cline CLI)
  3. 如CLI不可用·先用 ChatNVIDIA Mock 替代·待后续接入
  4. 写 tests/test_decomposer.py
  5. 跑 uv run pytest tests/test_decomposer.py -v → 验证能正确解析所有 ## feature: 段落

产出检查:
  ✅ TaskDecomposer 输出 22 个 TaskPackage (F-001到F-021)
  ✅ 拓扑排序结果中 F-001第一层无依赖·F-010依赖F-004
  ✅ engine字段按 Router规则正确分配
```

### 第三批：管道+路由 (3个文件)

```
编码Agent任务:
  1. 实现 loop_agent/router.py
  2. 实现 loop_agent/graph_v2.py (组装完整v2 StateGraph)
  3. 写 tests/test_router.py + tests/test_graph_v2.py
  4. 跑 uv run pytest tests/ -v --ignore=tests/test_e2e.py → 全绿

产出检查:
  ✅ StateGraph流转: decomposer→planner→router→coder→tester→reviewer→evaluator→...
  ✅ Evaluator的continue/finish/rewind/escalate 4种裁决均触发
  ✅ break_early 可中断长时间Coder
```

### 第四批：跑一个真实Feature

```
施工队长指令:
  1. 挑一个最简单的Feature (如F-013 SOP管理·单页面占位替换)
  2. 生成 TaskPackage → 交给 Router 分派引擎
  3. 观察全链路: TaskDecomposer→Planner→Coder→Tester→Reviewer→Evaluator→finish
  4. 审查 szyg code diff · 跑 npm run build

产出检查:
  ✅ 全链路无中断
  ✅ 输出的代码符合 szyg 风格 (Tailwind class命名等)
  ✅ Evaluator的5维评分全部≥3分
```

---

## 四、验收标准

### 施工工具自身的验收 (Loop Agent v2)

| AC | 条件 | passes |
|----|------|--------|
| AC-1 | task_package.py TaskPackage数据类各字段类型正确 | false |
| AC-2 | task_decomposer.py 能正确解析22个Feature并拓扑排序 | false |
| AC-3 | router.py 按文件类型/数量正确分派引擎 | false |
| AC-4 | graph_v2.py StateGraph 流转完整·无死节点 | false |
| AC-5 | 所有测试 uv run pytest tests/ -v 通过 (含新建 + v1 64个不退步) | false |
| AC-6 | 跑完1个真实Feature·szyg代码diff可审查·前端构建不破 | false |

### szyg的验收 (施工结果)

| AC | 条件 | passes |
|----|------|--------|
| AC-7 | 施工后 npm run build (szyg-frontend) 通过 | false |
| AC-8 | 施工后 uv run pytest tests/ (szyg后端) 测试数增加 | false |
| AC-9 | 施工产出与 szyg 现有代码风格一致 (Tailwind+deep theme) | false |

---

## 五、施工队长的工作节奏

```
每次施工会话:
  1. 施工队长指定 Feature ID (如 F-003)
  2. 编码Agent读对应 TaskPackage → 读 szyg-system-spec.md 的Feature段
  3. 编码Agent写代码 → 跑测试 → 写 logbook
  4. 施工队长审阅 → 通过/打回 → 更新 szyg-system-spec.md 的 AC.passes

迭代:
  每完成一个批次·施工队长更新 KnowledgeBase/CURRENT_GOALS.md
```

