const { spawn } = require('child_process')
const crypto = require('crypto')
const fs = require('fs')
const net = require('net')
const path = require('path')
const { employeeModels, profileChanges, creationId, managedInstructions, modelChoice, permissionChoice } = require('./employee-profile')
const { directorRenderJobs } = require('./director-render-receipts')
const { CredentialStore } = require('./credential-store')
const {
  OPENCLAW_RUNTIME_VERSION,
  OPENCLAW_GATEWAY_CLIENT_VERSION,
  OPENCLAW_PROTOCOL_VERSION,
  OPENCLAW_WIRE_VERSION,
  OPENCLAW_NODE_VERSION,
} = require('./runtime-constants')

const DIRECTOR_ID = 'xiaoyu-director'
const DIRECTOR_NAME = '视频导演'
const LEGACY_DIRECTOR_NAME = '小妤导演'
const BUSINESS_MCP_SERVER = 'szyg-business'
const LOCAL_SKILL_SOURCES = new Set([
  'openclaw-bundled', 'openclaw-extra', 'openclaw-workspace', 'openclaw-managed',
  'agents-skills-project', 'agents-skills-personal',
])
const TERMINAL_STATES = new Set(['completed', 'failed', 'cancelled'])
const XIAOYU_FAST_MODEL = 'xiaoyu-managed/text.fast'
const XIAOYU_REASONING_MODEL = 'xiaoyu-managed/text.reasoning'
// Kept as the public default-model export for existing callers. Xiaoyu now
// starts in the lower-cost normal mode; reasoning is an explicit user choice.
const XIAOYU_MANAGED_MODEL = XIAOYU_FAST_MODEL
const RETIRED_MEMORY_JOB_DECLARATION = 'memory-core:memory-dreaming-promotion'
const DEFAULT_SCOPES = [
  'operator.read',
  'operator.write',
  'operator.approvals',
  'operator.questions',
  'operator.admin',
]

function isDesktopSession(key) {
  return /^agent:[a-z0-9_-]+:dashboard:(?:incognito-)?[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(key)
}

function sessionOwner(key, agentId) {
  const owner = typeof key === 'string' && /^agent:([a-z0-9_-]+):/i.exec(key)?.[1]
  if (!owner || (agentId !== undefined && agentId !== owner)) throw new Error('该对话不属于当前员工')
  return owner
}

function desktopSessionOwner(key, agentId) {
  if (!isDesktopSession(key)) throw new Error('仅本机任务对话支持此操作')
  return sessionOwner(key, agentId)
}

function validSkillKey(value) {
  return typeof value === 'string' && /^[a-z0-9][a-z0-9._-]{0,95}$/i.test(value)
    && !Object.hasOwn(Object.prototype, value) && value !== 'prototype'
}

function addConversationContextDetail(context, page, key, value) {
  const detail = { ...context?.detail, [key]: value }
  // The Gateway accepts at most four detail fields. The expert references are
  // also present in selection; keep those full references when slots fill up.
  for (const name of Object.keys(detail).filter(name => /^expert\d+$/.test(name)).reverse()) {
    if (Object.keys(detail).length <= 4) break
    delete detail[name]
  }
  return { page, ...context, detail }
}

function atomicWriteJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  const temporary = `${filePath}.${process.pid}.${Date.now()}.tmp`
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
  fs.renameSync(temporary, filePath)
}

function readJson(filePath, fallback = null) {
  try {
    // Windows PowerShell may emit UTF-8 JSON with a BOM. JSON.parse does not
    // accept that marker, so normalize it at the runtime package boundary.
    return JSON.parse(fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, ''))
  } catch (_) {
    return fallback
  }
}

function sha256FileSync(filePath) {
  const hash = crypto.createHash('sha256')
  hash.update(fs.readFileSync(filePath))
  return hash.digest('hex')
}

function publicKeyRawFromPem(publicKeyPem) {
  const der = crypto.createPublicKey(publicKeyPem).export({ type: 'spki', format: 'der' })
  const prefix = Buffer.from('302a300506032b6570032100', 'hex')
  if (der.length !== prefix.length + 32 || !der.subarray(0, prefix.length).equals(prefix)) {
    throw new Error('Device public key is not canonical Ed25519 SPKI')
  }
  return der.subarray(prefix.length)
}

function publicKeyRawBase64UrlFromPem(publicKeyPem) {
  return publicKeyRawFromPem(publicKeyPem).toString('base64url')
}

function signDevicePayload(privateKeyPem, payload) {
  return crypto.sign(null, Buffer.from(payload, 'utf8'), crypto.createPrivateKey(privateKeyPem)).toString('base64url')
}

function generateDeviceIdentity() {
  const { publicKey, privateKey } = crypto.generateKeyPairSync('ed25519')
  const publicKeyPem = publicKey.export({ type: 'spki', format: 'pem' })
  const privateKeyPem = privateKey.export({ type: 'pkcs8', format: 'pem' })
  return {
    deviceId: crypto.createHash('sha256').update(publicKeyRawFromPem(publicKeyPem)).digest('hex'),
    publicKeyPem,
    privateKeyPem,
  }
}

function findAvailablePort(start = 18789, end = 18809) {
  return new Promise((resolve, reject) => {
    const tryPort = (port) => {
      if (port > end) return reject(new Error('No OpenClaw Gateway port is available'))
      const server = net.createServer()
      server.once('error', () => tryPort(port + 1))
      server.once('listening', () => server.close(() => resolve(port)))
      server.listen(port, '127.0.0.1')
    }
    tryPort(start)
  })
}

function sanitizeForRenderer(value, depth = 0) {
  if (depth > 8) return '[truncated]'
  if (value === null || value === undefined) return value
  if (typeof value === 'string') return value.length > 12000 ? `${value.slice(0, 12000)}…` : value
  if (typeof value === 'number' || typeof value === 'boolean') return value
  if (Array.isArray(value)) return value.slice(0, 200).map((item) => sanitizeForRenderer(item, depth + 1))
  if (typeof value === 'object') {
    const output = {}
    for (const [key, item] of Object.entries(value)) {
      if (/token|secret|password|authorization|privatekey/i.test(key)) continue
      output[key] = sanitizeForRenderer(item, depth + 1)
    }
    return output
  }
  return String(value)
}

function normalizeGatewayEvent(event) {
  const rawType = String(event?.event || event?.type || 'runtime.event')
  const payload = sanitizeForRenderer(event?.payload ?? event)
  let type = 'runtime.event'
  if (rawType === 'agent' || rawType === 'chat') type = 'message'
  else if (rawType.includes('approval') && rawType.includes('requested')) type = 'approval'
  else if (rawType.startsWith('question.') && rawType.endsWith('requested')) type = 'question'
  else if (rawType.includes('artifact')) type = 'artifact'
  else if (rawType.startsWith('cron.')) type = 'routine'
  else if (rawType.startsWith('desktop.') || rawType.startsWith('computer.')) type = 'computer'
  else if (rawType.startsWith('sessions.')) type = 'session'
  let runStatus = ''
  if (rawType === 'chat') {
    if (payload?.state === 'status') runStatus = payload.phase === 'starting_model' ? 'thinking' : 'working'
    else if (payload?.state === 'delta') runStatus = 'working'
    else if (payload?.state === 'final') runStatus = 'completed'
    else if (payload?.state === 'error') runStatus = 'failed'
    else if (payload?.state === 'aborted') runStatus = 'cancelled'
  } else if (rawType === 'agent') runStatus = 'working'
  else if (type === 'approval') runStatus = 'waiting_approval'
  else if (type === 'question') runStatus = 'blocked'
  if (runStatus && payload && typeof payload === 'object' && !Array.isArray(payload)) payload.runStatus = runStatus
  return {
    id: crypto.randomUUID(),
    type,
    source: rawType,
    timestamp: Date.now(),
    payload,
  }
}

function resolveRuntimeCandidates({ isDev, projectRoot, resourcesPath, dataDir }) {
  const candidates = []
  if (process.env.SZYG_OPENCLAW_RUNTIME_DIR) candidates.push(process.env.SZYG_OPENCLAW_RUNTIME_DIR)
  const active = readJson(path.join(dataDir, 'openclaw', 'runtime', 'active.json'))
  if (active?.path) candidates.push(active.path)
  if (isDev) candidates.push(path.join(projectRoot, 'electron', 'runtime', 'openclaw', OPENCLAW_RUNTIME_VERSION))
  else candidates.push(path.join(resourcesPath, 'runtime', 'openclaw', OPENCLAW_RUNTIME_VERSION))
  return [...new Set(candidates.map((item) => path.resolve(item)))]
}

function resolveRuntimeLayout(root) {
  const nodeExecutable = path.join(root, process.platform === 'win32' ? 'node.exe' : 'node')
  const packageRoot = path.join(root, 'app', 'node_modules', 'openclaw')
  const entry = path.join(packageRoot, 'openclaw.mjs')
  const openclawPackagePath = path.join(packageRoot, 'package.json')
  const manifestPath = path.join(root, 'manifest.json')
  if (![nodeExecutable, entry, openclawPackagePath, manifestPath].every((item) => fs.existsSync(item))) return null
  const manifest = readJson(manifestPath)
  const openclawPackage = readJson(openclawPackagePath)
  if (!manifest || manifest.openclawVersion !== OPENCLAW_RUNTIME_VERSION) return null
  if (openclawPackage?.version !== OPENCLAW_RUNTIME_VERSION) return null
  if (manifest.gatewayClientVersion !== OPENCLAW_GATEWAY_CLIENT_VERSION) return null
  if (manifest.protocolVersion !== OPENCLAW_PROTOCOL_VERSION) return null
  if (Number(manifest.wireVersion) !== OPENCLAW_WIRE_VERSION) return null
  if (manifest.nodeVersion !== OPENCLAW_NODE_VERSION) return null
  for (const file of Array.isArray(manifest.files) ? manifest.files : []) {
    const target = path.resolve(root, String(file.path || ''))
    if (!target.startsWith(path.resolve(root) + path.sep) || !fs.existsSync(target)) return null
    if (file.sha256 && sha256FileSync(target) !== String(file.sha256).toLowerCase()) return null
  }
  return { root, nodeExecutable, packageRoot, entry, manifest }
}

