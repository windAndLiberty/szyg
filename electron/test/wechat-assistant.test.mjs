import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { TaskQueue, parseTask } from '../wechat/tasks.mjs'

const now = Date.now()
const binding = { id: 'binding-1', peer: 'alice', account: 'bot-A', employee: 'editor', since: now }
const message = (text, extra = {}) => ({
  message_id: '42', message_type: 1, from_user_id: 'alice', to_user_id: 'bot-A',
  context_token: 'thread-1', create_time_ms: now, item_list: [{ type: 1, text_item: { text } }], ...extra,
})
function operations(grants = ['knowledge_stats']) {
  const calls = [], deliveries = []
  return { calls, deliveries, current: () => true, permissions: async () => grants,
    call: async (tool, args) => { calls.push({ tool, args }); return { totalDocs: 5, totalChunks: 7, text: '员工答复' } },
    send: async (peer, context, text) => { deliveries.push({ peer, context, text }) } }
}
function memory(t) {
  const queue = new TaskQueue(':memory:')
  t.after(() => queue.db.close())
  return queue
}

test('only the scanner’s direct, text-only, post-binding messages are accepted', t => {
  const queue = memory(t)
  const denied = [
    { from_user_id: 'stranger' }, { group_id: 'group' }, { to_user_id: 'bot-B' }, { message_type: 2 },
    { create_time_ms: now - 1 }, { create_time_ms: undefined }, { context_token: '' }, { message_id: '' },
    { item_list: [{ type: 2 }] }, { item_list: [] },
  ]
  queue.ingest(binding, { msgs: denied.map((fields, i) => message('知识库概览', { message_id: String(i + 1), ...fields })), get_updates_buf: 'seen' }, now)
  assert.equal(queue.db.prepare('SELECT count(*) n FROM jobs').get().n, 0)
  assert.equal(queue.cursor(binding.id), 'seen')
})

test('a delayed task survives restart, repeated delivery preserves the source context', async t => {
  const dir = mkdtempSync(path.join(tmpdir(), 'szyg-wechat-test-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  const file = path.join(dir, 'queue.db')
  let queue = new TaskQueue(file)
  const msg = message('1分钟后 知识库概览')
  queue.ingest(binding, { msgs: [msg], get_updates_buf: 'first' }, now)
  const op = operations()
  assert.ok(await queue.executeNext(binding, now, op))
  assert.match(op.deliveries[0].text, /已收到/)
  queue.db.close()
  queue = new TaskQueue(file)
  t.after(() => queue.db.close())
  queue.recover(binding.id)
  queue.ingest(binding, { msgs: [{ ...msg, context_token: 'different' }], get_updates_buf: 'second' }, now + 2000)
  assert.equal(await queue.executeNext(binding, now + 59999, op), false)
  assert.equal(await queue.executeNext(binding, now + 60000, op), true)
  assert.deepEqual(op.deliveries[1], { peer: 'alice', context: 'thread-1', text: '知识库共有 5 篇文档、7 个文本片段。' })
  assert.equal(op.calls.length, 1)
  assert.equal(await queue.executeNext(binding, now + 60001, op), false)
  assert.equal(queue.cursor(binding.id), 'second')
})
test('free text uses only the bound employee and a separately granted tool', async t => {
  const queue = memory(t)
  const txt = '请让另一个员工处理这条消息'
  queue.ingest(binding, { msgs: [message(txt)] }, now)
  const denied = operations()
  await queue.executeNext(binding, now, denied)
  assert.equal(denied.calls.length, 0)
  assert.match(denied.deliveries[0].text, /没有这项工具的授权/)
  queue.ingest(binding, { msgs: [message(txt, { message_id: '43' })] }, now)
  const allowed = operations(['employee_reply'])
  await queue.executeNext(binding, now, allowed)
  assert.deepEqual(allowed.calls, [{ tool: 'employee_reply', args: { prompt: txt, employee_id: 'editor' } }])
  assert.equal(allowed.deliveries[0].text, '员工答复')
})

test('revocation or rebinding during a call suppresses the reply', async t => {
  const queue = memory(t)
  for (const reason of ['revoke', 'rebind']) {
    const op = operations()
    let checks = 0
    op.permissions = async () => {
      if (++checks === 2 && reason === 'revoke') throw new Error('inactive grant')
      return ['knowledge_stats']
    }
    op.current = () => reason !== 'rebind' || checks === 1
    queue.ingest(binding, { msgs: [message('知识库概览', { message_id: reason })] }, now)
    await queue.executeNext(binding, now, op)
    assert.equal(op.deliveries.length, 0)
  }
})
test('a missing receipt or interrupted send never replays work', async t => {
  const queue = memory(t)
  const op = operations()
  let attempts = 0
  op.send = async () => { attempts++; throw new Error('reply lost after acceptance') }
  queue.ingest(binding, { msgs: [message('知识库概览')] }, now)
  await queue.executeNext(binding, now, op)
  queue.ingest(binding, { msgs: [message('知识库概览')] }, now)
  assert.equal(await queue.executeNext(binding, now, op), false)
  assert.equal(attempts, 1)
  for (const status of ['running', 'sending']) {
    queue.db.prepare("UPDATE jobs SET status=?").run(status)
    queue.recover(binding.id)
    assert.equal(await queue.executeNext(binding, now, op), false)
    const row = queue.db.prepare('SELECT status,context,input FROM jobs').get()
    assert.deepEqual({ ...row }, { status: 'unconfirmed', context: '', input: '' })
  }
})
test('unlink clears saved work and cursor for this binding', t => {
  const queue = memory(t)
  const second = { ...binding, id: 'second' }
  for (const b of [binding, second]) queue.ingest(b, { msgs: [message('写文案 活动')], get_updates_buf: b.id }, now)
  queue.forget(binding.id)
  assert.equal(queue.cursor(binding.id), '')
  assert.equal(queue.cursor(second.id), 'second')
  assert.equal(queue.db.prepare('SELECT binding FROM jobs').get().binding, second.id)
})
test('parses explicit tools and bounds relative scheduling', () => {
  assert.deepEqual(parseTask('24小时后 查知识库 产品', now), { tool: 'knowledge_search', input: '产品', due: now + 86400000 })
  assert.equal(parseTask('25小时后 查询', now).tool, 'help')
  assert.equal(parseTask('0分钟后 查询', now).tool, 'help')
  assert.equal(parseTask('写文案 夏季', now).tool, 'content_copy_generate')
})


test('bindable employees include Main before it has a profile and show saved employee names', t => {
  const base = mkdtempSync(path.join(tmpdir(), 'xiaoyu-wechat-roster-'))
  t.after(() => rmSync(base, { recursive: true, force: true }))
  const script = fileURLToPath(new URL('../wechat/assistant.mjs', import.meta.url))
  const list = () => execFileSync(process.execPath, [script, 'employees'], {
    env: { ...process.env, SZYG_DATA_DIR: base }, encoding: 'utf8',
  }).trim().split('\n')
  assert.deepEqual(list(), ['xiaoyu-wechat 小妤微信助理', 'main 小妤'])
  mkdirSync(path.join(base, 'openclaw'))
  writeFileSync(path.join(base, 'openclaw', 'xiaoyu-bots.json'), JSON.stringify({
    profiles: { main: { avatar: 'robot:2' }, editor: { name: '阿巧', title: '内容编辑' }, old: { title: '旧员工' } },
    archived: { old: 1 },
  }))
  assert.deepEqual(list(), ['xiaoyu-wechat 小妤微信助理', 'main 小妤', 'editor 阿巧'])
})
