const { app, BrowserWindow, Tray, Menu, nativeImage, WebContentsView } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')
const net = require('net')

// ── Platform BrowserView Manager ──
// Maps platform id → WebContentsView instance for in-app login/publishing
const platformViews = new Map()
const PLATFORM_VIEW_BOUNDS = { x: 360, y: 80, width: 900, height: 640 }

// ── Anti-detect configuration for embedded browser views ──
const STEALTH_USER_AGENT = (
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' +
  'AppleWebKit/537.36 (KHTML, like Gecko) ' +
  'Chrome/131.0.0.0 Safari/537.36'
)

const STEALTH_INJECTION = `
(function() {
  'use strict';
  // 1. navigator.webdriver
  Object.defineProperty(navigator, 'webdriver', { get: () => false });
  // 2. chrome runtime
  window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
  // 3. plugins
  Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
  // 4. languages
  Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN','zh','en'] });
  // 5. Permissions
  const origQuery = window.navigator.permissions.query;
  window.navigator.permissions.query = (p) => (
    p.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : origQuery(p)
  );
  // 6. hardwareConcurrency / deviceMemory / platform
  Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
  Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
  Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
  // 7. Remove Electron traces from userAgentData if present
  if (navigator.userAgentData) {
    Object.defineProperty(navigator, 'userAgentData', {
      get: () => ({
        brands: [
          { brand: 'Chromium', version: '131' },
          { brand: 'Google Chrome', version: '131' },
          { brand: 'Not_A Brand', version: '24' }
        ],
        mobile: false,
        platform: 'Windows',
      })
    });
  }
})();
`

function setupAntiDetect(view) {
  const wc = view.webContents
  // Override User-Agent before any request
  wc.setUserAgent(STEALTH_USER_AGENT)
  // Override Accept-Language header
  wc.session.webRequest.onBeforeSendHeaders((details, callback) => {
    details.requestHeaders['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'
    callback({ requestHeaders: details.requestHeaders })
  })
  // Inject stealth script on every page load
  wc.on('dom-ready', () => {
    wc.executeJavaScript(STEALTH_INJECTION, false).catch(() => {})
  })
}

function openPlatformView(platform, url) {
  if (!mainWindow) return null
  closePlatformView(platform)

  const view = new WebContentsView({
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      // Use persistent partition so cookies survive within Electron session
      partition: `persist:platform_${platform}`,
    }
  })

  // Apply anti-detect measures
  setupAntiDetect(view)

  // Position inside main window (right side)
  const bounds = getPlatformViewBounds()
  view.setBounds(bounds)
  view.webContents.loadURL(url)

  mainWindow.contentView.addChildView(view)
  platformViews.set(platform, view)

  // Notify renderer of page title changes (used to detect login success)
  view.webContents.on('page-title-updated', (e, title) => {
    mainWindow.webContents.send('platform-title-changed', { platform, title })
  })

  // Notify renderer of navigation (used to detect login redirect)
  view.webContents.on('did-navigate', (e, url) => {
    mainWindow.webContents.send('platform-navigated', { platform, url })
  })

  console.log(`[BrowserView] Opened ${platform} → ${url}`)
  return view
}

function closePlatformView(platform) {
  const view = platformViews.get(platform)
  if (!view) return
  if (mainWindow) {
    try { mainWindow.contentView.removeChildView(view) } catch (_) {}
  }
  try { view.webContents.close() } catch (_) {}
  platformViews.delete(platform)
  console.log(`[BrowserView] Closed ${platform}`)
}

function closeAllPlatformViews() {
  for (const [platform, view] of platformViews) {
    if (mainWindow) {
      try { mainWindow.contentView.removeChildView(view) } catch (_) {}
    }
    try { view.webContents.close() } catch (_) {}
  }
  platformViews.clear()
}

function getPlatformViewBounds() {
  if (!mainWindow) return PLATFORM_VIEW_BOUNDS
  const size = mainWindow.getContentSize()
  // Right panel: fixed left margin, fill remaining width/height
  const leftMargin = 360
  const topMargin = 80
  return {
    x: leftMargin,
    y: topMargin,
    width: Math.max(600, size[0] - leftMargin - 20),
    height: Math.max(400, size[1] - topMargin - 20),
  }
}

