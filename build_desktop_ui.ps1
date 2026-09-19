param(
    [switch]$SkipLegacyRuntime
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$uiDir = Join-Path $scriptDir "desktop-ui"
Set-Location $uiDir

if (-not (Test-Path -LiteralPath "package-lock.json")) {
    throw "desktop-ui/package-lock.json is missing. Run npm install once before building the desktop UI."
}

if (-not $SkipLegacyRuntime) {
    $legacyRuntime = Join-Path $scriptDir "artifacts\build\portable-dist\JanesCriber\JanesCriber.exe"
    if (-not (Test-Path -LiteralPath $legacyRuntime)) {
        throw "The bundled Python runtime is missing. Run build_release.ps1 first, or pass -SkipLegacyRuntime for a development-only UI build."
    }
}

Write-Host "Building JanesCriber Studio frontend..." -ForegroundColor Cyan
& npm ci
if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
& npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
if ($SkipLegacyRuntime) {
    Write-Host "Frontend-only build complete; the native bundle needs the portable backend." -ForegroundColor Yellow
    exit 0
}

Write-Host "Building the native Tauri executable and installer..." -ForegroundColor Cyan
& npm run tauri:build
if ($LASTEXITCODE -ne 0) { throw "Tauri build failed." }

$bundleRoot = Join-Path $uiDir "src-tauri\target\release\bundle"
Write-Host "Desktop UI artifacts: $bundleRoot" -ForegroundColor Green