function copyTemplateDirectory(source, target) {
  if (!fs.existsSync(source)) return
  fs.mkdirSync(target, { recursive: true })
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const sourcePath = path.join(source, entry.name)
    const targetPath = path.join(target, entry.name)
    if (entry.isDirectory()) copyTemplateDirectory(sourcePath, targetPath)
    else if (!fs.existsSync(targetPath)) fs.copyFileSync(sourcePath, targetPath)
  }
}

class OpenClawRuntimeManager {
  constructor(options) {
    this.options = options
    this.child = null
    this.client = null
    this.gatewayPort = null
    this.stopRequested = false
    this.doctorAttempted = false
    this.startPromise = null
    this.readyResolver = null
    this.readyRejecter = null
    this.restartTimer = null
    this.restartAttempts = 0
    this.lastShutdown = null
    this.activeRuns = new Set()
    this.activeSessions = new Map()
    this.finishedRunSessions = new Map()
    this.activeRunStatuses = new Map()
    this.activeSessionStartedAt = new Map()
    this.sessionReconcileTimers = new Map()
    this.state = {
      phase: 'stopped',
      available: false,
      ready: false,
      version: OPENCLAW_RUNTIME_VERSION,
      gatewayClientVersion: OPENCLAW_GATEWAY_CLIENT_VERSION,
      protocolVersion: OPENCLAW_PROTOCOL_VERSION,
      wireVersion: OPENCLAW_WIRE_VERSION,
      error: '',
      gatewayUrl: '',
    }
    this.rootDir = path.join(options.dataDir, 'openclaw')
    this.stateDir = path.join(this.rootDir, 'state')
    this.workspaceDir = path.join(this.rootDir, 'workspaces', 'xiaoyu')
    this.configPath = path.join(this.stateDir, 'openclaw.json')
    this.pendingMutations = new Map()
    this.privateSessionChoices = new Map()
    this.botStatePath = path.join(this.rootDir, 'xiaoyu-bots.json')
    this.credentials = new CredentialStore({ safeStorage: options.safeStorage, rootDir: this.rootDir })
  }

  snapshot() {
    return { ...this.state, activeRuns: this.activeRuns.size }
  }

  emitStatus() {
    this.options.onEvent?.({
      id: crypto.randomUUID(),
      type: 'runtime.status',
      source: 'xiaoyu.runtime',
      timestamp: Date.now(),
      payload: this.snapshot(),
    })
  }

  setState(patch) {
    Object.assign(this.state, patch)
    this.emitStatus()
  }

  log(message) {
    this.options.log?.(`[openclaw] ${message}`)
  }

  findRuntime() {
    const candidates = resolveRuntimeCandidates({
      isDev: this.options.isDev,
      projectRoot: this.options.projectRoot,
      resourcesPath: this.options.resourcesPath,
      dataDir: this.options.dataDir,
    })
    for (const candidate of candidates) {
      const layout = resolveRuntimeLayout(candidate)
      if (layout) return layout
    }
    return null
  }

  prepareWorkspace() {
    fs.mkdirSync(this.stateDir, { recursive: true })
    fs.mkdirSync(this.workspaceDir, { recursive: true })
    fs.mkdirSync(path.join(this.workspaceDir, 'skills'), { recursive: true })
    copyTemplateDirectory(path.join(__dirname, 'workspace-template'), this.workspaceDir)
    if (!fs.existsSync(this.configPath)) {
      atomicWriteJson(this.configPath, { gateway: { mode: 'local' } })
    }
  }

  runtimeEnv(token) {
    return {
      ...process.env,
      OPENCLAW_DISABLE_BONJOUR: '1',
      OPENCLAW_EXEC_SHELL_SNAPSHOT: '0',
      OPENCLAW_NO_RESPAWN: '1',
      OPENCLAW_SKIP_CHANNELS: '1',
      OPENCLAW_STATE_DIR: this.stateDir,
      OPENCLAW_CONFIG_PATH: this.configPath,
      OPENCLAW_WORKSPACE_DIR: this.workspaceDir,
      OPENCLAW_GATEWAY_TOKEN: token,
      SZYG_BUSINESS_MCP_TOKEN: this.options.businessMcpToken,
      SZYG_OPENCLAW_MODEL_TOKEN: this.options.openClawModelToken,
    }
  }

  clearStaleGatewayLock() {
    const lockPath = path.join(this.stateDir, 'tmp', 'openclaw', 'gateway.state.lock')
    const lock = readJson(lockPath)
    const pid = Number(lock?.pid)
    if (!Number.isInteger(pid) || pid <= 0) return
    try {
      process.kill(pid, 0)
    } catch (error) {
      if (error?.code !== 'ESRCH') return
      fs.rmSync(lockPath, { force: true })
      this.log(`removed stale gateway lock for pid ${pid}`)
    }
  }

  clearStaleCronAuthorityLock() {
    const sharedStateDir = path.join(this.stateDir, 'state')
    const lockPath = path.join(sharedStateDir, 'openclaw.sqlite.cron-authority.lock')
    const reclaimPath = `${lockPath}.reclaim`
    let ageMs = 0
    try {
      ageMs = Date.now() - fs.statSync(lockPath).mtimeMs
    } catch (_) {
      return
    }
    // This manager is the sole owner of Xiaoyu's app-specific state directory
    // and calls this only before spawning its child. A lock older than five
    // minutes therefore belongs to an earlier crashed runtime, even when its
    // PID has since been reused by an unrelated Windows process.
    if (this.child || ageMs < 5 * 60 * 1000) return
    fs.rmSync(lockPath, { force: true })
    fs.rmSync(reclaimPath, { recursive: true, force: true })
    this.log(`removed stale cron authority lock (${Math.round(ageMs / 1000)}s old)`)
  }

  disableRetiredMemoryJobsBeforeStart() {
    const databasePath = path.join(this.stateDir, 'state', 'openclaw.sqlite')
    if (!fs.existsSync(databasePath)) return 0
    let database
    try {
      const { DatabaseSync } = require('node:sqlite')
      database = new DatabaseSync(databasePath)
      const rows = database.prepare(`
        SELECT store_key, job_id, job_json
        FROM cron_jobs
        WHERE declaration_key = ?
           OR name = 'Memory Dreaming Promotion'
           OR description LIKE '%managed-by=memory-core.short-term-promotion%'
      `).all(RETIRED_MEMORY_JOB_DECLARATION)
      const update = database.prepare(`
        UPDATE cron_jobs
        SET enabled = 0, job_json = ?, updated_at = ?
        WHERE store_key = ? AND job_id = ?
      `)
      const now = Date.now()
      database.exec('BEGIN IMMEDIATE')
      try {
        for (const row of rows) {
          const job = JSON.parse(String(row.job_json || '{}'))
          job.enabled = false
          update.run(JSON.stringify(job), now, row.store_key, row.job_id)
        }
        database.prepare('DELETE FROM claw_cron_refs WHERE declaration_key = ?').run(RETIRED_MEMORY_JOB_DECLARATION)
        database.exec('COMMIT')
      } catch (error) {
        database.exec('ROLLBACK')
        throw error
      }
      if (rows.length) this.log(`disabled ${rows.length} retired memory background job(s) before gateway start`)
      return rows.length
    } catch (error) {
      this.log(`retired memory job preflight failed: ${error.message}`)
      return 0
    } finally {
      try { database?.close() } catch (_) {}
    }
  }

  async removeRetiredMemoryJobs() {
    if (!this.client) return 0
    const result = await this.client.request('cron.list', { includeDisabled: true, limit: 200 })
    const rows = Array.isArray(result?.jobs) ? result.jobs : Array.isArray(result?.items) ? result.items : []
    const retired = rows.filter((job) => {
      const description = String(job?.description || '')
      return job?.declarationKey === RETIRED_MEMORY_JOB_DECLARATION
        || job?.name === 'Memory Dreaming Promotion'
        || description.includes('managed-by=memory-core.short-term-promotion')
    })
    for (const job of retired) {
      await this.client.request('cron.remove', { id: String(job.id) })
    }
    if (retired.length) this.log(`removed ${retired.length} retired memory background job(s)`)
    return retired.length
  }

  runCli(layout, args, env, timeoutMs = 30000) {
    return new Promise((resolve, reject) => {
      const child = spawn(layout.nodeExecutable, [layout.entry, ...args], {
        cwd: this.rootDir,
        env,
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
      })
      let stderr = ''
      let stdout = ''
      const timer = setTimeout(() => {
        child.kill()
        reject(new Error(`OpenClaw command timed out: ${args[0]}`))
      }, timeoutMs)
      child.stdout.on('data', (data) => { stdout += String(data) })
      child.stderr.on('data', (data) => { stderr += String(data) })
      child.once('error', (error) => { clearTimeout(timer); reject(error) })
      child.once('exit', (code) => {
        clearTimeout(timer)
        if (code === 0) resolve({ stdout, stderr })
        else reject(Object.assign(new Error((stderr || stdout || `OpenClaw command failed (${code})`).trim().slice(-1500)), { code }))
      })
    })
  }

