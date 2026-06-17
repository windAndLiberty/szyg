#!/bin/bash
# szyg Desktop — 零依赖独立窗口
# 使用 Chrome/Chromium app mode，无需 Electron
set -e

FRONTEND_URL="${1:-http://localhost:5173}"
TITLE="szyg 智能矩阵运营系统"

# 查找可用的浏览器
for browser in \
  google-chrome google-chrome-stable chromium chromium-browser \
  brave-browser microsoft-edge; do
  if command -v "$browser" &> /dev/null; then
    echo "[desktop] Launching with $browser..."
    exec "$browser" \
      --app="$FRONTEND_URL" \
      --window-size=1300,760 \
      --window-position=center \
      --disable-extensions \
      --disable-sync \
      --no-first-run \
      --no-default-browser-check \
      &
    echo "[desktop] PID $!"
    exit 0
  fi
done

# Fallback: use xdg-open (opens in default browser, no app mode)
echo "[desktop] No Chrome found, using default browser..."
xdg-open "$FRONTEND_URL" &
