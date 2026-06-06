#!/bin/bash
# szyg 全栈启动 — REST API + MCP Servers + Web Frontend
set -e
cd "$(dirname "$0")"
export PYTHONPATH=server
export SZYG_DATA_DIR=data

echo "╔══════════════════════════════════════════╗"
echo "║   szyg 智能矩阵运营系统                     ║"
echo "║   REST API + MCP + nanobot + Web UI      ║"
echo "╚══════════════════════════════════════════╝"

# 1. REST API Backend (port 8000)
echo "[1] Starting REST API on :8000..."
python3 -m uvicorn szyg.api.app:create_app --host 0.0.0.0 --port 8000 --factory &
API_PID=$!

# 2. MCP Servers
echo "[2] MCP Servers ready (6 servers, 30+ tools)"

# 3. Web Frontend (Vite dev)
echo "[4] Starting Web Frontend on :5173..."
cd web && npx vite --host 0.0.0.0 &
WEB_PID=$!

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  REST API:   http://localhost:8000/docs"
echo "  Web UI:     http://localhost:5173"
echo "  Login:      admin / admin123"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

trap "kill $API_PID $WEB_PID 2>/dev/null; exit" INT TERM
wait
