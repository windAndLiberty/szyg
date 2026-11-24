import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { randomUUID } from 'node:crypto'
import { setTimeout as sleep } from 'node:timers/promises'
import { TaskQueue } from './tasks.mjs'

process.umask(0o077)
const base = process.env.SZYG_DATA_DIR || path.join(process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config'), 'xiaoyu-digital-employee', 'data')
const state = path.join(base, 'wechat-assistant')
fs.mkdirSync(state, { recursive: true, mode: 0o700 })
process.env.OPENCLAW_STATE_DIR = state
process.env.OPENCLAW_LOG_LEVEL = 'FATAL'
const file = path.join(state, 'binding.json')
const defaultApi = 'https://ilinkai.weixin.qq.com'
const plugin = new URL('../app/node_modules/@tencent-weixin/openclaw-weixin/dist/src/', import.meta.url)
const load = name => import(new URL(name, plugin))
const read = () => JSON.parse(fs.readFileSync(file, 'utf8'))

function employees() {
  const metadata = path.join(base, 'openclaw', 'xiaoyu-bots.json')
  const { profiles = {}, archived = {} } = fs.existsSync(metadata) ? JSON.parse(fs.readFileSync(metadata, 'utf8')) : {}
  const list = new Map([['xiaoyu-wechat', '小妤微信助理']])
  if (!archived.main) list.set('main', '小妤')
  for (const [id, profile] of Object.entries(profiles)) {
    if (!archived[id]) list.set(id, profile.name || profile.title || list.get(id) || id)
  }
  return list
}

async function bind() {
  const employee = process.argv[3] || 'xiaoyu-wechat'
  if (!employees().has(employee)) throw new Error('找不到指定员工，请先运行 szyg-wechat employees。')
  if (fs.existsSync(file)) throw new Error('请先解除现有绑定。')
  const mcp = process.env.XIAOYU_MCP_TOKEN?.trim()
  if (!mcp) throw new Error('请提供小妤「智能体接入」签发的凭证。')
  const qr = await load('auth/login-qr.js')
  const started = await qr.startWeixinLoginWithQr({ apiBaseUrl: defaultApi })
  if (!started.qrcodeUrl) throw new Error('腾讯未返回二维码，请重新绑定。')
  await qr.displayQRCode(started.qrcodeUrl)
  const result = await qr.waitForWeixinLogin({ apiBaseUrl: defaultApi, sessionKey: started.sessionKey })
  if (!result.connected || !result.botToken || !result.userId || !result.accountId)
    throw new Error('微信未返回完整的扫码身份和授权，请重新绑定。')
  const api = new URL(result.baseUrl || defaultApi)
  if (api.protocol !== 'https:' || api.username || api.password || !api.hostname.endsWith('.weixin.qq.com'))
    throw new Error('微信返回了无法验证的服务地址。')
  const binding = { id: randomUUID(), since: Date.now(), employee, peer: result.userId,
    account: result.accountId, api: api.href, token: result.botToken, mcp }
  const temp = path.join(state, binding.id + '.tmp')
  fs.writeFileSync(temp, JSON.stringify(binding), { flag: 'wx', mode: 0o600 })
  try { fs.linkSync(temp, file) } finally { fs.unlinkSync(temp) }
  console.log('已绑定本机小妤微信助理。请在原单聊发送「1分钟后 知识库概览」。')
}

async function serve() {
  // IPC ties this process to its own Electron parent even after an abnormal desktop exit.
  if (!process.connected) throw new Error('请由桌面应用启动服务。')
  process.on('disconnect', () => process.exit(0))
  const binding = read()
  const current = () => {
    try { return process.connected && read().id === binding.id } catch { return false }
  }
  const queue = new TaskQueue(path.join(state, 'tasks.db'))
  queue.recover(binding.id)
  const api = await load('api/api.js')
  const wx = { baseUrl: binding.api, token: binding.token }
  const port = Number(process.env.SZYG_BACKEND_PORT)
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('无效的本机端口。')
  const url = `http://127.0.0.1:${port}/api/mcp/xiaoyu`
  async function rpc(method, params) {
    const res = await fetch(url, { method: 'POST', redirect: 'error', signal: AbortSignal.timeout(185000),
      headers: { Authorization: 'Bearer ' + binding.mcp, 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }) })
    if (!res.ok) throw new Error('桌面账户或 MCP 凭证不可用。')
    const reply = await res.json()
    if (!reply.result || reply.result.isError) throw new Error('小妤工具未能完成任务。')
    return reply.result
  }
  const operations = {
    current,
    permissions: async () => (await rpc('tools/list', {})).tools.map(t => t.name),
    call: async (name, args) => (await rpc('tools/call', { name, arguments: args })).structuredContent,
    send: async (to, context, text) => {
      if (!current()) throw new Error('绑定已解除。')
      const receipt = await api.sendMessage({ ...wx, body: { msg: { from_user_id: '', to_user_id: to,
        context_token: context, client_id: randomUUID(), message_type: 2, message_state: 2,
        item_list: [{ type: 1, text_item: { text } }] } } })
      if (receipt.errcode || (receipt.ret !== 0 && !receipt.message_id)) throw new Error('微信未确认发送结果。')
    },
  }
  const health = queue.db.prepare('INSERT OR REPLACE INTO health VALUES(?,?,?)')
  async function receive() {
    while (current()) {
      let stage = '请检查小妤登录状态和微信助理凭证'
      try {
        await operations.permissions()
        stage = '请检查微信网络连接或重新扫码绑定'
        if (!current()) return
        const updates = await api.getUpdates({ ...wx, get_updates_buf: queue.cursor(binding.id), timeoutMs: 30000 })
        if (updates.ret || updates.errcode) throw new Error('微信连接需要检查。')
        if (current()) {
          queue.ingest(binding, updates, Date.now())
          health.run(binding.id, '正在接收', Date.now())
        }
        if (!updates.msgs?.length) await sleep(500)
      } catch { health.run(binding.id, stage, Date.now()); await sleep(5000) }
    }
  }
  async function execute() {
    while (current()) {
      try {
        if (!await queue.executeNext(binding, Date.now(), operations)) await sleep(800)
      } catch { await sleep(5000) }
    }
  }
  await Promise.all([receive(), execute()])
  queue.db.close()
}

