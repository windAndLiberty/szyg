const { app, BrowserWindow, Tray, Menu, nativeImage, session, shell, safeStorage } = require('electron')
const { spawn } = require('child_process')
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const http = require('http')
const net = require('net')
const { BrowserSessionManager } = require('./browser/browser-session-manager')
const { startBrowserControlServer } = require('./browser/browser-control-server')
const { OpenClawRuntimeManager } = require('./openclaw/runtime-manager')
const product = require('./product')

const APP_ICON_PATH = path.join(__dirname, 'assets', product.icon)
const TRAY_ICON_PATH = path.join(__dirname, 'assets', product.trayIcon)

// Chromium can select the appropriate GPU/software backend by itself. Disabling
// acceleration globally also disables compositor rendering, which can turn the
// main window black during wheel-driven repaints on some Windows machines.
// Keep an explicit escape hatch for genuinely incompatible RDP/VM environments.
if (process.env.SZYG_DISABLE_GPU === '1') {
  app.disableHardwareAcceleration()
}

const isDev = process.env.NODE_ENV === 'development'
const enableDevTools = isDev || process.env.SZYG_DEBUG === '1'

// The two products share runtime code while keeping local sessions and data isolated.
app.setPath('userData', path.join(app.getPath('appData'), product.userDataDirectory))
app.setAppUserModelId(product.appUserModelId)

let PORT = 8000
const FRONTEND_PORT = 5173
const PRODUCTION_CONTROL_URL = ''

let mainWindow = null
let tray = null
let backendProcess = null
let backendWatcher = null
let backendRestartTimer = null
let isQuitting = false
let backendReady = false
let backendLaunchError = ''
let openClawRuntime = null
let startupGateActive = true
const desktopToken = crypto.randomBytes(32).toString('hex')
const browserControlToken = crypto.randomBytes(32).toString('hex')
const businessMcpToken = crypto.randomBytes(32).toString('hex')
const openClawModelToken = crypto.randomBytes(32).toString('hex')
let browserControlUrl = ''
let browserControlServer = null
let currentUiLocale = 'zh-CN'
const BACKEND_STARTUP_RETRIES = 180
const blockedBrowserOrigins = [
  `http://localhost:${FRONTEND_PORT}`,
  `http://127.0.0.1:${FRONTEND_PORT}`,
  ...Array.from({ length: 11 }, (_, index) => `http://127.0.0.1:${8000 + index}`),
]
const browserManager = new BrowserSessionManager({ blockedOrigins: blockedBrowserOrigins })

function productDisplayName(locale = currentUiLocale) {
  return locale === 'en-US' ? (product.englishName || product.name) : product.name
}

function productWindowTitle(locale = currentUiLocale) {
  const suffix = locale === 'en-US' ? 'Super Digital Workforce' : '超级数字员工'
  return `${productDisplayName(locale)} - ${suffix}`
}

function updateApplicationMenu() {
  if (process.platform !== 'darwin') {
    Menu.setApplicationMenu(null)
    return
  }
  const name = productDisplayName()
  const english = currentUiLocale === 'en-US'
  Menu.setApplicationMenu(Menu.buildFromTemplate([{
    label: name,
    submenu: [
      { role: 'about', label: english ? `About ${name}` : `关于 ${name}` },
      { type: 'separator' },
      { role: 'hide', label: english ? `Hide ${name}` : `隐藏 ${name}` },
      { role: 'hideOthers', label: english ? 'Hide Others' : '隐藏其他' },
      { role: 'unhide', label: english ? 'Show All' : '全部显示' },
      { type: 'separator' },
      { role: 'quit', label: english ? `Quit ${name}` : `退出 ${name}` },
    ],
  }]))
}

