@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo             Starting JanesCriber Setup
echo ============================================================
echo.
set "WITH_QWEN="
set "WITH_DIRECTML="
set "INSTALL_ARGS="
for %%A in (%*) do (
    if /I "%%~A"=="qwen" set "WITH_QWEN=1"
    if /I "%%~A"=="directml" set "WITH_DIRECTML=1"
)
if defined WITH_QWEN set "INSTALL_ARGS=%INSTALL_ARGS% -WithQwen"
if defined WITH_DIRECTML set "INSTALL_ARGS=%INSTALL_ARGS% -WithDirectML"

echo Running JanesCriber installer...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %INSTALL_ARGS%
set "SETUP_EXIT=%ERRORLEVEL%"
if not "%SETUP_EXIT%"=="0" (
    echo.
    echo Setup encountered an error.
    pause
)
exit /b %SETUP_EXIT%
