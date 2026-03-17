param(
    [string]$Version = "v0.1.0"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $projectRoot "build\\win_amd64"
$releaseDir = Join-Path $projectRoot "dist"
$zipName = "arpg-prototype-win64-$Version.zip"
$zipPath = Join-Path $releaseDir $zipName

if (!(Test-Path $buildRoot)) {
    throw "Build output not found at $buildRoot. Run the Windows build first."
}

if (!(Test-Path $releaseDir)) {
    New-Item -ItemType Directory -Path $releaseDir | Out-Null
}

if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}

Compress-Archive -Path (Join-Path $buildRoot '*') -DestinationPath $zipPath
Write-Host "Created release archive: $zipPath"
