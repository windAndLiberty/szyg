const { app, BrowserWindow, Tray, Menu, nativeImage, session, shell } = require('electron')
const { spawn } = require('child_process')
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const http = require('http')
const net = require('net')

// Disable GPU acceleration for RDP/VM compatibility
// Falls back to software rendering — works everywhere
app.disableHardwareAcceleration()

const isDev = process.env.NODE_ENV === 'development'
const enableDevTools = isDev || process.env.SZYG_DEBUG === '1'
const PORT = 8000
const FRONTEND_PORT = 5173
const PRODUCTION_CONTROL_URL = 'https://szyg.qdtracing.com'

let mainWindow = null
let tray = null
let backendProcess = null
let comfyuiProcess = null
let isQuitting = false
const desktopToken = crypto.randomBytes(32).toString('hex')

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

async function startBackend() {
  if (await isPortInUse(PORT)) {
    if (isDev) {
      console.log(`Backend already running on port ${PORT}, skipping spawn`)
      return
    }
    throw new Error(`Local service port ${PORT} is already in use`)
  }

  const projectRoot = getProjectRoot()
  const runtimeDataDir = getRuntimeDataDir()
  const serverDir = path.join(projectRoot, 'server')
  const backendExecutable = path.join(process.resourcesPath, 'backend', 'szyg-backend.exe')
  const env = {
    ...process.env,
    PYTHONPATH: serverDir,
    SZYG_DATA_DIR: runtimeDataDir,
    SZYG_CLOUD_ENABLED: isDev ? (process.env.SZYG_CLOUD_ENABLED || 'false') : 'true',
    SZYG_CONTROL_URL: isDev ? (process.env.SZYG_CONTROL_URL || '') : PRODUCTION_CONTROL_URL,
    SZYG_LOCAL_AUTH_ENABLED: isDev ? (process.env.SZYG_LOCAL_AUTH_ENABLED || 'false') : 'false',
    SZYG_PRODUCTION: isDev ? 'false' : 'true',
    SZYG_DESKTOP_TOKEN: desktopToken,
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
    SZYG_CORS_ORIGINS: isDev
      ? 'http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:8000'
      : 'http://127.0.0.1:8000',
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

// ── ComfyUI management ──
const COMFYUI_PORT = 8188
const COMFYUI_DIR = process.env.SZYG_COMFYUI_DIR || ''
const COMFYUI_PYTHON = COMFYUI_DIR ? path.join(COMFYUI_DIR, '.venv', 'Scripts', 'python.exe') : ''

function startComfyUI() {
  const fs = require('fs')
  if (!COMFYUI_DIR) {
    console.log('ComfyUI is not configured - skipping')
    return
  }
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
async function createWindow() {
  if (!isDev) {
    await session.defaultSession.cookies.set({
      url: `http://127.0.0.1:${PORT}`,
      name: 'szyg_desktop_token',
      value: desktopToken,
      httpOnly: true,
      sameSite: 'strict',
    })
  }

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
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
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

  mainWindow.on('closed', () => { mainWindow = null })
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
  await createWindow()
})

app.on('before-quit', () => {
  isQuitting = true
  stopBackend()
  stopComfyUI()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

} // end single instance lock