  async provisionBusinessMcp(layout, env) {
    const definition = {
      url: `http://127.0.0.1:${this.options.backendPort}/api/mcp/szyg-business`,
      transport: 'streamable-http',
      enabled: true,
      headers: { Authorization: `Bearer ${this.options.businessMcpToken}` },
      connectionTimeoutMs: 5000,
      requestTimeoutMs: 180000,
      supportsParallelToolCalls: false,
    }
    const config = readJson(this.configPath, {}) || {}
    config.gateway = { ...(config.gateway || {}), mode: 'local' }
    config.mcp = { ...(config.mcp || {}), servers: { ...(config.mcp?.servers || {}), [BUSINESS_MCP_SERVER]: definition } }
    config.models = {
      ...(config.models || {}),
      mode: 'replace',
      providers: {
        'xiaoyu-managed': {
          baseUrl: `http://127.0.0.1:${this.options.backendPort}/api/internal/openclaw/v1`,
          apiKey: { source: 'env', provider: 'default', id: 'SZYG_OPENCLAW_MODEL_TOKEN' },
          api: 'openai-completions',
          timeoutSeconds: 120,
          models: [
            {
              id: 'text.fast',
              name: 'Xiaoyu Managed Fast',
              reasoning: false,
              input: ['text'],
              contextWindow: 128000,
              maxTokens: 8192,
            },
            {
              id: 'text.reasoning',
              name: 'Xiaoyu Managed Reasoning',
              reasoning: true,
              input: ['text'],
              contextWindow: 128000,
              maxTokens: 8192,
            },
            ...employeeModels.map(id => ({
              id, name: id, reasoning: true, input: ['text'], contextWindow: 128000, maxTokens: 8192,
            })),
          ],
        },
      },
    }
    config.agents = {
      ...(config.agents || {}),
      defaults: {
        ...(config.agents?.defaults || {}),
        model: { primary: XIAOYU_MANAGED_MODEL, fallbacks: [] },
        modelPolicy: { allow: [XIAOYU_FAST_MODEL, XIAOYU_REASONING_MODEL, ...employeeModels.map(id => 'xiaoyu-managed/' + id)] },
      },
    }
    // Preserve the legacy implicit main agent when the first custom employee
    // turns the OpenClaw roster into an explicit multi-agent configuration.
    if (!Object.hasOwn(config.agents, 'entries') && !Object.hasOwn(config.agents, 'list')) {
      config.agents.entries = { main: { name: '小妤', workspace: this.workspaceDir } }
    }
    config.cron = {
      ...(config.cron || {}),
      // Recurring work missed while the desktop app was closed must not be
      // replayed at the next launch. Users can still run any visible routine
      // manually from the background-task window.
      skipMissedJobs: true,
      sessionRetention: '24h',
    }
    config.plugins = {
      ...(config.plugins || {}),
      // memory-core currently shares the same SQLite/cron authority used by
      // the desktop Gateway. A failed authority settlement can leave an
      // otherwise successful model turn open forever. Selecting "none" keeps
      // file-backed MEMORY.md context available while disabling only the
      // optional semantic-memory plugin; Xiaoyu business routines continue to
      // use the normal cron service.
      slots: {
        ...(config.plugins?.slots || {}),
        memory: 'none',
      },
      entries: {
        ...(config.plugins?.entries || {}),
        'memory-core': {
          ...(config.plugins?.entries?.['memory-core'] || {}),
          enabled: false,
          config: {
            ...(config.plugins?.entries?.['memory-core']?.config || {}),
            // Dreaming is an optional background consolidation job. On the
            // local Windows runtime it can contend with an active turn for the
            // same SQLite state and wait on cron receipt authority. File-backed
            // workspace memory remains available while scheduled business
            // routines stay on the runtime's normal cron service.
            dreaming: {
              ...(config.plugins?.entries?.['memory-core']?.config?.dreaming || {}),
              enabled: false,
            },
          },
        },
      },
    }
    atomicWriteJson(this.configPath, config)
    // A cold Windows start has to load the complete OpenClaw module graph and
    // can take well over 30 seconds on machines with real-time scanning.
    await this.runCli(layout, ['config', 'validate', '--json'], env, 120000)
  }

  async start() {
    if (this.startPromise) return this.startPromise
    this.startPromise = this._start().finally(() => { this.startPromise = null })
    return this.startPromise
  }

  async _start() {
    if (this.state.ready) return this.snapshot()
    this.stopRequested = false
    this.prepareWorkspace()
    const layout = this.findRuntime()
    if (!layout) {
      const message = `OpenClaw ${OPENCLAW_RUNTIME_VERSION} runtime package is not installed`
      this.setState({ phase: 'unavailable', available: false, ready: false, error: message })
      throw new Error(message)
    }
    this.setState({ phase: 'starting', available: true, ready: false, error: '' })
    const gatewayToken = this.credentials.getOrCreate('gatewayToken', () => crypto.randomBytes(32).toString('hex'))
    this.deviceIdentity = this.credentials.getOrCreate('deviceIdentity', generateDeviceIdentity)
    const env = this.runtimeEnv(gatewayToken)
    this.gatewayPort = await findAvailablePort()
    await this.provisionBusinessMcp(layout, env)
    this.clearStaleGatewayLock()
    this.clearStaleCronAuthorityLock()
    this.disableRetiredMemoryJobsBeforeStart()
    await this.spawnGateway(layout, env, gatewayToken)
    return this.snapshot()
  }

  async spawnGateway(layout, env, gatewayToken) {
    const args = [layout.entry, 'gateway', '--bind', 'loopback', '--port', String(this.gatewayPort)]
    const child = spawn(layout.nodeExecutable, args, {
      cwd: this.rootDir,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })
    this.child = child
    child.stdout.on('data', (data) => this.log(`stdout ${String(data).trim()}`))
    child.stderr.on('data', (data) => this.log(`stderr ${String(data).trim()}`))
    child.once('error', error => { if (this.child === child) this.fail(error) })
    child.once('exit', (code, signal) => {
      if (this.child === child) void this.handleExit(code, signal, layout, env, gatewayToken)
    })
    await this.connectClient(gatewayToken, env)
  }

  async connectClient(gatewayToken, env) {
    const [{ GatewayClient, startGatewayClientWhenEventLoopReady }, protocol] = await Promise.all([
      import('@openclaw/gateway-client'),
      import('@openclaw/gateway-protocol'),
    ])
    if (Number(protocol.PROTOCOL_VERSION) !== OPENCLAW_WIRE_VERSION) {
      throw new Error(`OpenClaw protocol mismatch: expected ${OPENCLAW_WIRE_VERSION}, got ${protocol.PROTOCOL_VERSION}`)
    }
    const url = `ws://127.0.0.1:${this.gatewayPort}`
    await new Promise(async (resolve, reject) => {
      let settled = false
      const rejectReadiness = (error) => {
        if (settled) return
        settled = true
        clearTimeout(timeout)
        this.readyRejecter = null
        reject(error)
      }
      const timeout = setTimeout(() => {
        rejectReadiness(new Error('OpenClaw Gateway readiness timed out'))
        if (this.child) this.child.kill()
      }, 300000)
      this.readyRejecter = rejectReadiness
      this.client = new GatewayClient({
        url,
        token: gatewayToken,
        clientName: 'gateway-client',
        clientDisplayName: 'Xiaoyu Desktop',
        clientVersion: this.options.appVersion,
        platform: 'win32',
        mode: 'backend',
        role: 'operator',
        scopes: DEFAULT_SCOPES,
        caps: ['approvals', 'exec-approvals', 'inline-widgets', 'session-scoped-events', 'tool-events'],
        minProtocol: OPENCLAW_WIRE_VERSION,
        maxProtocol: OPENCLAW_WIRE_VERSION,
        env,
        deviceIdentity: this.deviceIdentity,
        onHelloOk: () => {
          if (settled) return
          settled = true
          clearTimeout(timeout)
          this.readyRejecter = null
          resolve()
        },
        onEvent: (event) => this.handleEvent(event),
        onConnectError: (error) => this.log(`connect ${error.message}`),
        onClose: (_code, reason) => {
          if (!this.stopRequested) this.setState({ phase: 'reconnecting', ready: false, error: reason || 'Gateway disconnected' })
        },
        hostDeps: {
          signDevicePayload,
          publicKeyRawBase64UrlFromPem,
          loadDeviceAuthToken: ({ deviceId, role }) => this.credentials.get(`deviceToken:${deviceId}:${role}`) || null,
          storeDeviceAuthToken: ({ deviceId, role, token, scopes, expectedToken }) => {
            const key = `deviceToken:${deviceId}:${role}`
            const current = this.credentials.get(key)
            if (expectedToken !== undefined && (current?.token ?? null) !== expectedToken) return
            this.credentials.set(key, { token, scopes })
          },
          clearDeviceAuthToken: ({ deviceId, role, expectedToken }) => {
            const key = `deviceToken:${deviceId}:${role}`
            const current = this.credentials.get(key)
            if (expectedToken !== undefined && current?.token !== expectedToken) return
            this.credentials.delete(key)
          },
          logDebug: (message) => this.log(message),
          logError: (message) => this.log(message),
          redactForLog: (message) => String(message).replaceAll(gatewayToken, '[redacted]'),
        },
      })
      try {
        await startGatewayClientWhenEventLoopReady(this.client, { timeoutMs: 5000 })
      } catch (error) {
        rejectReadiness(error)
      }
    })
    // Do not expose a ready workspace until disabled-plugin residue has been
    // reconciled. The pre-start database pass already made it non-runnable;
    // this protocol-level removal clears it from the user's routine list too.
    try {
      await this.removeRetiredMemoryJobs()
    } catch (error) {
      // The pre-start pass has already disabled the job. A temporarily busy
      // cron authority must not make the whole employee workspace unavailable.
      this.log(`retired memory job protocol cleanup deferred: ${error.message}`)
    }
    this.directorNeedsInstall = true
    await this.installDirector().catch(error => this.log(`director setup deferred: ${error.message}`))
    this.doctorAttempted = false
    this.restartAttempts = 0
    this.setState({ phase: 'ready', ready: true, error: '', gatewayUrl: url })
    this.backfillPending().catch((error) => this.log(`approval backfill failed: ${error.message}`))
  }