function resizePlatformViews() {
  if (!mainWindow) return
  const bounds = getPlatformViewBounds()
  for (const view of platformViews.values()) {
    view.setBounds(bounds)
  }
}

// Disable GPU acceleration for RDP/VM compatibility
// Falls back to software rendering — works everywhere
app.disableHardwareAcceleration()

const isDev = process.env.NODE_ENV === 'development'
const enableDevTools = isDev || process.env.SZYG_DEBUG === '1'
const PORT = 8000
const FRONTEND_PORT = 5173

let mainWindow = null
let tray = null
let backendProcess = null
let comfyuiProcess = null
let isQuitting = false

// ── Single instance lock ──
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) { app.quit() } else {

// ── Crash protection: catch unhandled errors instead of hard crash ──
process.on('uncaughtException', (err) => {
  console.error('[Fatal] uncaughtException:', err)
  // Don't exit — log and recover
})
process.on('unhandledRejection', (reason, promise) => {
  console.error('[Fatal] unhandledRejection:', reason)
})

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  }
})

// ── Backend management ──
function findPython() {
  const fs = require('fs')
  const projectRoot = path.join(__dirname, '..')

  const candidates = [
    // 1. Project .venv (D:\szyg\.venv — has all deps)
    path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    // 2. hermes-agent venv (fallback, has CUDA + most deps)
    path.join(process.env.USERPROFILE || 'C:\\Users\\Administrator', 'AppData', 'Local', 'hermes', 'hermes-agent', 'venv', 'Scripts', 'python.exe'),
    // 3. PATH fallback
    'python',
    'python3',
  ]
  for (const c of candidates) {
    try {
      if (fs.existsSync(c)) {
        console.log(`Found Python: ${c}`)
        return c
      }
    } catch (_) {}
  }
  console.warn('No Python found in known locations, falling back to "python"')
  return 'python'
}

function isPortInUse(port) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', (err) => resolve(err.code !== 'EADDRNOTAVAIL'))
    server.once('listening', () => {
      server.close()
      resolve(false)
    })
    server.listen(port, '127.0.0.1')
  })
}

