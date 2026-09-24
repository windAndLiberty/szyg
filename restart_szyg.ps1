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
Write-Host "[szyg] Step 3: Build frontend (szyg-frontend)" -ForegroundColor Cyan
Push-Location "$root\szyg-frontend"
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
$logDir = Join-Path $root "data\logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backendOutLog = Join-Path $logDir "backend-$stamp.out.log"
$backendErrLog = Join-Path $logDir "backend-$stamp.err.log"
$env:PYTHONPATH = "$root\server"
$env:SZYG_DATA_DIR = "$root\data"
$env:PYTHONUNBUFFERED = "1"
# Bundled ffmpeg (with ffprobe) shipped inside the Electron runtime —
# dev machines may not have ffmpeg on PATH; probe_duration/extract_audio need it.
$bundledFfmpeg = Join-Path $root "electron\runtime\candidate-1.1.4\backend\szyg-backend\_internal\third_party\ffmpeg\ffmpeg.exe"
if (-not $env:SZYG_FFMPEG_PATH -and (Test-Path $bundledFfmpeg)) {
    $env:SZYG_FFMPEG_PATH = $bundledFfmpeg
    Write-Host "  Using bundled ffmpeg: $bundledFfmpeg"
}
# Note: Start-Process cannot combine -WindowStyle with -RedirectStandardOutput,
# so wrap the command in cmd.exe and let cmd do the file redirection.
$cmdLine = "`"`"$root\.venv\Scripts\python.exe`" -m uvicorn szyg.api.app:create_app --host 127.0.0.1 --port $BackendPort --factory > `"$backendOutLog`" 2> `"$backendErrLog`"`""
$proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmdLine -WindowStyle Minimized -PassThru
Write-Host "  Backend wrapper PID: $($proc.Id)"
Write-Host "  Backend stdout log: $backendOutLog"
Write-Host "  Backend stderr log: $backendErrLog"

Write-Host "[szyg] Step 5: Wait for backend" -ForegroundColor Cyan
Wait-For-Port -Port $BackendPort -Name "Backend" -TimeoutSeconds 30

# ── 5. Start Vite dev server ────────────────────────────────────────────────
Write-Host "[szyg] Step 6: Start Vite dev server (port $VitePort)" -ForegroundColor Cyan
$viteProc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoExit", "-Command", "cd `"$root\szyg-frontend`"; npm run dev -- --port $VitePort --strictPort" `
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
