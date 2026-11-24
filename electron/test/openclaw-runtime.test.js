const nodeBinary = process.platform === 'win32' ? 'node.exe' : 'node'
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
  manager.activeSessions.set('agent:main:dashboard:b84a49db-c668-4cb4-be86-083fa4099f67', 'stale-run')
  manager.activeSessionStartedAt.set('agent:main:dashboard:b84a49db-c668-4cb4-be86-083fa4099f67', Date.now() - 10_000)
  manager.rpc = async (method) => {
    if (method === 'sessions.describe') return { session: { key: 'agent:main:dashboard:b84a49db-c668-4cb4-be86-083fa4099f67', status: 'done', hasActiveRun: false } }
    if (method === 'sessions.patch') return { ok: true }
    if (method === 'chat.send') return { runId: 'new-run' }
    throw new Error(`unexpected method: ${method}`)
  }
  const result = await manager.sendRun({ sessionKey: 'agent:main:dashboard:b84a49db-c668-4cb4-be86-083fa4099f67', message: 'hello' })
  assert.equal(result.runId, 'new-run')
  assert.equal(manager.activeRuns.has('stale-run'), false)
  assert.equal(manager.activeSessions.get('agent:main:dashboard:b84a49db-c668-4cb4-be86-083fa4099f67'), 'new-run')
})

