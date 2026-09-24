const fs = require('fs')
const path = require('path')
const ts = require('typescript')

const root = path.resolve(__dirname, '..')
const sourceRoot = path.join(root, 'src')
const localeRoot = path.join(sourceRoot, 'locales')
const catalogKeys = new Set()
const sourceCopyKeys = new Set()
const invalidPlaceholders = []
for (const name of fs.readdirSync(localeRoot)) {
  if (!name.endsWith('.ts')) continue
  const catalogSource = fs.readFileSync(path.join(localeRoot, name), 'utf8')
  for (const match of catalogSource.matchAll(/^\s*'([a-z][A-Za-z0-9.-]+)':/gm)) catalogKeys.add(match[1])
}
for (const [file, declaration] of [
  [path.join(sourceRoot, 'lib', 'i18n.tsx'), 'legacyEnUS'],
  [path.join(localeRoot, 'autoUi.ts'), 'autoUiEnUS'],
]) {
  const source = fs.readFileSync(file, 'utf8')
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const walk = (node) => {
    if (ts.isVariableDeclaration(node) && node.name.getText(ast) === declaration && node.initializer && ts.isObjectLiteralExpression(node.initializer)) {
      for (const property of node.initializer.properties) {
        if (ts.isPropertyAssignment(property) && (ts.isStringLiteral(property.name) || ts.isIdentifier(property.name))) {
          sourceCopyKeys.add(property.name.text)
          if (ts.isStringLiteral(property.initializer)) {
            const placeholders = (value) => [...new Set([...value.matchAll(/\{([A-Za-z][A-Za-z0-9_]*)\}/g)].map((match) => match[1]))].sort().join(',')
            if (placeholders(property.name.text) !== placeholders(property.initializer.text)) {
              invalidPlaceholders.push(`${path.relative(root, file)}: ${property.name.text}`)
            }
          }
        }
      }
    }
    ts.forEachChild(node, walk)
  }
  walk(ast)
}
const missing = []
const missingSourceCopy = []
const hardcoded = []
const translatedAttributes = new Set(['placeholder', 'title', 'aria-label', 'alt', 'label'])

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
    const sourceFile = ts.createSourceFile(fullPath, source, ts.ScriptTarget.Latest, true, entry.name.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
    {
      const inspect = (node) => {
        if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && ['t', 'translateCurrent'].includes(node.expression.text)) {
          const key = node.arguments[0]
          if (key && ts.isStringLiteral(key) && /[\u3400-\u9fff]/.test(key.text) && !sourceCopyKeys.has(key.text)) {
            const line = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
            missingSourceCopy.push(`${path.relative(root, fullPath)}:${line} ${key.text}`)
          }
        }
        if (!entry.name.endsWith('.tsx')) {
          ts.forEachChild(node, inspect)
          return
        }
        let value = ''
        if (ts.isJsxText(node)) value = node.text.trim()
        if (
          ts.isJsxAttribute(node) &&
          translatedAttributes.has(String(node.name.text)) &&
          node.initializer &&
          ts.isStringLiteral(node.initializer)
        ) value = node.initializer.text.trim()
        if (value && /[\u3400-\u9fff]/.test(value)) {
          const line = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
          hardcoded.push(`${path.relative(root, fullPath)}:${line} ${value.replace(/\s+/g, ' ')}`)
        }
        ts.forEachChild(node, inspect)
      }
      inspect(sourceFile)
    }
  }
}

visit(sourceRoot)
if (missing.length) {
  console.error(`Missing i18n keys:\n${missing.join('\n')}`)
  process.exit(1)
}
if (missingSourceCopy.length) {
  console.error(`Missing English source-copy translations:\n${missingSourceCopy.join('\n')}`)
  process.exit(1)
}
if (invalidPlaceholders.length) {
  console.error(`Mismatched i18n placeholders:\n${invalidPlaceholders.join('\n')}`)
  process.exit(1)
}
if (hardcoded.length) {
  console.error(`Hard-coded Chinese UI copy must use i18n:\n${hardcoded.join('\n')}`)
  process.exit(1)
}
console.log(`i18n catalog check passed (${catalogKeys.size} semantic keys, ${sourceCopyKeys.size} source-copy keys).`)
