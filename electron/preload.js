const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // ── Window controls ──
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  getVersion: () => ipcRenderer.invoke('get-version'),
  setLocale: (locale) => ipcRenderer.invoke('branding-set-locale', locale),

  // Managed browser used by the super employee work view.
  browserSetVisible: (visible) => ipcRenderer.invoke('browser-set-visible', Boolean(visible)),
  browserSetBounds: (bounds) => ipcRenderer.invoke('browser-set-bounds', bounds),
  browserGetState: () => ipcRenderer.invoke('browser-state'),
  browserAction: (payload) => ipcRenderer.invoke('browser-action', payload),
  onBrowserState: (callback) => {
    const handler = (_event, state) => callback(state)
    ipcRenderer.on('szyg-browser-state', handler)
    return () => ipcRenderer.removeListener('szyg-browser-state', handler)
  },

  // OpenClaw runtime facade. Gateway URLs, bootstrap tokens and device
  // credentials remain in the main process.
  openClaw: {
    runtime: {
      start: () => ipcRenderer.invoke('openclaw-runtime-start'),
      status: () => ipcRenderer.invoke('openclaw-runtime-status'),
      version: () => ipcRenderer.invoke('openclaw-runtime-version'),
      restart: () => ipcRenderer.invoke('openclaw-runtime-restart'),
    },
    bots: {
      list: (params = {}) => ipcRenderer.invoke('openclaw-bots-list', params),
      create: (params) => ipcRenderer.invoke('openclaw-bots-create', params),
      update: (params) => ipcRenderer.invoke('openclaw-bots-update', params),
      archive: (params) => ipcRenderer.invoke('openclaw-bots-archive', params),
    },
    sessions: {
      list: (params = {}) => ipcRenderer.invoke('openclaw-sessions-list', params),
      create: (params = {}) => ipcRenderer.invoke('openclaw-sessions-create', params),
      history: (params) => ipcRenderer.invoke('openclaw-sessions-history', params),
    },
    runs: {
      send: (params) => ipcRenderer.invoke('openclaw-runs-send', params),
      interrupt: (params) => ipcRenderer.invoke('openclaw-runs-interrupt', params),
      subscribe: (callback) => {
        const handler = (_event, runtimeEvent) => callback(runtimeEvent)
        ipcRenderer.on('szyg-openclaw-event', handler)
        return () => ipcRenderer.removeListener('szyg-openclaw-event', handler)
      },
    },
    approvals: {
      resolve: (params) => ipcRenderer.invoke('openclaw-approvals-resolve', params),
    },
    questions: {
      answer: (params) => ipcRenderer.invoke('openclaw-questions-answer', params),
    },
    skills: {
      list: (params = {}) => ipcRenderer.invoke('openclaw-skills-list', params),
      readStatus: (params) => ipcRenderer.invoke('openclaw-skills-read-status', params),
    },
    routines: {
      list: (params = {}) => ipcRenderer.invoke('openclaw-routines-list', params),
      save: (params) => ipcRenderer.invoke('openclaw-routines-save', params),
      run: (params) => ipcRenderer.invoke('openclaw-routines-run', params),
      pause: (params) => ipcRenderer.invoke('openclaw-routines-pause', params),
    },
    computer: {
      status: (params = {}) => ipcRenderer.invoke('openclaw-computer-status', params),
      preview: (params = {}) => ipcRenderer.invoke('openclaw-computer-preview', params),
      takeover: (params = {}) => ipcRenderer.invoke('openclaw-computer-takeover', params),
      returnControl: (params = {}) => ipcRenderer.invoke('openclaw-computer-return', params),
    },
    artifacts: {
      list: (params = {}) => ipcRenderer.invoke('openclaw-artifacts-list', params),
      open: (params) => ipcRenderer.invoke('openclaw-artifacts-open', params),
    },
  },

  removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel),
})
