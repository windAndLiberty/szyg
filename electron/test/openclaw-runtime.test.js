const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')
const {
  normalizeGatewayEvent,
  generateDeviceIdentity,
  publicKeyRawBase64UrlFromPem,
  signDevicePayload,
  resolveRuntimeLayout,
  sanitizeForRenderer,
  sha256FileSync,
  OpenClawRuntimeManager,
  XIAOYU_MANAGED_MODEL,
  XIAOYU_FAST_MODEL,
  XIAOYU_REASONING_MODEL,
} = require('../openclaw/runtime-manager')

test('renderer projection removes credentials recursively', () => {
  const value = sanitizeForRenderer({ token: 'nope', nested: { Authorization: 'nope', ok: 'visible' } })
  assert.deepEqual(value, { nested: { ok: 'visible' } })
})

test('gateway events are normalized to stable Xiaoyu event kinds', () => {
  const event = normalizeGatewayEvent({ event: 'exec.approval.requested', payload: { id: 'a1', command: 'publish' } })
  assert.equal(event.type, 'approval')
  assert.equal(event.payload.id, 'a1')
})

test('chat events use the Xiaoyu message and run-state model', () => {
  const event = normalizeGatewayEvent({ event: 'chat', payload: { runId: 'r1', sessionKey: 's1', state: 'final', seq: 2 } })
  assert.equal(event.type, 'message')
  assert.equal(event.payload.runStatus, 'completed')
})

test('terminal chat events clear a tracked session even without sessionKey', () => {
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  manager.activeRuns.add('r1')
  manager.activeSessions.set('s1', 'r1')
  manager.activeSessionStartedAt.set('s1', Date.now() - 10_000)
  manager.handleEvent({ event: 'chat', payload: { runId: 'r1', state: 'final' } })
  assert.equal(manager.activeRuns.has('r1'), false)
  assert.equal(manager.activeSessions.has('s1'), false)
  assert.equal(manager.activeSessionStartedAt.has('s1'), false)
})

test('sendRun reconciles a stale local session lock before dispatch', async () => {
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  manager.activeRuns.add('stale-run')
  manager.activeSessions.set('s1', 'stale-run')
  manager.activeSessionStartedAt.set('s1', Date.now() - 10_000)
  manager.rpc = async (method) => {
    if (method === 'sessions.list') return { sessions: [{ key: 's1', status: 'done', hasActiveRun: false }] }
    if (method === 'sessions.patch') return { ok: true }
    if (method === 'chat.send') return { runId: 'new-run' }
    throw new Error(`unexpected method: ${method}`)
  }
  const result = await manager.sendRun({ sessionKey: 's1', message: 'hello' })
  assert.equal(result.runId, 'new-run')
  assert.equal(manager.activeRuns.has('stale-run'), false)
  assert.equal(manager.activeSessions.get('s1'), 'new-run')
})

test('completed sessions are reconciled automatically when terminal events omit identifiers', async () => {
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  manager.activeRuns.add('r1')
  manager.activeSessions.set('s1', 'r1')
  manager.activeSessionStartedAt.set('s1', Date.now() - 10_000)
  manager.rpc = async (method) => {
    assert.equal(method, 'sessions.list')
    return { sessions: [{ key: 's1', status: 'done', hasActiveRun: false }] }
  }
  manager.scheduleSessionReconciliation('s1', 1)
  await new Promise((resolve) => setTimeout(resolve, 30))
  assert.equal(manager.activeRuns.has('r1'), false)
  assert.equal(manager.activeSessions.has('s1'), false)
  assert.equal(manager.activeSessionStartedAt.has('s1'), false)
})

