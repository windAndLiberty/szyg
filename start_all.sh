#!/bin/bash
# szyg 全栈启动 — REST API + MCP Servers + Web Frontend
set -e
cd "$(dirname "$0")"
export PYTHONPATH=server

echo "╔══════════════════════════════════════════╗"
echo "║   szyg 智能矩阵运营系统                   ║"
echo "║   REST API + Hermes Agent + Web UI      ║"
echo "╚══════════════════════════════════════════╝"

# 1. REST API Backend (port 8000)
echo "[1] Starting REST API on :8000..."
python3 -m uvicorn szyg.api.app:create_app --host 0.0.0.0 --port 8000 --factory &
API_PID=$!

# 2. MCP Servers (launched by Hermes on-demand via hermes.yaml)
echo "[2] MCP Servers ready (6 servers, 30+ tools)"
echo "    - szyg-publisher   (12 tools)"
echo "    - szyg-scheduler   (9 tools)"
echo "    - szyg-tools       (5 tools)"
echo "    - szyg-knowledge   (3 tools)"
echo "    - szyg-agents      (4 tools)"
echo "    - szyg-oem         (2 tools)"

# 3. Hermes Agent (if installed)
if command -v hermes &> /dev/null; then
    echo "[3] Hermes Agent CLI available"
    echo "    Run: hermes"
else
    echo "[3] Hermes Agent embedded in server/ (CLI not in PATH)"
    echo "    Source: Nous Research hermes-agent v0.15.1"
fi

# 4. Web Frontend (Next.js dev)
echo "[4] Starting Web Frontend on :5173..."
cd web && npx next dev -p 5173 --host 0.0.0.0 &
WEB_PID=$!

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  REST API:   http://localhost:8000/docs"
echo "  MCP tools:  python3 server/szyg/mcp_servers/{name}_mcp.py"
echo "  Web UI:     http://localhost:5173"
echo "  Login:      admin / admin123"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

trap "kill $API_PID $WEB_PID 2>/dev/null; exit" INT TERM
wait
