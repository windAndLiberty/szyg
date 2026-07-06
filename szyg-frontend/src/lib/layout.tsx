/**
 * 布局常量与共享状态 — Sidebar/TopBar/Layout/App 共用，避免硬编码偏移值不一致。
 */
import { createContext, useContext, useState, type ReactNode } from 'react'

// 侧边栏宽度常量（DESIGN_SYSTEM.md 规范）
export const SIDEBAR_WIDTH_EXPANDED = 260
export const SIDEBAR_WIDTH_COLLAPSED = 72
export const TOPBAR_HEIGHT = 64 // h-16

interface LayoutState {
  collapsed: boolean
  setCollapsed: (v: boolean) => void
  /** 当前侧边栏实际宽度（px），供 TopBar/Layout 计算 margin */
  sidebarWidth: number
}

const LayoutContext = createContext<LayoutState | null>(null)

export function LayoutProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const sidebarWidth = collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED
  return (
    <LayoutContext.Provider value={{ collapsed, setCollapsed, sidebarWidth }}>
      {children}
    </LayoutContext.Provider>
  )
}

export function useLayout(): LayoutState {
  const ctx = useContext(LayoutContext)
  if (!ctx) {
    // 兜底：若未包裹 Provider（如独立测试），返回默认展开态
    return {
      collapsed: false,
      setCollapsed: () => {},
      sidebarWidth: SIDEBAR_WIDTH_EXPANDED,
    }
  }
  return ctx
}
