const path = require('path')
const base = require('./package.json').build

const productName = '数字员工'
const icon = '../assets/szyg.ico'

module.exports = {
  ...base,
  // Reuse the Electron runtime installed by npm. This keeps offline/restricted
  // network builds from attempting to download the same Electron version.
  electronDist: path.join(__dirname, 'node_modules', 'electron', 'dist'),
  appId: 'com.szyg.app',
  productName,
  files: [...base.files, 'product.js'],
  extraResources: [...base.extraResources, { from: 'runtime/product.json', to: 'product.json' }],
  win: {
    ...base.win,
    icon,
    executableName: '数字员工',
  },
  nsis: {
    ...base.nsis,
    // Close the currently installed edition before the standard update logic
    // begins. This also handles older releases which used to hide to tray on
    // window close and therefore stayed running during an upgrade.
    include: 'build/private-installer.nsh',
    shortcutName: productName,
    installerIcon: icon,
    uninstallerIcon: icon,
    installerHeaderIcon: icon,
    uninstallDisplayName: `${productName} ${'${version}'}`,
    artifactName: `${productName}-${'${version}'}-Windows-${'${arch}'}-安装包.${'${ext}'}`,
  },
  artifactName: `${productName}-${'${version}'}-Windows-${'${arch}'}.${'${ext}'}`,
}
