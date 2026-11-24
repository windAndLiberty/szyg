const crypto = require('node:crypto')

const employeeModels = [
  'doubao-seed-evolving',
  'deepseek-v4-1-flash-economy-261017',
  'kimi-k3-1-pro-261024',
]
const permissionModes = new Set(['guarded', 'read-only', 'workspace', 'full'])

function modelChoice(value) {
  if (value === 'auto' || employeeModels.includes(value)) return value
  throw new Error('请选择可用的模型')
}

function permissionChoice(value) {
  if (permissionModes.has(value)) return value
  throw new Error('请选择有效的访问权限')
}

function textField(value, limit, field) {
  if (typeof value !== 'string' || value.length > limit) throw new Error(`${field}最多支持 ${limit} 个字符`)
  return value.trim()
}

function localAvatar(value) {
  if (value === 'xiaoyu' || value === 'director' || (typeof value === 'string' && /^robot:[0-5]$/.test(value))) return value
  if (typeof value !== 'string' || value.length > 700000) throw new Error('头像请使用不超过 512 KB 的本地图片')
  const match = /^data:image\/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})$/.exec(value)
  if (!match) throw new Error('头像支持 PNG、JPEG 或 WebP 图片')
  const bytes = Buffer.from(match[2], 'base64')
  let signatureMatches = false
  switch (match[1]) {
    case 'png':
      signatureMatches = bytes.subarray(0, 8).equals(Buffer.from('89504e470d0a1a0a', 'hex'))
      break
    case 'jpeg':
      signatureMatches = bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255
      break
    case 'webp':
      signatureMatches = bytes.toString('ascii', 0, 4) === 'RIFF' && bytes.toString('ascii', 8, 12) === 'WEBP'
      break
  }
  if (!signatureMatches || bytes.length < 16 || bytes.length > 512 * 1024 || bytes.toString('base64') !== match[2]) {
    throw new Error('头像图片格式或大小无效')
  }
  return value
}

function profileChanges(params) {
  const next = {}
  if (params.name !== undefined) {
    next.name = textField(params.name, 80, '员工姓名')
    if (!next.name || /[\r\n\u0000]/.test(next.name)) throw new Error('请填写有效的员工姓名')
  }
  if (params.title !== undefined) next.title = textField(params.title, 160, '职位')
  if (params.instructions !== undefined) next.instructions = textField(params.instructions, 8000, '自定义指令')
  if (params.avatar !== undefined) next.avatar = localAvatar(params.avatar)
  if (params.model !== undefined) next.model = modelChoice(params.model)
  if (params.toolPolicy !== undefined) {
    const policy = params.toolPolicy
    if (!policy || typeof policy !== 'object' || Array.isArray(policy)) throw new Error('员工工具策略无效')
    next.toolPolicy = { ...policy }
    if (policy.permissionMode !== undefined) next.toolPolicy.permissionMode = permissionChoice(policy.permissionMode)
  }
  if (params.skills !== undefined) {
    if (params.skills !== null && (!Array.isArray(params.skills) || !params.skills.every(skill => typeof skill === 'string'))) throw new Error('员工技能列表无效')
    next.skills = params.skills
  }
  return next
}

function creationId(requestId = crypto.randomUUID()) {
  if (typeof requestId !== 'string' || !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(requestId)) throw new Error('无效的创建请求')
  return 'employee-' + requestId.toLowerCase()
}

function managedInstructions(content, profile) {
  const start = '<!-- xiaoyu:employee-profile:start -->'
  const end = '<!-- xiaoyu:employee-profile:end -->'
  const block = [start, '## 当前员工身份与职责', profile.name, profile.title, profile.instructions, end]
    .filter(Boolean).join('\n\n')
  const previous = content.indexOf(start)
  const previousEnd = content.lastIndexOf(end)
  if (previous !== -1 && previousEnd >= previous) return content.slice(0, previous) + block + content.slice(previousEnd + end.length)
  return content.trimEnd() + '\n\n' + block + '\n'
}

module.exports = { employeeModels, modelChoice, permissionChoice, localAvatar, profileChanges, creationId, managedInstructions }
