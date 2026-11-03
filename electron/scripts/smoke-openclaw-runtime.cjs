const { execFile, spawn } = require('child_process')
const { promisify } = require('util')
const crypto = require('crypto')
const fs = require('fs')
const net = require('net')
const os = require('os')
const path = require('path')
const { OPENCLAW_RUNTIME_VERSION, OPENCLAW_WIRE_VERSION } = require('../openclaw/runtime-constants')
const { generateDeviceIdentity, publicKeyRawBase64UrlFromPem, signDevicePayload } = require('../openclaw/runtime-manager')
const execFileAsync = promisify(execFile)

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      server.close(() => resolve(address.port))
    })
  })
}

async function main() {
  const runtimeRoot = path.resolve(__dirname, '..', 'runtime', 'openclaw', OPENCLAW_RUNTIME_VERSION)
  const node = path.join(runtimeRoot, 'node.exe')
  const entry = path.join(runtimeRoot, 'app', 'node_modules', 'openclaw', 'openclaw.mjs')
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'xiaoyu-openclaw-smoke-'))
  const port = await freePort()
  const unavailableBusinessPort = await freePort()
  const token = crypto.randomBytes(32).toString('hex')
  const env = {
    ...process.env,
    OPENCLAW_DISABLE_BONJOUR: '1',
    OPENCLAW_EXEC_SHELL_SNAPSHOT: '0',
    OPENCLAW_NO_RESPAWN: '1',
    OPENCLAW_SKIP_CHANNELS: '1',
    OPENCLAW_STATE_DIR: path.join(temporary, 'state'),
    OPENCLAW_CONFIG_PATH: path.join(temporary, 'state', 'openclaw.json'),
    OPENCLAW_WORKSPACE_DIR: path.join(temporary, 'workspace'),
    OPENCLAW_GATEWAY_TOKEN: token,
  }
  fs.mkdirSync(env.OPENCLAW_WORKSPACE_DIR, { recursive: true })
  fs.mkdirSync(env.OPENCLAW_STATE_DIR, { recursive: true })
  fs.writeFileSync(env.OPENCLAW_CONFIG_PATH, `${JSON.stringify({
    gateway: { mode: 'local' },
    mcp: {
      servers: {
        'szyg-business': {
          url: `http://127.0.0.1:${unavailableBusinessPort}/api/mcp/szyg-business`,
          transport: 'streamable-http',
          enabled: true,
          headers: { Authorization: `Bearer ${token}` },
          connectionTimeoutMs: 5000,
          requestTimeoutMs: 180000,
          supportsParallelToolCalls: false,
        },
      },
    },
  }, null, 2)}\n`, 'utf8')
  await execFileAsync(node, [entry, 'config', 'validate', '--json'], { env, cwd: temporary, timeout: 30000, windowsHide: true })
  const child = spawn(node, [entry, 'gateway', '--bind', 'loopback', '--port', String(port)], {
    env,
    cwd: temporary,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  let stderr = ''
  let stdout = ''
  let client = null
  const deviceIdentity = generateDeviceIdentity()
  child.stderr.on('data', (data) => { stderr += String(data) })
  child.stdout.on('data', (data) => { stdout += String(data) })
  try {
    const [{ GatewayClient, startGatewayClientWhenEventLoopReady }, { PROTOCOL_VERSION }] = await Promise.all([
      import('@openclaw/gateway-client'),
      import('@openclaw/gateway-protocol'),
    ])
    if (Number(PROTOCOL_VERSION) !== OPENCLAW_WIRE_VERSION) throw new Error(`wire version ${PROTOCOL_VERSION}`)
    await new Promise(async (resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`Gateway handshake timeout\n${(stderr || stdout).slice(-4000)}`)), 120000)
      client = new GatewayClient({
        url: `ws://127.0.0.1:${port}`,
        token,
        clientName: 'gateway-client',
        clientDisplayName: 'Xiaoyu Runtime Smoke Test',
        clientVersion: '1.0.0',
        platform: 'win32',
        mode: 'backend',
        role: 'operator',
        scopes: ['operator.read', 'operator.write', 'operator.approvals', 'operator.questions'],
        minProtocol: OPENCLAW_WIRE_VERSION,
        maxProtocol: OPENCLAW_WIRE_VERSION,
        deviceIdentity,
        env,
        onHelloOk: async () => {
          try {
            const health = await client.request('health', {})
            const skills = await client.request('skills.status', {})
            console.log(JSON.stringify({ ok: true, protocol: PROTOCOL_VERSION, health: Boolean(health), skills: Boolean(skills) }))
            clearTimeout(timer)
            await client.stopAndWait({ timeoutMs: 1500 })
            resolve()
          } catch (error) {
            clearTimeout(timer)
            reject(error)
          }
        },
        onConnectError: (error) => { stderr += `\n${error.message}` },
        hostDeps: { signDevicePayload, publicKeyRawBase64UrlFromPem },
      })
      await startGatewayClientWhenEventLoopReady(client, { timeoutMs: 5000 })
    })
  } finally {
    if (client) {
      try { await client.stopAndWait({ timeoutMs: 1500 }) } catch (_) {}
    }
    if (child.exitCode === null && child.signalCode === null) {
      child.kill()
      await new Promise((resolve) => child.once('exit', resolve))
    }
    fs.rmSync(temporary, { recursive: true, force: true })
  }
}

main().catch((error) => {
  if (error.stdout) console.error(String(error.stdout).trim())
  if (error.stderr) console.error(String(error.stderr).trim())
  console.error(error.stack || error.message)
  process.exit(1)
})
