export {}

type OpenClawParams = Record<string, unknown>
type OpenClawResult = Record<string, unknown>
type OpenClawEvent = {
  id: string
  type: string
  source: string
  timestamp: number
  payload: OpenClawResult
}

interface OpenClawAPI {
  runtime: {
    start: () => Promise<OpenClawResult>
    status: () => Promise<OpenClawResult>
    version: () => Promise<OpenClawResult>
    restart: () => Promise<OpenClawResult>
  }
  bots: {
    list: (params?: OpenClawParams) => Promise<OpenClawResult>
    create: (params: OpenClawParams) => Promise<OpenClawResult>
    update: (params: OpenClawParams) => Promise<OpenClawResult>
    archive: (params: OpenClawParams) => Promise<OpenClawResult>
  }
  sessions: {
    list: (params?: OpenClawParams) => Promise<OpenClawResult>
    create: (params?: OpenClawParams) => Promise<OpenClawResult>
    history: (params: OpenClawParams) => Promise<OpenClawResult>
  }
  runs: {
    send: (params: OpenClawParams) => Promise<OpenClawResult>
    interrupt: (params: OpenClawParams) => Promise<OpenClawResult>
    subscribe: (callback: (event: OpenClawEvent) => void) => (() => void)
  }
  approvals: { resolve: (params: OpenClawParams) => Promise<OpenClawResult> }
  questions: { answer: (params: OpenClawParams) => Promise<OpenClawResult> }
  skills: {
    list: (params?: OpenClawParams) => Promise<OpenClawResult>
    readStatus: (params: OpenClawParams) => Promise<OpenClawResult>
  }
  routines: {
    list: (params?: OpenClawParams) => Promise<OpenClawResult>
    save: (params: OpenClawParams) => Promise<OpenClawResult>
    run: (params: OpenClawParams) => Promise<OpenClawResult>
    pause: (params: OpenClawParams) => Promise<OpenClawResult>
  }
  computer: {
    status: (params?: OpenClawParams) => Promise<OpenClawResult>
    preview: (params?: OpenClawParams) => Promise<OpenClawResult>
    takeover: (params?: OpenClawParams) => Promise<OpenClawResult>
    returnControl: (params?: OpenClawParams) => Promise<OpenClawResult>
  }
  artifacts: {
    list: (params?: OpenClawParams) => Promise<OpenClawResult>
    open: (params: OpenClawParams) => Promise<OpenClawResult>
  }
}

declare global {
  interface Window {
    electronAPI?: {
      minimize?: () => void
      maximize?: () => void
      close?: () => void
      isMaximized?: () => Promise<boolean>
      getVersion?: () => Promise<string>
      setLocale?: (locale: 'zh-CN' | 'en-US') => Promise<{ ok: boolean; locale: string; name: string }>
      browserSetVisible?: (visible: boolean) => Promise<Record<string, unknown>>
      browserSetBounds?: (bounds: { x: number; y: number; width: number; height: number }) => Promise<Record<string, unknown>>
      browserGetState?: () => Promise<Record<string, unknown>>
      browserAction?: (payload: Record<string, unknown>) => Promise<Record<string, unknown>>
      onBrowserState?: (callback: (state: Record<string, unknown>) => void) => (() => void)
      openClaw?: OpenClawAPI
      removeAllListeners?: (channel: string) => void
    }
  }
}
