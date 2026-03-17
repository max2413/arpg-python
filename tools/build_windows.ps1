param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$buildDir = Join-Path $projectRoot "build"
$distDir = Join-Path $projectRoot "dist"

if ($Clean) {
    if (Test-Path $buildDir) {
        Remove-Item -Recurse -Force $buildDir
    }
    if (Test-Path $distDir) {
        Remove-Item -Recurse -Force $distDir
    }
}

Push-Location $projectRoot
try {
    ppython setup.py build_apps
}
finally {
    Pop-Location
}
