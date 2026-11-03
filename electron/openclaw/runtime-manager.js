const { spawn } = require('child_process')
const crypto = require('crypto')
const fs = require('fs')
const net = require('net')
const path = require('path')
const { CredentialStore } = require('./credential-store')
const {
  OPENCLAW_RUNTIME_VERSION,
  OPENCLAW_GATEWAY_CLIENT_VERSION,
  OPENCLAW_PROTOCOL_VERSION,
  OPENCLAW_WIRE_VERSION,
  OPENCLAW_NODE_VERSION,
} = require('./runtime-constants')

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
  const nodeExecutable = path.join(root, 'node.exe')
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
    config.mcp = { ...(config.mcp || {}), servers: { ...(config.mcp?.servers || {}), 'szyg-business': definition } }
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
          ],
        },
      },
    }
    config.agents = {
      ...(config.agents || {}),
      defaults: {
        ...(config.agents?.defaults || {}),
        model: { primary: XIAOYU_MANAGED_MODEL, fallbacks: [] },
        modelPolicy: { allow: [XIAOYU_FAST_MODEL, XIAOYU_REASONING_MODEL] },
      },
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
    this.child = spawn(layout.nodeExecutable, args, {
      cwd: this.rootDir,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })
    this.child.stdout.on('data', (data) => this.log(`stdout ${String(data).trim()}`))
    this.child.stderr.on('data', (data) => this.log(`stderr ${String(data).trim()}`))
    this.child.once('error', (error) => this.fail(error))
    this.child.once('exit', (code, signal) => this.handleExit(code, signal, layout, env, gatewayToken))
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
    const runId = normalized.payload?.runId
    const sessionKey = normalized.payload?.sessionKey
    const status = normalized.payload?.runStatus
    if (runId && status && TERMINAL_STATES.has(status)) {
      this.activeRuns.delete(runId)
      // Successful final chat events are not guaranteed to carry sessionKey.
      // Reconcile by run id as well so a completed turn cannot leave the
      // session permanently locked in Xiaoyu's fail-first queue.
      for (const [trackedSessionKey, trackedRunId] of this.activeSessions) {
        if (trackedRunId === runId) {
          this.activeSessions.delete(trackedSessionKey)
          this.activeSessionStartedAt.delete(trackedSessionKey)
          this.clearSessionReconcileTimer(trackedSessionKey)
        }
      }
    } else if (runId) this.activeRuns.add(runId)
    if (sessionKey && status && TERMINAL_STATES.has(status)) {
      this.activeSessions.delete(sessionKey)
      this.activeSessionStartedAt.delete(sessionKey)
      this.clearSessionReconcileTimer(sessionKey)
    } else if (sessionKey && runId) {
      this.activeSessions.set(sessionKey, runId)
      if (!this.activeSessionStartedAt.has(sessionKey)) this.activeSessionStartedAt.set(sessionKey, Date.now())
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
    if (this.child) {
      const child = this.child
      this.child = null
      child.kill()
    }
    if (this.client) {
      try { await this.client.stopAndWait({ timeoutMs: 1500 }) } catch (_) {}
      this.client = null
    }
    this.activeRuns.clear()
    this.activeSessions.clear()
    this.activeSessionStartedAt.clear()
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

  async sendRun(params = {}) {
    const sessionKey = String(params.sessionKey || '').trim()
    const message = String(params.message || '')
    if (!sessionKey) throw new Error('sessionKey is required')
    if (!message.trim()) throw new Error('消息不能为空')
    if (await this.isTrackedSessionActive(sessionKey)) throw new Error('该会话已有任务正在执行，请等待完成后再发送')
    const pendingId = `pending:${crypto.randomUUID()}`
    this.activeSessions.set(sessionKey, pendingId)
    this.activeSessionStartedAt.set(sessionKey, Date.now())
    this.activeRuns.add(pendingId)
    this.emitStatus()
    try {
      const deepThinking = params.deepThinking === true
      // Model selection is a session property in the Gateway protocol. Patch
      // it immediately before dispatch so an existing conversation honors the
      // current composer toggle instead of retaining an earlier costly mode.
      await this.rpc('sessions.patch', {
        key: sessionKey,
        model: deepThinking ? XIAOYU_REASONING_MODEL : XIAOYU_FAST_MODEL,
        thinkingLevel: deepThinking ? 'medium' : 'off',
        fastMode: deepThinking ? false : true,
      })
      const payload = { ...params, sessionKey, message, deliver: false, idempotencyKey: crypto.randomUUID() }
      delete payload.deepThinking
      delete payload.queueMode
      const result = await this.rpc('chat.send', payload)
      const runId = String(result?.runId || pendingId)
      this.activeRuns.delete(pendingId)
      if (this.activeSessions.has(sessionKey)) {
        this.activeSessions.set(sessionKey, runId)
        this.activeRuns.add(runId)
        this.scheduleSessionReconciliation(sessionKey)
      }
      this.emitStatus()
      return result
    } catch (error) {
      this.activeRuns.delete(pendingId)
      this.activeSessions.delete(sessionKey)
      this.activeSessionStartedAt.delete(sessionKey)
      this.clearSessionReconcileTimer(sessionKey)
      this.emitStatus()
      throw error
    }
  }

  async isTrackedSessionActive(sessionKey) {
    const trackedRunId = this.activeSessions.get(sessionKey)
    if (!trackedRunId) return false
    const startedAt = this.activeSessionStartedAt.get(sessionKey) || 0
    // Never second-guess a dispatch that is still pending, and give a newly
    // admitted run a short window to appear in the authoritative session row.
    if (String(trackedRunId).startsWith('pending:') || Date.now() - startedAt < 5000) return true
    try {
      const result = await this.rpc('sessions.list', { limit: 100, ownerFirst: true })
      const rows = Array.isArray(result?.sessions) ? result.sessions : Array.isArray(result?.items) ? result.items : []
      const row = rows.find((item) => String(item?.key || item?.sessionKey || item?.id || '') === sessionKey)
      const status = String(row?.status || row?.runStatus || '').toLowerCase()
      const active = Boolean(row?.hasActiveRun || row?.activeRunId || ['queued', 'thinking', 'working', 'waiting_approval', 'blocked', 'running'].includes(status))
      if (active) return true
      this.activeRuns.delete(trackedRunId)
      this.activeSessions.delete(sessionKey)
      this.activeSessionStartedAt.delete(sessionKey)
      this.clearSessionReconcileTimer(sessionKey)
      this.emitStatus()
      return false
    } catch (error) {
      // Fail first when the authoritative check itself is unavailable.
      this.log(`session activity reconciliation failed: ${error.message}`)
      return true
    }
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
    try {
      return await this.rpc('sessions.abort', { ...params, clearQueued: true })
    } finally {
      if (sessionKey) {
        const runId = this.activeSessions.get(sessionKey)
        if (runId) this.activeRuns.delete(runId)
        this.activeSessions.delete(sessionKey)
        this.activeSessionStartedAt.delete(sessionKey)
        this.clearSessionReconcileTimer(sessionKey)
        this.emitStatus()
      }
    }
  }

  loadBotMetadata() {
    return readJson(this.botStatePath, { archived: {}, profiles: {} }) || { archived: {}, profiles: {} }
  }

  saveBotMetadata(value) {
    atomicWriteJson(this.botStatePath, value)
  }

  async listBots(params = {}) {
    const result = await this.rpc('agents.list', params)
    const metadata = this.loadBotMetadata()
    const agents = Array.isArray(result?.agents) ? result.agents : Array.isArray(result) ? result : []
    return {
      ...result,
      agents: agents.map((agent) => ({ ...agent, ...(metadata.profiles?.[agent.id || agent.agentId] || {}), archived: Boolean(metadata.archived?.[agent.id || agent.agentId]) })),
    }
  }

  async createSession(params = {}) {
    const agentId = String(params.agentId || '').trim()
    if (!agentId) throw new Error('agentId is required')
    const metadata = this.loadBotMetadata()
    const profile = metadata.profiles?.[agentId] || {}
    const allowedModes = new Set(['read-only', 'guarded', 'workspace'])
    const requestedMode = String(profile.toolPolicy?.permissionMode || 'guarded')
    const deepThinking = params.deepThinking === true
    const payload = {
      agentId,
      model: deepThinking ? XIAOYU_REASONING_MODEL : XIAOYU_FAST_MODEL,
      thinkingLevel: deepThinking ? 'medium' : 'off',
      fastMode: deepThinking ? false : true,
      permissionMode: allowedModes.has(requestedMode) ? requestedMode : 'guarded',
      toolOverrides: { mcpServers: { 'szyg-business': true } },
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
        if (name) payload.toolOverrides.skills[name] = allow.has(name)
      }
    }
    if (profile.toolPolicy?.mcpToolsDeny && typeof profile.toolPolicy.mcpToolsDeny === 'object') {
      payload.toolOverrides.mcpToolsDeny = sanitizeForRenderer(profile.toolPolicy.mcpToolsDeny)
    }
    return this.rpc('sessions.create', payload)
  }

  async saveRoutine(params = {}) {
    const payload = { ...params }
    const id = payload.id
    const deepThinking = payload.deepThinking === true
    delete payload.id
    delete payload.deepThinking
    if (payload.payload?.kind === 'agentTurn') {
      payload.payload = {
        ...payload.payload,
        model: deepThinking ? XIAOYU_REASONING_MODEL : (payload.payload.model || XIAOYU_FAST_MODEL),
        thinking: deepThinking ? (payload.payload.thinking || 'medium') : (payload.payload.thinking || 'off'),
      }
    }
    return this.rpc(id ? 'cron.update' : 'cron.add', id ? { id, patch: payload } : payload)
  }

  async createBot(params) {
    const safe = { name: String(params?.name || '').trim() }
    if (!safe.name) throw new Error('员工名称不能为空')
    safe.workspace = path.join(this.rootDir, 'workspaces', 'agents', crypto.randomUUID())
    fs.mkdirSync(safe.workspace, { recursive: true })
    copyTemplateDirectory(path.join(__dirname, 'workspace-template'), safe.workspace)
    safe.model = XIAOYU_MANAGED_MODEL
    if (params?.emoji) safe.emoji = String(params.emoji)
    if (params?.avatar) safe.avatar = String(params.avatar)
    const result = await this.rpc('agents.create', safe)
    const agentId = result.agentId
    if (agentId) {
      const metadata = this.loadBotMetadata()
      metadata.profiles[agentId] = {
        title: String(params?.title || '数字员工'),
        instructions: String(params?.instructions || ''),
        skills: Array.isArray(params?.skills) ? params.skills.map(String) : null,
        toolPolicy: params?.toolPolicy || { permissionMode: 'guarded' },
        workspace: safe.workspace,
        browserProfile: `persist:szyg-agent-${agentId}`,
      }
      this.saveBotMetadata(metadata)
    }
    return result
  }

  async updateBot(params) {
    const agentId = String(params?.agentId || '')
    if (!agentId) throw new Error('agentId is required')
    const gatewayParams = { agentId }
    for (const key of ['name', 'agentRuntime', 'emoji', 'avatar']) {
      if (Object.prototype.hasOwnProperty.call(params, key)) gatewayParams[key] = params[key]
    }
    gatewayParams.model = XIAOYU_MANAGED_MODEL
    const result = await this.rpc('agents.update', gatewayParams)
    const metadata = this.loadBotMetadata()
    metadata.profiles[agentId] = {
      ...(metadata.profiles[agentId] || {}),
      ...sanitizeForRenderer({
        title: params.title,
        instructions: params.instructions,
        skills: params.skills,
        toolPolicy: params.toolPolicy,
      }),
    }
    for (const key of Object.keys(metadata.profiles[agentId])) {
      if (metadata.profiles[agentId][key] === undefined) delete metadata.profiles[agentId][key]
    }
    this.saveBotMetadata(metadata)
    return result
  }

  archiveBot(agentId, archived = true) {
    const metadata = this.loadBotMetadata()
    if (archived) metadata.archived[agentId] = Date.now()
    else delete metadata.archived[agentId]
    this.saveBotMetadata(metadata)
    return { ok: true, agentId, archived }
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
