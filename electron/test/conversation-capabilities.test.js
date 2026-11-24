const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const http = require('node:http')
const os = require('node:os')
const path = require('node:path')
const { randomUUID } = require('node:crypto')
const { OpenClawRuntimeManager } = require('../openclaw/runtime-manager')

const image = 'content.image.generate'
const inspect = 'materials.inspect'
const publish = 'publish.submit'
const business = 'szyg-business'
const catalog = [
  { name: image, title: '生成图片', description: '生成图片并保存', domain: 'content' },
  { name: inspect, title: '检查素材', description: '检查本机素材', domain: 'materials' },
  { name: publish, title: '发布内容', description: '发布前需确认', domain: 'publish' },
]

function fixture(t) {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-capabilities-'))
  t.after(() => fs.rmSync(dataDir, { force: true, recursive: true }))
  const sessions = new Map()
  const calls = []
  function open() {
    const manager = new OpenClawRuntimeManager({ dataDir })
    manager.businessCapabilityCatalog = async () => catalog
    manager.rpc = async (method, params) => {
      calls.push({ method, params })
      const row = sessions.get(params.key || params.sessionKey)
      if (method === 'sessions.describe') return { session: row }
      if (method === 'sessions.patch') {
        if (params.toolOverrides) {
          assert.equal(params.expectedSessionId, row.sessionId)
          assert.deepEqual(params.expectedToolOverrides, row.toolOverrides)
          row.toolOverrides = params.toolOverrides
        }
        return { ok: true }
      }
      if (method === 'chat.send') return { runId: randomUUID() }
      if (method === 'skills.status') return { skills: [{
        name: 'canvas', source: 'openclaw-bundled', eligible: true, modelVisible: true, userInvocable: true,
      }] }
      throw Error('Unexpected method ' + method)
    }
    return manager
  }
  function session(agentId = 'main', incognito = false) {
    const sessionKey = `agent:${agentId}:dashboard:${incognito ? 'incognito-' : ''}${randomUUID()}`
    const gateway = { key: sessionKey, agentId, sessionId: randomUUID(), permissionMode: 'read-only',
      toolOverrides: { mcpToolsDeny: { other: ['write'] }, skills: { canvas: false }, mcpServers: { [business]: true } } }
    sessions.set(sessionKey, gateway)
    return { params: { agentId, sessionKey }, gateway }
  }
  return { manager: open(), open, session, calls }
}

