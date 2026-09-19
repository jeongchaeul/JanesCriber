@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo             Starting JanesCriber Setup
echo ============================================================
echo.
if /I "%~1"=="qwen" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -WithQwen
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Setup encountered an error.
    pause
)
