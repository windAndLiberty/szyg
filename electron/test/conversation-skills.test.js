const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { randomUUID } = require('node:crypto')
const { OpenClawRuntimeManager } = require('../openclaw/runtime-manager')

function fixture(t) {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-skill-selection-'))
  t.after(() => fs.rmSync(dataDir, { recursive: true, force: true }))
  const gatewaySessions = new Map()
  const cases = []
  const skills = ['canvas', 'weather'].map(name => ({
    name, skillKey: name + '-key', source: 'openclaw-bundled', description: name,
    eligible: true, modelVisible: true, userInvocable: true,
  }))
  function context(incognito = false) {
    const key = 'agent:main:dashboard:' + (incognito ? 'incognito-' : '') + randomUUID()
    gatewaySessions.set(key, { key, agentId: 'main', sessionId: randomUUID(),
      permissionMode: 'read-only', toolOverrides: { mcpToolsDeny: { business: ['write'] } } })
    return { sessionKey: key, agentId: 'main' }
  }
  function open() {
    const manager = new OpenClawRuntimeManager({ dataDir })
    manager.rpc = async (method, params) => {
      cases.push({ method, params })
      if (method === 'skills.status') return { skills }
      const session = gatewaySessions.get(params.key || params.sessionKey)
      if (method === 'sessions.describe') return { session }
      if (method === 'sessions.patch') {
        if (params.toolOverrides) {
          assert.equal(params.expectedSessionId, session.sessionId)
          assert.deepEqual(params.expectedToolOverrides, session.toolOverrides)
          session.toolOverrides = params.toolOverrides
        }
        return { ok: true }
      }
      if (method === 'chat.send') return { runId: randomUUID() }
      throw Error('Unexpected method ' + method)
    }
    return manager
  }
  return { manager: open(), open, context, cases, skills, gatewaySessions }
}

test('manual skill selection persists per conversation without granting tool access', async t => {
  const { manager, open, context, gatewaySessions, cases } = fixture(t)
  const first = context()
  const other = context()
  const target = { ...first, name: 'canvas' }
  assert.deepEqual(await manager.changeSkillSelection(target, true), { selected: ['canvas'] })
  const state = gatewaySessions.get(first.sessionKey)
  assert.deepEqual(state.toolOverrides.mcpToolsDeny, { business: ['write'] })
  assert.equal(state.permissionMode, 'read-only')
  assert.equal(state.toolOverrides.skills['canvas-key'], undefined)
  await manager.configureSession({ key: first.sessionKey, agentId: first.agentId, model: 'auto' })
  assert.deepEqual(await open().skillSelection(first), { selected: ['canvas'] })
  assert.deepEqual(await manager.skillSelection(other), { selected: [] })
  await manager.sendRun({ ...first, message: '明天几点日出？' })
  const sent = cases.find(row => row.method === 'chat.send').params
  assert.deepEqual(sent.workContext.detail, { '本轮先读取并应用所选技能的 SKILL.md': 'canvas' })
  assert.equal(sent.message, '明天几点日出？')
  assert.deepEqual(sent.expectedToolOverrides, state.toolOverrides)
  manager.clearTrackedRun(first.sessionKey, manager.activeSessions.get(first.sessionKey))
  assert.deepEqual(await manager.changeSkillSelection(target, false), { selected: [] })
  assert.equal(state.toolOverrides.skills['canvas-key'], false)
  assert.deepEqual(await open().skillSelection(first), { selected: [] })
  const reopened = open()
  await reopened.sendRun({ ...first, message: '再次提问' })
  assert.equal(cases.filter(row => row.method === 'chat.send').at(-1).params.workContext, undefined)
  reopened.clearTrackedRun(first.sessionKey, reopened.activeSessions.get(first.sessionKey))
  assert.deepEqual(await manager.changeSkillSelection(target, true), { selected: ['canvas'] })
  assert.equal(state.toolOverrides.skills['canvas-key'], undefined)
})

test('session and employee restrictions take precedence over manual selection', async t => {
  const { manager, context, skills, gatewaySessions } = fixture(t)
  const first = context()
  const target = { ...first, name: 'canvas' }
  const row = gatewaySessions.get(first.sessionKey)
  row.toolOverrides.skills = { 'canvas-key': false }
  await assert.rejects(manager.changeSkillSelection(target, true), /限制/)
  assert.deepEqual((await manager.skillCatalog(first)).skills.map(x => x.name), ['weather'])
  delete row.toolOverrides.skills['canvas-key']
  await manager.changeSkillSelection(target, true)
  manager.storeProfile('main', { skills: ['weather'] })
  assert.deepEqual(await manager.skillSelection(first), { selected: [] })
  await assert.rejects(manager.changeSkillSelection(target, true), /没有可用/)
  manager.storeProfile('main', { skills: null })
  skills[0].blockedByAgentFilter = true
  skills[1].eligible = false
  assert.deepEqual((await manager.skillCatalog(first)).skills, [])
  assert.throws(() => manager.changeSkillSelection({ ...target, agentId: 'other' }, true), /不属于/)
  assert.throws(() => manager.changeSkillSelection({ ...target, sessionKey: 'agent:main:wechat:external' }, true), /仅本机/)
  assert.throws(() => manager.changeSkillSelection({ ...first, name: '__proto__' }, true), /无效/)
})

test('concurrent selections compose and a rejected native change does not persist', async t => {
  const { manager, context, gatewaySessions } = fixture(t)
  const first = context()
  await Promise.all(['canvas', 'weather'].map(name => manager.changeSkillSelection({ ...first, name }, true)))
  assert.deepEqual(await manager.skillSelection(first), { selected: ['canvas', 'weather'] })
  const row = gatewaySessions.get(first.sessionKey)
  row.hasActiveRun = true
  await assert.rejects(manager.changeSkillSelection({ ...first, name: 'weather' }, false), /当前回复/)
  row.hasActiveRun = false
  const rpc = manager.rpc
  manager.rpc = (method, params) => method === 'sessions.patch' ? Promise.reject(Error('overlay changed')) : rpc(method, params)
  await assert.rejects(manager.changeSkillSelection({ ...first, name: 'weather' }, false), /overlay changed/)
  assert.deepEqual(await manager.skillSelection(first), { selected: ['canvas', 'weather'] })
})

test('incognito skill choices only live in memory', async t => {
  const { manager, open, context } = fixture(t)
  const first = context(true)
  await manager.changeSkillSelection({ ...first, name: 'canvas' }, true)
  assert.deepEqual(await manager.skillSelection(first), { selected: ['canvas'] })
  assert.equal(manager.loadBotMetadata().sessions[first.sessionKey], undefined)
  assert.deepEqual(await open().skillSelection(first), { selected: [] })
})

test('preserves restricted native keys while exposing only the skill name and description', async t => {
  const { manager, context, skills, gatewaySessions } = fixture(t)
  const first = context()
  const state = gatewaySessions.get(first.sessionKey)
  state.toolOverrides.skills = { '1password': false }
  skills[0].filePath = '/local/private/path'
  const request = manager.rpc
  manager.client = { request }
  const { sanitizeForRenderer } = require('../openclaw/runtime-manager')
  manager.rpc = async (method, params) => sanitizeForRenderer(await request(method, params))
  const result = await manager.skillCatalog(first)
  assert.deepEqual(Object.keys(result.skills[0]).sort(), ['description', 'name'])
  await manager.changeSkillSelection({ ...first, name: 'canvas' }, true)
  assert.deepEqual(state.toolOverrides.skills, { '1password': false })
})