async function main() {
  switch (process.argv[2]) {
    case 'bind': return bind()
    case 'serve': return serve()
    case 'unbind': {
      if (!fs.existsSync(file)) { console.log('未绑定'); break }
      const binding = read()
      fs.unlinkSync(file)
      const queue = new TaskQueue(path.join(state, 'tasks.db'))
      try { queue.forget(binding.id) } finally { queue.db.close() }
      console.log('本机微信绑定已解除。可在小妤设置中撤销对应 MCP 凭证。')
      break
    }
    case 'employees':
      for (const [id, title] of employees()) console.log(id, title)
      break
    case 'status': {
      if (!fs.existsSync(file)) { console.log('未绑定'); break }
      const queue = new TaskQueue(path.join(state, 'tasks.db'))
      const rows = queue.db.prepare('SELECT status,count(*) AS count FROM jobs WHERE binding=? AND kind=? GROUP BY status').all(read().id, 'result')
      const last = queue.db.prepare('SELECT state,updated FROM health WHERE binding=?').get(read().id)
      console.log(last ? `最近检查：${new Date(last.updated).toLocaleString()} · ${last.state}` : '等待桌面端连接。')
      console.log('绑定员工：', read().employee, '任务统计：', Object.fromEntries(rows.map(r => [r.status, r.count])))
      queue.db.close()
      break
    }
    default: throw new Error('用法：szyg-wechat bind [员工ID] | employees | status | unbind')
  }
}

main().catch(err => { console.error(err.message); process.exitCode = 1 })
