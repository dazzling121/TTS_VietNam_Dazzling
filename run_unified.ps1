$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "App virtual environment is missing. Run START_HERE.bat first."
}
& $Python (Join-Path $Root "app.py") --server-name 127.0.0.1 --server-port 7870