function updateTrayBranding() {
  if (!tray) return
  const name = productDisplayName()
  const english = currentUiLocale === 'en-US'
  tray.setToolTip(english ? `${name} - Double-click to open` : `${name} - 双击打开`)
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: english ? 'Open main window' : '打开主窗口', click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { label: english ? 'Reload' : '重新加载', click: () => { mainWindow?.reload() } },
    { type: 'separator' },
    { label: english ? `Quit ${name}` : `退出${name}`, click: () => { isQuitting = true; app.quit() } },
  ]))
}

function getProjectRoot() {
  return isDev ? path.join(__dirname, '..') : process.resourcesPath
}

function getRuntimeDataDir() {
  if (!isDev) return path.join(app.getPath('userData'), 'data')
  // Keep the public Xiaoyu development state isolated from the legacy private
  // product while preserving the existing private development data location.
  return product.id === 'xiaoyu_public'
    ? path.join(getProjectRoot(), 'data', 'xiaoyu_public')
    : path.join(getProjectRoot(), 'data')
}

function ensureRuntimeDataDir() {
  const runtimeDataDir = getRuntimeDataDir()
  fs.mkdirSync(runtimeDataDir, { recursive: true })
  // Fail before spawning the frozen Python runtime if the current Windows
  // account cannot write its own application-data directory. Installation
  // directories are intentionally never used for mutable state.
  const probePath = path.join(runtimeDataDir, `.write-probe-${process.pid}-${Date.now()}`)
  fs.writeFileSync(probePath, '')
  fs.rmSync(probePath, { force: true })
  return runtimeDataDir
}

function getDesktopLogPath() {
  return path.join(getRuntimeDataDir(), 'logs', 'desktop.log')
}

function writeDesktopLog(message) {
  const timestamp = new Date().toISOString()
  try {
    const logPath = getDesktopLogPath()
    fs.mkdirSync(path.dirname(logPath), { recursive: true })
    fs.appendFileSync(logPath, `[${timestamp}] ${message}\n`, 'utf8')
  } catch (_) {
    // A diagnostic write must never prevent the app from starting.
  }
}

function getBundledFfmpegPath(projectRoot) {
  const candidate = isDev
    ? path.join(projectRoot, 'runtime', 'ffmpeg', 'ffmpeg.exe')
    : path.join(process.resourcesPath, 'runtime', 'ffmpeg', 'ffmpeg.exe')
  return fs.existsSync(candidate) ? candidate : ''
}

