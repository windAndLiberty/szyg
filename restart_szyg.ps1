# szyg Restarter — PowerShell launcher
# Called by restart_szyg.bat, or run directly: powershell -File restart_szyg.ps1

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$VitePort = 5173
$BackendPort = 8000

function Kill-Listeners {
    param(
        [Parameter(Mandatory)]
        [int[]]$Ports
    )
    foreach ($port in $Ports) {
        $pids = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
            Where-Object { $_.State -eq 'Listen' } |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $pids) {
            if ($p -gt 0) {
                Write-Host "  Killing PID $p on port $port ..."
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Wait-For-Port {
    param(
        [Parameter(Mandatory)]
        [int]$Port,
        [Parameter(Mandatory)]
        [string]$Name,
        [int]$TimeoutSeconds = 30
    )
    $ready = $false
    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        Start-Sleep -Seconds 1
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port" -TimeoutSec 2 -UseBasicParsing
            if ($r.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
    }
    if (-not $ready) {
        Write-Host "[szyg] ERROR: $Name did not start on port $Port!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "  $Name ready on port $Port"
}

# ── 1. Kill old backend ─────────────────────────────────────────────────────
Write-Host "[szyg] Step 1: Kill old backend (port $BackendPort)" -ForegroundColor Cyan
Kill-Listeners -Ports @($BackendPort)
Start-Sleep -Seconds 2

# ── 2. Kill old Vite dev servers ────────────────────────────────────────────
Write-Host "[szyg] Step 2: Kill old Vite dev servers (ports 5173-5200)" -ForegroundColor Cyan
Kill-Listeners -Ports @(5173..5200)
Start-Sleep -Seconds 2

# ── 3. Build frontend ─────────────────────────────────────────────────────
Write-Host "[szyg] Step 3: Build frontend" -ForegroundColor Cyan
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

# ── 4. Start backend ────────────────────────────────────────────────────────
Write-Host "[szyg] Step 4: Start backend" -ForegroundColor Cyan
$env:PYTHONPATH = "$root\server"
$env:SZYG_DATA_DIR = "$root\data"
$env:VOLCENGINE_API_KEY = "ark-149c9bff-2284-4193-a61f-8885dbb19ad5-d18be"
$env:SZYG_ADMIN_PASSWORD = "admin123"
$proc = Start-Process -FilePath "$root\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "szyg.api.app:create_app", "--host", "127.0.0.1", "--port", "$BackendPort", "--factory" `
    -WindowStyle Minimized `
    -PassThru
Write-Host "  Backend PID: $($proc.Id)"

Write-Host "[szyg] Step 5: Wait for backend" -ForegroundColor Cyan
Wait-For-Port -Port $BackendPort -Name "Backend" -TimeoutSeconds 30

# ── 5. Start Vite dev server ────────────────────────────────────────────────
Write-Host "[szyg] Step 6: Start Vite dev server (port $VitePort)" -ForegroundColor Cyan
$viteProc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-Command", "cd `"$root\web`"; npm run dev -- --port $VitePort --strictPort" `
    -WindowStyle Minimized `
    -PassThru
Write-Host "  Vite PID: $($viteProc.Id)"

Write-Host "[szyg] Step 7: Wait for Vite dev server" -ForegroundColor Cyan
Wait-For-Port -Port $VitePort -Name "Vite dev server" -TimeoutSeconds 30

# ── 6. Open browser ─────────────────────────────────────────────────────────
Write-Host "[szyg] Step 8: Open browser" -ForegroundColor Cyan
$url = "http://127.0.0.1:$VitePort"
Start-Process "chrome" -ArgumentList "--app=$url", "--window-size=1300,760", "--disable-cache", "--new-window", "--incognito"
if ($LASTEXITCODE -ne 0) {
    Start-Process "msedge" -ArgumentList "--app=$url", "--window-size=1300,760", "--new-window", "--inprivate"
}

Write-Host "[szyg] Done." -ForegroundColor Green
