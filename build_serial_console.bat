@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_serial_console.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Build finished. Check the dist folder.
) else (
    echo Build failed. Read the error above, or check the logs folder.
)
pause

exit /b %EXIT_CODE%
