#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[electron] Setting up..."

# Force clean install if binary missing
if [ ! -f "node_modules/electron/dist/electron" ]; then
  echo "[electron] Electron binary not found, reinstalling..."
  rm -rf node_modules pnpm-lock.yaml
  pnpm install --force 2>&1 | tail -3
fi

# Verify binary
if [ ! -f "node_modules/electron/dist/electron" ]; then
  echo "[electron] ❌ Electron binary still missing after install."
  echo "  Try manually: cd electron && rm -rf node_modules && pnpm install"
  exit 1
fi

# Check services
curl -s http://localhost:8000/api/health > /dev/null 2>&1 || {
  echo "[electron] ⚠️  Backend not on :8000 — run ./start.sh first"
  exit 1
}
curl -s http://localhost:5173 > /dev/null 2>&1 || {
  echo "[electron] ⚠️  Frontend not on :5173 — run ./start.sh first"
  exit 1
}

echo "[electron] Launching..."
NODE_ENV=development pnpm exec electron . --no-sandbox