async function startBackend() {
  if (await isPortInUse(PORT)) {
    console.log(`Backend already running on port ${PORT}, skipping spawn`)
    return
  }

  const python = findPython()
  const projectRoot = path.join(__dirname, '..')
  const serverDir = path.join(projectRoot, 'server')
  const env = {
    ...process.env,
    PYTHONPATH: serverDir,
    SZYG_DATA_DIR: path.join(projectRoot, 'data'),
  }

  console.log(`Starting backend: ${python} - ${serverDir}`)
  console.log(`PYTHONPATH: ${serverDir}`)
  backendProcess = spawn(python, ['-m', 'uvicorn', 'szyg.api.app:create_app', '--host', '127.0.0.1', '--port', String(PORT), '--factory'], {
    cwd: projectRoot,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  backendProcess.stdout.on('data', (d) => console.log(`[backend] ${d}`))
  backendProcess.stderr.on('data', (d) => console.error(`[backend] ${d}`))
  backendProcess.on('exit', (code) => {
    console.log(`Backend exited: ${code}`)
    if (!isQuitting) {
      console.log('Restarting backend in 2s...')
      setTimeout(startBackend, 2000)
    }
  })
}

function stopBackend() {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
}

function waitForBackend(retries = 30) {
  return new Promise((resolve, reject) => {
    function check(i) {
      const req = http.get(`http://127.0.0.1:${PORT}/api/health`, (res) => {
        if (res.statusCode === 200) return resolve()
        if (i > 0) setTimeout(() => check(i - 1), 500)
        else reject(new Error('Backend not ready'))
      })
      req.on('error', () => {
        if (i > 0) setTimeout(() => check(i - 1), 500)
        else reject(new Error('Backend timeout'))
      })
      req.setTimeout(2000, () => { req.destroy(); if (i > 0) setTimeout(() => check(i - 1), 500) })
    }
    check(retries)
  })
}

// ── ComfyUI management ──
const COMFYUI_PORT = 8188
const COMFYUI_DIR = 'D:\\ComfyUI'
const COMFYUI_PYTHON = path.join(COMFYUI_DIR, '.venv', 'Scripts', 'python.exe')

function startComfyUI() {
  const fs = require('fs')
  if (!fs.existsSync(COMFYUI_PYTHON)) {
    console.log(`ComfyUI Python not found: ${COMFYUI_PYTHON} — skipping`)
    return
  }
  if (!fs.existsSync(path.join(COMFYUI_DIR, 'main.py'))) {
    console.log(`ComfyUI main.py not found in ${COMFYUI_DIR} — skipping`)
    return
  }
  // Validate the venv Python actually runs (handles broken relocated venvs)
  const probe = require('child_process').spawnSync(COMFYUI_PYTHON, ['--version'], { encoding: 'utf8' })
  if (probe.status !== 0) {
    console.log(`ComfyUI Python validation failed — skipping`)
    console.log(probe.stderr || probe.error?.message || '')
    return
  }

  console.log(`Starting ComfyUI: ${COMFYUI_PYTHON} ${COMFYUI_DIR}`)
  comfyuiProcess = spawn(COMFYUI_PYTHON, ['main.py', '--listen', '127.0.0.1', '--port', String(COMFYUI_PORT)], {
    cwd: COMFYUI_DIR,
    env: { ...process.env },
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  comfyuiProcess.stdout.on('data', (d) => console.log(`[comfyui] ${d}`))
  comfyuiProcess.stderr.on('data', (d) => console.error(`[comfyui] ${d}`))
  comfyuiProcess.on('exit', (code) => {
    console.log(`ComfyUI exited: ${code}`)
    if (!isQuitting) {
      console.log('Restarting ComfyUI in 3s...')
      setTimeout(startComfyUI, 3000)
    }
  })
}

function stopComfyUI() {
  if (comfyuiProcess) {
    comfyuiProcess.kill()
    comfyuiProcess = null
  }
}

function waitForComfyUI(retries = 40) {
  return new Promise((resolve, reject) => {
    function check(i) {
      const req = http.get(`http://127.0.0.1:${COMFYUI_PORT}/system_stats`, (res) => {
        if (res.statusCode === 200) return resolve()
        if (i > 0) setTimeout(() => check(i - 1), 1000)
        else reject(new Error('ComfyUI not ready'))
      })
      req.on('error', () => {
        if (i > 0) setTimeout(() => check(i - 1), 1000)
        else reject(new Error('ComfyUI timeout'))
      })
      req.setTimeout(3000, () => { req.destroy(); if (i > 0) setTimeout(() => check(i - 1), 1000) })
    }
    check(retries)
  })
}

// ── Window ──
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1300,
    height: 760,
    minWidth: 900,
    minHeight: 600,
    frame: true,
    show: true,
    backgroundColor: '#0a0e14',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  // DevTools shortcut: F12 or Ctrl+Shift+I
  if (enableDevTools) {
    mainWindow.webContents.on('before-input-event', (_, input) => {
      if ((input.key === 'F12') || (input.control && input.shift && input.key === 'I')) {
        mainWindow.webContents.toggleDevTools()
      }
    })
  }

  // Log page console to terminal for debugging white screen
  mainWindow.webContents.on('console-message', (_, level, message) => {
    const levels = ['VERBOSE', 'INFO', 'WARN', 'ERROR']
    console.log(`[renderer ${levels[level] || '?'}] ${message}`)
  })

  // Show errors if page fails to load
  mainWindow.webContents.on('did-fail-load', (_, errorCode, errorDescription, validatedURL) => {
    console.error(`Page load failed: ${errorDescription} (${errorCode}) at ${validatedURL}`)
    // Load an error page showing diagnostic info
    mainWindow.loadURL(`data:text/html,
      <html><body style="font-family:monospace;background:#1a1f25;color:#f44;padding:40px">
      <h2>⚠ 无法连接到服务</h2>
      <p>请确认后端服务已启动 (端口 ${PORT})</p>
      <p>错误: ${errorDescription} (${errorCode})</p>
      <p>URL: ${validatedURL}</p>
      <p style="color:#888;margin-top:30px">按 F12 打开开发者工具查看更多信息</p>
      </body></html>
    `)
  })

  mainWindow.loadURL(isDev ? `http://localhost:${FRONTEND_PORT}` : `http://127.0.0.1:${PORT}/`)

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    mainWindow.focus()
    if (enableDevTools) {
      mainWindow.webContents.openDevTools({ mode: 'detach' })
    }
  })

  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault()
      mainWindow.hide()
    }
  })

  mainWindow.on('closed', () => { mainWindow = null })

  // Resize embedded platform views when main window resizes
  mainWindow.on('resize', () => resizePlatformViews())
}

