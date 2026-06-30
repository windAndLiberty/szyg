const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // ── Window controls ──
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  getVersion: () => ipcRenderer.invoke('get-version'),

  // ── Platform BrowserView controls ──
  platformOpen: (platform, url) => ipcRenderer.invoke('platform-open', platform, url),
  platformClose: (platform) => ipcRenderer.send('platform-close', platform),
  platformCookies: (platform, filterUrl) => ipcRenderer.invoke('platform-cookies', platform, filterUrl),
  platformInject: (platform, script) => ipcRenderer.invoke('platform-inject', platform, script),
  platformGetUrl: (platform) => ipcRenderer.invoke('platform-get-url', platform),
  platformList: () => ipcRenderer.invoke('platform-list'),

  // ── Event listeners ──
  onPlatformTitleChanged: (callback) => ipcRenderer.on('platform-title-changed', (_, data) => callback(data)),
  onPlatformNavigated: (callback) => ipcRenderer.on('platform-navigated', (_, data) => callback(data)),
  removeAllListeners: (channel) => ipcRenderer.removeAllListeners(channel),
})