  async backfillPending() {
    const [approvals, questions] = await Promise.all([
      this.rpc('exec.approval.list', {}),
      this.rpc('question.list', {}),
    ])
    this.options.onEvent?.({ id: crypto.randomUUID(), type: 'approval.snapshot', source: 'xiaoyu.runtime', timestamp: Date.now(), payload: sanitizeForRenderer(approvals) })
    this.options.onEvent?.({ id: crypto.randomUUID(), type: 'question.snapshot', source: 'xiaoyu.runtime', timestamp: Date.now(), payload: sanitizeForRenderer(questions) })
    const approvalRows = approvals?.approvals || approvals?.requests || approvals?.items || []
    const questionRows = questions?.questions || questions?.requests || questions?.items || []
    for (const payload of Array.isArray(approvalRows) ? approvalRows : []) {
      this.options.onEvent?.({ id: crypto.randomUUID(), type: 'approval', source: 'exec.approval.backfill', timestamp: Date.now(), payload: sanitizeForRenderer(payload) })
    }
    for (const payload of Array.isArray(questionRows) ? questionRows : []) {
      this.options.onEvent?.({ id: crypto.randomUUID(), type: 'question', source: 'question.backfill', timestamp: Date.now(), payload: sanitizeForRenderer(payload) })
    }
  }

  handleEvent(event) {
    const normalized = normalizeGatewayEvent(event)
    const payload = normalized.payload
    const runId = payload?.runId || payload?.request?.runId
    const status = payload?.runStatus
    let sessionKey = payload?.sessionKey || payload?.request?.sessionKey || payload?.context?.sessionKey
    if (runId && !sessionKey) {
      sessionKey = this.finishedRunSessions.get(runId)
      if (!sessionKey) {
        for (const [key, tracked] of this.activeSessions) {
          if (tracked === runId || tracked === 'pending:' + runId) { sessionKey = key; break }
        }
      }
    }
    if (sessionKey && payload && typeof payload === 'object') {
      payload.sessionKey = sessionKey
      payload.agentId ||= /^agent:([^:]+):/.exec(sessionKey)?.[1]
      if (runId) payload.runId = runId
    }
    if (runId && status) {
      const tracked = this.activeSessions.get(sessionKey)
      const matches = tracked === runId || tracked === 'pending:' + runId
      if (TERMINAL_STATES.has(status)) {
        this.activeRunStatuses.delete(runId)
        this.activeRuns.delete(runId)
        if (sessionKey) this.rememberFinishedRun(runId, sessionKey)
        if (matches) this.clearTrackedRun(sessionKey, tracked)
      } else {
        if (this.finishedRunSessions.has(runId)) return
        if (sessionKey && (!tracked || matches)) {
          if (matches) this.activeRuns.delete(tracked)
          this.activeSessions.set(sessionKey, runId)
          this.activeRunStatuses.set(runId, ['waiting_approval', 'blocked'].includes(status) ? status : 'running')
          if (!tracked) this.scheduleSessionReconciliation(sessionKey)
          if (!this.activeSessionStartedAt.has(sessionKey)) this.activeSessionStartedAt.set(sessionKey, Date.now())
        }
        if (!tracked || matches) this.activeRuns.add(runId)
      }
    }
    if (normalized.source === 'shutdown') this.lastShutdown = normalized.payload
    this.options.onEvent?.(normalized)
  }

  async handleExit(code, signal, layout, env, gatewayToken) {
    this.child = null
    if (this.stopRequested) return
    this.log(`gateway exited: code=${code ?? 'null'}, signal=${signal || 'none'}`)
    if (code === 78) {
      if (!this.doctorAttempted) {
        this.doctorAttempted = true
        this.setState({ phase: 'repairing', ready: false, error: 'OpenClaw configuration requires repair' })
        try {
          await this.runCli(layout, ['doctor', '--fix', '--yes', '--non-interactive'], env, 120000)
          await this.spawnGateway(layout, env, gatewayToken)
          return
        } catch (error) {
          this.fail(error)
          return
        }
      }
      this.fail(new Error('OpenClaw configuration is still invalid after one doctor repair attempt'))
      return
    }
    const exitError = new Error(`OpenClaw Gateway exited: code=${code ?? 'null'}, signal=${signal || 'none'}`)
    this.readyRejecter?.(exitError)
    this.fail(exitError)
    if (this.restartAttempts >= 3) return
    this.restartAttempts += 1
    clearTimeout(this.restartTimer)
    this.restartTimer = setTimeout(async () => {
      if (this.startPromise) {
        try { await this.startPromise } catch (_) {}
      }
      if (!this.stopRequested) this.start().catch((error) => this.log(`restart failed: ${error.message}`))
    }, 2000)
  }

  fail(error) {
    this.setState({ phase: 'failed', ready: false, error: String(error?.message || error) })
  }

  async stop() {
    this.stopRequested = true
    clearTimeout(this.restartTimer)
    this.restartTimer = null
    this.readyRejecter?.(new Error('Xiaoyu runtime stopped'))
    this.readyRejecter = null
    const child = this.child
    const childClosed = child && child.exitCode === null && child.signalCode === null
      ? new Promise((resolve, reject) => {
        // The previous process must release its state database before another
        // Gateway is launched, even if its socket has already disconnected.
        const timer = setTimeout(() => reject(new Error('工作环境尚在关闭，请稍后重试')), 30000)
        child.once('close', () => { clearTimeout(timer); resolve() })
        child.kill()
      })
      : Promise.resolve()
    if (this.client) {
      try { await this.client.stopAndWait({ timeoutMs: 1500 }) } catch (_) {}
      this.client = null
    }
    await childClosed
    if (this.child === child) this.child = null
    this.activeRuns.clear()
    this.activeSessions.clear()
    this.finishedRunSessions.clear()
    this.activeRunStatuses.clear()
    this.activeSessionStartedAt.clear()
    this.privateSessionChoices.clear()
    for (const timer of this.sessionReconcileTimers.values()) clearTimeout(timer)
    this.sessionReconcileTimers.clear()
    this.setState({ phase: 'stopped', ready: false, error: '', gatewayUrl: '' })
  }

  async restart() {
    await this.stop()
    return this.start()
  }

  async rpc(method, params = {}) {
    if (!this.client || !this.state.ready) throw new Error('OpenClaw Gateway is not ready')
    return sanitizeForRenderer(await this.client.request(method, params))
  }

  serializeMutation(key, operation) {
    const previous = this.pendingMutations.get(key) || Promise.resolve()
    const next = previous.catch(() => {}).then(operation)
    this.pendingMutations.set(key, next)
    return next.finally(() => {
      if (this.pendingMutations.get(key) === next) this.pendingMutations.delete(key)
    })
  }

  sendRun(params = {}) {
    const sessionKey = String(params.sessionKey || '').trim()
    return this.serializeMutation('session:' + sessionKey, () => this.dispatchRun({ ...params, sessionKey }))
  }

