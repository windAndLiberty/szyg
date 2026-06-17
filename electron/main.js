const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')
const net = require('net')

const isDev = process.env.NODE_ENV === 'development'
const PORT = 8000
const FRONTEND_PORT = 5173

let mainWindow = null
let tray = null
let backendProcess = null
let isQuitting = false

// ── Single instance lock ──
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) { app.quit() } else {

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  }
})

// ── Backend management ──
function findPython() {
  const venv = path.join(process.resourcesPath, '..', '..', '..', 'hermes-agent', 'venv', 'Scripts', 'python.exe')
  const candidates = [
    path.join(__dirname, '..', '..', '..', '..', '..', 'Users', 'Administrator', 'AppData', 'Local', 'hermes', 'hermes-agent', 'venv', 'Scripts', 'python.exe'),
    venv,
    'python',
    'python3',
  ]
  for (const c of candidates) {
    if (require('fs').existsSync(c)) return c
  }
  return 'python'
}

function startBackend() {
  const python = findPython()
  const serverDir = path.join(__dirname, '..', 'server')
  const projectRoot = path.join(__dirname, '..')
  const env = {
    ...process.env,
    PYTHONPATH: path.join(__dirname, '..', 'server'),   // szyg package lives in server/
    SZYG_DATA_DIR: path.join(__dirname, '..', 'data'),
  }

  console.log(`Starting backend: ${python} - ${serverDir}`)
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

// ── Window ──
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1300,
    height: 760,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    show: false,
    backgroundColor: '#1a1f25',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  mainWindow.loadURL(isDev ? `http://localhost:${FRONTEND_PORT}` : `http://127.0.0.1:${PORT}/login`)

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    mainWindow.focus()
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
  const icon = nativeImage.createEmpty()
  tray = new Tray(icon.resize({ width: 16, height: 16 }))
  tray.setToolTip('szyg 智能矩阵运营系统')
  const menu = Menu.buildFromTemplate([
    { label: '打开主窗口', click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { type: 'separator' },
    { label: '退出 szyg', click: () => { isQuitting = true; app.quit() } },
  ])
  tray.setContextMenu(menu)
  tray.on('double-click', () => { mainWindow?.show(); mainWindow?.focus() })
}

// ── IPC handlers for frameless window controls ──
ipcMain.on('window-minimize', () => mainWindow?.minimize())
ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize()
  else mainWindow?.maximize()
})
ipcMain.on('window-close', () => { mainWindow?.hide() })
ipcMain.handle('window-is-maximized', () => mainWindow?.isMaximized() ?? false)

// ── App lifecycle ──
app.whenReady().then(async () => {
  createTray()
  if (!isDev) {
    startBackend()
    try {
      await waitForBackend(40)
      console.log('Backend ready')
    } catch (e) {
      console.error('Backend failed to start:', e.message)
    }
  } else {
    console.log('Dev mode — using existing backend on :8000')
  }
  createWindow()
})

app.on('before-quit', () => {
  isQuitting = true
  stopBackend()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

} // end single instance lock
