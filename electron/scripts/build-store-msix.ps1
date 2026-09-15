$ErrorActionPreference = 'Stop'

$electronDir = Split-Path -Parent $PSScriptRoot
$layoutDir = Join-Path $electronDir 'dist\win-unpacked'
$storeDir = Join-Path $electronDir 'store'
$version = (Get-Content (Join-Path $electronDir 'package.json') -Raw | ConvertFrom-Json).version
$outputDir = Join-Path $electronDir 'dist\store'
$outputFile = Join-Path $outputDir ("XiaoyuAI-$version.0-x64-Store.msix")

if (-not (Test-Path -LiteralPath (Join-Path $layoutDir 'XiaoyuAI.exe'))) {
    throw 'Store package layout is missing. Run npm run build:public:dir first.'
}

$layoutAssets = Join-Path $layoutDir 'Assets'
New-Item -ItemType Directory -Force -Path $layoutAssets | Out-Null
Copy-Item -Path (Join-Path $storeDir 'Assets\*') -Destination $layoutAssets -Recurse -Force
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
if (Test-Path -LiteralPath $outputFile) {
    Remove-Item -LiteralPath $outputFile -Force
}

& winapp package $layoutDir `
    --manifest (Join-Path $storeDir 'Package.appxmanifest') `
    --output $outputFile `
    --exe 'XiaoyuAI.exe'

if ($LASTEXITCODE -ne 0) {
    throw "winapp package failed with exit code $LASTEXITCODE"
}

Write-Host "Store MSIX created: $outputFile"