  async dispatchRun(params) {
    const sessionKey = String(params.sessionKey || '').trim()
    const message = String(params.message || '')
    const agentId = desktopSessionOwner(sessionKey, params.agentId)
    if (!message.trim()) throw new Error('消息不能为空')
    const previous = await this.runStatus({ sessionKey, agentId })
    if (previous.status === 'unknown' && !previous.active) throw new Error('尚未确认这个对话的运行状态，请稍后重试')
    if (previous.active) throw new Error('该会话已有任务正在执行，请等待完成后再发送')
    const requestId = crypto.randomUUID()
    const pendingId = 'pending:' + requestId
    this.activeSessions.set(sessionKey, pendingId)
    this.activeSessionStartedAt.set(sessionKey, Date.now())
    this.activeRuns.add(pendingId)
    this.emitStatus()
    let sending = false
    try {
      await this.ensureEmployeeInstructions(agentId)
      const settings = this.sessionSettings(params, agentId, sessionKey)
      const runModel = params.usingAutomaticModel === true ? 'auto' : settings.model
      await this.rpc('sessions.patch', {
        key: sessionKey, ...(agentId ? { agentId } : {}),
        ...this.gatewayModelSettings(runModel, params.deepThinking),
        ...(params.permissionMode !== undefined ? { permissionMode: settings.permissionMode } : {}),
      })
      const payload = { sessionKey, message, deliver: false, idempotencyKey: requestId }
      if (agentId) payload.agentId = agentId
      if (this.options.desktopToken) {
        const response = await fetch(`http://127.0.0.1:${this.options.backendPort}/api/agency/conversation-experts/resolve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-SZYG-Desktop-Token': this.options.desktopToken },
          body: JSON.stringify({ session_key: sessionKey, agent_id: agentId, message: message.slice(0, 8192) }),
          signal: AbortSignal.timeout(8000),
        })
        if (!response.ok) throw new Error('对话专家暂时不可用，请重试')
        const experts = await response.json()
        if (experts.workContext) payload.workContext = experts.workContext
        this.options.onEvent?.({
          id: crypto.randomUUID(), type: 'experts.changed', source: 'xiaoyu.runtime', timestamp: Date.now(),
          payload: { sessionKey, agentId },
        })
      }
      const hasAttachments = Array.isArray(params.attachments) && params.attachments.slice(0, 8).some(url =>
        typeof url === 'string' && /^\/api\/media\/files\/(image|audio|video)\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.[a-z0-9]{2,5}$/i.test(url)
        && message.includes(`](${url})`))
      if (hasAttachments) {
        payload.workContext = addConversationContextDetail(
          payload.workContext, '小妤 · 对话素材', '本轮附件',
          '回答涉及附件内容时，先通过 tool_search 查找 materials.inspect。用消息里的本机地址看图、转写音频或检查视频的画面及声音。保留原地址供后续任务使用。',
        )
      }
      const choices = this.sessionChoices(sessionKey, 'skillChoices')
      if (Object.values(choices).some(Boolean)) {
        const state = await this.sessionSkillState(agentId, sessionKey)
        const selected = this.selectedSkills(state, choices)
        if (selected.length) {
          payload.workContext = addConversationContextDetail(
            payload.workContext, '小妤 · 当前对话技能', '本轮先读取并应用所选技能的 SKILL.md', selected.join(', '),
          )
          payload.expectedToolOverrides = state.session.toolOverrides ?? null
        }
      }
      const capabilityChoices = this.sessionChoices(sessionKey, 'capabilityChoices')
      if (Object.values(capabilityChoices).some(Boolean)) {
        const state = await this.sessionCapabilityState(agentId, sessionKey)
        const { selected } = this.selectedCapabilities(state, capabilityChoices)
        if (selected.length) {
          payload.workContext = addConversationContextDetail(
            payload.workContext, '小妤 · 对话能力', '优先通过 tool_search 查找适用能力', selected.join(', '),
          )
          payload.expectedToolOverrides = state.session.toolOverrides ?? null
        }
      }
      if (params.model !== undefined || params.permissionMode !== undefined) this.saveSessionSettings(sessionKey, settings)
      sending = true
      const result = await this.rpc('chat.send', payload)
      const runId = String(result?.runId || requestId)
      this.activeRuns.delete(pendingId)
      const tracked = this.activeSessions.get(sessionKey)
      if ((tracked === pendingId || tracked === runId) && !this.finishedRunSessions.has(runId)) {
        this.activeSessions.set(sessionKey, runId)
        this.activeRuns.add(runId)
        this.scheduleSessionReconciliation(sessionKey)
      }
      this.emitStatus()
      return { ...result, runId }
    } catch (error) {
      // A dropped acknowledgment may follow a successful admission. Keep the
      // original request identity while native events and the projection catch up.
      if (sending && /timed? ?out|timeout|disconnect|connection (?:closed|lost)|socket closed/i.test(String(error?.message))) {
        if (this.activeSessions.get(sessionKey) === pendingId) {
          this.activeRuns.delete(pendingId)
          this.activeSessions.set(sessionKey, requestId)
          this.activeSessionStartedAt.set(sessionKey, Date.now())
          this.activeRuns.add(requestId)
          this.scheduleSessionReconciliation(sessionKey)
        }
        this.emitStatus()
        return { runId: requestId, status: 'unknown' }
      }
      this.clearTrackedRun(sessionKey, pendingId)
      this.emitStatus()
      throw error
    }
  }

  rememberFinishedRun(runId, sessionKey) {
    this.finishedRunSessions.set(runId, sessionKey)
    if (this.finishedRunSessions.size > 512) this.finishedRunSessions.delete(this.finishedRunSessions.keys().next().value)
  }

  clearTrackedRun(sessionKey, expected) {
    if (!expected || this.activeSessions.get(sessionKey) !== expected) return
    this.activeRuns.delete(expected)
    this.activeRunStatuses.delete(expected)
    this.activeSessions.delete(sessionKey)
    this.activeSessionStartedAt.delete(sessionKey)
    this.clearSessionReconcileTimer(sessionKey)
  }

  async runStatus(params) {
    const sessionKey = String(params.sessionKey || params.key || '')
    const agentId = sessionOwner(sessionKey, params.agentId)
    return this.readRunStatus(sessionKey, agentId)
  }

  async readRunStatus(sessionKey, agentId) {
    const local = () => {
      const tracked = this.activeSessions.get(sessionKey)
      const pending = tracked?.startsWith('pending:')
      return { sessionKey, agentId, active: Boolean(tracked), runId: pending ? null : tracked || null,
        status: pending ? 'queued' : tracked ? this.activeRunStatuses.get(tracked) || 'running' : 'idle' }
    }
    const tracked = this.activeSessions.get(sessionKey)
    if (tracked?.startsWith('pending:')) return local()
    let row
    try {
      // An embedded turn can have hasActiveRun=true while the Gateway omits
      // activeRunIds. Use only an identity already associated with this exact key.
      const result = await this.rpc('sessions.describe', { key: sessionKey, ...(agentId ? {agentId} : {}) })
      row = result?.session
    } catch (error) {
      this.log(`session status unavailable: ${error.message}`)
      return { ...local(), status: 'unknown' }
    }
    if (tracked !== this.activeSessions.get(sessionKey)) return local()
    // Missing projections are not completion receipts.
    if (!row || (row.key && row.key !== sessionKey) || (row.agentId && agentId && row.agentId !== agentId)) {
      return { ...local(), status: 'unknown' }
    }
    const ids = Array.isArray(row.activeRunIds) ? row.activeRunIds.filter(id => typeof id === 'string' && id) : []
    const state = String(row.status || row.runStatus || '').toLowerCase()
    const liveStates = ['queued', 'running', 'thinking', 'working', 'waiting_approval', 'blocked']
    const active = row.hasActiveRun === true || ids.length > 0 || (row.hasActiveRun !== false && liveStates.includes(state))
    if (active) {
      const runId = ids.length === 1 ? ids[0] : ids.includes(tracked) ? tracked : !ids.length ? tracked || null : null
      if (runId && this.finishedRunSessions.has(runId)) return { ...local(), status: 'unknown' }
      if (runId && runId !== tracked) {
        if (tracked) {
          this.rememberFinishedRun(tracked, sessionKey)
          this.clearTrackedRun(sessionKey, tracked)
        }
        this.activeSessions.set(sessionKey, runId)
        this.activeSessionStartedAt.set(sessionKey, Date.now())
        this.activeRuns.add(runId)
        this.scheduleSessionReconciliation(sessionKey)
      }
      const status = ['queued', 'waiting_approval', 'blocked'].includes(state) ? state : this.activeRunStatuses.get(runId) || 'running'
      return { sessionKey, agentId, active: true, runId, status }
    }
    // A new dispatch may not be visible in SQLite yet.
    if (tracked && Date.now() - (this.activeSessionStartedAt.get(sessionKey) || 0) < 5000) return local()
    if (tracked) {
      this.rememberFinishedRun(tracked, sessionKey)
      this.clearTrackedRun(sessionKey, tracked)
      this.emitStatus()
    }
    return local()
  }

  async isTrackedSessionActive(sessionKey) {
    const result = await this.readRunStatus(sessionKey, /^agent:([^:]+):/.exec(sessionKey)?.[1])
    return result.active || result.status === 'unknown'
  }

  clearSessionReconcileTimer(sessionKey) {
    const timer = this.sessionReconcileTimers.get(sessionKey)
    if (timer) clearTimeout(timer)
    this.sessionReconcileTimers.delete(sessionKey)
  }

  scheduleSessionReconciliation(sessionKey, delayMs = 5500) {
    this.clearSessionReconcileTimer(sessionKey)
    const timer = setTimeout(async () => {
      this.sessionReconcileTimers.delete(sessionKey)
      if (!this.activeSessions.has(sessionKey) || this.stopRequested) return
      const active = await this.isTrackedSessionActive(sessionKey)
      if (active && this.activeSessions.has(sessionKey) && !this.stopRequested) {
        this.scheduleSessionReconciliation(sessionKey, 2000)
      }
    }, delayMs)
    timer.unref?.()
    this.sessionReconcileTimers.set(sessionKey, timer)
  }

  async interruptRun(params = {}) {
    const sessionKey = String(params.sessionKey || params.key || '').trim()
    const agentId = desktopSessionOwner(sessionKey, params.agentId)
    const expected = String(params.runId || '')
    if (!expected || expected.startsWith('pending:')) return { aborted: false, stale: true }
    const current = await this.runStatus({sessionKey, agentId})
    if (current.status === 'unknown') return { aborted: false, status: 'unknown' }
    if (current.runId !== expected || !current.active) return { aborted: false, stale: true }
    // Always send the expected run, even when the session changes after the
    // probe. Clearing an entire session's queue could cancel a later turn.
    const result = await this.rpc('sessions.abort', {key: sessionKey, agentId, runId: expected, clearQueued: false})
    const aborted = result?.abortedRunId === expected && result.status === 'aborted'
    if (aborted) {
      this.rememberFinishedRun(expected, sessionKey)
      this.clearTrackedRun(sessionKey, expected)
      this.emitStatus()
    }
    return { ...result, aborted }
  }

  loadBotMetadata() {
    const data = readJson(this.botStatePath, {}) || {}
    return { ...data, archived: data.archived || {}, profiles: data.profiles || {}, sessions: data.sessions || {} }
  }

  saveBotMetadata(value) {
    atomicWriteJson(this.botStatePath, value)
  }

  async installDirector() {
    // Use the native roster mutation to migrate an implicit single-agent
    // installation without reassigning its past conversations or routines.
    return this.serializeMutation('install:' + DIRECTOR_ID, async () => {
      if (!this.directorNeedsInstall) return
      const request = this.client.request.bind(this.client)
      const roster = await request('agents.list', {})
      const registered = roster.agents.find(agent => (agent.id || agent.agentId) === DIRECTOR_ID)
      const saved = this.loadBotMetadata().profiles[DIRECTOR_ID]
      if (registered && !saved?.directorTemplate) {
        // A manually configured Gateway agent already owns this reserved ID.
        this.directorNeedsInstall = false
        return
      }
      const instructions = fs.readFileSync(path.join(__dirname, 'director.md'), 'utf8').trim()
      const digest = value => crypto.createHash('sha256').update(value).digest('hex')
      const version = digest(instructions)
      const customized = saved?.directorTemplate && digest(saved.instructions ?? '') !== saved.directorTemplate
      // Legacy built-ins used Xiaoyu's avatar. Apply the new defaults once so
      // choosing that avatar again, or renaming the director, survives restarts.
      const identityChanged = !saved?.directorIdentityVersion
      const nativeName = registered?.name
      const nativeHasLegacyName = !nativeName || nativeName === DIRECTOR_ID || nativeName === LEGACY_DIRECTOR_NAME
      const identity = {}
      if (identityChanged) {
        const defaultName = nativeHasLegacyName ? DIRECTOR_NAME : nativeName
        identity.name = saved?.name && saved.name !== LEGACY_DIRECTOR_NAME ? saved.name : defaultName
        identity.avatar = saved?.avatar && saved.avatar !== 'xiaoyu' ? saved.avatar : 'director'
        identity.directorIdentityVersion = 2
      }
      if (registered && saved?.creationComplete) {
        const templateChanged = saved.directorTemplate !== version
        if (identityChanged || templateChanged) {
          if (identityChanged && nativeHasLegacyName && nativeName !== identity.name) {
            await request('agents.update', { agentId: DIRECTOR_ID, name: identity.name })
          }
          const promptChanged = (templateChanged && !customized) || (identityChanged && identity.name !== saved.name)
          const prompt = customized ? saved.instructions : instructions
          if (promptChanged) await this.writeEmployeeInstructions(DIRECTOR_ID, { ...saved, ...identity, instructions: prompt }, request)
          this.storeProfile(DIRECTOR_ID, {
            ...identity, directorTemplate: version, ...(promptChanged ? { instructions: prompt, promptApplied: true } : {}),
          })
        }
        this.directorNeedsInstall = false
        return
      }
      const workspace = path.join(this.rootDir, 'workspaces', 'agents', DIRECTOR_ID)
      const profile = {
        name: DIRECTOR_NAME, title: '', avatar: 'director', model: 'auto', toolPolicy: { permissionMode: 'guarded' },
        browserProfile: 'persist:szyg-agent-' + DIRECTOR_ID, ...saved, ...identity,
        workspace, instructions: customized ? saved.instructions : instructions, directorTemplate: version,
      }
      // Record ownership before touching the Gateway. Incomplete provisioning
      // can be resumed after a crash without duplicating the native agent.
      this.storeProfile(DIRECTOR_ID, { ...profile, creationComplete: false, promptApplied: false })
      if (!registered) {
        copyTemplateDirectory(path.join(__dirname, 'workspace-template'), workspace)
        await request('agents.create', {
          name: DIRECTOR_ID, workspace, model: this.gatewayModelSettings(profile.model).model,
        })
      }
      if (registered?.name !== profile.name) {
        await request('agents.update', { agentId: DIRECTOR_ID, name: profile.name })
      }
      await this.writeEmployeeInstructions(DIRECTOR_ID, profile, request)
      this.storeProfile(DIRECTOR_ID, { creationComplete: true, promptApplied: true })
      this.directorNeedsInstall = false
    })
  }

  async listBots(params = {}) {
    if (this.directorNeedsInstall) await this.installDirector().catch(error => this.log(`director setup deferred: ${error.message}`))
    const result = await this.rpc('agents.list', params)
    const metadata = this.loadBotMetadata()
    const agents = Array.isArray(result?.agents) ? result.agents : Array.isArray(result) ? result : []
    const defaultId = agents.find(a => (a.id || a.agentId) === result.defaultId)?.id
      || agents.find(a => (a.id || a.agentId) === 'main')?.id || agents[0]?.id
    return {
      ...result, defaultId,
      agents: agents.map(agent => {
        const id = agent.id || agent.agentId
        const profile = metadata.profiles[id] || {}
        return {
          ...agent, ...profile,
          name: profile.name || agent.name || (id === defaultId ? '小妤' : agent.identity?.name || id),
          model: profile.model || 'auto',
          archived: Boolean(metadata.archived[id]),
        }
      }),
    }
  }

  sessionHistory(params) {
    const agentId = sessionOwner(params.sessionKey, params.agentId)
    return this.rpc('chat.history', { ...params, agentId })
  }

  async sessionDirectorRenders(params) {
    const key = String(params.sessionKey || '')
    const agentId = desktopSessionOwner(key, params.agentId)
    if (agentId !== DIRECTOR_ID) return { jobs: [] }
    const { messages } = await this.rpc('sessions.get', { key, agentId, limit: 200 })
    return { jobs: directorRenderJobs(Array.isArray(messages) ? messages : []) }
  }

  sessionChoices(key, field) {
    if (key.includes(':dashboard:incognito-')) return this.privateSessionChoices.get(key)?.[field] || {}
    return this.loadBotMetadata().sessions[key]?.[field] || {}
  }

  saveSessionChoices(key, field, choices) {
    if (key.includes(':dashboard:incognito-')) {
      this.privateSessionChoices.set(key, { ...this.privateSessionChoices.get(key), [field]: choices })
      return
    }
    const metadata = this.loadBotMetadata()
    metadata.sessions[key] = { ...metadata.sessions[key], [field]: choices }
    this.saveBotMetadata(metadata)
  }

  async sessionSkillState(agentId, key) {
    if (typeof agentId !== 'string' || !/^[a-z0-9_-]+$/i.test(agentId)) throw new Error('请选择当前员工')
    if (key !== undefined) desktopSessionOwner(key, agentId)
    // The renderer projection redacts keys such as "1password" and truncates large
    // lists. Native compare-and-swap requires the exact overlay, kept in this process.
    const request = this.client ? this.client.request.bind(this.client) : this.rpc.bind(this)
    const [status, description] = await Promise.all([
      request('skills.status', { agentId, ...(key ? { sessionKey: key } : {}) }),
      key ? request('sessions.describe', { key, agentId }) : null,
    ])
    const session = description?.session
    if (key && (session?.key !== key || session.agentId !== agentId)) throw new Error('找不到该员工的对话')
    const allow = this.loadBotMetadata().profiles[agentId]?.skills
    const skills = (status?.skills || []).filter(skill =>
      LOCAL_SKILL_SOURCES.has(skill.source) && validSkillKey(skill.name) && validSkillKey(skill.skillKey || skill.name)
      && skill.eligible === true && skill.modelVisible === true && skill.userInvocable === true
      && !skill.disabled && !skill.blockedByAllowlist && !skill.blockedByAgentFilter
      && (!Array.isArray(allow) || allow.includes(skill.name)))
    return { session, skills }
  }

  selectedSkills(state, choices) {
    return state.skills.filter(skill => choices[skill.name] === true
      && state.session?.toolOverrides?.skills?.[skill.skillKey || skill.name] !== false).map(skill => skill.name)
  }

  async skillCatalog({ agentId, sessionKey }) {
    const { session, skills } = await this.sessionSkillState(agentId, sessionKey)
    const choices = sessionKey ? this.sessionChoices(sessionKey, 'skillChoices') : {}
    return { skills: skills.filter(skill => session?.toolOverrides?.skills?.[skill.skillKey || skill.name] !== false
      || choices[skill.name] === false).map(({ name, description }) => ({ name, description })) }
  }

  async skillSelection({ agentId, sessionKey }) {
    desktopSessionOwner(sessionKey, agentId)
    const state = await this.sessionSkillState(agentId, sessionKey)
    return { selected: this.selectedSkills(state, this.sessionChoices(sessionKey, 'skillChoices')) }
  }

  changeSkillSelection({ agentId, sessionKey, name }, attach) {
    desktopSessionOwner(sessionKey, agentId)
    if (!validSkillKey(name)) throw new Error('技能名称无效')
    return this.serializeMutation('session:' + sessionKey, async () => {
      const state = await this.sessionSkillState(agentId, sessionKey)
      const { session, skills } = state
      if (session.archived || session.sendDisabledReason || session.sharingRole === 'viewer') throw new Error('此对话不可修改')
      if (session.hasActiveRun || this.activeSessions.has(sessionKey)) throw new Error('请等待当前回复完成后再更改技能')
      const choices = this.sessionChoices(sessionKey, 'skillChoices')
      const skill = skills.find(row => row.name === name)
      if (!skill) throw new Error('当前员工没有可用的这个技能')
      const skillKey = skill.skillKey || name
      const before = session.toolOverrides ?? null
      const overrides = { ...before?.skills }
      if (attach && overrides[skillKey] === false && choices[name] !== false) throw new Error('当前对话已限制此技能')
      if (choices[name] === attach || (!attach && choices[name] !== true)) return { selected: this.selectedSkills(state, choices) }
      const next = { ...choices, [name]: attach }
      // A positive native override grants a skill even outside the agent policy. Restore base policy on attach.
      if (attach) delete overrides[skillKey]
      else overrides[skillKey] = false
      const updated = { ...before, skills: overrides }
      const changed = { ...state, session: { ...session, toolOverrides: updated } }
      const selected = this.selectedSkills(changed, next)
      if (JSON.stringify(selected.join(', ')).length > 128) throw new Error('所选技能名称超出本轮可传递的长度，请先移除一个技能')
      await this.rpc('sessions.patch', {
        key: sessionKey, agentId, expectedSessionId: session.sessionId, expectedToolOverrides: before, toolOverrides: updated,
      })
      this.saveSessionChoices(sessionKey, 'skillChoices', next)
      return { selected }
    })
  }

  async businessCapabilityCatalog() {
    const { backendPort, businessMcpToken } = this.options
    if (!backendPort || !businessMcpToken) throw new Error('应用能力暂时不可用')
    const response = await fetch(`http://127.0.0.1:${backendPort}/api/mcp/szyg-business`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${businessMcpToken}` },
      body: JSON.stringify({ jsonrpc: '2.0', id: 'xiaoyu-capabilities', method: 'tools/list' }),
      signal: AbortSignal.timeout(8000),
    })
    if (!response.ok) throw new Error('应用能力暂时不可用')
    const { result } = await response.json()
    if (!Array.isArray(result?.tools)) throw new Error('应用能力暂时不可用')
    return result.tools.filter(tool => validSkillKey(tool?.name)).map(tool => ({
      name: tool.name,
      title: String(tool.title || tool.name),
      description: String(tool.description || ''),
      domain: String(tool._meta?.['szyg/domain'] || ''),
    }))
  }

