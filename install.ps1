$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

$running = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    try {
        $_.Path -and $_.Path.StartsWith((Join-Path $scriptDir ".venv"), [System.StringComparison]::OrdinalIgnoreCase)
    } catch {
        $false
    }
}
if ($running) {
    throw "Close all JanesCriber windows before updating its runtime, then run setup.bat again."
}

Write-Host "" 
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "             JanesCriber - Automated Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "" 

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found. Install it from https://docs.astral.sh/uv/ and run setup again."
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "FFmpeg was not found. Install the complete FFmpeg package and run setup again."
}
if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    throw "ffprobe was not found. Install the complete FFmpeg package and run setup again."
}

# Prefer the system Python when it is supported, but automatically fall back
# to the Python launcher when (for example) Python 3.14 is the default.
$pythonExecutable = $null
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $candidateVersion = & $pythonCommand.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($candidateVersion -match '^(3\.10|3\.11|3\.12)$') {
        $pythonExecutable = $pythonCommand.Source
    }
}
if (-not $pythonExecutable) {
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        foreach ($minor in @('3.12', '3.11', '3.10')) {
            $candidate = (& $pyCommand.Source "-$minor" -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1)
            if ($candidate -and (Test-Path -LiteralPath $candidate)) {
                $pythonExecutable = $candidate
                break
            }
        }
    }
}
if (-not $pythonExecutable) {
    throw "JanesCriber requires Python 3.10, 3.11, or 3.12. Install one of those versions and run setup again."
}
$pythonVersion = & $pythonExecutable -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Using Python $pythonVersion at $pythonExecutable" -ForegroundColor Cyan

# Keep uv's wheel cache beside the project so setup does not silently consume
# the system drive. The virtual environment and Whisper models are local too.
$env:UV_CACHE_DIR = Join-Path $scriptDir ".uv-cache"
$torchExtra = if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { "cuda" } else { "cpu" }
Write-Host "Hardware profile: Windows $torchExtra runtime" -ForegroundColor Cyan

Write-Host "Synchronizing the private JanesCriber environment..." -ForegroundColor Yellow
& uv sync --locked
if ($LASTEXITCODE -ne 0) { throw "uv sync failed with exit code $LASTEXITCODE." }

$pythonInEnvironment = Join-Path $scriptDir ".venv\Scripts\python.exe"
$torchVersion = if ($torchExtra -eq "cuda") { "2.7.1+cu128" } else { "2.7.1+cpu" }
$torchIndex = if ($torchExtra -eq "cuda") { "https://download.pytorch.org/whl/cu128" } else { "https://download.pytorch.org/whl/cpu" }
Write-Host "Installing the selected Torch runtime ($torchVersion)..." -ForegroundColor Yellow
# Both indexes are explicitly trusted: the selected Torch wheel comes from the
# PyTorch index while its ordinary Python dependencies come from PyPI.
& uv pip install --python $pythonInEnvironment "torch==$torchVersion" --index-url $torchIndex --extra-index-url "https://pypi.org/simple" --index-strategy unsafe-best-match
if ($LASTEXITCODE -ne 0) { throw "Torch runtime installation failed with exit code $LASTEXITCODE." }

$cscCandidates = @(
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)
$csc = $cscCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($csc) {
    & $csc /target:winexe /r:System.Windows.Forms.dll /win32icon:"$scriptDir\assets\icon.ico" /out:"$scriptDir\JanesCriber.exe" "$scriptDir\Program.cs" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "JanesCriber.exe compilation failed." }
    Write-Host "JanesCriber.exe compiled successfully." -ForegroundColor Green
} else {
    Write-Host "The .NET compiler was not found; the GUI can still be launched with:" -ForegroundColor Yellow
    Write-Host "uv run python -m janescriber --gui" -ForegroundColor Gray
}

Write-Host "" 
Write-Host "Setup complete. Models and scratch data remain in this project folder." -ForegroundColor Green
if (Test-Path -LiteralPath "$scriptDir\JanesCriber.exe") {
    Start-Process -FilePath "$scriptDir\JanesCriber.exe" -WorkingDirectory $scriptDir
}
