$ErrorActionPreference = "Stop"

$electronDir = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $electronDir
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$spec = Join-Path $PSScriptRoot "szyg-backend.spec"
$distPath = Join-Path $electronDir "runtime\backend"
$workPath = Join-Path $electronDir ".build\backend"

if (-not (Test-Path $python)) {
    throw "Build Python was not found at $python"
}

if (-not (Test-Path (Join-Path $repoRoot ".venv\Lib\site-packages\PyInstaller"))) {
    & $python -m pip install "pyinstaller==6.16.0"
}

if (Test-Path $distPath) {
    Remove-Item -LiteralPath $distPath -Recurse -Force
}
if (Test-Path $workPath) {
    Remove-Item -LiteralPath $workPath -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $distPath | Out-Null
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath $distPath `
    --workpath $workPath `
    $spec

if ($LASTEXITCODE -ne 0) {
    throw "Backend runtime build failed"
}

$backendExe = Join-Path $distPath "szyg-backend\szyg-backend.exe"
if (-not (Test-Path $backendExe)) {
    throw "Backend executable was not produced"
}

Remove-Item -LiteralPath $workPath -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Backend runtime ready: $backendExe"
