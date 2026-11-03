param(
    [string]$RuntimeConfig = (Join-Path $PSScriptRoot "..\runtime\openclaw-runtime.json"),
    [string]$OutputRoot = (Join-Path $PSScriptRoot "..\runtime\openclaw"),
    [string]$DownloadCache = (Join-Path $PSScriptRoot "..\runtime\.downloads"),
    [switch]$ForceRebuild
)

$ErrorActionPreference = "Stop"
$config = Get-Content -LiteralPath $RuntimeConfig -Raw | ConvertFrom-Json
$outputRootResolved = [System.IO.Path]::GetFullPath($OutputRoot)
$destination = [System.IO.Path]::GetFullPath((Join-Path $outputRootResolved $config.openclawVersion))
if (-not $destination.StartsWith($outputRootResolved + [System.IO.Path]::DirectorySeparatorChar)) {
    throw "OpenClaw runtime destination escaped its output root"
}

$stage = Join-Path ([System.IO.Path]::GetTempPath()) ("xiaoyu-openclaw-" + [guid]::NewGuid().ToString("N"))
$nodeArchive = Join-Path $stage "node.zip"
$nodeExtract = Join-Path $stage "node"
$appDir = Join-Path $stage "app"
$npmUserConfig = Join-Path $stage "npmrc"
$previousNpmUserConfig = $env:NPM_CONFIG_USERCONFIG
$previousNpmAllowScripts = $env:npm_config_allow_scripts

function Get-Sha256Hex {
    param([Parameter(Mandatory)][string]$Path)
    $stream = [System.IO.File]::OpenRead($Path)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($sha256.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha256.Dispose()
        $stream.Dispose()
    }
}

function Test-PinnedRuntime {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)]$ExpectedConfig
    )

    $manifestPath = Join-Path $Path "manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        return $false
    }

    try {
        $runtimeManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        $matchesConfig =
            ([string]$runtimeManifest.openclawVersion -eq [string]$ExpectedConfig.openclawVersion) -and
            ([string]$runtimeManifest.gatewayClientVersion -eq [string]$ExpectedConfig.gatewayClientVersion) -and
            ([string]$runtimeManifest.protocolVersion -eq [string]$ExpectedConfig.protocolVersion) -and
            ([int]$runtimeManifest.wireVersion -eq [int]$ExpectedConfig.wireVersion) -and
            ([string]$runtimeManifest.nodeVersion -eq [string]$ExpectedConfig.nodeVersion) -and
            ([string]$runtimeManifest.platform -eq [string]$ExpectedConfig.platform)
        if (-not $matchesConfig -or -not $runtimeManifest.files) {
            return $false
        }

        foreach ($file in $runtimeManifest.files) {
            $relativePath = ([string]$file.path).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
            $filePath = Join-Path $Path $relativePath
            if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
                return $false
            }
            if ((Get-Sha256Hex $filePath) -ne ([string]$file.sha256).ToLowerInvariant()) {
                return $false
            }
        }

        return $true
    }
    catch {
        Write-Warning "Existing OpenClaw runtime validation failed: $($_.Exception.Message)"
        return $false
    }
}

function Invoke-DownloadWithRetry {
    param(
        [Parameter(Mandatory)][string]$Uri,
        [Parameter(Mandatory)][string]$OutFile,
        [int]$Attempts = 5
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Invoke-WebRequest -Uri $Uri -OutFile $OutFile -UseBasicParsing -TimeoutSec 120
            return
        }
        catch {
            Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
            if ($attempt -eq $Attempts) {
                throw
            }
            $delaySeconds = [Math]::Min(15, [Math]::Pow(2, $attempt))
            Write-Warning "Download attempt $attempt/$Attempts failed: $($_.Exception.Message). Retrying in $delaySeconds seconds."
            Start-Sleep -Seconds $delaySeconds
        }
    }
}

function Test-NodeArchive {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }

    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
        try {
            return $null -ne ($archive.Entries | Where-Object { $_.FullName -match '/node\.exe$' } | Select-Object -First 1)
        }
        finally {
            $archive.Dispose()
        }
    }
    catch {
        return $false
    }
}

if (-not $ForceRebuild -and (Test-PinnedRuntime -Path $destination -ExpectedConfig $config)) {
    Write-Host "OpenClaw runtime already matches the pinned versions and hashes; reusing: $destination"
    exit 0
}

