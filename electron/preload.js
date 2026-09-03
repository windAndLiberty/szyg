const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // ── Window controls ──
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  getVersion: () => ipcRenderer.invoke('get-version'),

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

  removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel),
})