function dataPage(html) {
  return `data:text/html;charset=utf-8,${encodeURIComponent(html)}`
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function startupCopy() {
  if (currentUiLocale === 'en-US') {
    return {
      brand: productDisplayName(),
      title: 'AI engine starting',
      status: 'Preparing the local service...',
      detail: 'The runtime is being prepared or the gateway is being restored. The first launch and launches after an upgrade can take longer. Please wait.',
      note: 'The workspace will open automatically when everything is ready.',
    }
  }
  return {
    brand: productDisplayName(),
    title: 'AI 引擎启动中',
    status: '正在准备本地服务...',
    detail: '正在准备运行环境或恢复网关，首次启动和升级后可能需要较长时间，请稍候。',
    note: '全部组件就绪后将自动进入工作台。',
  }
}

async function loadStartupPage() {
  const copy = startupCopy()
  await mainWindow?.loadURL(dataPage(`
    <!doctype html>
    <html lang="${currentUiLocale}">
      <head>
        <meta charset="utf-8">
        <meta name="color-scheme" content="dark">
        <style>
          *{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;overflow:hidden;background:radial-gradient(circle at 70% 20%,rgba(79,70,229,.18),transparent 36%),#080d17;color:#e5e7eb;font-family:'Microsoft YaHei',Inter,system-ui,sans-serif}
          .shell{width:min(560px,calc(100vw - 48px));padding:42px;border:1px solid rgba(99,102,241,.22);border-radius:24px;background:rgba(15,23,42,.86);box-shadow:0 28px 80px rgba(0,0,0,.38);backdrop-filter:blur(16px)}
          .brand{display:flex;align-items:center;gap:10px;color:#a5b4fc;font-size:13px;letter-spacing:.12em;text-transform:uppercase}.mark{width:10px;height:10px;border-radius:50%;background:#6366f1;box-shadow:0 0 20px #818cf8}
          h1{margin:24px 0 10px;font-size:28px;line-height:1.25}.status{margin:0;color:#c7d2fe;font-size:16px}.detail{margin:18px 0 0;color:#94a3b8;font-size:14px;line-height:1.8}.note{margin:24px 0 0;color:#64748b;font-size:12px}
          .track{height:4px;margin-top:30px;overflow:hidden;border-radius:99px;background:#1e293b}.bar{width:38%;height:100%;border-radius:inherit;background:linear-gradient(90deg,#4f46e5,#67e8f9);animation:move 1.7s ease-in-out infinite}
          @keyframes move{0%{transform:translateX(-105%)}50%{transform:translateX(175%)}100%{transform:translateX(-105%)}}
          @media (prefers-reduced-motion:reduce){.bar{animation:none;width:100%;opacity:.65}}
        </style>
      </head>
      <body>
        <main class="shell" role="status" aria-live="polite">
          <div class="brand"><span class="mark"></span><span>${escapeHtml(copy.brand)}</span></div>
          <h1>${escapeHtml(copy.title)}</h1>
          <p class="status" id="startup-status">${escapeHtml(copy.status)}</p>
          <p class="detail" id="startup-detail">${escapeHtml(copy.detail)}</p>
          <div class="track" aria-hidden="true"><div class="bar"></div></div>
          <p class="note">${escapeHtml(copy.note)}</p>
        </main>
      </body>
    </html>
  `))
}

async function updateStartupPage(status, detail = startupCopy().detail) {
  if (!startupGateActive || !mainWindow || mainWindow.isDestroyed()) return
  const script = `(() => {
    const status = document.getElementById('startup-status');
    const detail = document.getElementById('startup-detail');
    if (status) status.textContent = ${JSON.stringify(String(status))};
    if (detail) detail.textContent = ${JSON.stringify(String(detail))};
  })()`
  try { await mainWindow.webContents.executeJavaScript(script) } catch (_) {}
}

function startupPhaseCopy(phase) {
  const english = currentUiLocale === 'en-US'
  const rows = english ? {
    backend: ['Starting local services...', 'Checking account, storage, and business services.'],
    gateway: ['AI engine is starting the gateway...', startupCopy().detail],
    repairing: ['AI engine is repairing its runtime...', 'A safe configuration repair is in progress. The workspace will open automatically when ready.'],
    workspace: ['Loading skills and workspace...', 'The AI engine is ready. Xiaoyu is now preparing employee identities, conversations, skills, and local workspace data.'],
    interface: ['Opening Xiaoyu workspace...', 'All core services are ready. The application interface is completing its final load.'],
  } : {
    backend: ['正在启动本地服务...', '正在检查账号、存储与业务服务。'],
    gateway: ['AI 引擎正在启动网关...', startupCopy().detail],
    repairing: ['AI 引擎正在修复运行环境...', '正在安全修复本地配置，完成后将自动进入工作台。'],
    workspace: ['正在加载技能和工作区...', 'AI 引擎已就绪，正在准备员工身份、对话、技能与本地工作区数据。'],
    interface: ['正在打开小妤工作台...', '核心服务已全部就绪，应用界面正在完成最后加载。'],
  }
  return rows[phase] || rows.gateway
}

async function showStartupPhase(phase) {
  const [status, detail] = startupPhaseCopy(phase)
  await updateStartupPage(status, detail)
}

function loadBackendErrorPage(errorDescription, errorCode, validatedURL) {
  const logPath = getDesktopLogPath()
  mainWindow?.loadURL(dataPage(`
    <html><body style="margin:0;min-height:100vh;background:#0a0e14;color:#f8fafc;font-family:'Microsoft YaHei',system-ui,sans-serif;padding:48px;box-sizing:border-box">
      <h2 style="margin:0 0 16px;color:#fca5a5">无法启动本地服务</h2>
      <p>数字员工的本地服务尚未成功启动。请退出应用后重新打开；若问题仍存在，请将下方日志文件发送给技术支持。</p>
      <p style="color:#94a3b8">日志：${escapeHtml(logPath)}</p>
      <p style="color:#94a3b8">错误：${escapeHtml(errorDescription)} (${escapeHtml(errorCode)})</p>
      <p style="color:#94a3b8">地址：${escapeHtml(validatedURL)}</p>
    </body></html>
  `))
}

async function showStartupFailure(error) {
  startupGateActive = true
  const english = currentUiLocale === 'en-US'
  const message = String(error?.message || error || (english ? 'Unknown startup error' : '未知启动错误')).slice(0, 800)
  const logPath = getDesktopLogPath()
  const title = english ? 'AI engine could not start' : 'AI 引擎启动失败'
  const status = english ? 'Xiaoyu did not enter the workspace' : '小妤尚未进入工作台'
  const detail = english
    ? `Restart Xiaoyu and try again. If the problem continues, send this log to support: ${logPath}\nError: ${message}`
    : `请重新启动小妤后再试。若问题持续，请将此日志发送给技术支持：${logPath}\n错误：${message}`
  if (!mainWindow || mainWindow.isDestroyed()) return
  const script = `(() => {
    const title = document.querySelector('h1');
    const status = document.getElementById('startup-status');
    const detail = document.getElementById('startup-detail');
    const bar = document.querySelector('.bar');
    const mark = document.querySelector('.mark');
    if (title) title.textContent = ${JSON.stringify(title)};
    if (status) status.textContent = ${JSON.stringify(status)};
    if (detail) { detail.textContent = ${JSON.stringify(detail)}; detail.style.whiteSpace = 'pre-line'; }
    if (bar) { bar.style.animation = 'none'; bar.style.width = '100%'; bar.style.background = '#ef4444'; }
    if (mark) { mark.style.background = '#ef4444'; mark.style.boxShadow = '0 0 20px #ef4444'; }
  })()`
  try { await mainWindow.webContents.executeJavaScript(script) } catch (_) {
    loadBackendErrorPage(message, 'STARTUP_FAILED', '')
  }
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
    mainWindow.show()
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

function ensureBackendWatcher(serverDir) {
  if (!isDev || backendWatcher) return
  // Guard against mtime-only touches (e.g. Syncthing rescans, antivirus,
  // editor temp-file churn) that would otherwise restart the backend on every
  // periodic rescan. We only restart when a .py file's content hash actually
  // changes. The baseline is seeded from every existing .py file at startup so
  // that the first fs.watch event for each file is compared against its real
  // content rather than an empty map (which would always look "changed").
  const fileContentHashes = new Map()
  const ignoredDirectoryNames = new Set([
    '.git',
    '.hermes-venv',
    '.pytest_cache',
    '__pycache__',
    'data',
    'node_modules',
    'vendor',
  ])
  function isIgnoredPath(filePath) {
    const relativePath = path.relative(serverDir, filePath)
    return relativePath.split(path.sep).some((segment) => ignoredDirectoryNames.has(segment))
  }
  function seedFile(filePath) {
    try {
      const content = fs.readFileSync(filePath, 'utf8')
      fileContentHashes.set(filePath, crypto.createHash('sha256').update(content).digest('hex'))
    } catch (_) { /* ignore: file may be unreadable/locked; will be (re)hashed on next event */ }
  }
  function seedRecursive(dir) {
    let entries
    try { entries = fs.readdirSync(dir, { withFileTypes: true }) } catch (_) { return }
    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name)
      if (entry.isDirectory() && !ignoredDirectoryNames.has(entry.name)) seedRecursive(fullPath)
      else if (entry.isFile() && entry.name.endsWith('.py')) seedFile(fullPath)
    }
  }
  seedRecursive(serverDir)
  backendWatcher = fs.watch(serverDir, { recursive: true }, (_eventType, filename) => {
    const changed = String(filename || '')
    if (!changed.endsWith('.py')) return
    const targetPath = path.join(serverDir, changed)
    if (isIgnoredPath(targetPath)) return
    let content
    try {
      content = fs.readFileSync(targetPath, 'utf8')
    } catch (_) {
      return
    }
    const hash = crypto.createHash('sha256').update(content).digest('hex')
    if (fileContentHashes.get(targetPath) === hash) return
    fileContentHashes.set(targetPath, hash)
    clearTimeout(backendRestartTimer)
    backendRestartTimer = setTimeout(() => {
      if (!backendProcess || isQuitting) return
      console.log(`[backend] Source changed (${changed}); restarting...`)
      backendProcess.kill()
    }, 350)
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
  backendReady = false
  backendLaunchError = ''
  const runtimeDataDir = ensureRuntimeDataDir()
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
  const serverDir = path.join(projectRoot, 'server')
  const bundledFfmpegPath = getBundledFfmpegPath(projectRoot)
  const backendExecutable = path.join(process.resourcesPath, 'backend', 'szyg-backend.exe')
  const env = {
    ...process.env,
    PYTHONPATH: serverDir,
    SZYG_DATA_DIR: runtimeDataDir,
    SZYG_USER_HOME: app.getPath('home'),
    SZYG_OMNIHUMAN_MAX_CONCURRENCY: process.env.SZYG_OMNIHUMAN_MAX_CONCURRENCY || '1',
    SZYG_FFMPEG_PATH: process.env.SZYG_FFMPEG_PATH || bundledFfmpegPath,
    SZYG_AUTH_DB: path.join(runtimeDataDir, 'auth.db'),
    SZYG_SAU_RUNTIME_HOME: path.join(runtimeDataDir, 'social_auto_upload'),
    SZYG_CLOUD_ENABLED: process.env.SZYG_CLOUD_ENABLED || 'true',
    SZYG_CONTROL_URL: process.env.SZYG_CONTROL_URL || PRODUCTION_CONTROL_URL,
    SZYG_PRODUCT_ID: product.id,
    SZYG_APP_VERSION: app.getVersion(),
    SZYG_LOCAL_AUTH_ENABLED: isDev ? (process.env.SZYG_LOCAL_AUTH_ENABLED || 'false') : 'false',
    SZYG_PRODUCTION: isDev ? 'false' : 'true',
    SZYG_DESKTOP_TOKEN: desktopToken,
    SZYG_BROWSER_CONTROL_URL: browserControlUrl,
    SZYG_BROWSER_CONTROL_TOKEN: browserControlToken,
    SZYG_BUSINESS_MCP_TOKEN: businessMcpToken,
    SZYG_OPENCLAW_MODEL_TOKEN: openClawModelToken,
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
    args = [
      '-m', 'uvicorn', 'szyg.api.app:create_app',
      '--host', '127.0.0.1', '--port', String(PORT), '--factory',
    ]
    ensureBackendWatcher(serverDir)
  } else {
    if (!fs.existsSync(backendExecutable)) {
      throw new Error('The bundled backend runtime is missing')
    }
    command = backendExecutable
    args = []
  }

  console.log(`Starting backend: ${command}`)
  writeDesktopLog(`Starting backend: ${command} ${args.join(' ')}`)
  backendProcess = spawn(command, args, {
    // A packaged app is commonly installed in Program Files, which is
    // read-only for ordinary users. Third-party libraries sometimes create
    // relative cache files, so give the backend a writable current directory
    // even though every first-party state path is passed explicitly above.
    cwd: isDev ? projectRoot : runtimeDataDir,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })

  backendProcess.stdout.on('data', (d) => {
    const message = String(d).trim()
    console.log(`[backend] ${message}`)
    if (message) writeDesktopLog(`[backend stdout] ${message}`)
  })
  backendProcess.stderr.on('data', (d) => {
    const message = String(d).trim()
    console.error(`[backend] ${message}`)
    if (message) writeDesktopLog(`[backend stderr] ${message}`)
  })
  backendProcess.on('error', (error) => {
    backendLaunchError = `Backend process could not start: ${error.message}`
    writeDesktopLog(backendLaunchError)
  })
  backendProcess.on('exit', (code, signal) => {
    const reason = `Backend exited before it became ready: code=${code ?? 'null'}, signal=${signal ?? 'none'}`
    console.log(backendReady ? reason.replace(' before it became ready', '') : reason)
    writeDesktopLog(backendReady ? reason.replace(' before it became ready', '') : reason)
    if (!backendReady && !isQuitting) {
      backendLaunchError = reason
      return
    }
    if (!isQuitting) {
      console.log('Restarting backend in 2s...')
      setTimeout(startBackend, 2000)
    }
  })
}

function stopBackend() {
  clearTimeout(backendRestartTimer)
  backendRestartTimer = null
  if (backendWatcher) {
    backendWatcher.close()
    backendWatcher = null
  }
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
}

function waitForBackend(retries = 30) {
  return new Promise((resolve, reject) => {
    function check(i) {
      if (backendLaunchError) return reject(new Error(backendLaunchError))
      const endpoint = isDev ? '/api/health' : '/api/config'
      const req = http.get({
        hostname: '127.0.0.1',
        port: PORT,
        path: endpoint,
        headers: isDev ? {} : { 'X-SZYG-Desktop-Token': desktopToken },
      }, (res) => {
        if (res.statusCode === 200) {
          backendReady = true
          writeDesktopLog(`Backend ready on http://127.0.0.1:${PORT}${endpoint}`)
          return resolve()
        }
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
    url: isDev ? `http://127.0.0.1:${FRONTEND_PORT}` : `http://127.0.0.1:${PORT}`,
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
    show: false,
    title: productWindowTitle(),
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
  // Keep native menus aligned with the language selected in the renderer.
  updateApplicationMenu()
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
      ? url.startsWith(`http://127.0.0.1:${FRONTEND_PORT}`)
      : url.startsWith(`http://127.0.0.1:${PORT}`)
    if (!allowed && !url.startsWith('data:')) {
      event.preventDefault()
      if (/^https?:\/\//i.test(url)) shell.openExternal(url)
    }
  })

  // Show errors if page fails to load
  mainWindow.webContents.on('did-fail-load', (_, errorCode, errorDescription, validatedURL) => {
    console.error(`Page load failed: ${errorDescription} (${errorCode}) at ${validatedURL}`)
    if (startupGateActive) void showStartupFailure(new Error(`${errorDescription} (${errorCode})`))
    else loadBackendErrorPage(errorDescription, errorCode, validatedURL)
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    mainWindow.focus()
  })
  await loadStartupPage()

  // Closing the main window keeps the desktop service available from the tray.
  // A user must choose “退出数字员工” from the tray menu to stop Electron and
  // the local backend. The installer separately closes old processes during an
  // upgrade, so this behaviour does not block replacement of application files.
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
  updateTrayBranding()
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
ipcMain.handle('branding-set-locale', (_event, locale) => {
  currentUiLocale = locale === 'en-US' ? 'en-US' : 'zh-CN'
  const name = productDisplayName()
  app.setName(name)
  updateApplicationMenu()
  updateTrayBranding()
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.setTitle(productWindowTitle())
  return { ok: true, locale: currentUiLocale, name }
})
ipcMain.handle('browser-set-visible', (_event, visible) => browserManager.setVisible(visible))
ipcMain.handle('browser-set-bounds', (_event, bounds) => browserManager.setBounds(bounds))
ipcMain.handle('browser-state', () => browserManager.state())
ipcMain.handle('browser-action', (_event, payload) => browserManager.action(payload || {}))

function requireOpenClaw() {
  if (!openClawRuntime) throw new Error('OpenClaw runtime is not initialized')
  return openClawRuntime
}

// OpenClaw is owned by the Electron main process. The renderer receives only
// narrow, intention-revealing IPC methods and never sees Gateway credentials.
ipcMain.handle('openclaw-runtime-start', () => requireOpenClaw().start())
ipcMain.handle('openclaw-runtime-status', () => requireOpenClaw().snapshot())
ipcMain.handle('openclaw-runtime-version', () => ({
  version: requireOpenClaw().snapshot().version,
  gatewayClientVersion: requireOpenClaw().snapshot().gatewayClientVersion,
  protocolVersion: requireOpenClaw().snapshot().protocolVersion,
  wireVersion: requireOpenClaw().snapshot().wireVersion,
}))
ipcMain.handle('openclaw-runtime-restart', () => requireOpenClaw().restart())
ipcMain.handle('openclaw-bots-list', (_event, params) => requireOpenClaw().listBots(params || {}))
ipcMain.handle('openclaw-bots-create', (_event, params) => requireOpenClaw().createBot(params || {}))
ipcMain.handle('openclaw-bots-update', (_event, params) => requireOpenClaw().updateBot(params || {}))
ipcMain.handle('openclaw-bots-archive', (_event, params) => requireOpenClaw().archiveBot(String(params?.agentId || ''), params?.archived !== false))
ipcMain.handle('openclaw-sessions-list', (_event, params) => requireOpenClaw().rpc('sessions.list', params || {}))
ipcMain.handle('openclaw-sessions-create', (_event, params) => requireOpenClaw().createSession(params || {}))
ipcMain.handle('openclaw-sessions-history', (_event, params) => requireOpenClaw().rpc('chat.history', params || {}))
ipcMain.handle('openclaw-runs-send', (_event, params) => requireOpenClaw().sendRun(params || {}))
ipcMain.handle('openclaw-runs-interrupt', (_event, params) => requireOpenClaw().interruptRun(params || {}))
ipcMain.handle('openclaw-approvals-resolve', (_event, params) => requireOpenClaw().rpc('exec.approval.resolve', params || {}))
ipcMain.handle('openclaw-questions-answer', (_event, params) => requireOpenClaw().rpc('question.resolve', params || {}))
ipcMain.handle('openclaw-skills-list', (_event, params) => requireOpenClaw().rpc('skills.status', params || {}))
ipcMain.handle('openclaw-skills-read-status', (_event, params) => requireOpenClaw().rpc('skills.detail', params || {}))
ipcMain.handle('openclaw-routines-list', (_event, params) => requireOpenClaw().rpc('cron.list', params || {}))
ipcMain.handle('openclaw-routines-save', (_event, params) => requireOpenClaw().saveRoutine(params || {}))
ipcMain.handle('openclaw-routines-run', (_event, params) => requireOpenClaw().rpc('cron.run', params || {}))
ipcMain.handle('openclaw-routines-pause', (_event, params) => requireOpenClaw().rpc('cron.update', { id: params?.id, patch: { enabled: !params?.paused } }))
ipcMain.handle('openclaw-computer-status', (_event, params) => {
  if (params?.agentId) browserManager.useAgentProfile(params.agentId)
  return { runtime: requireOpenClaw().snapshot(), browser: browserManager.state() }
})
ipcMain.handle('openclaw-computer-preview', (_event, params) => {
  if (params?.agentId) browserManager.useAgentProfile(params.agentId)
  return browserManager.setVisible(true)
})
ipcMain.handle('openclaw-computer-takeover', (_event, params) => {
  if (params?.agentId) browserManager.useAgentProfile(params.agentId)
  return browserManager.takeover()
})
ipcMain.handle('openclaw-computer-return', (_event, params) => {
  if (params?.agentId) browserManager.useAgentProfile(params.agentId)
  return browserManager.resume()
})
ipcMain.handle('openclaw-artifacts-list', (_event, params) => requireOpenClaw().rpc('artifacts.list', params || {}))
ipcMain.handle('openclaw-artifacts-open', async (_event, params) => {
  const filePath = path.resolve(String(params?.path || ''))
  const allowedRoot = path.resolve(getRuntimeDataDir()) + path.sep
  if (!filePath.startsWith(allowedRoot)) throw new Error('Only Xiaoyu-managed local artifacts can be opened directly')
  const error = await shell.openPath(filePath)
  if (error) throw new Error(error)
  return { ok: true }
})

async function waitForOpenClawWorkspace(retries = 60) {
  let lastError = null
  for (let attempt = 0; attempt < retries; attempt += 1) {
    try {
      const [bots] = await Promise.all([
        requireOpenClaw().listBots({}),
        requireOpenClaw().rpc('sessions.list', { limit: 1, ownerFirst: true }),
      ])
      const agents = Array.isArray(bots?.agents) ? bots.agents : []
      const unavailableAgent = agents.find((agent) => agent?.admissionRefusal || agent?.status === 'degraded')
      if (unavailableAgent) {
        const detail = unavailableAgent.admissionRefusal?.message || unavailableAgent.admissionRefusal?.reason || 'agent database is still preparing'
        throw new Error(`AI employee workspace is still preparing: ${detail}`)
      }
      return
    } catch (error) {
      lastError = error
      if (attempt < retries - 1) await new Promise((resolve) => setTimeout(resolve, 1000))
    }
  }
  throw lastError || new Error('AI engine workspace did not become ready')
}

async function loadMainApplication() {
  const target = isDev ? `http://127.0.0.1:${FRONTEND_PORT}` : `http://127.0.0.1:${PORT}/`
  await mainWindow?.loadURL(target)
  startupGateActive = false
  if (enableDevTools && process.env.SZYG_AUTO_OPEN_DEVTOOLS === '1') {
    mainWindow?.webContents.openDevTools({ mode: 'detach' })
  }
}

// ── App lifecycle ──
app.whenReady().then(async () => {
  currentUiLocale = app.getLocale().toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US'
  app.setName(productDisplayName())
  createTray()
  const browserControl = await startBrowserControlServer(browserManager, browserControlToken)
  browserControlServer = browserControl.server
  browserControlUrl = browserControl.url
  await createWindow()
  try {
    await showStartupPhase('backend')
    await startBackend()
    await waitForBackend(BACKEND_STARTUP_RETRIES)
    console.log('Backend ready')
    openClawRuntime = new OpenClawRuntimeManager({
      safeStorage,
      isDev,
      projectRoot: getProjectRoot(),
      resourcesPath: process.resourcesPath,
      dataDir: getRuntimeDataDir(),
      backendPort: PORT,
      businessMcpToken,
      openClawModelToken,
      appVersion: app.getVersion(),
      log: writeDesktopLog,
      onEvent: (event) => {
        if (startupGateActive && event?.type === 'runtime.status') {
          if (event.payload?.phase === 'repairing') void showStartupPhase('repairing')
          else if (event.payload?.phase === 'starting' || event.payload?.phase === 'reconnecting') void showStartupPhase('gateway')
        }
        if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('szyg-openclaw-event', event)
      },
    })
    await showStartupPhase('gateway')
    await openClawRuntime.start()
    await showStartupPhase('workspace')
    await waitForOpenClawWorkspace()
    await showStartupPhase('interface')
    await loadMainApplication()
  } catch (e) {
    console.error('Application failed to start:', e.message)
    writeDesktopLog(`[startup] ${e.stack || e.message}`)
    await showStartupFailure(e)
  }
})

app.on('before-quit', () => {
  isQuitting = true
  browserManager.destroy()
  browserControlServer?.close()
  browserControlServer = null
  stopBackend()
  void openClawRuntime?.stop()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

} // end single instance lock
