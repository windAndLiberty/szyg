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
  /(^|[\\/])cloud[\\/]session\.json$/i,
  /(^|[\\/])cloud[\\/]auth\.db$/i,
  /(^|[\\/])storage_state[^\\/]*\.json$/i,
  /(^|[\\/])[^\\/]*cookie[^\\/]*\.(?:json|txt|ini|db)$/i,
  /(^|[\\/])(?:channel_accounts|publishing_profiles|media_storage|wechat_desktop_calibration)\.json$/i,
  /\.(?:key|pfx|p12)$/i,
]

const forbiddenReleaseRoots = [
  /^data(?:[\\/]|$)/i,
  /^resources[\\/]data(?:[\\/]|$)/i,
]

// This upstream Bilibili API fixture is reference metadata, not a browser
// credential. Every other session.json path is prohibited in a release.
const allowedStaticSessionFiles = new Set([
  'resources/backend/_internal/bilibili_api/data/api/session.json',
])

const secretPatterns = [
  { name: 'private key', regex: /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=\r\n]{64,}-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/ },
  { name: 'Volcengine access key', regex: /\bAKLT[A-Za-z0-9]{12,}\b/ },
  { name: 'cloud refresh token', regex: /["']refresh_token["']\s*:\s*["'][A-Za-z0-9._~-]{24,}["']/i },
  { name: 'serialized browser cookies', regex: /["']cookies?["']\s*:\s*(?:\[[^\]]+\]|["'](?!changeme)[^"']{20,}["'])/i },
  { name: 'developer machine path', regex: /(?:C:\\Users\\Administrator|D:\\szyg)/i },
]

const requiredRuntimeEntries = [
  'resources/backend/_internal/third_party/ffmpeg/ffprobe.exe',
  'resources/runtime/hermes/hermes-runtime.exe',
  'resources/runtime/hermes/upstream.lock.json',
  'resources/runtime/hermes/_internal/vendor/hermes_agent/LICENSE',
  'resources/runtime/cua/cua-driver.exe',
  'resources/runtime/cua/cua-driver-uia.exe',
  'resources/runtime/cua/cua_driver_sdk.dll',
  'resources/runtime/cua/cua-cursor-theme.exe',
  'resources/runtime/cua/manifest.json',
  'resources/runtime/cua/LICENSE.md',
  'resources/THIRD_PARTY_NOTICES.md',
  'resources/backend/_internal/third_party_licenses/wxauto/LICENSE',
  'resources/backend/_internal/third_party_licenses/social-auto-upload/UPSTREAM_README.md',
  'resources/backend/_internal/szyg/resources/social_auto_upload/stealth.min.js',
  'resources/backend/sau-cli.exe',
  'resources/runtime-integrity.json',
]

const obsoleteRuntimeRoots = [
  'resources/runtime/terminator/',
  'resources/runtime/omniparser/',
]

function validateRuntimeEntries(entries) {
  const normalized = new Set(entries.map((entry) => entry.replaceAll('\\', '/')))
  for (const required of requiredRuntimeEntries) {
    if (!normalized.has(required)) failures.push(`${required}: required external runtime file is missing`)
  }
  for (const obsolete of obsoleteRuntimeRoots) {
    if ([...normalized].some((entry) => entry.startsWith(obsolete))) {
      failures.push(`${obsolete}: obsolete computer-use runtime must not be distributed`)
    }
  }
}

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
  inspectReleasePath(relative)
  if (!textExtensions.has(path.extname(file).toLowerCase())) return
  const stat = fs.statSync(file)
  if (stat.size > 5 * 1024 * 1024) return
  const content = fs.readFileSync(file, 'utf8')
  for (const pattern of secretPatterns) {
    if (pattern.regex.test(content)) failures.push(`${relative}: contains ${pattern.name}`)
  }
}

function inspectReleasePath(releasePath) {
  const relative = releasePath.replaceAll('\\', '/').replace(/^\.\//, '')
  if (/session\.json$/i.test(relative) && !allowedStaticSessionFiles.has(relative)) {
    failures.push(`${relative}: session data is forbidden in a release`)
  }
  for (const rule of forbiddenReleaseRoots) {
    if (rule.test(relative)) failures.push(`${relative}: user data root is forbidden`)
  }
  for (const rule of forbiddenPaths) {
    if (rule.test(relative)) failures.push(`${relative}: forbidden release path`)
  }
}

function inspectArchive(archive, sevenZip) {
  const listed = spawnSync(sevenZip, ['l', '-slt', archive], {
    encoding: 'utf8',
    windowsHide: true,
    maxBuffer: 64 * 1024 * 1024,
  })
  if (listed.status !== 0) {
    failures.push(`unable to list release archive: ${path.basename(archive)}`)
    return
  }
  const archivePath = path.resolve(archive).replaceAll('\\', '/')
  const entries = []
  for (const line of listed.stdout.split(/\r?\n/)) {
    if (!line.startsWith('Path = ')) continue
    const entry = line.slice(7).trim().replaceAll('\\', '/')
    if (entry && entry !== archivePath) {
      entries.push(entry)
      inspectReleasePath(entry)
    }
  }

  const agencyRoot = 'resources/backend/_internal/szyg/resources/agency_agents/'
  const agencyMarkdown = entries.filter(
    (entry) => entry.startsWith(agencyRoot) && entry.toLowerCase().endsWith('.md'),
  )
  for (const required of [`${agencyRoot}divisions.json`, `${agencyRoot}LICENSE`]) {
    if (!entries.includes(required)) failures.push(`${required}: required marketplace resource is missing`)
  }
  if (agencyMarkdown.length < 155) {
    failures.push(`${agencyRoot}: expected at least 155 expert definitions, found ${agencyMarkdown.length}`)
  }

  validateRuntimeEntries(entries)

  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'szyg-archive-audit-'))
  try {
    const extracted = spawnSync(sevenZip, [
      'x', '-y', `-o${temp}`, archive, 'resources/app.asar', 'resources/config.yaml',
    ], { encoding: 'utf8', windowsHide: true })
    if (extracted.status !== 0) {
      failures.push(`unable to inspect protected release files: ${path.basename(archive)}`)
      return
    }
    const configPath = path.join(temp, 'resources', 'config.yaml')
    if (fs.existsSync(configPath)) inspectFile(configPath, temp)
    const asarPath = path.join(temp, 'resources', 'app.asar')
    if (fs.existsSync(asarPath)) {
      const asarTemp = fs.mkdtempSync(path.join(os.tmpdir(), 'szyg-asar-audit-'))
      try {
        require('@electron/asar').extractAll(asarPath, asarTemp)
        walk(asarTemp, (file) => inspectFile(file, asarTemp))
      } finally {
        fs.rmSync(asarTemp, { recursive: true, force: true })
      }
    }
  } finally {
    fs.rmSync(temp, { recursive: true, force: true })
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
  for (const required of [
    'runtime/backend/szyg-backend',
    '../szyg-frontend/dist',
    'runtime/hermes/hermes-runtime',
    '../server/vendor/hermes-agent.lock.json',
    'providers/cua',
    'runtime/runtime-integrity.json',
    'THIRD_PARTY_NOTICES.md',
  ]) {
    if (!resources.includes(required)) failures.push(`package.json: missing required runtime resource ${required}`)
  }
  if (/terminator|omniparser/i.test(resources)) {
    failures.push('package.json: obsolete Terminator or OmniParser runtime is forbidden')
  }
  if (/"from":"\.\.\/server"(?:,|})/.test(resources)) {
    failures.push('package.json: raw server source copy is forbidden')
  }
}

function auditDist() {
  const distDir = process.env.SZYG_RELEASE_DIST_DIR ? path.resolve(process.env.SZYG_RELEASE_DIST_DIR) : path.join(electronDir, 'dist')
  const unpacked = path.join(distDir, 'win-unpacked')
  const packageConfig = JSON.parse(fs.readFileSync(path.join(electronDir, 'package.json'), 'utf8'))
  const currentVersion = String(packageConfig.version || '')
  if (fs.existsSync(unpacked)) {
    const unpackedEntries = []
    walk(unpacked, (file) => {
      const extension = path.extname(file).toLowerCase()
      const relative = path.relative(unpacked, file).replaceAll('\\', '/')
      unpackedEntries.push(relative)
      const proprietaryPython = /^resources\/backend\/_internal\/(?:server|szyg)(?:\/|$)/i.test(relative)
      if ((extension === '.py' || extension === '.pyc') && proprietaryPython) {
        failures.push(`${path.relative(unpacked, file)}: source/debug artifact is forbidden`)
      }
      if (extension === '.map') failures.push(`${relative}: source map is forbidden`)
      inspectFile(file, unpacked)
    })
    validateRuntimeEntries(unpackedEntries)
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

  const outputs = fs.existsSync(distDir) ? fs.readdirSync(distDir) : []
  const portable = outputs
    .filter((name) => name.toLowerCase().endsWith('.exe') && name.includes(`-${currentVersion}-`))
    .map((name) => path.join(distDir, name))
    .sort((left, right) => fs.statSync(right).size - fs.statSync(left).size)[0]
  const archives = outputs
    .filter((name) => name.toLowerCase().endsWith('.zip') && name.includes(`-${currentVersion}-`))
    .map((name) => path.join(distDir, name))
  if (!fs.existsSync(unpacked) && !portable && archives.length === 0) {
    failures.push('no unpacked, portable, or zip release output was found')
  }
  const sevenZip = path.join(electronDir, 'node_modules', '7zip-bin', 'win', 'x64', '7za.exe')
  for (const archive of archives) inspectArchive(archive, sevenZip)
  if (portable) {
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
