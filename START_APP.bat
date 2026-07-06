@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo TTS Studio has not been installed yet.
    echo Please run START_HERE.bat one time first.
    echo.
    pause
    exit /b 1
)

echo Starting TTS Studio...
echo Local URL: http://127.0.0.1:7870
echo.
"%~dp0.venv\Scripts\python.exe" "%~dp0app.py" --server-name 127.0.0.1 --server-port 7870 %*

echo.
echo TTS Studio stopped.
pause
