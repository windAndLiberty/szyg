$ErrorActionPreference = "Stop"

$electronDir = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $electronDir
$python = Join-Path $repoRoot "server\.hermes-venv\Scripts\python.exe"
$spec = Join-Path $PSScriptRoot "hermes-runtime.spec"
$distPath = Join-Path $electronDir "runtime\hermes"
$workPath = Join-Path $electronDir ".build\hermes"

if (-not (Test-Path $python)) {
    throw "Hermes build environment is missing. Install server/vendor/hermes_agent into server/.hermes-venv first."
}

# A pinned, idempotent install also works on a clean build machine. Avoid
# `pip show` here because PowerShell's strict native-error handling terminates
# the script before the fallback install can run.
& $python -m pip install --disable-pip-version-check "pyinstaller==6.16.0"
if ($LASTEXITCODE -ne 0) {
    throw "Unable to install the pinned PyInstaller build dependency"
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
    throw "Hermes runtime build failed"
}

$runtimeExe = Join-Path $distPath "hermes-runtime\hermes-runtime.exe"
if (-not (Test-Path $runtimeExe)) {
    throw "Hermes runtime executable was not produced"
}

Remove-Item -LiteralPath $workPath -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Hermes runtime ready: $runtimeExe"
