param(
    [string]$LockFile = "server/vendor/hermes-agent.lock.json"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$lockPath = (Resolve-Path (Join-Path $repoRoot $LockFile)).Path
$lock = Get-Content -LiteralPath $lockPath -Raw | ConvertFrom-Json
$target = [IO.Path]::GetFullPath((Join-Path $repoRoot $lock.source_directory))
$vendorRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot "server/vendor"))

if (-not $target.StartsWith($vendorRoot + [IO.Path]::DirectorySeparatorChar)) {
    throw "Refusing to replace a path outside server/vendor: $target"
}

$work = Join-Path ([IO.Path]::GetTempPath()) ("szyg-hermes-" + [guid]::NewGuid().ToString("N"))
$archive = Join-Path $work "hermes.zip"
$expanded = Join-Path $work "expanded"
$staged = Join-Path $work "staged"

try {
    New-Item -ItemType Directory -Force -Path $expanded, $staged | Out-Null
    Invoke-WebRequest -UseBasicParsing -Uri $lock.archive_url -OutFile $archive
    $actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $lock.archive_sha256.ToLowerInvariant()) {
        throw "Hermes archive checksum mismatch: $actualHash"
    }

    Expand-Archive -LiteralPath $archive -DestinationPath $expanded
    $source = Get-ChildItem -LiteralPath $expanded -Directory | Select-Object -First 1
    if (-not $source) {
        throw "Hermes archive did not contain a source directory"
    }

    $excluded = @(".git", ".github", "apps", "website", "tests", "docs")
    $robocopyArgs = @($source.FullName, $staged, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/XD") + $excluded
    & robocopy @robocopyArgs | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Failed to stage Hermes sources (robocopy exit $LASTEXITCODE)"
    }

    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
    Move-Item -LiteralPath $staged -Destination $target
    Write-Host "Hermes $($lock.version) synchronized at $target"
}
finally {
    if (Test-Path -LiteralPath $work) {
        Remove-Item -LiteralPath $work -Recurse -Force
    }
}
