const fs = require('fs')
const path = require('path')

const root = path.resolve(__dirname, '..')
const sourceRoot = path.join(root, 'src')
const catalogSource = fs.readFileSync(path.join(sourceRoot, 'locales', 'core.ts'), 'utf8')
const catalogKeys = new Set([...catalogSource.matchAll(/^\s*'([a-z][A-Za-z0-9.-]+)':/gm)].map((match) => match[1]))
const missing = []

function visit(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name)
    if (entry.isDirectory()) {
      visit(fullPath)
      continue
    }
    if (!/\.(ts|tsx)$/.test(entry.name) || fullPath.endsWith(path.join('locales', 'core.ts'))) continue
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

