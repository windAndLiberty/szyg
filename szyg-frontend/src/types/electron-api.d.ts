export {}

declare global {
  interface Window {
    electronAPI?: {
      minimize?: () => void
      maximize?: () => void
      close?: () => void
      isMaximized?: () => Promise<boolean>
      getVersion?: () => Promise<string>
      browserSetVisible?: (visible: boolean) => Promise<Record<string, unknown>>
      browserSetBounds?: (bounds: { x: number; y: number; width: number; height: number }) => Promise<Record<string, unknown>>
      browserGetState?: () => Promise<Record<string, unknown>>
      browserAction?: (payload: Record<string, unknown>) => Promise<Record<string, unknown>>
      onBrowserState?: (callback: (state: Record<string, unknown>) => void) => (() => void)
      removeAllListeners?: (channel: string) => void
    }
  }
}
