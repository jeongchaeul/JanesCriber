param(
    [switch]$WithQwen,
    [switch]$WithDirectML
)
$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

if ($WithQwen -and $WithDirectML) {
    throw "Qwen3-ASR with DirectML is not supported by the current optional package matrix. Use CUDA, ROCm, XPU, or MPS for Qwen3-ASR, or omit -WithQwen when installing DirectML."
}

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

# Keep uv's interpreter and wheel caches beside the project so setup does not
# silently consume the system drive.
$env:UV_CACHE_DIR = Join-Path $scriptDir ".cache\uv-cache"

$hasNvidiaRuntime = [bool](Get-Command nvidia-smi -ErrorAction SilentlyContinue)
$displayAdapters = @()
try {
    $displayAdapters = @(Get-CimInstance -ClassName Win32_VideoController -ErrorAction SilentlyContinue)
} catch {
    $displayAdapters = @()
}
$ignoredAdapterPattern = "Microsoft Basic Display|Microsoft Remote Display|Remote Desktop|Parsec|VMware|VirtualBox|Citrix|RDP"
$hasDirectXGpu = @(
    $displayAdapters | Where-Object {
        $name = [string]$_.Name
        $name -and $name -notmatch $ignoredAdapterPattern
    }
).Count -gt 0
$autoDirectML = (-not $hasNvidiaRuntime) -and $hasDirectXGpu
$useDirectML = [bool]($WithDirectML -or $autoDirectML)
if ($WithQwen -and $autoDirectML) {
    $useDirectML = $false
    Write-Host "A non-NVIDIA GPU was detected, but Qwen3-ASR was requested. Keeping the standard CPU Torch runtime because Qwen3-ASR cannot share the optional DirectML package." -ForegroundColor Yellow
}
if ($autoDirectML -and -not $WithQwen) {
    Write-Host "Detected a Windows GPU without the NVIDIA CUDA runtime; selecting DirectML automatically." -ForegroundColor Cyan
}

# Prefer the project-local Python when it is supported, then use the system
# Python or launcher when (for example) Python 3.14 is the default.
$pythonExecutable = $null
$allowedPythonPattern = if ($useDirectML) { '^3\.10$' } else { '^(3\.10|3\.11|3\.12)$' }
$projectPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $projectPython) {
    $projectVersion = & $projectPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($projectVersion -match $allowedPythonPattern) {
        $pythonExecutable = $projectPython
    }
}
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonExecutable -and $pythonCommand) {
    $candidateVersion = & $pythonCommand.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($candidateVersion -match $allowedPythonPattern) {
        $pythonExecutable = $pythonCommand.Source
    }
}
if (-not $pythonExecutable) {
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        $pythonMinors = if ($useDirectML) { @('3.10') } else { @('3.12', '3.11', '3.10') }
        foreach ($minor in $pythonMinors) {
            $candidate = (& $pyCommand.Source "-$minor" -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1)
            if ($candidate -and (Test-Path -LiteralPath $candidate)) {
                $pythonExecutable = $candidate
                break
            }
        }
    }
}
if (-not $pythonExecutable) {
    $managedPythonVersion = if ($useDirectML) { "3.10" } else { "3.12" }
    $managedPythonDir = Join-Path $scriptDir ".cache\python"
    New-Item -ItemType Directory -Path $managedPythonDir -Force | Out-Null
    $env:UV_PYTHON_INSTALL_DIR = $managedPythonDir
    Write-Host "No supported Python runtime was found. Installing Python $managedPythonVersion into the project cache..." -ForegroundColor Yellow
    & uv python install $managedPythonVersion --install-dir $managedPythonDir --no-registry
    if ($LASTEXITCODE -ne 0) { throw "Could not install the project-local Python $managedPythonVersion runtime." }
    $pythonExecutable = (& uv python find $managedPythonVersion --managed-python 2>$null | Select-Object -Last 1)
    if ($pythonExecutable) { $pythonExecutable = $pythonExecutable.Trim() }
}
if (-not $pythonExecutable -or -not (Test-Path -LiteralPath $pythonExecutable)) {
    if ($useDirectML) {
        throw "The optional Windows DirectML runtime requires Python 3.10, and its project-local download could not be located. Run setup.bat directml again after checking network access."
    }
    throw "JanesCriber requires Python 3.10, 3.11, or 3.12. The project-local Python download could not be located. Run setup again after checking network access."
}
$pythonVersion = & $pythonExecutable -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Using Python $pythonVersion at $pythonExecutable" -ForegroundColor Cyan

