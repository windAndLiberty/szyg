#!/bin/bash
# szyg 一键启动脚本
set -e
cd "$(dirname "$0")"

echo "=== szyg 智能矩阵运营系统 ==="

# Backend
echo "[1/2] Starting backend on :8000..."
PYTHONPATH=server python3 -m uvicorn szyg.api.app:create_app --host 0.0.0.0 --port 8000 --factory --reload &
BACKEND_PID=$!

# Frontend
echo "[2/2] Starting frontend on :5173..."
cd web && npx vite --host 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000/docs"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
