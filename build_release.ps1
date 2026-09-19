param(
    [string]$Version = "",
    [string]$CertificatePath = ""
)
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir
if (-not $Version) { $Version = [regex]::Match((Get-Content -Raw "src\janescriber\__init__.py"), '__version__\s*=\s*"([^"]+)"').Groups[1].Value }
if (-not $Version) { throw "Could not determine JanesCriber version." }

if (-not (Test-Path -LiteralPath "assets\icon.ico")) {
    throw "assets\icon.ico is required for a branded Windows executable."
}
$python = Join-Path $scriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "The project environment is missing. Run setup.bat before building the release."
}
$artifactRoot = Join-Path $scriptDir "artifacts"
$staging = Join-Path $artifactRoot "releases\JanesCriber-$Version"
$archive = Join-Path $artifactRoot "releases\JanesCriber-$Version-windows.zip"
$portableDist = Join-Path $artifactRoot "build\portable-dist"
$pyinstallerWork = Join-Path $artifactRoot "build\pyinstaller-build"
$specRoot = Join-Path $artifactRoot "build"
$qwenInstalled = Test-Path -LiteralPath (Join-Path $scriptDir ".venv\Lib\site-packages\qwen_asr")
$qwenPyInstallerArgs = @()
if ($qwenInstalled) {
    $qwenPyInstallerArgs = @("--collect-all", "qwen_asr", "--collect-all", "qwen_omni_utils")
}
New-Item -ItemType Directory -Path (Join-Path $artifactRoot "releases"), (Join-Path $artifactRoot "build") -Force | Out-Null
foreach ($path in @($staging, $portableDist, $pyinstallerWork)) {
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
}
if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
New-Item -ItemType Directory -Path $staging -Force | Out-Null

Write-Host "Building the self-contained JanesCriber runtime..." -ForegroundColor Cyan
& $python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name JanesCriber `
    --icon (Join-Path $scriptDir "assets\icon.ico") `
    --paths (Join-Path $scriptDir "src") `
    --add-data ((Join-Path $scriptDir "assets") + ";assets") `
    --hidden-import proctap `
    --hidden-import proctap.backends.windows `
    --hidden-import vosk `
    --collect-all vosk `
    --hidden-import transformers `
    --collect-submodules transformers.models.wav2vec2 `
    @qwenPyInstallerArgs `
    --distpath $portableDist `
    --workpath $pyinstallerWork `
    --specpath $specRoot `
    (Join-Path $scriptDir "src\janescriber\__main__.py")
if ($LASTEXITCODE -ne 0) { throw "Portable runtime build failed with exit code $LASTEXITCODE." }

$portableApp = Join-Path $portableDist "JanesCriber"
if (-not (Test-Path -LiteralPath (Join-Path $portableApp "JanesCriber.exe"))) {
    throw "PyInstaller completed without producing JanesCriber.exe."
}
$studioExecutable = Join-Path $scriptDir "desktop-ui\src-tauri\target\release\janescriber-studio.exe"
if (Test-Path -LiteralPath $studioExecutable) {
    Copy-Item -LiteralPath $studioExecutable -Destination (Join-Path $portableApp "JanesCriberStudio.exe") -Force
    Write-Host "Included JanesCriber Studio beside the legacy Python launcher." -ForegroundColor Green
} else {
    Write-Warning "JanesCriber Studio was not found. The portable package will contain the legacy Python interface only."
}
Copy-Item -Path (Join-Path $portableApp "*") -Destination $staging -Recurse -Force
foreach ($file in @("README.md", "ARCHITECTURE.md")) {
    Copy-Item -LiteralPath (Join-Path $scriptDir $file) -Destination (Join-Path $staging $file) -Force
}

$ffmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffprobeCommand = Get-Command ffprobe -ErrorAction SilentlyContinue
if (-not $ffmpegCommand -or -not $ffprobeCommand) {
    throw "FFmpeg and FFprobe must be installed on the build machine so they can be bundled."
}
$ffmpegLink = Get-Item -LiteralPath $ffmpegCommand.Source -Force
$ffmpegBin = Split-Path -Parent $ffmpegCommand.Source
if ($ffmpegLink.Target) { $ffmpegBin = Split-Path -Parent ([string]$ffmpegLink.Target) }
$bundledFfmpeg = Join-Path $staging "ffmpeg"
New-Item -ItemType Directory -Path $bundledFfmpeg -Force | Out-Null
$ffmpegFiles = Get-ChildItem -LiteralPath $ffmpegBin -File | Where-Object { $_.Extension -in @(".exe", ".dll") }
if (-not ($ffmpegFiles | Where-Object Name -eq "ffmpeg.exe") -or -not ($ffmpegFiles | Where-Object Name -eq "ffprobe.exe")) {
    throw "The detected FFmpeg directory did not contain both ffmpeg.exe and ffprobe.exe."
}
foreach ($file in $ffmpegFiles) { Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $bundledFfmpeg $file.Name) -Force }

$licenseRoot = Join-Path $staging "licenses"
New-Item -ItemType Directory -Path $licenseRoot -Force | Out-Null
$sitePackages = Join-Path $scriptDir ".venv\Lib\site-packages"
foreach ($metadata in Get-ChildItem -LiteralPath $sitePackages -Directory -Filter "*.dist-info" -ErrorAction SilentlyContinue) {
    $licenseFiles = Get-ChildItem -LiteralPath (Join-Path $metadata.FullName "licenses") -File -ErrorAction SilentlyContinue
    foreach ($license in $licenseFiles) {
        $safeName = ($metadata.Name -replace "[^A-Za-z0-9_.-]", "_") + "-" + $license.Name
        Copy-Item -LiteralPath $license.FullName -Destination (Join-Path $licenseRoot $safeName) -Force
    }
    $notice = Join-Path $metadata.FullName "NOTICE"
    if (Test-Path -LiteralPath $notice) {
        Copy-Item -LiteralPath $notice -Destination (Join-Path $licenseRoot (($metadata.Name -replace "[^A-Za-z0-9_.-]", "_") + "-NOTICE")) -Force
    }
}

if ($CertificatePath) {
    $signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if (-not $signtool) { throw "CertificatePath was provided, but signtool.exe was not found." }
    & $signtool.Source sign /fd SHA256 /a /f $CertificatePath (Join-Path $staging "JanesCriber.exe")
    if ($LASTEXITCODE -ne 0) { throw "Executable signing failed with exit code $LASTEXITCODE." }
} else {
    Write-Warning "The release executable is unsigned. Provide -CertificatePath for a trusted Windows release."
}

$archiveScript = @'
import os
import sys
import zipfile

root, destination = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as bundle:
    for folder, _, filenames in os.walk(root):
        for filename in filenames:
            path = os.path.join(folder, filename)
            bundle.write(path, os.path.relpath(path, root))
'@
& $python -c $archiveScript $staging $archive
if ($LASTEXITCODE -ne 0) { throw "Portable archive creation failed with exit code $LASTEXITCODE." }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$archive.sha256" -Value "$hash  $(Split-Path $archive -Leaf)" -Encoding ascii
Write-Host "Created $archive" -ForegroundColor Green
Write-Host "SHA256: $hash"
