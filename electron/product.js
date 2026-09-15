const fs = require('fs')
const path = require('path')

const profiles = {
  private: {
    id: 'szyg_private',
    name: '数字员工',
    userDataDirectory: 'szyg',
    appUserModelId: 'com.szyg.app',
    icon: 'private/app-icon.png',
    trayIcon: 'private/tray-icon.png',
  },
  public: {
    id: 'xiaoyu_public',
    name: '小妤AI',
    userDataDirectory: 'xiaoyu-digital-employee',
    appUserModelId: 'YuSeTech.AI',
    icon: 'public/app-icon.png',
    trayIcon: 'public/tray-icon.png',
  },
}

function readEditionFile() {
  try {
    const file = path.join(process.resourcesPath, 'product.json')
    return JSON.parse(fs.readFileSync(file, 'utf8')).edition
  } catch {
    return undefined
  }
}

const edition = process.env.SZYG_PRODUCT_EDITION || readEditionFile() || 'private'
module.exports = profiles[edition] || profiles.private
