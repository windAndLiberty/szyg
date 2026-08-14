const { app, BrowserWindow, Tray, Menu, nativeImage, session, shell } = require('electron')
const { spawn } = require('child_process')
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const http = require('http')
const net = require('net')
const { BrowserSessionManager } = require('./browser/browser-session-manager')
const { startBrowserControlServer } = require('./browser/browser-control-server')

const APP_ICON_PATH = path.join(__dirname, 'assets', 'app-icon.png')
const TRAY_ICON_PATH = path.join(__dirname, 'assets', 'tray-icon.png')

// Disable GPU acceleration for RDP/VM compatibility
// Falls back to software rendering — works everywhere
app.disableHardwareAcceleration()

const isDev = process.env.NODE_ENV === 'development'
const enableDevTools = isDev || process.env.SZYG_DEBUG === '1'

// Keep local user data compatible with earlier SZYG builds after the product rename.
app.setPath('userData', path.join(app.getPath('appData'), 'szyg'))

let PORT = 8000
const FRONTEND_PORT = 5173
const PRODUCTION_CONTROL_URL = 'https://szyg.qdtracing.com'

let mainWindow = null
let tray = null
let backendProcess = null
let isQuitting = false
const desktopToken = crypto.randomBytes(32).toString('hex')
const browserControlToken = crypto.randomBytes(32).toString('hex')
let browserControlUrl = ''
let browserControlServer = null
const blockedBrowserOrigins = [
  `http://localhost:${FRONTEND_PORT}`,
  `http://127.0.0.1:${FRONTEND_PORT}`,
  ...Array.from({ length: 11 }, (_, index) => `http://127.0.0.1:${8000 + index}`),
]
const browserManager = new BrowserSessionManager({ blockedOrigins: blockedBrowserOrigins })

function getProjectRoot() {
  return isDev ? path.join(__dirname, '..') : process.resourcesPath
}

function getRuntimeDataDir() {
  return isDev ? path.join(getProjectRoot(), 'data') : path.join(app.getPath('userData'), 'data')
}

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
  const projectRoot = getProjectRoot()
  const localAppData = process.env.LOCALAPPDATA || path.join(app.getPath('home'), 'AppData', 'Local')

  const candidates = [
    // 1. Project virtual environment
    path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    // 2. hermes-agent venv (fallback, has CUDA + most deps)
    path.join(localAppData, 'hermes', 'hermes-agent', 'venv', 'Scripts', 'python.exe'),
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

function sha256File(file) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256')
    const stream = fs.createReadStream(file)
    stream.on('error', reject)
    stream.on('data', (chunk) => hash.update(chunk))
    stream.on('end', () => resolve(hash.digest('hex')))
  })
}

async function verifyRuntimeIntegrity() {
  if (isDev) return
  const manifestPath = path.join(process.resourcesPath, 'runtime-integrity.json')
  if (!fs.existsSync(manifestPath)) throw new Error('Runtime integrity manifest is missing')
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
  for (const entry of manifest.entries || []) {
    const target = path.resolve(process.resourcesPath, entry.path)
    if (!target.startsWith(path.resolve(process.resourcesPath) + path.sep)) {
      throw new Error('Runtime integrity manifest contains an invalid path')
    }
    if (!fs.existsSync(target)) throw new Error(`Required runtime file is missing: ${entry.path}`)
    if (fs.statSync(target).size !== entry.size || await sha256File(target) !== entry.sha256) {
      throw new Error(`Runtime integrity verification failed: ${entry.path}`)
    }
  }
}

