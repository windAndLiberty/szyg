const fs = require('fs')

const cert = process.env.CSC_LINK || ''
const password = process.env.CSC_KEY_PASSWORD || ''

if (!cert || !password) {
  console.error('Release signing is required. Set CSC_LINK and CSC_KEY_PASSWORD.')
  process.exit(1)
}

if (!/^https?:\/\//i.test(cert) && !cert.startsWith('base64:') && !fs.existsSync(cert)) {
  console.error(`CSC_LINK does not exist: ${cert}`)
  process.exit(1)
}

console.log('Windows code-signing configuration is present.')
