# 📒 域灵流水日志 — 全局状态感知 (Shared State Awareness)

> 本目录记录所有智能体的工程操作流水。它是多智能体之间**无需通读代码即可感知全局状态**的核心机制。

## 📂 结构说明

| 文件 | 用途 | 维护者 |
|------|------|--------|
| `CURRENT_STATE.md` | 实时全局状态快照（阻碍点、技术债、系统健康度） | QA_Guardian |
| `chronicles/{YYYY-MM}_activity.md` | 按月归档的原子操作流水 | Elite_Coder |

## ✍️ 日志书写规约

### 更新时机

每完成一个**独立的、可运行的逻辑步骤**并保存文件后，**必须**在 `chronicles/` 对应月份文件**顶部**追加一条记录。

### 颗粒度：原子化工程提交级 (Atomic Engineering Session)

- ❌ **过细（行级变更）**：写一行代码更新一次日志 → Token 爆炸
- ❌ **过粗（任务级变更）**：整个功能做完才写一句 → 并行智能体无法感知
- ✅ **黄金解法**：每完成一个独立可运行的逻辑步骤并保存文件时记录

### 标准格式

```markdown
## [YYYY-MM-DD HH:MM:SS] | Agent: {Agent_Name} | Action: {Brief_Action_Name}

- **🎯 核心目的**: 本次原子操作要解决什么问题
- **📂 变更文件**:
  - `path/to/file` (Created/Modified/Deleted: 简述变更内容)
- **⚡ 架构/副作用破坏**:
  - 影响了哪些接口/类型/组件/配置
  - **警告**：对其他模块的潜在破坏
- **🏁 当前状态**: ✅ 语法通过 | ✅/❌ 联调 | ✅/❌ 测试
```

## ⚠️ 铁律

1. **未写 Logbook = 任务未完成**（DoD 硬阻塞）。
2. 日志按时间戳**倒序**排列（最新在最上面）。
3. 颗粒度 = 原子化工程提交级，不是行级，不是任务级。
4. `CURRENT_STATE.md` 由 QA_Guardian 定期压缩 chronicles 内容后更新。
5. 新月份开始时自动创建 `chronicles/{YYYY-MM}_activity.md` 文件。
