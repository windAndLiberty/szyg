# 🎨 设计系统

> 本文件为旧版Vue+Element Plus设计系统的架构参考文档。
> **实际前端设计系统以 `szyg-frontend/DESIGN_SYSTEM.md` 为准**。

## 设计原则（可沿用）

1. **退让**：UI框架（侧边栏、顶栏）存在感极低
2. **呼吸**：用留白组织信息
3. **克制**：颜色、动效只做必要表达
4. **专注**：减少视觉噪音

## 实际设计系统速查

| 项目 | 值 |
|------|------|
| 主题 | 深色科技主题 (极深蓝黑 #0B0F1A + 靛蓝紫 #6366F1) |
| 框架 | Tailwind CSS 3 + Radix UI + Framer Motion |
| 布局 | 侧边栏 260px / 折叠 72px + 顶栏 64px |
| 卡片 | glass-card: 渐变背景(180deg) + 1px边框 + 12px圆角 |
| 圆角 | 卡片12px / 输入框10px / 按钮10px |
| 动效 | ease-out-expo cubic-bezier(0.16, 1, 0.3, 1) |
| 图标 | Lucide React 默认16px |

> 完整设计规范见 `szyg-frontend/DESIGN_SYSTEM.md`

