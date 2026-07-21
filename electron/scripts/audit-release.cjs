const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')

const electronDir = path.resolve(__dirname, '..')
const repoRoot = path.resolve(electronDir, '..')
const mode = process.argv[2] || 'source'

const forbiddenPaths = [
  /(^|[\\/])\.env(?:\.|$)/i,
  /(^|[\\/])secrets?(?:\.|[\\/])/i,
  /(^|[\\/])data[\\/](?:sessions|browser_profiles|cloud|audit)(?:[\\/]|$)/i,
  /(^|[\\/])(?:profiles?|browser_profiles|audit|logs?)(?:[\\/]|$)/i,
  /(^|[\\/])accounts\.ini$/i,
  /(^|[\\/])storage_state[^\\/]*\.json$/i,
  /(^|[\\/])[^\\/]*cookie[^\\/]*\.(?:json|txt|ini|db)$/i,
  /(^|[\\/])(?:channel_accounts|publishing_profiles|media_storage|wechat_desktop_calibration)\.json$/i,
  /\.(?:key|pfx|p12)$/i,
]

const secretPatterns = [
  { name: 'private key', regex: /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=\r\n]{64,}-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/ },
  { name: 'Volcengine access key', regex: /\bAKLT[A-Za-z0-9]{12,}\b/ },
  { name: 'cloud refresh token', regex: /["']refresh_token["']\s*:\s*["'][A-Za-z0-9._~-]{24,}["']/i },
  { name: 'serialized browser cookies', regex: /["']cookies?["']\s*:\s*(?:\[[^\]]+\]|["'](?!changeme)[^"']{20,}["'])/i },
  { name: 'developer machine path', regex: /(?:C:\\Users\\Administrator|D:\\szyg)/i },
]

const textExtensions = new Set([
  '.json', '.yaml', '.yml', '.ini', '.toml', '.txt', '.conf', '.cfg',
  '.py', '.js', '.cjs', '.mjs', '.ts', '.tsx', '.jsx', '.html', '.md',
])
const failures = []

function walk(root, visit) {
  if (!fs.existsSync(root)) return
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const full = path.join(root, entry.name)
    if (entry.isDirectory()) walk(full, visit)
    else if (entry.isFile()) visit(full)
  }
}

function inspectFile(file, displayRoot) {
  const relative = path.relative(displayRoot, file).replaceAll('\\', '/')
  for (const rule of forbiddenPaths) {
    if (rule.test(relative)) failures.push(`${relative}: forbidden release path`)
  }
  if (!textExtensions.has(path.extname(file).toLowerCase())) return
  const stat = fs.statSync(file)
  if (stat.size > 5 * 1024 * 1024) return
  const content = fs.readFileSync(file, 'utf8')
  for (const pattern of secretPatterns) {
    if (pattern.regex.test(content)) failures.push(`${relative}: contains ${pattern.name}`)
  }
}

function auditSource() {
  const forbiddenSourceRoots = [
    path.join(repoRoot, '.env'),
    path.join(repoRoot, 'secrets.yaml'),
    path.join(repoRoot, 'data'),
    path.join(repoRoot, 'server', 'data'),
  ]
  for (const item of forbiddenSourceRoots) {
    if (fs.existsSync(item)) {
      const relative = path.relative(repoRoot, item).replaceAll('\\', '/')
      console.log(`Excluded local-only source: ${relative}`)
    }
  }
  inspectFile(path.join(repoRoot, 'config.yaml'), repoRoot)
  const packageConfig = JSON.parse(fs.readFileSync(path.join(electronDir, 'package.json'), 'utf8'))
  const resources = JSON.stringify(packageConfig.build?.extraResources || [])
  for (const required of ['runtime/backend/szyg-backend', '../szyg-frontend/dist']) {
    if (!resources.includes(required)) failures.push(`package.json: missing required runtime resource ${required}`)
  }
  if (/"from":"\.\.\/server"(?:,|})/.test(resources)) {
    failures.push('package.json: raw server source copy is forbidden')
  }
}

function auditDist() {
  const unpacked = path.join(electronDir, 'dist', 'win-unpacked')
  if (fs.existsSync(unpacked)) {
    walk(unpacked, (file) => {
      const extension = path.extname(file).toLowerCase()
      const relative = path.relative(unpacked, file).replaceAll('\\', '/')
      const proprietaryPython = /(?:^|\/)(?:server|szyg)(?:\/|$)/i.test(relative)
      if ((extension === '.py' || extension === '.pyc') && proprietaryPython) {
        failures.push(`${path.relative(unpacked, file)}: source/debug artifact is forbidden`)
      }
      if (extension === '.map') failures.push(`${relative}: source map is forbidden`)
      inspectFile(file, unpacked)
    })
  }
  const asarPath = path.join(unpacked, 'resources', 'app.asar')
  if (fs.existsSync(asarPath)) {
    const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'szyg-asar-audit-'))
    try {
      require('@electron/asar').extractAll(asarPath, temp)
      walk(temp, (file) => inspectFile(file, temp))
    } finally {
      fs.rmSync(temp, { recursive: true, force: true })
    }
  }

  const portable = fs.readdirSync(path.join(electronDir, 'dist'))
    .filter((name) => name.toLowerCase().endsWith('.exe'))
    .map((name) => path.join(electronDir, 'dist', name))
    .sort((left, right) => fs.statSync(right).size - fs.statSync(left).size)[0]
  if (!fs.existsSync(unpacked) && !portable) {
    failures.push('no unpacked or portable release output was found')
  }
  if (portable) {
    const sevenZip = path.join(electronDir, 'node_modules', '7zip-bin', 'win', 'x64', '7za.exe')
    const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'szyg-portable-audit-'))
    try {
      const extracted = spawnSync(sevenZip, ['x', '-y', `-o${temp}`, portable], {
        encoding: 'utf8',
        windowsHide: true,
      })
      if (extracted.status !== 0) {
        failures.push(`unable to inspect portable executable: ${path.basename(portable)}`)
      } else {
        walk(temp, (file) => inspectFile(file, temp))
      }
    } finally {
      fs.rmSync(temp, { recursive: true, force: true })
    }
  }
}

if (mode === 'source') auditSource()
else if (mode === 'dist') auditDist()
else failures.push(`unknown audit mode: ${mode}`)

if (failures.length) {
  console.error('\nRelease privacy audit failed:')
  for (const failure of [...new Set(failures)]) console.error(`- ${failure}`)
  process.exit(1)
}

console.log(`Release privacy audit passed (${mode}).`)
