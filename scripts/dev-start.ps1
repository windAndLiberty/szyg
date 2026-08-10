# 一键启动开发版「领鹿员工」
# 用法: pwsh -ExecutionPolicy Bypass -File scripts/dev-start.ps1
# 说明: 会弹出两个前台窗口 —— [前端] vite (5173) 与 [Electron] (自动拉起后端 8000)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "检查端口占用..."
foreach ($port in 8000, 5173) {
    $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($busy) {
        Write-Host "端口 $port 被占用，可能已有进程。如需重启请先关闭旧进程。"
    }
}

Write-Host "[1/2] 启动前端 (vite, http://localhost:5173)..."
Start-Process pwsh.exe -ArgumentList "-NoExit", "-NoProfile", "-Command", "cd '$repoRoot\szyg-frontend'; npm run dev" -WorkingDirectory "$repoRoot\szyg-frontend"

Write-Host "[2/2] 启动 Electron (dev 模式，自动拉起后端 :8000)..."
Start-Process pwsh.exe -ArgumentList "-NoExit", "-NoProfile", "-Command", "cd '$repoRoot\electron'; `$env:NODE_ENV='development'; npm start" -WorkingDirectory "$repoRoot\electron"

Write-Host ""
Write-Host "已启动。等待 warmup 后可访问:"
Write-Host "  前端   http://localhost:5173"
Write-Host "  后端   http://127.0.0.1:8000/api/health"
Write-Host "窗口保持了 --NoExit，日志直接显示在各个窗口里。"
