const { spawnSync } = require('child_process')
const path = require('path')

const edition = process.argv[2]
const target = process.argv[3] || 'nsis'
if (!['private', 'public'].includes(edition)) {
  throw new Error('Usage: node scripts/build-product.cjs <private|public> [nsis|dir]')
}
if (!['nsis', 'dir'].includes(target)) {
  throw new Error('Target must be nsis or dir')
}

const electronDir = path.resolve(__dirname, '..')
const env = { ...process.env, SZYG_PRODUCT_EDITION: edition, VITE_PRODUCT_EDITION: edition }
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm'
const run = (args) => {
  const result = spawnSync(npm, args, { cwd: electronDir, env, stdio: 'inherit' })
  if (result.status !== 0) process.exit(result.status || 1)
}

run(['run', 'audit:source'])
run(['run', 'build:runtime'])
const builder = process.platform === 'win32' ? 'npx.cmd' : 'npx'
const result = spawnSync(builder, ['electron-builder', '--win', target, '--config', 'electron-builder.config.cjs'], { cwd: electronDir, env, stdio: 'inherit' })
if (result.status !== 0) process.exit(result.status || 1)
run(['run', 'audit:dist'])
