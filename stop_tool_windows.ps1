param(
    [int]$Port = 7870,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    Write-Host "This stop script is for Windows. On macOS/Linux, run: ./STOP_HERE.sh"
    exit 1
}

$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$StopLog = Join-Path $LogDir ("stop-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$LatestLog = Join-Path $LogDir "stop-latest.log"

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Write-Host $line
    Add-Content -LiteralPath $StopLog -Value $line -Encoding UTF8
    Set-Content -LiteralPath $LatestLog -Value (Get-Content -LiteralPath $StopLog -Raw -ErrorAction SilentlyContinue) -Encoding UTF8
}

function Stop-ProcessSafe {
    param(
        [int]$Pid,
        [string]$Reason
    )
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $Pid" -ErrorAction SilentlyContinue
    if (-not $proc) {
        return
    }
    Write-Log "Stopping PID $Pid ($Reason): $($proc.CommandLine)"
    if ($DryRun) {
        return
    }
    try {
        Stop-Process -Id $Pid -Force -ErrorAction Stop
    } catch {
        Write-Log "Could not stop PID ${Pid}: $($_.Exception.Message)" "WARN"
    }
}

function Get-TtsProcesses {
    $rootPattern = [Regex]::Escape($Root)
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -like "python*" -and
        $_.CommandLine -and
        $_.CommandLine -match $rootPattern -and
        (
            $_.CommandLine -like "*kokoro_worker.py*" -or
            $_.CommandLine -like "*vieneu_worker.py*" -or
            $_.CommandLine -like "*app.py*"
        )
    }
}

Write-Log "TTS Studio safe stop started."
Write-Log "Project root: $Root"

$processes = @(Get-TtsProcesses)
$workers = @($processes | Where-Object { $_.CommandLine -like "*kokoro_worker.py*" -or $_.CommandLine -like "*vieneu_worker.py*" })
$apps = @($processes | Where-Object { $_.CommandLine -like "*app.py*" })

foreach ($proc in $workers) {
    Stop-ProcessSafe -Pid $proc.ProcessId -Reason "model worker"
}

Start-Sleep -Milliseconds 500

foreach ($proc in $apps) {
    Stop-ProcessSafe -Pid $proc.ProcessId -Reason "web app"
}

$listeners = @(Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" })
foreach ($listener in $listeners) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -and $proc.CommandLine -match [Regex]::Escape($Root)) {
        Stop-ProcessSafe -Pid $listener.OwningProcess -Reason "listener on port $Port"
    } elseif ($proc) {
        Write-Log "Port $Port is used by a non-project process; not stopping PID $($listener.OwningProcess)." "WARN"
    }
}

Start-Sleep -Milliseconds 500
$remaining = @(Get-TtsProcesses)
if ($remaining.Count -eq 0) {
    Write-Log "TTS Studio stopped. No project app/worker process remains."
} else {
    foreach ($proc in $remaining) {
        Write-Log "Still running PID $($proc.ProcessId): $($proc.CommandLine)" "WARN"
    }
}
