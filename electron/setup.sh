#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[setup] Cleaning..."
rm -rf node_modules pnpm-lock.yaml

# Configure .npmrc for electron binary download
cat > .npmrc << 'EOF'
electron_mirror=https://registry.npmmirror.com/-/binary/electron/
electron_builder_binaries_mirror=https://registry.npmmirror.com/-/binary/
EOF

echo "[setup] .npmrc configured:"
cat .npmrc

echo "[setup] Installing..."
pnpm install

if [ -f "node_modules/electron/dist/electron" ]; then
  echo "✅ Electron installed!"
  ls -lh node_modules/electron/dist/electron
  rm -f .npmrc
else
  echo "❌ Still missing — trying with explicit env vars..."
  export ELECTRON_MIRROR="https://registry.npmmirror.com/-/binary/electron/"
  npx electron --version 2>/dev/null || true
  # Last resort: manual install script
  cd node_modules/electron
  node install.js
  cd ../..
  ls node_modules/electron/dist/electron && echo "✅ OK" || echo "❌ FAILED"
fi
