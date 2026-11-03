param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,
    [switch]$Install
)

$ErrorActionPreference = "Stop"
$workspacePath = [System.IO.Path]::GetFullPath($Workspace)
if (-not (Test-Path -LiteralPath $workspacePath -PathType Container)) {
    throw "OpenClaw workspace does not exist: $workspacePath"
}

$commandText = "npx skills add https://github.com/TeamWiseFlow/xiaobei --skill wechat-channels-publish"
if (-not $Install) {
    Write-Host "This script does not install the third-party skill without -Install."
    Write-Host "Review the source, then run from the intended employee workspace:"
    Write-Host $commandText
    exit 0
}

Push-Location $workspacePath
try {
    & npx.cmd skills add https://github.com/TeamWiseFlow/xiaobei --skill wechat-channels-publish
    if ($LASTEXITCODE -ne 0) { throw "skills CLI failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

$candidates = @(
    (Join-Path $workspacePath "skills\wechat-channels-publish"),
    (Join-Path $workspacePath ".agents\skills\wechat-channels-publish")
)
$sourceDirectory = $candidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ "SKILL.md") } | Select-Object -First 1
if (-not $sourceDirectory) {
    throw "Installation finished but wechat-channels-publish/SKILL.md was not found"
}

$targetDirectory = Join-Path $workspacePath "skills\wechat-channels-publish"
if ([System.IO.Path]::GetFullPath($sourceDirectory) -ne [System.IO.Path]::GetFullPath($targetDirectory)) {
    if (Test-Path -LiteralPath $targetDirectory) {
        throw "Target skill directory already exists; refusing to overwrite it"
    }
    Copy-Item -LiteralPath $sourceDirectory -Destination $targetDirectory -Recurse
}

$skillFile = Join-Path $targetDirectory "SKILL.md"
$hash = (Get-FileHash -LiteralPath $skillFile -Algorithm SHA256).Hash.ToLowerInvariant()
$lockDirectory = Join-Path $workspacePath ".xiaoyu"
New-Item -ItemType Directory -Path $lockDirectory -Force | Out-Null
$lockPath = Join-Path $lockDirectory "skill-lock.json"
$lock = @{}
if (Test-Path -LiteralPath $lockPath) {
    $existingLock = Get-Content -LiteralPath $lockPath -Raw | ConvertFrom-Json
    foreach ($property in $existingLock.PSObject.Properties) {
        $lock[$property.Name] = $property.Value
    }
}
$lock["wechat-channels-publish"] = @{
    source = "https://github.com/TeamWiseFlow/xiaobei"
    installedAt = [DateTime]::UtcNow.ToString("o")
    skillFile = "skills/wechat-channels-publish/SKILL.md"
    sha256 = $hash
}
$lock | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $lockPath -Encoding utf8
Write-Host "Verified unchanged SKILL.md: $skillFile"
Write-Host "SHA-256: $hash"
