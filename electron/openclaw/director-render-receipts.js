const renderName = 'szyg-business__director-render'
const renderId = 'mcp:szyg-business:' + renderName
const uuid = /^[a-f\d]{8}(?:-[a-f\d]{4}){3}-[a-f\d]{12}$/i

function parsed(value) {
  if (typeof value !== 'string') return value
  try { return JSON.parse(value.replace(/^structuredContent:\s*/, '')) }
  catch { return null }
}

function renderInvocation(block) {
  if (typeof block.id !== 'string' || !block.id) return false
  const args = parsed(block.arguments)
  if (block.name === 'tool_call') return args?.id === renderId && uuid.test(args.args?.project_id)
  return block.name === renderName && uuid.test(args?.project_id)
}

function nativeTextResult(block) {
  if (block?.type !== 'text' || typeof block.text !== 'string') return null
  // The native transcript can retain only the MCP control tool's framed JSON.
  // Parse the entire result envelope and check its tool identity below.
  const frame = /(?:^|\n)<<<EXTERNAL_UNTRUSTED_CONTENT id="([\da-f]+)">>>\nSource: API\n---\n([\s\S]*)\n<<<END_EXTERNAL_UNTRUSTED_CONTENT id="\1">>>$/.exec(block.text)
  return parsed(frame ? frame[2] : block.text)
}

function textResults(message) {
  return (Array.isArray(message?.content) ? message.content : [])
    .map(nativeTextResult).filter(Boolean)
}

function renderReceipt(message) {
  const wrapper = message.toolName === 'tool_call'
  const envelopes = wrapper ? [message.details, ...textResults(message)] : [message]
  for (const envelope of envelopes) {
    if (wrapper && envelope?.tool?.id !== renderId) continue
    const result = wrapper ? envelope.result : envelope
    const receipts = [result?.details?.structuredContent, ...textResults(result)]
    for (const receipt of receipts) {
      const payload = receipt?.data || receipt?.result || receipt
      if (typeof payload?.job_id === 'string' && uuid.test(payload.job_id)) return payload.job_id
    }
  }
}

function directorRenderJobs(messages) {
  const calls = new Map()
  const jobs = new Set()
  for (const message of messages) {
    if (message?.role === 'assistant' && Array.isArray(message.content)) {
      for (const block of message.content) {
        if (block?.type !== 'toolCall') continue
        // A reused call ID may now identify a different tool.
        calls.delete(block.id)
        if (renderInvocation(block)) calls.set(block.id, block.name)
      }
    } else if (message?.role === 'toolResult') {
      const name = calls.get(message.toolCallId)
      calls.delete(message.toolCallId)
      if (!name || name !== message.toolName) continue
      const jobId = renderReceipt(message)
      if (jobId) jobs.add(jobId)
    }
  }
  return [...jobs]
}

module.exports = { directorRenderJobs }
