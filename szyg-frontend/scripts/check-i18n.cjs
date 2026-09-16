const fs = require('fs')
const path = require('path')

const root = path.resolve(__dirname, '..')
const sourceRoot = path.join(root, 'src')
const localeRoot = path.join(sourceRoot, 'locales')
const catalogKeys = new Set()
for (const name of fs.readdirSync(localeRoot)) {
  if (!name.endsWith('.ts')) continue
  const catalogSource = fs.readFileSync(path.join(localeRoot, name), 'utf8')
  for (const match of catalogSource.matchAll(/^\s*'([a-z][A-Za-z0-9.-]+)':/gm)) catalogKeys.add(match[1])
}
const missing = []

function visit(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name)
    if (entry.isDirectory()) {
      visit(fullPath)
      continue
    }
    if (!/\.(ts|tsx)$/.test(entry.name) || fullPath.startsWith(localeRoot)) continue
    const source = fs.readFileSync(fullPath, 'utf8')
    for (const match of source.matchAll(/\bt\(\s*['"]([a-z][A-Za-z0-9.-]+)['"]/g)) {
      if (!catalogKeys.has(match[1])) {
        const line = source.slice(0, match.index).split(/\r?\n/).length
        missing.push(`${path.relative(root, fullPath)}:${line} ${match[1]}`)
      }
    }
  }
}

visit(sourceRoot)
if (missing.length) {
  console.error(`Missing i18n keys:\n${missing.join('\n')}`)
  process.exit(1)
}
console.log(`i18n catalog check passed (${catalogKeys.size} semantic keys).`)
