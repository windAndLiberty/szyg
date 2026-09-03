# 🎨 域灵设计系统

> **⚠️ 实际前端设计系统以 `szyg-frontend/DESIGN_SYSTEM.md` 为准**
> 本目录文件为架构参考，设计原则可沿用，具体实现以React+Tailwind为准。

## 目录索引

| 文件 | 内容 |
|------|------|
| `design-system.md` | 设计原则速查 + 实际设计系统关键参数 |
| `layout-framework.md` | 布局结构 (Sidebar 260px + TopBar 64px) |
| `component-specs.md` | 实际UI组件清单及命名规范 |
| `page-super-agent.md` | 超级员工页面级布局与交互规范 |
| `functional-design.md` | 功能设计方案 v1.0 |

## 设计哲学

1. **退让**：UI框架（侧边栏、顶栏）存在感极低
2. **呼吸**：用留白组织信息
3. **克制**：颜色、阴影、动效只做必要表达
4. **专注**：减少视觉噪音

## 范围边界

- 覆盖：`szyg-frontend/src/` 下所有React页面、组件、样式文件
- 不覆盖：业务逻辑、数据流、API 调用