try {
    New-Item -ItemType Directory -Path $nodeExtract, $appDir -Force | Out-Null
    # Runtime packaging must be reproducible and must not inherit a developer's
    # per-user npm script allowlist. npm 11 rejects a user-scoped allow-scripts
    # entry when `--prefix` targets this isolated temporary project.
    Set-Content -LiteralPath $npmUserConfig -Value "# Xiaoyu isolated OpenClaw runtime build" -Encoding ascii
    $env:NPM_CONFIG_USERCONFIG = $npmUserConfig
    # npm run exports user configuration as npm_config_* variables. npm 11.17
    # then misclassifies the inherited allow-scripts value as a forbidden CLI
    # policy for this nested project install (npm/cli#9912).
    Remove-Item Env:npm_config_allow_scripts -ErrorAction SilentlyContinue
    $runtimePackage = [ordered]@{
        private = $true
        dependencies = [ordered]@{
            openclaw = [string]$config.openclawVersion
        }
        # Exact versions are intentional. npm 11 blocks dependency lifecycle
        # scripts by default; fail closed if OpenClaw's script-bearing
        # dependency graph changes during a future rebuild.
        allowScripts = [ordered]@{
            '@google/genai@2.27.0' = $true
            'esbuild@0.28.2' = $true
            'koffi@3.3.2' = $true
            'protobufjs@7.6.6' = $true
            "openclaw@$($config.openclawVersion)" = $true
        }
    }
    $runtimePackage | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $appDir 'package.json') -Encoding utf8
    Set-Content -LiteralPath (Join-Path $appDir '.npmrc') -Value 'strict-allow-scripts=true' -Encoding ascii
    $nodeUrl = "https://nodejs.org/dist/v$($config.nodeVersion)/node-v$($config.nodeVersion)-win-x64.zip"
    $downloadCacheResolved = [System.IO.Path]::GetFullPath($DownloadCache)
    New-Item -ItemType Directory -Path $downloadCacheResolved -Force | Out-Null
    $cachedNodeArchive = Join-Path $downloadCacheResolved "node-v$($config.nodeVersion)-win-x64.zip"
    if (Test-NodeArchive $cachedNodeArchive) {
        Copy-Item -LiteralPath $cachedNodeArchive -Destination $nodeArchive
        Write-Host "Using cached Node.js archive: $cachedNodeArchive"
    }
    else {
        Remove-Item -LiteralPath $cachedNodeArchive -Force -ErrorAction SilentlyContinue
        Invoke-DownloadWithRetry -Uri $nodeUrl -OutFile $nodeArchive
        if (-not (Test-NodeArchive $nodeArchive)) {
            throw "Downloaded Node.js archive is not a valid Windows x64 distribution"
        }
        $cacheTemp = "$cachedNodeArchive.$([guid]::NewGuid().ToString('N')).partial"
        Copy-Item -LiteralPath $nodeArchive -Destination $cacheTemp
        Move-Item -LiteralPath $cacheTemp -Destination $cachedNodeArchive -Force
    }
    Expand-Archive -LiteralPath $nodeArchive -DestinationPath $nodeExtract
    $nodeDistribution = Get-ChildItem -LiteralPath $nodeExtract -Directory | Select-Object -First 1
    if (-not $nodeDistribution) { throw "Node.js archive did not contain a distribution directory" }

    & npm.cmd install --prefix $appDir --omit=dev
    if ($LASTEXITCODE -ne 0) { throw "OpenClaw npm installation failed" }

    # The Store runtime needs executable package contents, not upstream source
    # maps or dependency documentation. Removing these files keeps proprietary
    # source/privacy audits meaningful without changing the pinned package code.
    $nodeModules = Join-Path $appDir "node_modules"
    Get-ChildItem -LiteralPath $nodeModules -Recurse -File -Filter "*.map" |
        Remove-Item -Force
    $undiciDocs = Join-Path $nodeModules "undici\docs"
    if (Test-Path -LiteralPath $undiciDocs) {
        Remove-Item -LiteralPath $undiciDocs -Recurse -Force
    }

    $entry = Join-Path $appDir "node_modules\openclaw\openclaw.mjs"
    if (-not (Test-Path -LiteralPath $entry)) { throw "OpenClaw package entry is missing" }

    if (Test-Path -LiteralPath $destination) {
        Remove-Item -LiteralPath $destination -Recurse -Force
    }
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $nodeDistribution.FullName "node.exe") -Destination (Join-Path $destination "node.exe")
    Copy-Item -LiteralPath $appDir -Destination (Join-Path $destination "app") -Recurse

    $manifest = [ordered]@{
        openclawVersion = [string]$config.openclawVersion
        gatewayClientVersion = [string]$config.gatewayClientVersion
        protocolVersion = [string]$config.protocolVersion
        wireVersion = [int]$config.wireVersion
        nodeVersion = [string]$config.nodeVersion
        platform = [string]$config.platform
        createdAt = [DateTime]::UtcNow.ToString("o")
        files = @(
            [ordered]@{
                path = "node.exe"
                sha256 = Get-Sha256Hex (Join-Path $destination "node.exe")
            },
            [ordered]@{
                path = "app/node_modules/openclaw/openclaw.mjs"
                sha256 = Get-Sha256Hex (Join-Path $destination "app\node_modules\openclaw\openclaw.mjs")
            },
            [ordered]@{
                path = "app/package.json"
                sha256 = Get-Sha256Hex (Join-Path $destination "app\package.json")
            },
            [ordered]@{
                path = "app/package-lock.json"
                sha256 = Get-Sha256Hex (Join-Path $destination "app\package-lock.json")
            },
            [ordered]@{
                path = "app/node_modules/openclaw/package.json"
                sha256 = Get-Sha256Hex (Join-Path $destination "app\node_modules\openclaw\package.json")
            }
        )
    }
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $destination "manifest.json") -Encoding utf8
    Write-Host "OpenClaw runtime ready: $destination"
}
finally {
    if ($null -eq $previousNpmUserConfig) {
        Remove-Item Env:NPM_CONFIG_USERCONFIG -ErrorAction SilentlyContinue
    }
    else {
        $env:NPM_CONFIG_USERCONFIG = $previousNpmUserConfig
    }
    if ($null -eq $previousNpmAllowScripts) {
        Remove-Item Env:npm_config_allow_scripts -ErrorAction SilentlyContinue
    }
    else {
        $env:npm_config_allow_scripts = $previousNpmAllowScripts
    }
    if ((Test-Path -LiteralPath $stage) -and $stage.StartsWith([System.IO.Path]::GetTempPath())) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
