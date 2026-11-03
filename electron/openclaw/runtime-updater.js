const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const { atomicWriteJson, resolveRuntimeLayout, sha256FileSync } = require('./runtime-manager')

function copyDirectory(source, target) {
  fs.mkdirSync(target, { recursive: true })
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const from = path.join(source, entry.name)
    const to = path.join(target, entry.name)
    if (entry.isDirectory()) copyDirectory(from, to)
    else if (entry.isFile()) fs.copyFileSync(from, to)
  }
}

class OpenClawRuntimeUpdater {
  constructor({ dataDir, publicKeyPem = '' }) {
    this.root = path.join(dataDir, 'openclaw', 'runtime')
    this.versionsRoot = path.join(this.root, 'versions')
    this.backupsRoot = path.join(dataDir, 'openclaw', 'backups')
    this.activePath = path.join(this.root, 'active.json')
    this.publicKeyPem = publicKeyPem
  }

  verifySignedManifest(runtimeRoot) {
    const manifestPath = path.join(runtimeRoot, 'manifest.json')
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
    for (const item of manifest.files || []) {
      const target = path.resolve(runtimeRoot, String(item.path || ''))
      if (!target.startsWith(path.resolve(runtimeRoot) + path.sep)) throw new Error('Runtime manifest contains an invalid path')
      if (!fs.existsSync(target) || sha256FileSync(target) !== String(item.sha256 || '').toLowerCase()) {
        throw new Error(`Runtime integrity check failed: ${item.path}`)
      }
    }
    if (!manifest.signature) throw new Error('Runtime update is unsigned')
    if (!this.publicKeyPem) throw new Error('Runtime update signing key is not configured')
    const unsigned = { ...manifest }
    delete unsigned.signature
    const valid = crypto.verify(
      null,
      Buffer.from(JSON.stringify(unsigned)),
      this.publicKeyPem,
      Buffer.from(String(manifest.signature), 'base64'),
    )
    if (!valid) throw new Error('Runtime update signature is invalid')
    return manifest
  }

  stage(extractedRuntimeRoot) {
    const manifest = this.verifySignedManifest(extractedRuntimeRoot)
    const version = String(manifest.openclawVersion || '')
    if (!/^\d{4}\.\d{1,2}\.\d+$/.test(version)) throw new Error('Runtime version is invalid')
    const destination = path.resolve(this.versionsRoot, version)
    if (!destination.startsWith(path.resolve(this.versionsRoot) + path.sep)) throw new Error('Runtime destination is invalid')
    if (fs.existsSync(destination)) throw new Error(`Runtime ${version} is already staged`)
    copyDirectory(extractedRuntimeRoot, destination)
    if (!resolveRuntimeLayout(destination)) throw new Error('Staged runtime is not compatible with this Xiaoyu build')
    return { version, path: destination }
  }

  backupState(stateDir) {
    if (!fs.existsSync(stateDir)) return null
    const backup = path.join(this.backupsRoot, new Date().toISOString().replaceAll(':', '-'))
    copyDirectory(stateDir, backup)
    return backup
  }

  activate(staged, stateBackup = null) {
    const previous = (() => {
      try { return JSON.parse(fs.readFileSync(this.activePath, 'utf8')) } catch (_) { return null }
    })()
    atomicWriteJson(this.activePath, {
      version: staged.version,
      path: staged.path,
      previous,
      stateBackup,
      activatedAt: new Date().toISOString(),
    })
    return { active: staged, previous, stateBackup }
  }

  rollback() {
    const active = JSON.parse(fs.readFileSync(this.activePath, 'utf8'))
    if (!active.previous?.path) throw new Error('No previous runtime is available')
    atomicWriteJson(this.activePath, active.previous)
    return { active: active.previous, stateBackup: active.stateBackup || null }
  }
}

module.exports = { OpenClawRuntimeUpdater }
