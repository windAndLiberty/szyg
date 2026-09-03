# 🧩 组件规范

> 本文件为旧版Vue+Element Plus组件规范的架构参考。
> **实际前端UI组件库以 `szyg-frontend/src/components/ui/` 为准**。

## 实际组件清单

| 组件 | 文件 | 基座 |
|------|------|------|
| Button | `ui/button.tsx` | Radix Slot + CVA |
| Card | `ui/card.tsx` | Tailwind + CVA |
| Badge | `ui/badge.tsx` | Tailwind + CVA |
| Input | `ui/input.tsx` | Radix + Tailwind |
| Avatar | `ui/avatar.tsx` | Radix Avatar |
| Switch | `ui/switch.tsx` | Radix Switch |
| Label | `ui/label.tsx` | Radix Label |
| Separator | `ui/separator.tsx` | Radix Separator |
| Empty | `ui/empty.tsx` | Framer Motion + Tailwind |

## 组件命名规范

- 使用 `cva()` (class-variance-authority) 定义变体
- 使用 `cn()` (tailwind-merge + clsx) 合并类名
- 默认导出为命名导出
- 支持 `className` prop 外部覆盖

