#!/usr/bin/env bash
# szyg desktop development launcher
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$ROOT/szyg-frontend"
ELECTRON_DIR="$ROOT/electron"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Python environment is missing. Run: uv sync --extra dev --python 3.12" >&2
  exit 1
fi
if [[ ! -x "$ELECTRON_DIR/node_modules/electron/dist/electron" ]]; then
  echo "Electron runtime is missing. Run: npm --prefix electron ci" >&2
  exit 1
fi
if curl --noproxy '*' --silent --max-time 1 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  echo "Port 8000 is already in use by a running desktop or standalone backend." >&2
  echo "Close it first so the new Electron process can inject its browser-control service." >&2
  exit 1
fi

export NODE_ENV=development
export PATH="$ROOT/.venv/bin:$PATH"

frontend_pid=""
cleanup() {
  if [[ -n "$frontend_pid" ]]; then
    kill "$frontend_pid" 2>/dev/null || true
    wait "$frontend_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

(
  cd "$FRONTEND_DIR"
  exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort
) &
frontend_pid=$!

for _ in $(seq 1 30); do
  if curl --noproxy '*' --fail --silent --max-time 1 http://127.0.0.1:5173/ >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$frontend_pid" 2>/dev/null; then
    wait "$frontend_pid"
  fi
  sleep 1
done

if ! curl --noproxy '*' --fail --silent --max-time 1 http://127.0.0.1:5173/ >/dev/null 2>&1; then
  echo "Vite did not become ready on port 5173." >&2
  exit 1
fi

cd "$ELECTRON_DIR"
electron_args=(
  "--remote-debugging-port=9222"
  "--remote-allow-origins=*"
)

if [[ "$(uname -s)" == "Linux" ]]; then
  sandbox_helper="$ELECTRON_DIR/node_modules/electron/dist/chrome-sandbox"
  if [[ ! -u "$sandbox_helper" ]] || [[ "$(stat -c '%u' "$sandbox_helper")" != "0" ]]; then
    echo "Electron SUID sandbox is unavailable; using --no-sandbox for local development." >&2
    electron_args+=("--no-sandbox")
  fi
fi

npm start -- "${electron_args[@]}"
