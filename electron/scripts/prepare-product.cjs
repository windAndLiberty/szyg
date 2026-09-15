const fs = require('fs')
const path = require('path')

const edition = process.env.SZYG_PRODUCT_EDITION || 'private'
if (!['private', 'public'].includes(edition)) {
  throw new Error(`Unsupported SZYG_PRODUCT_EDITION: ${edition}`)
}

const runtimeDir = path.resolve(__dirname, '..', 'runtime')
fs.mkdirSync(runtimeDir, { recursive: true })
fs.writeFileSync(path.join(runtimeDir, 'product.json'), `${JSON.stringify({ edition }, null, 2)}\n`)
console.log(`Prepared ${edition} product profile.`)
