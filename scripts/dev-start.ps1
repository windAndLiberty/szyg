# Start the SZYG Electron development environment with hot reload.
# Compatible with Windows PowerShell 5 and PowerShell 7.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "szyg-frontend"
$electronDir = Join-Path $repoRoot "electron"
$electronRuntime = Join-Path $electronDir "node_modules\electron"

function Get-PortListener {
    param([int]$Port)
    return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
}

function Stop-ProjectElectron {
    $snapshot = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $electronProcesses = @($snapshot | Where-Object {
        $_.Name -eq "electron.exe" -and
        $_.ExecutablePath -and
        $_.ExecutablePath.StartsWith($electronRuntime, [System.StringComparison]::OrdinalIgnoreCase)
    })
    $electronIds = @($electronProcesses | Select-Object -ExpandProperty ProcessId)
    $roots = @($electronProcesses | Where-Object { $electronIds -notcontains $_.ParentProcessId })
    $orderedIds = New-Object System.Collections.Generic.List[int]

    function Add-ProcessTreePostOrder {
        param([int]$ParentId)
        foreach ($child in @($snapshot | Where-Object { $_.ParentProcessId -eq $ParentId })) {
            Add-ProcessTreePostOrder -ParentId ([int]$child.ProcessId)
        }
        if (-not $orderedIds.Contains($ParentId)) {
            $orderedIds.Add($ParentId)
        }
    }

    foreach ($root in $roots) {
        Add-ProcessTreePostOrder -ParentId ([int]$root.ProcessId)
    }
    foreach ($processId in $orderedIds) {
        Write-Host "Stopping old project process PID $processId..."
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

function Stop-ProjectPortListener {
    param(
        [int]$Port,
        [string]$ExpectedPathFragment
    )

    $listeners = @(Get-PortListener -Port $Port)
    foreach ($listener in $listeners) {
        $processId = [int]$listener.OwningProcess
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
        $commandLine = [string]$processInfo.CommandLine
        if ($commandLine -and $commandLine.IndexOf($ExpectedPathFragment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
            Write-Host "Stopping old project listener on port $Port (PID $processId)..."
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Wait-ForHttp {
    param(
        [string]$Url,
        [string]$ServiceName,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host "$ServiceName is ready." -ForegroundColor Green
                return
            }
        } catch {
            Start-Sleep -Milliseconds 300
        }
    }
    throw "$ServiceName did not become ready: $Url"
}

Write-Host "Preparing SZYG desktop development environment..." -ForegroundColor Cyan
Stop-ProjectElectron
Stop-ProjectPortListener -Port 5173 -ExpectedPathFragment $frontendDir

Start-Sleep -Milliseconds 800
foreach ($port in 8000, 5173) {
    $listener = Get-PortListener -Port $port
    if ($listener) {
        $processIds = ($listener | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
        throw "Port $port is still in use by PID $processIds. Close that process and run this script again."
    }
}

function Resolve-SzygFfmpeg {
    if ($env:SZYG_FFMPEG_PATH -and (Test-Path $env:SZYG_FFMPEG_PATH)) { return }
    if (Get-Command ffmpeg -All -ErrorAction SilentlyContinue) { return }
    $candidates = @("C:\ffmpeg\bin\ffmpeg.exe", "C:\tools\ffmpeg\bin\ffmpeg.exe")
    foreach ($root in @("$env:LOCALAPPDATA", "C:\DevTools", "C:\Work")) {
        if (-not (Test-Path $root)) { continue }
        Get-ChildItem -Path $root -Recurse -Filter ffmpeg.exe -Depth 3 -ErrorAction SilentlyContinue |
            Where-Object { $_.Directory.Name -eq 'bin' } |
            ForEach-Object { $candidates += $_.FullName }
    }
    foreach ($c in ($candidates | Select-Object -Unique)) {
        if (Test-Path $c) {
            $env:SZYG_FFMPEG_PATH = $c
            Write-Host "  Detected ffmpeg: $c" -ForegroundColor Green
            return
        }
    }
    Write-Host "  WARNING: ffmpeg not found. 数字人高仿复刻需要探测视频时长，运行 'winget install ffmpeg'。" -ForegroundColor Yellow
}
Resolve-SzygFfmpeg

Write-Host "[1/2] Starting Vite with hot module reload..." -ForegroundColor Cyan
$viteWindow = Start-Process powershell.exe `
    -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location -LiteralPath '$frontendDir'; npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort" `
    -WorkingDirectory $frontendDir `
    -WindowStyle Hidden `
    -PassThru

try {
    Wait-ForHttp -Url "http://127.0.0.1:5173/" -ServiceName "Vite"

    Write-Host "[2/2] Starting Electron and the hot-reload backend..." -ForegroundColor Cyan
    Write-Host "Keep this window open. Press Ctrl+C to stop development." -ForegroundColor DarkGray
    $env:NODE_ENV = "development"
    Push-Location $electronDir
    try {
        & npm.cmd start
        if ($LASTEXITCODE -ne 0) {
            throw "Electron exited with code $LASTEXITCODE."
        }
    } finally {
        Pop-Location
    }
} finally {
    if ($viteWindow -and -not $viteWindow.HasExited) {
        Stop-Process -Id $viteWindow.Id -Force -ErrorAction SilentlyContinue
    }
}
