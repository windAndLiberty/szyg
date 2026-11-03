const fs = require('fs')
const path = require('path')

class CredentialStore {
  constructor({ safeStorage, rootDir }) {
    this.safeStorage = safeStorage
    this.filePath = path.join(rootDir, 'credentials.bin')
  }

  load() {
    if (!fs.existsSync(this.filePath)) return {}
    try {
      const stored = fs.readFileSync(this.filePath)
      if (!this.safeStorage?.isEncryptionAvailable()) return {}
      return JSON.parse(this.safeStorage.decryptString(stored))
    } catch (_) {
      return {}
    }
  }

  save(value) {
    if (!this.safeStorage?.isEncryptionAvailable()) {
      throw new Error('Windows credential encryption is unavailable')
    }
    fs.mkdirSync(path.dirname(this.filePath), { recursive: true })
    const encrypted = this.safeStorage.encryptString(JSON.stringify(value))
    const temporary = `${this.filePath}.${process.pid}.tmp`
    fs.writeFileSync(temporary, encrypted)
    fs.renameSync(temporary, this.filePath)
  }

  getOrCreate(name, factory) {
    const credentials = this.load()
    if (credentials[name] !== undefined && credentials[name] !== null) return credentials[name]
    credentials[name] = factory()
    this.save(credentials)
    return credentials[name]
  }

  get(name) {
    return this.load()[name]
  }

  set(name, value) {
    const credentials = this.load()
    credentials[name] = value
    this.save(credentials)
  }

  delete(name) {
    const credentials = this.load()
    delete credentials[name]
    this.save(credentials)
  }
}

module.exports = { CredentialStore }