async function startBackend() {
  await verifyRuntimeIntegrity()
  if (await isPortInUse(PORT)) {
    if (isDev) {
      console.log(`Backend already running on port ${PORT}, skipping spawn`)
      return
    }
    let availablePort = null
    for (let candidate = 8001; candidate <= 8010; candidate += 1) {
      if (!await isPortInUse(candidate)) {
        availablePort = candidate
        break
      }
    }
    if (!availablePort) throw new Error('No local service port is available')
    PORT = availablePort
  }

  const projectRoot = getProjectRoot()
  const runtimeDataDir = getRuntimeDataDir()
  const serverDir = path.join(projectRoot, 'server')
  const backendExecutable = path.join(process.resourcesPath, 'backend', 'szyg-backend.exe')
  const env = {
    ...process.env,
    PYTHONPATH: serverDir,
    SZYG_DATA_DIR: runtimeDataDir,
    SZYG_AUTH_DB: path.join(runtimeDataDir, 'auth.db'),
    SZYG_SAU_RUNTIME_HOME: path.join(runtimeDataDir, 'social_auto_upload'),
    SZYG_CLOUD_ENABLED: process.env.SZYG_CLOUD_ENABLED || 'true',
    SZYG_CONTROL_URL: process.env.SZYG_CONTROL_URL || PRODUCTION_CONTROL_URL,
    SZYG_APP_VERSION: app.getVersion(),
    SZYG_LOCAL_AUTH_ENABLED: isDev ? (process.env.SZYG_LOCAL_AUTH_ENABLED || 'false') : 'false',
    SZYG_PRODUCTION: isDev ? 'false' : 'true',
    SZYG_DESKTOP_TOKEN: desktopToken,
    SZYG_BROWSER_CONTROL_URL: browserControlUrl,
    SZYG_BROWSER_CONTROL_TOKEN: browserControlToken,
    SZYG_BACKEND_PORT: String(PORT),
    SZYG_SECRET_KEY: isDev ? (process.env.SZYG_SECRET_KEY || '') : crypto.randomBytes(48).toString('base64url'),
    SZYG_CONFIG_PATH: path.join(projectRoot, 'config.yaml'),
    SZYG_FRONTEND_DIST: isDev
      ? path.join(projectRoot, 'szyg-frontend', 'dist')
      : path.join(process.resourcesPath, 'frontend'),
    SZYG_LLAMA_RUNTIME_DIR: isDev
      ? path.join(projectRoot, 'runtime', 'llama')
      : path.join(process.resourcesPath, 'runtime', 'llama'),
    SZYG_LOCAL_MODEL_DIR: path.join(runtimeDataDir, 'local_models'),
    SZYG_CHROMIUM_DIR: isDev
      ? path.join(projectRoot, 'server', 'szyg', 'storage', 'chromium')
      : path.join(process.resourcesPath, 'runtime', 'chromium'),
    SZYG_NODE_EXECUTABLE: isDev ? (process.env.SZYG_NODE_EXECUTABLE || '') : process.execPath,
    SZYG_HERMES_RUNTIME_EXECUTABLE: isDev
      ? (process.env.SZYG_HERMES_RUNTIME_EXECUTABLE || '')
      : path.join(process.resourcesPath, 'runtime', 'hermes', 'hermes-runtime.exe'),
    SZYG_CUA_DRIVER_PATH: isDev
      ? path.join(projectRoot, 'electron', 'providers', 'cua', 'cua-driver.exe')
      : path.join(process.resourcesPath, 'runtime', 'cua', 'cua-driver.exe'),
    SZYG_CORS_ORIGINS: isDev
      ? 'http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:8000'
      : `http://127.0.0.1:${PORT}`,
    // Force the packaged patchright browser registry to the bundle-internal
    // `.local-browsers` directory (see szyg-backend.spec). Without this,
    // patchright resolves chromium-1208 from %LOCALAPPDATA%\ms-playwright,
    // which does not exist on end-user machines, breaking account login and
    // publishing with "Executable doesn't exist".
    PLAYWRIGHT_BROWSERS_PATH: isDev ? (process.env.PLAYWRIGHT_BROWSERS_PATH || '') : '0',
  }

  let command
  let args
  if (isDev) {
    command = findPython()
    args = ['-m', 'uvicorn', 'szyg.api.app:create_app', '--host', '127.0.0.1', '--port', String(PORT), '--factory']
  } else {
    if (!fs.existsSync(backendExecutable)) {
      throw new Error('The bundled backend runtime is missing')
    }
    command = backendExecutable
    args = []
  }

  console.log(`Starting backend: ${command}`)
  backendProcess = spawn(command, args, {
    cwd: projectRoot,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
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
      const endpoint = isDev ? '/api/health' : '/api/config'
      const req = http.get({
        hostname: '127.0.0.1',
        port: PORT,
        path: endpoint,
        headers: isDev ? {} : { 'X-SZYG-Desktop-Token': desktopToken },
      }, (res) => {
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

// ── Window ──
async function createWindow() {
  await session.defaultSession.cookies.set({
    url: isDev ? `http://localhost:${FRONTEND_PORT}` : `http://127.0.0.1:${PORT}`,
    name: 'szyg_desktop_token',
    value: desktopToken,
    httpOnly: true,
    sameSite: 'strict',
  })

  mainWindow = new BrowserWindow({
    width: 1300,
    height: 760,
    minWidth: 900,
    minHeight: 600,
    frame: true,
    autoHideMenuBar: true,
    show: true,
    icon: APP_ICON_PATH,
    backgroundColor: '#0a0e14',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  })
  // 去掉系统级顶栏菜单（File/Edit/...），只保留业务界面
  if (process.platform !== 'darwin') {
    Menu.setApplicationMenu(null)
  } else {
    // macOS 无法彻底去掉菜单栏，改用最简菜单（仅应用名：关于/隐藏/退出）
    Menu.setApplicationMenu(
      Menu.buildFromTemplate([
        {
          label: app.name,
          submenu: [
            { role: 'about', label: `关于 ${app.name}` },
            { type: 'separator' },
            { role: 'hide', label: `隐藏 ${app.name}` },
            { role: 'hideOthers', label: '隐藏其他' },
            { role: 'unhide', label: '全部显示' },
            { type: 'separator' },
            { role: 'quit', label: `退出 ${app.name}` },
          ],
        },
      ])
    )
  }
  browserManager.setHostWindow(mainWindow)

  // DevTools shortcut: F12 or Ctrl+Shift+I
  if (enableDevTools) {
    mainWindow.webContents.on('before-input-event', (_, input) => {
      if ((input.key === 'F12') || (input.control && input.shift && input.key === 'I')) {
        mainWindow.webContents.toggleDevTools()
      }
    })
  }

  if (enableDevTools) {
    mainWindow.webContents.on('console-message', (_, level, message) => {
      const levels = ['VERBOSE', 'INFO', 'WARN', 'ERROR']
      console.log(`[renderer ${levels[level] || '?'}] ${message}`)
    })
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) shell.openExternal(url)
    return { action: 'deny' }
  })
  mainWindow.webContents.on('will-navigate', (event, url) => {
    const allowed = isDev
      ? url.startsWith(`http://localhost:${FRONTEND_PORT}`)
      : url.startsWith(`http://127.0.0.1:${PORT}`)
    if (!allowed && !url.startsWith('data:')) {
      event.preventDefault()
      if (/^https?:\/\//i.test(url)) shell.openExternal(url)
    }
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

  mainWindow.on('closed', () => {
    browserManager.setHostWindow(null)
    mainWindow = null
  })
}

// ── Tray ──
function createTray() {
  const icon = nativeImage.createFromPath(TRAY_ICON_PATH)
  tray = new Tray(icon.resize({ width: 16, height: 16 }))
  tray.setToolTip('领鹿员工 - 双击打开')
  const menu = Menu.buildFromTemplate([
    { label: '打开主窗口', click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { label: '重新加载', click: () => { mainWindow?.reload() } },
    { type: 'separator' },
    { label: '退出领鹿员工', click: () => { isQuitting = true; app.quit() } },
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
ipcMain.handle('browser-set-visible', (_event, visible) => browserManager.setVisible(visible))
ipcMain.handle('browser-set-bounds', (_event, bounds) => browserManager.setBounds(bounds))
ipcMain.handle('browser-state', () => browserManager.state())
ipcMain.handle('browser-action', (_event, payload) => browserManager.action(payload || {}))

// ── App lifecycle ──
app.whenReady().then(async () => {
  createTray()
  const browserControl = await startBrowserControlServer(browserManager, browserControlToken)
  browserControlServer = browserControl.server
  browserControlUrl = browserControl.url
  try {
    await startBackend()
    await waitForBackend(40)
    console.log('Backend ready')
  } catch (e) {
    console.error('Backend failed to start:', e.message)
  }
  await createWindow()
})

app.on('before-quit', () => {
  isQuitting = true
  browserManager.destroy()
  browserControlServer?.close()
  browserControlServer = null
  stopBackend()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

} // end single instance lock