async function localServer(t, respond) {
  const server = http.createServer(async (req, res) => {
    try {
      const chunks = []
      for await (const chunk of req) chunks.push(chunk)
      const result = await respond(req, JSON.parse(Buffer.concat(chunks)))
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify(result))
    } catch (error) {
      res.writeHead(500)
      res.end(String(error))
    }
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  t.after(() => server.close())
  return server.address().port
}

test('business capabilities use the signed local catalogue and expose only display fields', async t => {
  const port = await localServer(t, (request, body) => {
    assert.equal(request.url, '/api/mcp/szyg-business')
    assert.equal(request.headers.authorization, 'Bearer fixture')
    assert.equal(body.method, 'tools/list')
    return { result: { tools: [
      { ...catalog[0], _meta: { 'szyg/domain': 'content' }, inputSchema: {}, secret: 'never returned' },
      { name: '__proto__', title: 'invalid' },
    ] } }
  })
  const manager = new OpenClawRuntimeManager({ backendPort: port, businessMcpToken: 'fixture', dataDir: os.tmpdir() })
  assert.deepEqual(await manager.businessCapabilityCatalog(), [catalog[0]])
})

test('choose and unload app tools per chat, preserving each employee’s native tool and permission settings', async t => {
  const { manager, open, session } = fixture(t)
  const first = session(), director = session('xiaoyu-director')
  const target = { ...first.params, name: image }
  const loaded = { selected: [image], titles: { [image]: '生成图片' } }
  const empty = { selected: [], titles: {} }
  const before = structuredClone(first.gateway.toolOverrides)
  assert.deepEqual(await manager.changeCapabilitySelection(target, true), loaded)
  assert.deepEqual(first.gateway.toolOverrides, before)
  assert.deepEqual(await manager.capabilitySelection(director.params), empty)
  assert.deepEqual(await open().capabilitySelection(first.params), loaded)
  assert.deepEqual(await manager.changeCapabilitySelection(target, false), empty)
  assert.deepEqual(first.gateway.toolOverrides, { ...before, mcpToolsDeny: { ...before.mcpToolsDeny, [business]: [image] } })
  assert.equal(first.gateway.permissionMode, 'read-only')
  assert.deepEqual(director.gateway.toolOverrides, before)
  assert.deepEqual((await manager.capabilityCatalog(first.params)).capabilities, catalog)
  assert.deepEqual(await open().changeCapabilitySelection(target, true), loaded)
  assert.deepEqual(first.gateway.toolOverrides, before)
})

test('tool selections cannot remove session restrictions or employee tool denials', async t => {
  const { manager, session } = fixture(t)
  const { params, gateway } = session()
  gateway.toolOverrides.mcpToolsDeny[business] = [image]
  manager.storeProfile('main', { toolPolicy: { mcpToolsDeny: { [business]: [publish] } } })
  assert.deepEqual((await manager.capabilityCatalog(params)).capabilities, [catalog[1]])
  await assert.rejects(manager.changeCapabilitySelection({ ...params, name: image }, true), /限制/)
  await assert.rejects(manager.changeCapabilitySelection({ ...params, name: publish }, true), /没有可用/)
  await manager.changeCapabilitySelection({ ...params, name: inspect }, true)
  await manager.changeCapabilitySelection({ ...params, name: inspect }, false)
  await manager.changeCapabilitySelection({ ...params, name: inspect }, true)
  assert.deepEqual(gateway.toolOverrides.mcpToolsDeny[business], [image])
  gateway.toolOverrides.mcpServers[business] = false
  assert.deepEqual(await manager.capabilityCatalog(params), { capabilities: [] })
  assert.deepEqual(await manager.capabilitySelection(params), { selected: [], titles: {} })
  assert.throws(() => manager.changeCapabilitySelection({ ...params, agentId: 'someone-else', name: image }, true), /不属于/)
  assert.throws(() => manager.changeCapabilitySelection({ ...params, sessionKey: 'agent:main:wechat:subject', name: image }, true), /仅本机/)
  assert.throws(() => manager.changeCapabilitySelection({ ...params, name: '__proto__' }, true), /无效/)
})

test('incognito choices remain in memory, and a failed gateway save does not record an unload', async t => {
  const { manager, open, session } = fixture(t)
  const { params, gateway } = session('main', true)
  const target = { ...params, name: image }
  await Promise.all([manager.changeCapabilitySelection(target, true), manager.changeCapabilitySelection({ ...params, name: inspect }, true)])
  assert.deepEqual((await manager.capabilitySelection(params)).selected, [image, inspect])
  assert.equal(manager.loadBotMetadata().sessions[params.sessionKey], undefined)
  assert.deepEqual((await open().capabilitySelection(params)).selected, [])
  gateway.hasActiveRun = true
  await assert.rejects(manager.changeCapabilitySelection(target, false), /当前回复/)
  gateway.hasActiveRun = false
  const rpc = manager.rpc
  manager.rpc = (method, options) => method === 'sessions.patch' ? Promise.reject(Error('session changed')) : rpc(method, options)
  await assert.rejects(manager.changeCapabilitySelection(target, false), /session changed/)
  assert.deepEqual((await manager.capabilitySelection(params)).selected, [image, inspect])
})

test('selected application tools, attachments, skills and three experts share the same turn safely', async t => {
  const { manager, session, calls } = fixture(t)
  const { params, gateway } = session()
  delete gateway.toolOverrides.skills.canvas
  manager.options.desktopToken = 'fixture'
  manager.options.backendPort = await localServer(t, (_, body) => {
    assert.equal(body.session_key, params.sessionKey)
    return { workContext: { page: '专家', selection: '三位专家的完整参考', detail: { expert1: 'a', expert2: 'b', expert3: 'c' } } }
  })
  await manager.changeCapabilitySelection({ ...params, name: image }, true)
  await manager.changeSkillSelection({ ...params, name: 'canvas' }, true)
  const asset = '/api/media/files/image/9b19b470-7a31-4a07-9cbf-bdce256bffcc.png'
  const message = `请参考[这张图](${asset})`
  const run = await manager.sendRun({ ...params, message, attachments: [asset] })
  const request = calls.find(row => row.method === 'chat.send').params
  assert.equal(request.message, message)
  assert.equal(request.workContext.selection, '三位专家的完整参考')
  assert.equal(Object.keys(request.workContext.detail).length, 4)
  assert.match(request.workContext.detail['本轮附件'], /materials\.inspect/)
  assert.equal(request.workContext.detail['本轮先读取并应用所选技能的 SKILL.md'], 'canvas')
  assert.equal(request.workContext.detail['优先通过 tool_search 查找适用能力'], image)
  assert.deepEqual(request.expectedToolOverrides, gateway.toolOverrides)
  manager.clearTrackedRun(params.sessionKey, run.runId)
})