test('stale cron authority locks are removed before a new owned runtime starts', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-openclaw-cron-lock-'))
  try {
    const manager = new OpenClawRuntimeManager({ dataDir: root })
    const lockPath = path.join(manager.stateDir, 'state', 'openclaw.sqlite.cron-authority.lock')
    const reclaimPath = `${lockPath}.reclaim`
    fs.mkdirSync(reclaimPath, { recursive: true })
    fs.writeFileSync(lockPath, JSON.stringify({ pid: 1234 }))
    const stale = new Date(Date.now() - 10 * 60 * 1000)
    fs.utimesSync(lockPath, stale, stale)
    manager.clearStaleCronAuthorityLock()
    assert.equal(fs.existsSync(lockPath), false)
    assert.equal(fs.existsSync(reclaimPath), false)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('retired memory dreaming jobs are disabled before the gateway can catch them up', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-openclaw-memory-job-'))
  try {
    const manager = new OpenClawRuntimeManager({ dataDir: root })
    const databasePath = path.join(manager.stateDir, 'state', 'openclaw.sqlite')
    fs.mkdirSync(path.dirname(databasePath), { recursive: true })
    const { DatabaseSync } = require('node:sqlite')
    const database = new DatabaseSync(databasePath)
    database.exec(`
      CREATE TABLE cron_jobs (
        store_key TEXT NOT NULL,
        job_id TEXT NOT NULL,
        declaration_key TEXT,
        name TEXT NOT NULL,
        description TEXT,
        enabled INTEGER NOT NULL,
        job_json TEXT NOT NULL,
        updated_at INTEGER NOT NULL,
        PRIMARY KEY (store_key, job_id)
      );
      CREATE TABLE claw_cron_refs (
        agent_id TEXT NOT NULL,
        manifest_id TEXT NOT NULL,
        declaration_key TEXT NOT NULL,
        PRIMARY KEY (agent_id, manifest_id)
      );
    `)
    database.prepare('INSERT INTO cron_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)').run(
      'default', 'job-1', 'memory-core:memory-dreaming-promotion', 'Memory Dreaming Promotion',
      '[managed-by=memory-core.short-term-promotion]', 1, JSON.stringify({ enabled: true }), Date.now(),
    )
    database.prepare('INSERT INTO claw_cron_refs VALUES (?, ?, ?)').run(
      'main', 'memory-core', 'memory-core:memory-dreaming-promotion',
    )
    database.close()

    assert.equal(manager.disableRetiredMemoryJobsBeforeStart(), 1)
    const check = new DatabaseSync(databasePath, { readOnly: true })
    const job = check.prepare('SELECT enabled, job_json FROM cron_jobs WHERE job_id = ?').get('job-1')
    assert.equal(job.enabled, 0)
    assert.equal(JSON.parse(job.job_json).enabled, false)
    assert.equal(check.prepare('SELECT COUNT(*) AS count FROM claw_cron_refs').get().count, 0)
    check.close()
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('device identity signs challenge payloads with canonical Ed25519 material', () => {
  const identity = generateDeviceIdentity()
  const payload = 'connect.challenge:test'
  const signature = Buffer.from(signDevicePayload(identity.privateKeyPem, payload), 'base64url')
  assert.equal(identity.deviceId.length, 64)
  assert.equal(publicKeyRawBase64UrlFromPem(identity.publicKeyPem).length, 43)
  assert.equal(require('node:crypto').verify(null, Buffer.from(payload), identity.publicKeyPem, signature), true)
})

test('runtime layout requires pinned compatible versions and hashes', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-openclaw-layout-'))
  try {
    fs.mkdirSync(path.join(root, 'app', 'node_modules', 'openclaw'), { recursive: true })
    fs.writeFileSync(path.join(root, 'node.exe'), 'node')
    fs.writeFileSync(path.join(root, 'app', 'node_modules', 'openclaw', 'openclaw.mjs'), 'entry')
    fs.writeFileSync(path.join(root, 'app', 'node_modules', 'openclaw', 'package.json'), JSON.stringify({ version: '2026.10.5' }))
    fs.writeFileSync(path.join(root, 'manifest.json'), JSON.stringify({
      openclawVersion: '2026.10.5',
      gatewayClientVersion: '2026.10.5',
      protocolVersion: '2026.10.5',
      wireVersion: 4,
      nodeVersion: '24.16.0',
      files: [{ path: 'node.exe', sha256: sha256FileSync(path.join(root, 'node.exe')) }],
    }))
    assert.ok(resolveRuntimeLayout(root))
    fs.writeFileSync(path.join(root, 'node.exe'), 'tampered')
    assert.equal(resolveRuntimeLayout(root), null)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('runtime layout accepts a PowerShell UTF-8 BOM manifest', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-openclaw-bom-layout-'))
  try {
    const packageRoot = path.join(root, 'app', 'node_modules', 'openclaw')
    fs.mkdirSync(packageRoot, { recursive: true })
    fs.writeFileSync(path.join(root, 'node.exe'), 'node')
    fs.writeFileSync(path.join(packageRoot, 'openclaw.mjs'), 'entry')
    fs.writeFileSync(path.join(packageRoot, 'package.json'), JSON.stringify({ version: '2026.10.5' }))
    const manifest = JSON.stringify({
      openclawVersion: '2026.10.5',
      gatewayClientVersion: '2026.10.5',
      protocolVersion: '2026.10.5',
      wireVersion: 4,
      nodeVersion: '24.16.0',
      files: [{ path: 'node.exe', sha256: sha256FileSync(path.join(root, 'node.exe')) }],
    })
    fs.writeFileSync(path.join(root, 'manifest.json'), `\uFEFF${manifest}`, 'utf8')
    assert.ok(resolveRuntimeLayout(root))
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('runtime provisions normal and opt-in reasoning models without persisting its token', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-openclaw-config-'))
  try {
    const manager = new OpenClawRuntimeManager({
      dataDir: root,
      backendPort: 8123,
      businessMcpToken: 'business-secret',
      openClawModelToken: 'model-secret',
    })
    manager.prepareWorkspace()
    manager.runCli = async () => ({ stdout: '', stderr: '' })
    const env = manager.runtimeEnv('gateway-secret')
    await manager.provisionBusinessMcp({}, env)
    const configText = fs.readFileSync(manager.configPath, 'utf8')
    const config = JSON.parse(configText)
    assert.equal(env.SZYG_OPENCLAW_MODEL_TOKEN, 'model-secret')
    assert.equal(config.models.mode, 'replace')
    assert.equal(config.agents.defaults.model.primary, XIAOYU_MANAGED_MODEL)
    assert.equal(config.agents.defaults.model.primary, XIAOYU_FAST_MODEL)
    assert.deepEqual(config.agents.defaults.modelPolicy.allow, [XIAOYU_FAST_MODEL, XIAOYU_REASONING_MODEL])
    assert.deepEqual(config.models.providers['xiaoyu-managed'].apiKey, {
      source: 'env', provider: 'default', id: 'SZYG_OPENCLAW_MODEL_TOKEN',
    })
    assert.deepEqual(config.models.providers['xiaoyu-managed'].models.map((model) => [model.id, model.reasoning]), [
      ['text.fast', false],
      ['text.reasoning', true],
    ])
    assert.equal(config.models.providers['xiaoyu-managed'].models[0].params, undefined)
    assert.equal(config.cron.skipMissedJobs, true)
    assert.equal(config.plugins.slots.memory, 'none')
    assert.equal(config.plugins.entries['memory-core'].enabled, false)
    assert.equal(config.plugins.entries['memory-core'].config.dreaming.enabled, false)
    assert.equal(configText.includes('model-secret'), false)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('sendRun switches the existing session model from the user deep-thinking choice', async () => {
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  const calls = []
  manager.rpc = async (method, params) => {
    calls.push([method, params])
    if (method === 'sessions.patch') return { ok: true }
    if (method === 'chat.send') return { runId: 'r1' }
    throw new Error(`unexpected method: ${method}`)
  }
  await manager.sendRun({ sessionKey: 's1', message: 'analyze', deepThinking: true })
  assert.deepEqual(calls[0], ['sessions.patch', {
    key: 's1', model: XIAOYU_REASONING_MODEL, thinkingLevel: 'medium', fastMode: false,
  }])
  assert.equal(Object.hasOwn(calls[1][1], 'deepThinking'), false)
})

test('new background routines default to the fast managed model', async () => {
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  let request
  manager.rpc = async (method, params) => {
    request = { method, params }
    return { ok: true }
  }
  await manager.saveRoutine({
    name: 'daily digest',
    schedule: { kind: 'cron', expr: '0 9 * * *' },
    payload: { kind: 'agentTurn', message: 'prepare digest' },
  })
  assert.equal(request.method, 'cron.add')
  assert.equal(request.params.payload.model, XIAOYU_FAST_MODEL)
  assert.equal(request.params.payload.thinking, 'off')
})
