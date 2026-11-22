import { DatabaseSync } from 'node:sqlite'

export const usage = '可以直接向绑定员工提问，或发送「知识库概览」「查知识库 关键词」「写文案 需求」。延时示例：「1分钟后 知识库概览」。'
const commands = [
  [/^知识库概览$/, 'knowledge_stats'],
  [/^查知识库[：:\s]+(.+)$/s, 'knowledge_search'],
  [/^写文案[：:\s]+(.+)$/s, 'content_copy_generate'],
]

export function parseTask(text, now) {
  let due = now
  const schedule = /^(\d{1,4})\s*(分钟|小时)后[，,：:\s]*(.+)$/s.exec(text)
  if (schedule) {
    const delay = Number(schedule[1]) * (schedule[2] === '小时' ? 3600000 : 60000)
    if (delay < 60000 || delay > 86400000) return { tool: 'help', due: now, input: '' }
    due += delay
    text = schedule[3].trim()
  }
  for (const [pattern, tool] of commands) {
    const match = pattern.exec(text)
    if (match) return { tool, due, input: (match[1] || '').trim() }
  }
  if (text === '帮助' || text === '/help') return { tool: 'help', due: now, input: '' }
  return { tool: 'employee_reply', due, input: text }
}

export function formatResult(tool, result) {
  if (tool === 'employee_reply' && result.text) return String(result.text)
  if (tool === 'knowledge_stats' && Number.isInteger(result.totalDocs) && Number.isInteger(result.totalChunks))
    return `知识库共有 ${result.totalDocs} 篇文档、${result.totalChunks} 个文本片段。`
  if (tool === 'knowledge_search' && Array.isArray(result.results))
    return result.results.map(r => `${r.filename}\n${String(r.content).slice(0, 360)}`).join('\n\n') || '没有找到相关文档。'
  if (tool === 'content_copy_generate' && result.copies?.[0]) return String(result.copies[0])
  throw new Error('unexpected tool result')
}

export class TaskQueue {
  constructor(file) {
    this.db = new DatabaseSync(file)
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS cursors (binding TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS jobs (
        binding TEXT NOT NULL, msg TEXT NOT NULL, kind TEXT NOT NULL,
        due INTEGER NOT NULL, tool TEXT NOT NULL, input TEXT NOT NULL,
        context TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
        PRIMARY KEY(binding,msg,kind)
      );
      CREATE TABLE IF NOT EXISTS health (binding TEXT PRIMARY KEY, state TEXT NOT NULL, updated INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS pending_jobs ON jobs(binding,status,due);
    `)
  }

  recover(binding) {
    this.db.prepare("UPDATE jobs SET status='unconfirmed',context='',input='' WHERE binding=? AND status IN ('running','sending')").run(binding)
  }

  forget(binding) {
    this.db.exec('BEGIN IMMEDIATE')
    try {
      for (const table of ['jobs', 'cursors', 'health']) {
        this.db.prepare(`DELETE FROM ${table} WHERE binding=?`).run(binding)
      }
      this.db.exec('COMMIT')
    } catch (err) { this.db.exec('ROLLBACK'); throw err }
  }

  cursor(binding) {
    return this.db.prepare('SELECT value FROM cursors WHERE binding=?').get(binding)?.value ?? ''
  }

  ingest(binding, updates, now) {
    const insert = this.db.prepare('INSERT OR IGNORE INTO jobs(binding,msg,kind,due,tool,input,context) VALUES(?,?,?,?,?,?,?)')
    this.db.exec('BEGIN IMMEDIATE')
    try {
      for (const msg of updates.msgs ?? []) {
        const id = msg.message_id || msg.client_id
        const timestamp = Number(msg.create_time_ms)
        if (!id || !Number.isSafeInteger(timestamp) || timestamp < binding.since ||
            msg.message_type !== 1 || msg.group_id || msg.from_user_id !== binding.peer ||
            (msg.to_user_id && msg.to_user_id !== binding.account) || !msg.context_token) continue
        const items = msg.item_list
        if (items?.length !== 1 || items[0].type !== 1) continue
        const text = items[0].text_item?.text
        if (typeof text !== 'string' || !text.trim() || text.length > 4000) continue
        const { tool, due, input } = parseTask(text.trim(), Math.min(timestamp, now))
        insert.run(binding.id, String(id), 'result', due, tool, input, msg.context_token)
        if (due > now) insert.run(binding.id, String(id), 'ack', now, 'ack', String(due), msg.context_token)
      }
      if (updates.get_updates_buf) this.db.prepare('INSERT OR REPLACE INTO cursors VALUES(?,?)')
        .run(binding.id, updates.get_updates_buf)
      this.db.exec('COMMIT')
    } catch (err) { this.db.exec('ROLLBACK'); throw err }
  }

  async executeNext(binding, now, { permissions, call, send, current }) {
    const job = this.db.prepare("SELECT rowid AS id,* FROM jobs WHERE binding=? AND status='queued' AND due<=? ORDER BY due,rowid LIMIT 1").get(binding.id, now)
    if (!job) return false
    const allowed = await permissions()
    if (!current()) return false
    const claimed = this.db.prepare("UPDATE jobs SET status='running' WHERE rowid=? AND status='queued'").run(job.id)
    if (!claimed.changes) return false
    let text
    if (job.tool === 'ack') text = `小妤已收到，预计 ${new Date(Number(job.input)).toLocaleString('zh-CN', { hour12: false })} 在本机执行。`
    else if (job.tool === 'help') text = usage
    else if (!allowed.includes(job.tool)) text = '当前微信助理没有这项工具的授权。' + usage
    else {
      try {
        const args = job.tool === 'knowledge_search' ? { q: job.input, top_k: 3 }
          : job.tool === 'employee_reply' ? { prompt: job.input, employee_id: binding.employee }
          : job.tool === 'content_copy_generate' ? { prompt: job.input, count: 1 } : {}
        text = formatResult(job.tool, await call(job.tool, args))
      } catch { text = '任务未取得可验证的结果。请在小妤桌面端检查工具和账户状态。' }
    }
    // Verify again after slow work. A replaced binding or revoked credential cannot deliver.
    const setStatus = this.db.prepare("UPDATE jobs SET status=?, input='',context='' WHERE rowid=?")
    try {
      await permissions()
      if (!current()) { setStatus.run('cancelled', job.id); return true }
      this.db.prepare("UPDATE jobs SET status='sending' WHERE rowid=?").run(job.id)
      await send(binding.peer, job.context, text.length > 1800 ? text.slice(0, 1799) + '…' : text)
      setStatus.run('sent', job.id)
    } catch {
      // A timeout may be a lost receipt. Never replay an ambiguous send.
      setStatus.run('unconfirmed', job.id)
    }
    return true
  }
}
