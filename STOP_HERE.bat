@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_tool_windows.ps1" %*
echo.
echo Finished. If the window shows an error, send logs\stop-latest.log to the developer.
pause