$torchExtra = if ($hasNvidiaRuntime) { "cuda" } else { "cpu" }
$hardwareProfile = if ($useDirectML) { "DirectML (AMD / Intel / NVIDIA / other DirectX 12 GPUs)" } elseif ($torchExtra -eq "cuda") { "NVIDIA CUDA" } else { "CPU base runtime" }
Write-Host "Hardware profile: $hardwareProfile" -ForegroundColor Cyan

Write-Host "Synchronizing the private JanesCriber environment..." -ForegroundColor Yellow
$syncArguments = @("--locked")
$projectVenvPython = [System.IO.Path]::GetFullPath((Join-Path $scriptDir ".venv\Scripts\python.exe"))
if ([System.IO.Path]::GetFullPath($pythonExecutable) -ne $projectVenvPython) {
    $syncArguments += @("--python", $pythonExecutable)
}
& uv sync @syncArguments
if ($LASTEXITCODE -ne 0) { throw "uv sync failed with exit code $LASTEXITCODE." }

$pythonInEnvironment = Join-Path $scriptDir ".venv\Scripts\python.exe"
$torchVersion = if ($torchExtra -eq "cuda") { "2.7.1+cu128" } else { "2.7.1+cpu" }
$torchIndex = if ($torchExtra -eq "cuda") { "https://download.pytorch.org/whl/cu128" } else { "https://download.pytorch.org/whl/cpu" }
if ($useDirectML) {
    Write-Host "Installing the optional Windows DirectML Torch runtime..." -ForegroundColor Yellow
    & uv pip install --python $pythonInEnvironment "torch-directml" --index-url "https://pypi.org/simple"
    if ($LASTEXITCODE -ne 0) { throw "DirectML runtime installation failed with exit code $LASTEXITCODE." }
} else {
    Write-Host "Installing the selected Torch runtime ($torchVersion)..." -ForegroundColor Yellow
    # Both indexes are explicitly trusted: the selected Torch wheel comes from the
    # PyTorch index while its ordinary Python dependencies come from PyPI.
    & uv pip install --python $pythonInEnvironment "torch==$torchVersion" --index-url $torchIndex --extra-index-url "https://pypi.org/simple" --index-strategy unsafe-best-match
    if ($LASTEXITCODE -ne 0) { throw "Torch runtime installation failed with exit code $LASTEXITCODE." }
}

if ($WithQwen) {
    Write-Host "Installing the optional Qwen3-ASR local model pack..." -ForegroundColor Yellow
    & uv pip install --python $pythonInEnvironment "qwen-asr==0.0.6" --index-url "https://pypi.org/simple"
    if ($LASTEXITCODE -ne 0) { throw "Qwen3-ASR installation failed with exit code $LASTEXITCODE." }
    Write-Host "Installing the matching TorchVision audio utility runtime ($hardwareProfile)..." -ForegroundColor Yellow
    $torchVisionIndex = if ($useDirectML) { "https://pypi.org/simple" } else { $torchIndex }
    & uv pip install --python $pythonInEnvironment "torchvision==0.22.1" --index-url $torchVisionIndex --extra-index-url "https://pypi.org/simple" --index-strategy unsafe-best-match
    if ($LASTEXITCODE -ne 0) { throw "TorchVision installation failed with exit code $LASTEXITCODE." }
}

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
if ($WithQwen) {
    Write-Host "Qwen3-ASR is enabled. Its model weights download only when selected and remain in .cache\qwen3-asr." -ForegroundColor Green
} else {
    Write-Host "Qwen3-ASR is available as an optional model pack: install.ps1 -WithQwen" -ForegroundColor Gray
}
if ($useDirectML) {
    Write-Host "DirectML is enabled for compatible Windows DirectX 12 GPUs. It is a compatibility path; CUDA, ROCm, XPU, or MPS are preferred when available." -ForegroundColor Yellow
} elseif ($torchExtra -ne "cuda") {
    Write-Host "No NVIDIA CUDA runtime was selected. AMD/Intel/other DirectX 12 users can opt into the compatibility path with: setup.bat directml" -ForegroundColor Gray
}
if (Test-Path -LiteralPath "$scriptDir\JanesCriberStudio.exe") {
    Start-Process -FilePath "$scriptDir\JanesCriberStudio.exe" -WorkingDirectory $scriptDir
} elseif (Test-Path -LiteralPath "$scriptDir\JanesCriber.exe") {
    Start-Process -FilePath "$scriptDir\JanesCriber.exe" -WorkingDirectory $scriptDir
}
