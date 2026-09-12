const crypto = require('crypto')
const fs = require('fs')
const path = require('path')

const electronDir = path.resolve(__dirname, '..')
const backendDir = process.env.SZYG_BACKEND_RUNTIME_DIR || path.join(electronDir, 'runtime', 'backend', 'szyg-backend')
const files = [
  {
    source: path.join(backendDir, 'szyg-backend.exe'),
    target: 'backend/szyg-backend.exe',
  },
  {
    source: path.join(backendDir, 'sau-cli.exe'),
    target: 'backend/sau-cli.exe',
  },
  {
    source: path.join(backendDir, '_internal', 'third_party', 'ffmpeg', 'ffmpeg.exe'),
    target: 'backend/_internal/third_party/ffmpeg/ffmpeg.exe',
  },
  {
    source: path.join(backendDir, '_internal', 'third_party', 'ffmpeg', 'ffprobe.exe'),
    target: 'backend/_internal/third_party/ffmpeg/ffprobe.exe',
  },
  {
    source: path.join(electronDir, 'runtime', 'hermes', 'hermes-runtime', 'hermes-runtime.exe'),
    target: 'runtime/hermes/hermes-runtime.exe',
  },
  {
    source: path.join(electronDir, 'providers', 'cua', 'cua-driver.exe'),
    target: 'runtime/cua/cua-driver.exe',
  },
  {
    source: path.join(electronDir, 'providers', 'cua', 'cua-driver-uia.exe'),
    target: 'runtime/cua/cua-driver-uia.exe',
  },
  {
    source: path.join(electronDir, 'providers', 'cua', 'cua_driver_sdk.dll'),
    target: 'runtime/cua/cua_driver_sdk.dll',
  },
  {
    source: path.join(electronDir, 'providers', 'cua', 'cua-cursor-theme.exe'),
    target: 'runtime/cua/cua-cursor-theme.exe',
  },
  {
    source: path.join(electronDir, 'providers', 'cua', 'manifest.json'),
    target: 'runtime/cua/manifest.json',
  },
  {
    source: path.join(electronDir, '..', 'server', 'vendor', 'hermes-agent.lock.json'),
    target: 'runtime/hermes/upstream.lock.json',
  },
  {
    source: process.env.SZYG_RELEASE_CONFIG || path.join(electronDir, 'runtime', 'config.yaml'),
    target: 'config.yaml',
  },
]

function digest(file) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256')
    const stream = fs.createReadStream(file)
    stream.on('error', reject)
    stream.on('data', (chunk) => hash.update(chunk))
    stream.on('end', () => resolve(hash.digest('hex')))
  })
}

async function main() {
  const entries = []
  const packagedResources = process.env.SZYG_PACKAGED_RESOURCES_DIR
  for (const item of files) {
    const { target } = item
    const source = packagedResources ? path.join(packagedResources, target) : item.source
    if (!fs.existsSync(source)) throw new Error(`Runtime file is missing: ${source}`)
    entries.push({
      path: target,
      sha256: await digest(source),
      size: fs.statSync(source).size,
    })
  }

  const output = process.env.SZYG_RUNTIME_MANIFEST || (packagedResources ? path.join(packagedResources, 'runtime-integrity.json') : path.join(electronDir, 'runtime', 'runtime-integrity.json'))
  fs.writeFileSync(output, `${JSON.stringify({ algorithm: 'sha256', entries }, null, 2)}\n`)
  console.log(`Runtime integrity manifest ready: ${output}`)
}

main().catch((error) => {
  console.error(error.message)
  process.exit(1)
})
