param(
    [string]$Version = "",
    [switch]$SkipBackendBuild,
    [switch]$SkipFrontendInstall,
    [switch]$IncludeQwen,
    [string]$CertificatePath = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

if (-not $Version) {
    $Version = [regex]::Match((Get-Content -Raw "src\janescriber\__init__.py"), '__version__\s*=\s*"([^"]+)"').Groups[1].Value
}
if (-not $Version) { throw "Could not determine JanesCriber version." }

$projectPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $projectPython)) {
    throw "The developer Python environment is required to validate the release version. Run setup.bat first."
}
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $scriptDir "src"
try {
    & $projectPython -m janescriber.versioning --root $scriptDir --version $Version
    if ($LASTEXITCODE -ne 0) { throw "Project version metadata is inconsistent." }
} finally {
    $env:PYTHONPATH = $previousPythonPath
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$FailureMessage
    )
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) { throw "$FailureMessage Exit code: $LASTEXITCODE." }
}

function Ensure-ConsumerRuntime {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) {
        throw "uv is required to prepare the universal consumer runtime. Run setup.bat first."
    }

    $projectPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $projectPython)) {
        throw "The developer environment is missing. Run setup.bat before building the consumer installer."
    }

    $runtimeRoot = Join-Path $scriptDir ".cache\consumer-build"
    $runtimeVenv = Join-Path $runtimeRoot "venv-cpu"
    $runtimePython = Join-Path $runtimeVenv "Scripts\python.exe"
    $readyMarker = Join-Path $runtimeRoot "cpu-runtime-ready.txt"
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    $env:UV_CACHE_DIR = Join-Path $scriptDir ".cache\uv-cache"

    if (-not (Test-Path -LiteralPath $runtimePython)) {
        Write-Host "Creating the isolated universal CPU fallback runtime..." -ForegroundColor Cyan
        Invoke-Checked -FilePath $uv.Source -ArgumentList @(
            "venv", $runtimeVenv, "--python", $projectPython
        ) -FailureMessage "Could not create the consumer build environment."
    }

    if (-not (Test-Path -LiteralPath $readyMarker)) {
        Write-Host "Installing the universal CPU runtime used by the consumer installer..." -ForegroundColor Cyan
        $packages = @(
            "numpy>=1.26.0",
            "openai-whisper>=20240930",
            "psutil>=5.9.0",
            "proc-tap>=1.1.1",
            "soundcard>=0.4.6",
            "sounddevice>=0.5.1",
            "transformers>=4.45,<5",
            "vosk>=0.3.45",
            "pyinstaller>=6.0",
            "torch==2.7.1+cpu"
        )
        Invoke-Checked -FilePath $uv.Source -ArgumentList (@(
            "pip", "install", "--python", $runtimePython,
            "--index-url", "https://download.pytorch.org/whl/cpu",
            "--extra-index-url", "https://pypi.org/simple",
            "--index-strategy", "unsafe-best-match"
        ) + $packages) -FailureMessage "Could not install the universal consumer runtime."
        Set-Content -LiteralPath $readyMarker -Value "CPU runtime prepared $(Get-Date -Format o)" -Encoding ascii
    }

    return $runtimePython
}

$consumerPython = $null
if (-not $SkipBackendBuild) {
    if ($IncludeQwen) {
        throw "Qwen3-ASR is intentionally excluded from the universal one-file consumer installer. Use build_release.ps1 -WithQwen for the developer/specialist bundle."
    }
    $consumerPython = Ensure-ConsumerRuntime
}

$portableRoot = Join-Path $scriptDir "artifacts\build\portable-dist\JanesCriber"
$bundleRoot = Join-Path $scriptDir "desktop-ui\src-tauri\target\release\bundle"
$releaseRoot = Join-Path $scriptDir "artifacts\releases"
$setupOutput = Join-Path $releaseRoot "JanesCriber-$Version-Setup.exe"
$hashOutput = "$setupOutput.sha256"
$manifestOutput = "$setupOutput.json"

if (-not $SkipBackendBuild) {
    $releaseArguments = @("-Version", $Version, "-PythonPath", $consumerPython)
    if ($CertificatePath) { $releaseArguments += @("-CertificatePath", $CertificatePath) }
    Write-Host "Building the packaged Python backend and local FFmpeg bundle..." -ForegroundColor Cyan
    Invoke-Checked -FilePath "powershell.exe" -ArgumentList (@(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
        (Join-Path $scriptDir "build_release.ps1")
    ) + $releaseArguments) -FailureMessage "The backend release build failed."
}

$backendExecutable = Join-Path $portableRoot "JanesCriber.exe"
$ffmpegExecutable = Join-Path $portableRoot "ffmpeg\ffmpeg.exe"
$ffprobeExecutable = Join-Path $portableRoot "ffmpeg\ffprobe.exe"
foreach ($required in @($backendExecutable, $ffmpegExecutable, $ffprobeExecutable)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Consumer bundle is incomplete; missing $required. Run build_release.ps1 first."
    }
}

$uiRoot = Join-Path $scriptDir "desktop-ui"
Set-Location $uiRoot
if (-not $SkipFrontendInstall) {
    Write-Host "Installing the locked Studio frontend dependencies..." -ForegroundColor Cyan
    Invoke-Checked -FilePath "npm.cmd" -ArgumentList @("ci") -FailureMessage "Studio dependency installation failed."
}
Write-Host "Building JanesCriber Studio and the single Windows installer..." -ForegroundColor Cyan
Invoke-Checked -FilePath "npm.cmd" -ArgumentList @("run", "tauri:build", "--", "--bundles", "nsis") -FailureMessage "The Studio NSIS build failed."
Set-Location $scriptDir

$setupCandidate = Get-ChildItem -LiteralPath $bundleRoot -Filter "*-setup.exe" -File -Recurse -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime |
    Select-Object -Last 1
if (-not $setupCandidate) {
    throw "Tauri completed without producing an NSIS setup executable under $bundleRoot."
}

New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
Copy-Item -LiteralPath $setupCandidate.FullName -Destination $setupOutput -Force
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $setupOutput).Hash.ToLowerInvariant()
Set-Content -LiteralPath $hashOutput -Value "$hash  $(Split-Path $setupOutput -Leaf)" -Encoding ascii

$manifest = [ordered]@{
    product = "JanesCriber"
    version = $Version
    installer = (Split-Path $setupOutput -Leaf)
    installerType = "NSIS"
    backend = "Packaged Python service"
    ffmpegBundled = $true
    dataPolicy = "User-selected writable data directory; existing transcripts and models are preserved during repair and uninstall by default."
    generatedUtc = [DateTime]::UtcNow.ToString("o")
    sha256 = $hash
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath $manifestOutput -Encoding utf8

$validationPython = $projectPython
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = Join-Path $scriptDir "src"
try {
    Invoke-Checked -FilePath $validationPython -ArgumentList @(
        "-m", "janescriber.release_validation", $setupOutput,
        "--manifest", $manifestOutput,
        "--checksum", $hashOutput,
        "--version", $Version
    ) -FailureMessage "The consumer release artifact validation failed."
} finally {
    $env:PYTHONPATH = $previousPythonPath
}

Write-Host "Consumer installer: $setupOutput" -ForegroundColor Green
Write-Host "SHA256: $hash" -ForegroundColor Green
Write-Host "The developer safety path remains setup.bat + install.ps1." -ForegroundColor Yellow