// ── Tray ──
function createTray() {
  // Create a visible tray icon (blue square) so user can find it
  const icon = nativeImage.createFromBuffer(
    Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAOVJREFUWEftlrENwjAURM9WoGAGSkbICIyARMoKGSEjMAIlI2QERqBkBEaA/wRIlmTZloPvJAqkF7/v+/d9dhzDMAxKqS2AHTADygB4C9xzzq9CCGutBzAFHoAVsBMRTym9c84fEXkCmwj4BDa+718BNsBGRO4islFKJ2AKvE3At4g8ABvgFgEH4M33/SuwBpYi8goci8gG2BqBPbA2Ag/B/C3a+L5fy+8V5gXITUBdQLoAawGE1gSEbQR4DIDBPYXGMyPwCfjzPBhGAeFLTkBrANgABMAW+HLBVwBcA+AT8AUvL8Cg5aGbGgAAAABJRU5ErkJggg==',
      'base64'
    )
  )
  tray = new Tray(icon.resize({ width: 16, height: 16 }))
  tray.setToolTip('szyg - Double-click to show')
  const menu = Menu.buildFromTemplate([
    { label: '打开主窗口', click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { label: '重新加载', click: () => { mainWindow?.reload() } },
    { type: 'separator' },
    { label: '退出 szyg', click: () => { isQuitting = true; app.quit() } },
  ])
  tray.setContextMenu(menu)
  tray.on('double-click', () => { mainWindow?.show(); mainWindow?.focus() })
}

// ── IPC handlers (for preload.js) ──
const { ipcMain } = require('electron')
ipcMain.on('window-minimize', () => mainWindow?.minimize())
ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.restore()
  else mainWindow?.maximize()
})
ipcMain.on('window-close', () => mainWindow?.close())
ipcMain.handle('window-is-maximized', () => mainWindow?.isMaximized() ?? false)
ipcMain.handle('get-version', () => app.getVersion())

// ── Platform BrowserView IPC handlers ──
ipcMain.handle('platform-open', (event, platform, url) => {
  const view = openPlatformView(platform, url)
  return { success: !!view, webContentsId: view?.webContents.id ?? null }
})
ipcMain.on('platform-close', (event, platform) => closePlatformView(platform))
ipcMain.handle('platform-cookies', async (event, platform, filterUrl) => {
  const view = platformViews.get(platform)
  if (!view) return []
  try {
    const cookies = await view.webContents.session.cookies.get(filterUrl ? { url: filterUrl } : {})
    return cookies
  } catch (e) {
    console.error(`[BrowserView] Failed to get cookies for ${platform}:`, e)
    return []
  }
})
ipcMain.handle('platform-inject', async (event, platform, script) => {
  const view = platformViews.get(platform)
  if (!view) return { success: false, error: 'View not found' }
  try {
    const result = await view.webContents.executeJavaScript(script, true)
    return { success: true, result }
  } catch (e) {
    console.error(`[BrowserView] Inject failed for ${platform}:`, e)
    return { success: false, error: e.message }
  }
})
ipcMain.handle('platform-get-url', (event, platform) => {
  const view = platformViews.get(platform)
  return view ? view.webContents.getURL() : ''
})
ipcMain.handle('platform-list', () => {
  return Array.from(platformViews.keys())
})

// ── App lifecycle ──
app.whenReady().then(async () => {
  createTray()
  startBackend()
  startComfyUI()
  try {
    await waitForBackend(40)
    console.log('Backend ready')
  } catch (e) {
    console.error('Backend failed to start:', e.message)
  }
  try {
    await waitForComfyUI(40)
    console.log('ComfyUI ready')
  } catch (e) {
    console.error('ComfyUI failed to start:', e.message)
  }
  createWindow()
})

app.on('before-quit', () => {
  isQuitting = true
  closeAllPlatformViews()
  stopBackend()
  stopComfyUI()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

} // end single instance lock