  async sessionCapabilityState(agentId, key) {
    if (typeof agentId !== 'string' || !/^[a-z0-9_-]+$/i.test(agentId)) throw new Error('请选择当前员工')
    if (key !== undefined) desktopSessionOwner(key, agentId)
    const request = this.client ? this.client.request.bind(this.client) : this.rpc.bind(this)
    const [catalog, description] = await Promise.all([
      this.businessCapabilityCatalog(),
      key ? request('sessions.describe', { key, agentId }) : null,
    ])
    const session = description?.session
    if (key && (session?.key !== key || session.agentId !== agentId)) throw new Error('找不到该员工的对话')
    const policy = this.loadBotMetadata().profiles[agentId]?.toolPolicy
    const native = session?.toolOverrides
    const blocked = native?.mcpServers?.[BUSINESS_MCP_SERVER] === false || policy?.mcpServers?.[BUSINESS_MCP_SERVER] === false
    const excluded = policy?.mcpToolsDeny?.[BUSINESS_MCP_SERVER]
    const capabilities = blocked ? [] : catalog.filter(({ name }) => !Array.isArray(excluded) || !excluded.includes(name))
    const deny = native?.mcpToolsDeny?.[BUSINESS_MCP_SERVER] ?? []
    return { session, capabilities, deny }
  }