test('a turn can use the automatic model without overwriting the preferred model', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-openclaw-fallback-'))
  const manager = new OpenClawRuntimeManager({ dataDir: root })
  const sessionKey = 'agent:main:dashboard:b84a49db-c668-4cb4-be86-083fa4099f67'
  const preferredModel = 'doubao-seed-evolving'
  const models = []
  manager.saveSessionSettings(sessionKey, { model: preferredModel, permissionMode: 'guarded' })
  manager.rpc = async (method, params) => {
    if (method === 'sessions.describe') return { session: { hasActiveRun: false } }
    if (method === 'sessions.patch') { models.push(params.model); return {} }
    if (method === 'chat.send') return { runId: 'fallback-test' }
    throw new Error(`unexpected method: ${method}`)
  }

  try {
    await manager.sendRun({ sessionKey, message: 'hello', usingAutomaticModel: true })
    assert.equal(manager.loadBotMetadata().sessions[sessionKey].model, preferredModel)
    manager.handleEvent({ event: 'chat', payload: { runId: 'fallback-test', sessionKey, state: 'final' } })
    await manager.sendRun({ sessionKey, message: 'hello again' })
    assert.deepEqual(models, [XIAOYU_FAST_MODEL, 'xiaoyu-managed/' + preferredModel])
  } finally {
    manager.clearSessionReconcileTimer(sessionKey)
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('a desktop turn points the model to media inspection only for attached local files', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-openclaw-attachment-'))
  const manager = new OpenClawRuntimeManager({ dataDir: root })
  const sessionKey = 'agent:main:dashboard:b84a49db-c668-4cb4-be86-083fa4099f67'
  const url = '/api/media/files/image/00b97dbc-6a49-49c9-b43e-0d4acef5f8ca.jpg'
  const messages = []
  manager.rpc = async (method, params) => {
    if (method === 'sessions.describe') return { session: { hasActiveRun: false } }
    if (method === 'sessions.patch') return {}
    if (method === 'chat.send') { messages.push(params); return { runId: 'media-test' } }
    throw new Error(`unexpected method: ${method}`)
  }

  try {
    const message = `看看附件。\n[随附图片](${url})`
    await manager.sendRun({ sessionKey, message, attachments: [url] })
    assert.equal(messages[0].message, message)
    assert.match(messages[0].workContext.detail['本轮附件'], /materials\.inspect/)
    manager.handleEvent({ event: 'chat', payload: { runId: 'media-test', sessionKey, state: 'final' } })
    await manager.sendRun({ sessionKey, message: `[外链](https://example.test${url})`, attachments: [url] })
    assert.equal(messages[1].workContext, undefined)
  } finally {
    manager.clearSessionReconcileTimer(sessionKey)
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('completed sessions are reconciled automatically when terminal events omit identifiers', async () => {
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  manager.activeRuns.add('r1')
  manager.activeSessions.set('s1', 'r1')
  manager.activeSessionStartedAt.set('s1', Date.now() - 10_000)
  manager.rpc = async (method) => {
    assert.equal(method, 'sessions.describe')
    return { session: { key: 's1', status: 'done', hasActiveRun: false } }
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
    fs.writeFileSync(path.join(root, nodeBinary), 'node')
    fs.writeFileSync(path.join(root, 'app', 'node_modules', 'openclaw', 'openclaw.mjs'), 'entry')
    fs.writeFileSync(path.join(root, 'app', 'node_modules', 'openclaw', 'package.json'), JSON.stringify({ version: '2026.10.5' }))
    fs.writeFileSync(path.join(root, 'manifest.json'), JSON.stringify({
      openclawVersion: '2026.10.5',
      gatewayClientVersion: '2026.10.5',
      protocolVersion: '2026.10.5',
      wireVersion: 4,
      nodeVersion: '24.16.0',
      files: [{ path: nodeBinary, sha256: sha256FileSync(path.join(root, nodeBinary)) }],
    }))
    assert.ok(resolveRuntimeLayout(root))
    fs.writeFileSync(path.join(root, nodeBinary), 'tampered')
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
    fs.writeFileSync(path.join(root, nodeBinary), 'node')
    fs.writeFileSync(path.join(packageRoot, 'openclaw.mjs'), 'entry')
    fs.writeFileSync(path.join(packageRoot, 'package.json'), JSON.stringify({ version: '2026.10.5' }))
    const manifest = JSON.stringify({
      openclawVersion: '2026.10.5',
      gatewayClientVersion: '2026.10.5',
      protocolVersion: '2026.10.5',
      wireVersion: 4,
      nodeVersion: '24.16.0',
      files: [{ path: nodeBinary, sha256: sha256FileSync(path.join(root, nodeBinary)) }],
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
    const choices = require('../openclaw/employee-profile').employeeModels
    assert.deepEqual(config.agents.defaults.modelPolicy.allow, [XIAOYU_FAST_MODEL, XIAOYU_REASONING_MODEL, ...choices.map(id => 'xiaoyu-managed/' + id)])
    assert.deepEqual(config.models.providers['xiaoyu-managed'].apiKey, {
      source: 'env', provider: 'default', id: 'SZYG_OPENCLAW_MODEL_TOKEN',
    })
    assert.deepEqual(config.models.providers['xiaoyu-managed'].models.map((model) => [model.id, model.reasoning]), [
      ['text.fast', false],
      ['text.reasoning', true],
      ...choices.map(id => [id, true]),
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
    if (method === 'sessions.describe') return {session: {key: params.key, hasActiveRun: false}}
    calls.push([method, params])
    if (method === 'sessions.patch') return { ok: true }
    if (method === 'chat.send') return { runId: 'r1' }
    throw new Error(`unexpected method: ${method}`)
  }
  await manager.sendRun({ sessionKey: 'agent:main:dashboard:b84a49db-c668-4cb4-be86-083fa4099f67', message: 'analyze', deepThinking: true })
  assert.deepEqual(calls[0], ['sessions.patch', {
    key: 'agent:main:dashboard:b84a49db-c668-4cb4-be86-083fa4099f67', agentId: 'main', model: XIAOYU_REASONING_MODEL, thinkingLevel: 'medium', fastMode: false,
  }])
  assert.equal(Object.hasOwn(calls[1][1], 'deepThinking'), false)
})

test('desk chat resolves expert references locally without changing the message or tool permissions', async (t) => {
  const sessionKey = 'agent:main:dashboard:b84a49db-c668-4cb4-be86-083fa4099f67'
  const context = { page: '领域专家', selection: 'Compare the scenarios' }
  const events = []
  const manager = new OpenClawRuntimeManager({
    dataDir: os.tmpdir(), backendPort: 19707, desktopToken: 'local-test-token', onEvent: event => events.push(event),
  })
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:19707/api/agency/conversation-experts/resolve')
    assert.equal(options.headers['X-SZYG-Desktop-Token'], 'local-test-token')
    assert.deepEqual(JSON.parse(options.body), { session_key: sessionKey, agent_id: 'main', message: '财务分析' })
    return { ok: true, json: async () => ({ workContext: context, active: [], permissionMode: 'full' }) }
  })
  const calls = []
  manager.rpc = async (method, params) => {
    calls.push([method, params])
    if (method === 'sessions.describe') return { session: { key: sessionKey, hasActiveRun: false } }
    return { runId: 'r1' }
  }
  await manager.sendRun({ sessionKey, message: '财务分析' })
  const [, send] = calls.find(([method]) => method === 'chat.send')
  assert.deepEqual(send.workContext, context)
  assert.equal(send.message, '财务分析')
  assert.equal(send.permissionMode, undefined)
  assert.ok(events.some(e => e.type === 'experts.changed' && e.payload.sessionKey === sessionKey))
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

test('Chinese employee profiles are retryable, editable and isolated from the default identity', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-profile-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  const manager = new OpenClawRuntimeManager({ dataDir: root })
  const docs = new Map()
  const agents = [{ id: 'main' }]
  const creates = []
  manager.rpc = async (method, body) => {
    if (method === 'agents.list') return { defaultId: 'main', agents }
    if (method === 'agents.create') {
      assert.match(body.name, /^[a-z0-9-]+$/)
      creates.push(body)
      agents.push({ id: body.name })
      return { agentId: body.name }
    }
    if (method === 'agents.update') {
      Object.assign(agents.find(a => a.id === body.agentId), {name: body.name})
      return { ok: true }
    }
    if (method === 'agents.files.get') return { file: { content: docs.get(body.agentId), hash: 'local' } }
    if (method === 'agents.files.set') { docs.set(body.agentId, body.content); return { ok: true } }
    throw Error('Unexpected ' + method)
  }
  const payload = {
    requestId: require('node:crypto').randomUUID(), name: '小灰灰', title: '负责人', instructions: '先列目标',
    avatar: 'robot:3', skills: ['write'], toolPolicy: { permissionMode: 'guarded', mcpToolsDeny: { external: ['write'] } },
  }
  const [first, retry] = await Promise.all([manager.createBot(payload), manager.createBot(payload)])
  assert.equal(creates.length, 1)
  assert.equal(first.agentId, retry.agentId)
  assert.equal(creates[0].avatar, undefined)
  assert.match(docs.get(first.agentId), /先列目标/)
  await manager.updateBot({ agentId: first.agentId, name: '新名', instructions: '先列成果', toolPolicy: { permissionMode: 'full' } })
  await manager.updateBot({ agentId: first.agentId, avatar: 'robot:1' })
  assert.doesNotMatch(docs.get(first.agentId), /先列目标/)
  assert.match(docs.get(first.agentId), /先列成果/)
  const roster = await manager.listBots()
  assert.equal(roster.agents[0].name, '小妤')
  assert.deepEqual(roster.agents[1].toolPolicy, { permissionMode: 'full', mcpToolsDeny: {external: ['write']} })
  assert.deepEqual(roster.agents[1].skills, ['write'])
  await manager.updateBot({ agentId: 'main', avatar: 'robot:4' })
  await assert.rejects(manager.updateBot({ agentId: 'main', name: '不可更改' }), /默认员工/)
  await assert.rejects(manager.archiveBot('main'), /默认员工/)
  assert.equal((await manager.listBots()).agents[0].avatar, 'robot:4')
  await manager.updateBot({ agentId: 'main', avatar: 'xiaoyu' })
  assert.equal((await manager.listBots()).agents[0].avatar, 'xiaoyu')
  const defaultAvatar = await manager.createBot({name: '小妤助理'})
  assert.equal((await manager.listBots()).agents.find(agent => agent.id === defaultAvatar.agentId).avatar, 'xiaoyu')
  assert.throws(() => manager.createBot({...payload, avatar: 'https://example.org/face.png'}), /头像/)
  assert.throws(() => manager.createBot({...payload, model: 'external/random'}), /模型/)
})

test('conversation preferences survive restart, are stripped from chat.send and cannot grant full access to channel sessions', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-conversation-settings-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  const manager = new OpenClawRuntimeManager({ dataDir: root })
  const sessionKey = 'agent:main:dashboard:' + require('node:crypto').randomUUID()
  const choice = 'deepseek-v4-1-flash-economy-261017'
  const calls = []
  const rpc = async (method, data) => {
    calls.push([method, data])
    if (method === 'sessions.describe') return { session: { key: sessionKey, hasActiveRun: false } }
    if (method === 'sessions.list') return { sessions: [{ key: sessionKey }] }
    if (method === 'sessions.create') return { key: sessionKey }
    return {}
  }
  manager.rpc = rpc
  await manager.createSession({ agentId: 'main', permissionMode: 'guarded' })
  await manager.configureSession({ key: sessionKey, agentId: 'main', model: choice, permissionMode: 'full' })
  const restored = new OpenClawRuntimeManager({ dataDir: root })
  restored.rpc = rpc
  t.after(() => restored.stop())
  const row = (await restored.listSessions({})).sessions[0]
  assert.equal(row.model, choice)
  assert.equal(row.permissionMode, 'full')
  await restored.sendRun({ sessionKey, agentId: 'main', message: 'local test' })
  const patch = calls.findLast(([method]) => method === 'sessions.patch')[1]
  assert.equal(patch.model, 'xiaoyu-managed/' + choice)
  // A send without an explicit access change must retain the native live
  // session setting, including a downgrade made after the last UI refresh.
  assert.equal(patch.permissionMode, undefined)
  const send = calls.find(([method]) => method === 'chat.send')[1]
  assert.equal(send.model, undefined)
  assert.equal(send.permissionMode, undefined)
  assert.throws(() => restored.configureSession({key: 'agent:main:weixin:direct:user', permissionMode: 'full'}), /仅本机/)
  assert.throws(() => restored.configureSession({key: sessionKey, agentId: 'other', permissionMode: 'full'}), /不属于/)
  await assert.rejects(restored.sendRun({sessionKey, agentId: 'other', message: 'wrong employee'}), /不属于/)
  await assert.rejects(restored.sendRun({sessionKey: 'agent:main:weixin:direct:user', message: 'foreign transport'}), /仅本机/)
  assert.throws(() => restored.sessionHistory({sessionKey, agentId: 'other'}), /不属于/)
  await assert.rejects(restored.interruptRun({key: sessionKey, agentId: 'other'}), /不属于/)
  await assert.rejects(restored.createSession({agentId: 'main', key: 'agent:main:weixin:direct:user'}), /本机/)
})

test('Kimi always uses a reasoning turn, including when the composer requests fast mode', () => {
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  assert.deepEqual(manager.gatewayModelSettings('kimi-k3-1-pro-261024', false), {
    model: 'xiaoyu-managed/kimi-k3-1-pro-261024', thinkingLevel: 'medium', fastMode: false,
  })
})

test('stopping the gateway waits for the old process to release its state', async () => {
  const { EventEmitter } = require('node:events')
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  const child = new EventEmitter()
  Object.assign(child, { exitCode: null, signalCode: null, kill() {} })
  manager.child = child
  let closed = false
  const stop = manager.stop().then(() => { closed = true })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(closed, false)
  child.emit('close', 0)
  await stop
  assert.equal(closed, true)
  assert.equal(manager.child, null)
})

test('director installation resumes partial creation and preserves a customized or archived director', async t => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-install-director-'))
  t.after(() => fs.rmSync(root, {recursive:true, force:true}))
  const manager = new OpenClawRuntimeManager({dataDir:root})
  const agents = [{id:'main', name:'小妤'}, {id:'existing', name:'我的员工'}]
  let creates = 0
  let disconnect = true
  let instructions
  manager.client = {request:async (method, params) => {
    if (method === 'agents.list') return {defaultId:'main', agents}
    if (method === 'agents.create') {
      assert.equal(params.name, 'xiaoyu-director')
      creates++
      agents.push({id:params.name, name:params.name})
      return {}
    }
    if (method === 'agents.update') {
      if (disconnect) { disconnect = false; throw Error('Gateway disconnected') }
      agents.find(agent => agent.id === params.agentId).name = params.name
      return {}
    }
    if (method === 'agents.files.get') return {file:{content:instructions, hash:instructions ? 'local-hash' : undefined}}
    if (method === 'agents.files.set') { instructions = params.content; return {} }
    throw Error('Unexpected ' + method)
  }}
  manager.state.ready = true
  manager.directorNeedsInstall = true
  await assert.rejects(manager.installDirector(), /disconnected/)
  assert.equal(manager.loadBotMetadata().profiles['xiaoyu-director'].creationComplete, false)
  const [first, concurrent] = await Promise.all([manager.listBots(), manager.listBots()])
  assert.deepEqual(first, concurrent)
  assert.equal(creates, 1)
  assert.equal(first.defaultId, 'main')
  assert.deepEqual(first.agents.map(agent=>agent.name), ['小妤', '我的员工', '视频导演'])
  assert.equal(first.agents.find(agent => agent.id === 'xiaoyu-director').avatar, 'director')
  assert.match(instructions, /director\.render/)
  await manager.updateBot({agentId:'xiaoyu-director', name:'导演组', instructions:'先给我分镜清单。', avatar:'robot:2'})
  await manager.archiveBot('xiaoyu-director')
  // Simulate an app upgrade from an earlier built-in director template.
  manager.storeProfile('xiaoyu-director', {directorTemplate:'prior-template-digest'})
  manager.directorNeedsInstall = true
  await manager.installDirector()
  const entry = (await manager.listBots()).agents.find(agent => agent.id === 'xiaoyu-director')
  assert.equal(entry.avatar, 'robot:2')
  assert.equal(entry.archived, true)
  assert.equal(entry.name, '导演组')
  assert.equal(entry.instructions, '先给我分镜清单。')
  assert.match(instructions, /先给我分镜清单/)
  assert.equal(creates, 1)
})

test('director upgrade changes only the legacy identity and respects subsequent choices', async t => {
  const { localAvatar } = require('../openclaw/employee-profile')
  assert.equal(localAvatar('director'), 'director')
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-director-identity-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  const manager = new OpenClawRuntimeManager({dataDir:root})
  const id = 'xiaoyu-director'
  const agent = {id, name:'小妤导演'}
  const oldPrompt = '你是小妤导演，负责剪辑。'
  const digest = require('node:crypto').createHash('sha256').update(oldPrompt).digest('hex')
  let content = 'Existing workspace notes'
  let updates = 0
  manager.client = {request: async (method, params) => {
    if (method === 'agents.list') return {defaultId:'main', agents:[{id:'main'}, agent]}
    if (method === 'agents.update') { updates++; agent.name = params.name; return {} }
    if (method === 'agents.files.get') return {file:{content, hash:'current'}}
    if (method === 'agents.files.set') { content = params.content; return {} }
    assert.fail(method)
  }}
  manager.state.ready = true
  const upgrade = async () => {
    manager.directorNeedsInstall = true
    await manager.installDirector()
    return manager.loadBotMetadata().profiles[id]
  }
  manager.storeProfile(id, {name:agent.name, avatar:'xiaoyu', instructions:oldPrompt, directorTemplate:digest, creationComplete:true})
  const upgraded = await upgrade()
  assert.equal(upgraded.name, '视频导演')
  assert.equal(agent.name, upgraded.name)
  assert.equal(upgraded.avatar, 'director')
  assert.match(content, /Existing workspace notes/)
  assert.match(content, /你是视频导演/)
  assert.equal(updates, 1)
  // A user can explicitly select the old name and Xiaoyu avatar again.
  await manager.updateBot({agentId:id, name:'小妤导演', avatar:'xiaoyu'})
  const chosen = await upgrade()
  assert.equal(chosen.name, '小妤导演')
  assert.equal(chosen.avatar, 'xiaoyu')
  assert.equal(updates, 2)
  // An older native rename and independently edited portrait/prompt are also kept.
  agent.name = '剪辑组'
  manager.storeProfile(id, {name:'小妤导演', avatar:'robot:4', instructions:'先询问片长。', directorTemplate:digest, directorIdentityVersion:null})
  const custom = await upgrade()
  assert.equal(custom.name, '剪辑组')
  assert.equal(custom.avatar, 'robot:4')
  assert.equal(custom.instructions, '先询问片长。')
  assert.match(content, /剪辑组/)
  assert.match(content, /先询问片长/)
  assert.equal(updates, 2)
})

test('parallel runs recover by exact session, and stopping an old identity cannot cancel another turn', async t => {
  const events = []
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir(), onEvent: event => events.push(event) })
  t.after(() => manager.stop())
  const keys = ['main', 'xiaoyu-director'].map(agent => 'agent:' + agent + ':dashboard:' + require('node:crypto').randomUUID())
  const live = new Map()
  const aborts = []
  let hidden = false
  manager.rpc = async (method, params) => {
    if (method === 'chat.send') {
      live.set(params.sessionKey, params.idempotencyKey)
      return { runId: params.idempotencyKey }
    }
    if (method === 'sessions.patch') return {}
    if (method === 'sessions.describe') {
      const current = live.get(params.key)
      return { session: { key: params.key, hasActiveRun: Boolean(current), activeRunIds: hidden ? undefined : current ? [current] : [] } }
    }
    if (method === 'sessions.abort') {
      aborts.push(params)
      assert.equal(params.clearQueued, false)
      assert.equal(params.runId, live.get(params.key))
      live.delete(params.key)
      return { status: 'aborted', abortedRunId: params.runId }
    }
    assert.fail(method)
  }
  const [a, b] = await Promise.all(keys.map(sessionKey => manager.sendRun({ sessionKey, message: '并行工作' })))
  assert.notEqual(a.runId, b.runId)
  const fresh = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  t.after(() => fresh.stop())
  fresh.rpc = manager.rpc
  assert.equal((await fresh.runStatus({ sessionKey: keys[0] })).runId, a.runId)
  hidden = true
  const unknown = await fresh.runStatus({ sessionKey: keys[1] })
  assert.equal(unknown.active, true)
  assert.equal(unknown.runId, null)
  await assert.rejects(manager.sendRun({ sessionKey: keys[0], message: '重复发送' }), /已有任务/)
  assert.equal((await manager.interruptRun({ key: keys[0], runId: b.runId })).aborted, false)
  assert.equal((await manager.interruptRun({ key: keys[0] })).aborted, false)
  assert.equal(aborts.length, 0)
  assert.equal((await manager.interruptRun({ key: keys[0], runId: a.runId })).aborted, true)
  assert.equal((await manager.runStatus({ sessionKey: keys[1] })).runId, b.runId)
  const c = await manager.sendRun({ sessionKey: keys[0], message: '下一轮' })
  manager.handleEvent({ event: 'chat', payload: { runId: a.runId, state: 'final' } })
  assert.equal(events.at(-1).payload.sessionKey, keys[0])
  assert.equal((await manager.runStatus({ sessionKey: keys[0] })).runId, c.runId)
  const activity = events.length
  manager.handleEvent({ event: 'chat', payload: { runId: a.runId, state: 'delta' } })
  assert.equal(events.length, activity)
  assert.equal((await manager.interruptRun({ key: keys[0], runId: a.runId })).aborted, false)
  assert.equal(aborts.length, 1)
})

test('an unavailable status, a failed abort and a lost acknowledgment preserve exact session identity', async t => {
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  t.after(() => manager.stop())
  const sessionKey = 'agent:main:dashboard:' + require('node:crypto').randomUUID()
  let requestId
  let state = 'idle'
  manager.rpc = async (method, params) => {
    if (method === 'sessions.patch') return {}
    if (method === 'chat.send') { requestId = params.idempotencyKey; throw new Error('connection closed') }
    if (method === 'sessions.abort') throw new Error('abort failed')
    assert.equal(method, 'sessions.describe')
    if (state === 'offline') throw new Error('temporarily offline')
    return { session: {key: sessionKey, hasActiveRun: state === 'running'} }
  }
  const receipt = await manager.sendRun({ sessionKey, message: 'hello' })
  assert.equal(receipt.runId, requestId)
  assert.equal(receipt.status, 'unknown')
  state = 'running'
  manager.handleEvent({ event: 'question.requested', payload: { request: { runId: requestId } } })
  assert.equal((await manager.runStatus({ sessionKey })).status, 'blocked')
  await assert.rejects(manager.interruptRun({key: sessionKey, runId: requestId}), /abort failed/)
  assert.equal(manager.activeSessions.get(sessionKey), requestId)
  state = 'offline'
  assert.equal((await manager.interruptRun({key: sessionKey, runId: requestId})).status, 'unknown')
  assert.equal(manager.activeSessions.get(sessionKey), requestId)
})

test('director render receipts require matching native tool invocation and result in the selected local session', async () => {
  const manager = new OpenClawRuntimeManager({ dataDir: os.tmpdir() })
  const project = require('node:crypto').randomUUID()
  const job = require('node:crypto').randomUUID()
  const tool = 'mcp:szyg-business:szyg-business__director-render'
  const receipt = { job_id: job, status: 'running' }
  const call = { role: 'assistant', content: [{type: 'toolCall', id: 'c1', name: 'tool_call', arguments: { id: tool, args: {project_id: project} } }] }
  const result = { role: 'toolResult', toolName: 'tool_call', toolCallId: 'c1', details: { tool: {id: tool}, result: { details: {structuredContent: receipt} } } }
  const selection = {sessionKey: 'agent:xiaoyu-director:dashboard:' + project, agentId: 'xiaoyu-director'}
  let messages
  manager.rpc = async (method, params) => {
    assert.equal(method, 'sessions.get')
    assert.deepEqual(params, {key: selection.sessionKey, agentId: selection.agentId, limit: 200})
    return { messages }
  }
  messages = [call, result, call, result]
  assert.deepEqual((await manager.sessionDirectorRenders(selection)).jobs, [job])
  for (const rows of [
    [result], [call], [{role: 'user', content: call.content}, result], [call, {...result, toolCallId: 'foreign'}],
    [call, {...result, details: {...result.details, tool: {id:'other'}}}],
    [call, {...result, toolName:'other'}], [{role:'assistant', content: JSON.stringify(receipt)}],
    [call, {role:'assistant', content: [{...call.content[0], arguments: {id:'other'}}]}, result],
  ]) {
    messages = rows
    assert.deepEqual((await manager.sessionDirectorRenders(selection)).jobs, [])
  }
  assert.deepEqual((await manager.sessionDirectorRenders({sessionKey: 'agent:main:dashboard:' + project})).jobs, [])
  await assert.rejects(manager.sessionDirectorRenders({...selection, agentId: 'main'}), /不属于/)
})
