const base = require('./package.json').build

const edition = process.env.SZYG_PRODUCT_EDITION || 'private'
const publicEdition = edition === 'public'
const productName = publicEdition ? '小妤AI' : '数字员工'
const icon = publicEdition ? '../assets/xiaoyu.ico' : '../assets/szyg.ico'

module.exports = {
  ...base,
  appId: publicEdition ? 'com.yusetech.xiaoyuai' : 'com.szyg.app',
  productName,
  files: [...base.files, 'product.js'],
  extraResources: [...base.extraResources, { from: 'runtime/product.json', to: 'product.json' }],
  win: {
    ...base.win,
    icon,
    executableName: publicEdition ? 'XiaoyuAI' : '数字员工',
  },
  nsis: {
    ...base.nsis,
    shortcutName: productName,
    installerIcon: icon,
    uninstallerIcon: icon,
    installerHeaderIcon: icon,
    uninstallDisplayName: `${productName} ${'${version}'}`,
    artifactName: `${productName}-${'${version}'}-Windows-${'${arch}'}-安装包.${'${ext}'}`,
  },
  artifactName: `${productName}-${'${version}'}-Windows-${'${arch}'}.${'${ext}'}`,
}
