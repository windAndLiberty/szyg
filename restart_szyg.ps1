# szyg Restarter — PowerShell launcher
# Called by restart_szyg.bat, or run directly: powershell -File restart_szyg.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "[szyg] Step 1: Kill old backend (port 8000)" -ForegroundColor Cyan
$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
$pids = ($conns | Where-Object { $_.State -eq 'Listen' }).OwningProcess | Select-Object -Unique
foreach ($p in $pids) {
    if ($p -gt 0) {
        Write-Host "  Killing PID $p ..."
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

# Verify port is free
$leftover = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
if ($leftover) {
    Write-Host "[szyg] ERROR: Port 8000 still in use!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[szyg] Step 2: Build frontend" -ForegroundColor Cyan
Push-Location "$root\web"
if (-not (Test-Path "node_modules")) {
    Write-Host "  Installing dependencies..."
    npm install --silent
}
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[szyg] ERROR: Frontend build failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Pop-Location
Write-Host "  Frontend build done."

Write-Host "[szyg] Step 3: Start backend" -ForegroundColor Cyan
$env:PYTHONPATH = "$root\server"
$env:SZYG_DATA_DIR = "$root\data"
$proc = Start-Process -FilePath "$root\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "szyg.api.app:create_app", "--host", "127.0.0.1", "--port", "8000", "--factory" `
    -WindowStyle Minimized `
    -PassThru
Write-Host "  Backend PID: $($proc.Id)"

Write-Host "[szyg] Step 4: Wait for backend (max 30s)" -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}
if (-not $ready) {
    Write-Host "[szyg] ERROR: Backend startup timeout!" -ForegroundColor Red
    Write-Host "  Check logs\backend.log for details."
    if (Test-Path "$root\logs\backend.log") { notepad "$root\logs\backend.log" }
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "  Backend ready!"

Write-Host "[szyg] Step 5: Open browser" -ForegroundColor Cyan
$url = "http://127.0.0.1:8000/login?dev=1&username=admin&password=admin123"
Start-Process "chrome" -ArgumentList "--app=$url", "--window-size=1300,760", "--disable-cache", "--new-window", "--incognito"
if ($LASTEXITCODE -ne 0) {
    Start-Process "msedge" -ArgumentList "--app=$url", "--window-size=1300,760", "--new-window", "--inprivate"
}

Write-Host "[szyg] Done." -ForegroundColor Green