  selectedCapabilities({ capabilities, deny }, choices) {
    const rows = capabilities.filter(({ name }) => choices[name] === true && !deny.includes(name))
    return {
      selected: rows.map(({ name }) => name),
      titles: Object.fromEntries(rows.map(({ name, title }) => [name, title])),
    }
  }

  async capabilityCatalog({ agentId, sessionKey }) {
    const { capabilities, deny } = await this.sessionCapabilityState(agentId, sessionKey)
    const choices = sessionKey ? this.sessionChoices(sessionKey, 'capabilityChoices') : {}
    return { capabilities: capabilities.filter(({ name }) => !deny.includes(name) || choices[name] === false) }
  }

  async capabilitySelection({ agentId, sessionKey }) {
    desktopSessionOwner(sessionKey, agentId)
    const choices = this.sessionChoices(sessionKey, 'capabilityChoices')
    if (!Object.values(choices).some(Boolean)) return { selected: [], titles: {} }
    const state = await this.sessionCapabilityState(agentId, sessionKey)
    return this.selectedCapabilities(state, choices)
  }

  changeCapabilitySelection({ agentId, sessionKey, name }, attach) {
    desktopSessionOwner(sessionKey, agentId)
    if (!validSkillKey(name)) throw new Error('应用能力名称无效')
    return this.serializeMutation('session:' + sessionKey, async () => {
      const state = await this.sessionCapabilityState(agentId, sessionKey)
      const { session, capabilities, deny } = state
      if (session.archived || session.sendDisabledReason || session.sharingRole === 'viewer') throw new Error('此对话不可修改')
      if (session.hasActiveRun || this.activeSessions.has(sessionKey)) throw new Error('请等待当前回复完成后再更改应用能力')
      if (!capabilities.some(capability => capability.name === name)) throw new Error('当前员工没有可用的这个应用能力')
      const choices = this.sessionChoices(sessionKey, 'capabilityChoices')
      const wasDenied = deny.includes(name)
      if (attach && wasDenied && choices[name] !== false) throw new Error('当前对话已限制此应用能力')
      if (choices[name] === attach || (!attach && choices[name] !== true)) return this.selectedCapabilities(state, choices)
      const next = { ...choices, [name]: attach }
      const nextDeny = attach ? deny.filter(tool => tool !== name) : [...new Set([...deny, name])]
      const selection = this.selectedCapabilities({ capabilities, deny: nextDeny }, next)
      if (JSON.stringify(selection.selected.join(', ')).length > 128) throw new Error('本轮加载的应用能力超出长度限制，请先移除一项')
      // Adding an application tool only restores this chat's own previous
      // exclusion. It must never grant additional native tool access.
      if (wasDenied !== nextDeny.includes(name)) {
        const before = session.toolOverrides ?? null
        const mcpToolsDeny = { ...before?.mcpToolsDeny, [BUSINESS_MCP_SERVER]: nextDeny }
        if (!nextDeny.length) delete mcpToolsDeny[BUSINESS_MCP_SERVER]
        await this.rpc('sessions.patch', {
          key: sessionKey, agentId, expectedSessionId: session.sessionId, expectedToolOverrides: before,
          toolOverrides: { ...before, mcpToolsDeny },
        })
      }
      this.saveSessionChoices(sessionKey, 'capabilityChoices', next)
      return selection
    })
  }

