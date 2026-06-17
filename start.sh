#!/bin/bash
# szyg 一键启动脚本
set -e
cd "$(dirname "$0")"

echo "=== szyg 智能矩阵运营系统 ==="

# Backend
echo "[1/2] Starting backend on :8000..."
PYTHONPATH=server python3 -m uvicorn szyg.api.app:create_app --host 127.0.0.1 --port 8000 --factory --reload &
BACKEND_PID=$!

# Frontend (Next.js — must run from web/ directory)
echo "[2/2] Starting frontend on :5173..."
(cd web && pnpm next dev -p 5173) &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000/docs"
echo "Frontend: http://localhost:5173"
echo "Login:    admin / admin123"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
