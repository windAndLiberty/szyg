const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const versions = require('../openclaw/runtime-constants')
const resources = process.argv[2]
const runtimePath = `runtime/openclaw/${versions.OPENCLAW_RUNTIME_VERSION}`
const runtime = path.join(resources, runtimePath)

function entry(root, file) {
  const bytes = fs.readFileSync(path.join(root, file))
  return { path: file, size: bytes.length, sha256: crypto.createHash('sha256').update(bytes).digest('hex') }
}

function write(file, value) {
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n')
}

write(path.join(runtime, 'manifest.json'), {
  platform: 'linux-x64',
  openclawVersion: versions.OPENCLAW_RUNTIME_VERSION,
  gatewayClientVersion: versions.OPENCLAW_GATEWAY_CLIENT_VERSION,
  protocolVersion: versions.OPENCLAW_PROTOCOL_VERSION,
  wireVersion: versions.OPENCLAW_WIRE_VERSION,
  nodeVersion: versions.OPENCLAW_NODE_VERSION,
  files: ['node', 'app/package-lock.json', 'app/node_modules/openclaw/openclaw.mjs',
    'app/node_modules/openclaw/package.json', 'wechat/tasks.mjs', 'wechat/assistant.mjs',
    'wechat/szyg-wechat', 'app/node_modules/@tencent-weixin/openclaw-weixin/package.json'].map(file => entry(runtime, file)),
})
const files = ['config.yaml', 'python/bin/python3', 'hermes-runtime', 'server/szyg_backend_entry.py',
  'server/hermes_runtime_entry.py', 'frontend/index.html', `${runtimePath}/manifest.json`]
write(path.join(resources, 'runtime-integrity.json'), {
  algorithm: 'sha256',
  entries: files.map(file => entry(resources, file)),
})