  async listSessions(params) {
    const result = await this.rpc('sessions.list', params)
    const { sessions } = this.loadBotMetadata()
    const key = Array.isArray(result.sessions) ? 'sessions' : 'items'
    if (!Array.isArray(result[key])) return result
    return { ...result, [key]: result[key].map(row => {
      const sessionKey = row.key || row.sessionKey
      const canConfigure = isDesktopSession(sessionKey)
      const agentId = /^agent:([a-z0-9_-]+):/i.exec(sessionKey)?.[1] || row.agentId
      const pref = sessions[sessionKey]
      const id = String(row.model || '').replace(/^xiaoyu-managed\//, '')
      return {
        ...row, agentId, canConfigure,
        model: pref?.model || (employeeModels.includes(id) ? id : 'auto'),
        permissionMode: row.permissionMode || pref?.permissionMode || 'guarded',
      }
    }) }
  }

  gatewayModelSettings(model, deepThinking) {
    const reasoning = deepThinking === true || model === 'kimi-k3-1-pro-261024'
    return {
      model: model && model !== 'auto' ? 'xiaoyu-managed/' + model : reasoning ? XIAOYU_REASONING_MODEL : XIAOYU_FAST_MODEL,
      thinkingLevel: reasoning ? 'medium' : 'off', fastMode: !reasoning,
    }
  }

  sessionSettings(params, agentId, sessionKey) {
    const metadata = this.loadBotMetadata()
    const profile = metadata.profiles[agentId] || {}
    const saved = metadata.sessions[sessionKey] || {}
    const mode = params.permissionMode ?? saved.permissionMode ?? profile.toolPolicy?.permissionMode ?? 'guarded'
    return {
      model: modelChoice(params.model ?? saved.model ?? profile.model ?? 'auto'),
      permissionMode: permissionChoice(mode),
    }
  }

  saveSessionSettings(key, next) {
    if (!key) return
    const metadata = this.loadBotMetadata()
    const previous = metadata.sessions[key]
    if (previous?.model === next.model && previous?.permissionMode === next.permissionMode) return
    metadata.sessions[key] = { ...previous, ...next }
    this.saveBotMetadata(metadata)
  }

  configureSession(params) {
    const key = String(params.key || '')
    const agentId = desktopSessionOwner(key, params.agentId)
    return this.serializeMutation('session:' + key, async () => {
      const settings = this.sessionSettings(params, agentId, key)
      const patch = { key, ...(agentId ? { agentId } : {}) }
      if (params.model !== undefined || params.deepThinking !== undefined) Object.assign(patch, this.gatewayModelSettings(settings.model, params.deepThinking))
      if (params.permissionMode !== undefined) patch.permissionMode = settings.permissionMode
      const result = await this.rpc('sessions.patch', patch)
      this.saveSessionSettings(key, settings)
      return { ...result, ...settings }
    })
  }

  async createSession(params = {}) {
    const agentId = String(params.agentId || '').trim()
    if (!agentId) throw new Error('agentId is required')
    if (params.key) desktopSessionOwner(params.key, agentId)
    await this.ensureEmployeeInstructions(agentId)
    const profile = this.loadBotMetadata().profiles[agentId] || {}
    const settings = this.sessionSettings(params, agentId, params.key)
    const payload = {
      agentId,
      ...this.gatewayModelSettings(settings.model, params.deepThinking),
      permissionMode: settings.permissionMode,
      toolOverrides: { mcpServers: { [BUSINESS_MCP_SERVER]: true } },
    }
    for (const key of ['key', 'idempotencyKey', 'label', 'displayName', 'titleSource', 'category', 'incognito', 'visibility']) {
      if (Object.prototype.hasOwnProperty.call(params, key)) payload[key] = params[key]
    }
    if (Array.isArray(profile.skills)) {
      const skillStatus = await this.rpc('skills.status', { agentId })
      const rows = Array.isArray(skillStatus?.skills) ? skillStatus.skills : Array.isArray(skillStatus?.items) ? skillStatus.items : []
      const allow = new Set(profile.skills.map(String))
      payload.toolOverrides.skills = {}
      for (const row of rows) {
        const record = row && typeof row === 'object' ? row : {}
        const name = String(record.name || record.slug || record.id || '')
        const skillKey = record.skillKey || name
        if (validSkillKey(skillKey) && !allow.has(name)) payload.toolOverrides.skills[skillKey] = false
      }
    }
    if (profile.toolPolicy?.mcpToolsDeny && typeof profile.toolPolicy.mcpToolsDeny === 'object') {
      payload.toolOverrides.mcpToolsDeny = sanitizeForRenderer(profile.toolPolicy.mcpToolsDeny)
    }
    const result = await this.rpc('sessions.create', payload)
    this.saveSessionSettings(result.key || result.sessionKey, settings)
    return result
  }

  async saveRoutine(params = {}) {
    const payload = { ...params }
    const id = payload.id
    const deepThinking = payload.deepThinking === true
    delete payload.id
    delete payload.deepThinking
    if (payload.payload?.kind === 'agentTurn') {
      const profile = this.loadBotMetadata().profiles[payload.agentId]
      if (payload.agentId) await this.ensureEmployeeInstructions(payload.agentId)
      const selected = this.gatewayModelSettings(profile?.model, deepThinking)
      const model = payload.payload.model || selected.model
      const kimi = model === 'xiaoyu-managed/kimi-k3-1-pro-261024' || model === 'kimi-k3-1-pro-261024'
      payload.payload = {
        ...payload.payload, model,
        thinking: kimi && (!payload.payload.thinking || payload.payload.thinking === 'off')
          ? 'medium' : payload.payload.thinking || selected.thinkingLevel,
      }
    }
    return this.rpc(id ? 'cron.update' : 'cron.add', id ? { id, patch: payload } : payload)
  }

  async writeEmployeeInstructions(agentId, profile, request = this.client
    ? this.client.request.bind(this.client) : this.rpc.bind(this)) {
    const params = { agentId, name: 'AGENTS.md' }
    // Preserve the full document even when it exceeds renderer string limits.
    const result = await request('agents.files.get', params)
    const file = result.file
    const previous = file?.content || fs.readFileSync(path.join(__dirname, 'workspace-template', 'AGENTS.md'), 'utf8')
    const content = managedInstructions(previous, profile)
    if (content !== file?.content) {
      await request('agents.files.set', { ...params, content, ...(file?.hash ? {expectedHash: file.hash} : {expectedMissing: true}) })
    }
  }

  async ensureEmployeeInstructions(agentId) {
    const profile = this.loadBotMetadata().profiles[agentId]
    if (!profile || profile.promptApplied || (!profile.instructions && !profile.creationPending)) return
    await this.serializeMutation('bot:' + agentId, async () => {
      const current = this.loadBotMetadata().profiles[agentId]
      if (!current || current.promptApplied) return
      const roster = await this.listBots()
      const bot = roster.agents.find(row => row.id === agentId)
      if (!bot || roster.defaultId === agentId) return
      if (current.creationPending) await this.rpc('agents.update', { agentId, name: current.name })
      await this.writeEmployeeInstructions(agentId, { ...current, name: bot.name })
      this.storeProfile(agentId, { promptApplied: true, creationComplete: true, creationPending: false })
    })
  }

  storeProfile(agentId, patch) {
    const metadata = this.loadBotMetadata()
    const previous = metadata.profiles[agentId] || {}
    metadata.profiles[agentId] = {
      ...previous, ...patch,
      ...(patch.toolPolicy ? { toolPolicy: { ...previous.toolPolicy, ...patch.toolPolicy } } : {}),
    }
    this.saveBotMetadata(metadata)
  }

  createBot(params = {}) {
    const fields = profileChanges(params)
    if (!fields.name) throw new Error('请填写员工姓名')
    const agentId = creationId(params.requestId)
    return this.serializeMutation('bot:' + agentId, async () => {
      const roster = await this.listBots()
      const alreadyCreated = roster.agents.find(a => (a.id || a.agentId) === agentId)
      const saved = this.loadBotMetadata().profiles[agentId]
      if (alreadyCreated && saved?.creationComplete) return { ok: true, agentId }
      const workspace = path.join(this.rootDir, 'workspaces', 'agents', agentId)
      const profile = {
        title: '', instructions: '', skills: null, toolPolicy: { permissionMode: 'guarded' },
        model: 'auto', avatar: 'xiaoyu', ...fields, workspace, browserProfile: 'persist:szyg-agent-' + agentId,
      }
      this.storeProfile(agentId, { ...profile, creationPending: true })
      if (!alreadyCreated) {
        copyTemplateDirectory(path.join(__dirname, 'workspace-template'), workspace)
        // The Gateway derives the ID from name and rejects names made solely of
        // CJK characters. Reserve an opaque ID, then set its display name.
        await this.rpc('agents.create', {
          name: agentId, workspace, model: this.gatewayModelSettings(profile.model).model,
          ...(params.emoji ? { emoji: String(params.emoji) } : {}),
        })
      }
      // The stable request ID also allows retries after a Gateway timeout or
      // crash between creation, renaming, and updating the bootstrap document.
      await this.rpc('agents.update', { agentId, name: fields.name })
      await this.writeEmployeeInstructions(agentId, profile)
      this.storeProfile(agentId, { ...profile, promptApplied: true, creationComplete: true, creationPending: false })
      return { ok: true, agentId }
    })
  }

  updateBot(params = {}) {
    const agentId = String(params.agentId || '')
    if (!agentId) throw new Error('请选择员工')
    return this.serializeMutation('bot:' + agentId, async () => {
      const roster = await this.listBots()
      const agent = roster.agents.find(a => (a.id || a.agentId) === agentId)
      if (!agent) throw new Error('员工不存在')
      if (agentId === roster.defaultId && Object.keys(params).some(key => key !== 'agentId' && key !== 'avatar')) {
        throw new Error('默认员工仅支持更改头像')
      }
      const patch = profileChanges(params)
      if (patch.name !== undefined || patch.model !== undefined || params.emoji !== undefined) {
        await this.rpc('agents.update', {
          agentId, ...(patch.name !== undefined ? { name: patch.name } : {}),
          ...(params.emoji !== undefined ? { emoji: String(params.emoji) } : {}),
          ...(patch.model !== undefined ? { model: this.gatewayModelSettings(patch.model).model } : {}),
        })
      }
      if (patch.name !== undefined || patch.title !== undefined || patch.instructions !== undefined) {
        await this.writeEmployeeInstructions(agentId, {...agent, ...patch})
        patch.promptApplied = true
      }
      this.storeProfile(agentId, patch)
      return { ok: true, agentId }
    })
  }

  async archiveBot(agentId, archived = true) {
    return this.serializeMutation('bot:' + agentId, async () => {
      const roster = await this.listBots()
      if (agentId === roster.defaultId) throw new Error('默认员工无法归档')
      if (!roster.agents.some(a => (a.id || a.agentId) === agentId)) throw new Error('员工不存在')
      const metadata = this.loadBotMetadata()
      if (archived) metadata.archived[agentId] = Date.now()
      else delete metadata.archived[agentId]
      this.saveBotMetadata(metadata)
      return { ok: true, agentId, archived }
    })
  }
}

module.exports = {
  OpenClawRuntimeManager,
  atomicWriteJson,
  findAvailablePort,
  normalizeGatewayEvent,
  resolveRuntimeCandidates,
  resolveRuntimeLayout,
  sanitizeForRenderer,
  sha256FileSync,
  generateDeviceIdentity,
  publicKeyRawBase64UrlFromPem,
  signDevicePayload,
  XIAOYU_MANAGED_MODEL,
  XIAOYU_FAST_MODEL,
  XIAOYU_REASONING_MODEL,
}
