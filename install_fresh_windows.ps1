param(
    [switch]$CheckOnly,
    [switch]$NoStart,
    [switch]$SkipFfmpeg,
    [switch]$SkipVCRedist,
    [switch]$SkipModelRuntimes,
    [switch]$InstallGpuTorch,
    [string]$PythonVersion = "3.12.10",
    [string]$ModelRoot = (Join-Path $env:USERPROFILE "TTS\Models"),
    [int]$Port = 7870
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    Write-Host "This PowerShell installer is for Windows. On macOS/Linux, run: ./START_HERE.sh"
    exit 1
}

$LogDir = Join-Path $Root "logs"
$DownloadDir = Join-Path $Root "downloads"
$ToolsDir = Join-Path $Root "tools"
New-Item -ItemType Directory -Path $LogDir, $DownloadDir, $ToolsDir -Force | Out-Null

$InstallLog = Join-Path $LogDir ("install-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$LatestLog = Join-Path $LogDir "install-latest.log"

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    $line = "[{0}] [{1}] {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Write-Host $line
    Add-Content -LiteralPath $InstallLog -Value $line -Encoding UTF8
    Set-Content -LiteralPath $LatestLog -Value (Get-Content -LiteralPath $InstallLog -Raw -ErrorAction SilentlyContinue) -Encoding UTF8
}

function Test-Command {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-VCRedistX64 {
    $paths = @(
        "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
    )
    foreach ($path in $paths) {
        try {
            $item = Get-ItemProperty -LiteralPath $path -ErrorAction Stop
            if ($item.Installed -eq 1) { return $true }
        } catch {
        }
    }
    return $false
}

function Add-UserPath {
    param([string]$PathToAdd)
    if (-not (Test-Path -LiteralPath $PathToAdd)) { return }
    $full = [IO.Path]::GetFullPath($PathToAdd)
    $currentParts = ($env:Path -split ";") | Where-Object { $_ }
    if ($currentParts -notcontains $full) {
        $env:Path = "$full;$env:Path"
    }

    try {
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $userParts = ($userPath -split ";") | Where-Object { $_ }
        if ($userParts -notcontains $full) {
            $newUserPath = if ($userPath) { "$full;$userPath" } else { $full }
            [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
            Write-Log "Added to user PATH: $full"
        }
    } catch {
        Write-Log "Could not update user PATH: $($_.Exception.Message)" "WARN"
    }
}

function Invoke-Download {
    param(
        [string]$Url,
        [string]$Destination
    )
    if (Test-Path -LiteralPath $Destination) {
        Write-Log "Using cached download: $Destination"
        return
    }
    Write-Log "Downloading: $Url"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
    } catch {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    }
    Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
}

function Invoke-DownloadFirstAvailable {
    param(
        [array]$Candidates
    )
    $errors = @()
    foreach ($candidate in $Candidates) {
        try {
            Invoke-Download -Url $candidate.Url -Destination $candidate.Destination
            return $candidate
        } catch {
            $errors += "$($candidate.Url): $($_.Exception.Message)"
            Write-Log "Download candidate failed: $($candidate.Url) | $($_.Exception.Message)" "WARN"
            if (Test-Path -LiteralPath $candidate.Destination) {
                Remove-Item -LiteralPath $candidate.Destination -Force -ErrorAction SilentlyContinue
            }
        }
    }
    throw "All download candidates failed:`n$($errors -join "`n")"
}

function Invoke-Exe {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$Name
    )
    Write-Log "Running installer: $Name"
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Wait -PassThru
    if ($process.ExitCode -notin @(0, 3010, 1638)) {
        throw "$Name installer failed with exit code $($process.ExitCode)"
    }
    Write-Log "$Name installer finished with exit code $($process.ExitCode)"
}

function Invoke-Python {
    param(
        [string]$Python,
        [string[]]$Arguments,
        [string]$Name
    )
    Write-Log "Running: $Name"
    & $Python @Arguments 2>&1 | Tee-Object -Variable output | ForEach-Object {
        Add-Content -LiteralPath $InstallLog -Value $_ -Encoding UTF8
        Write-Host $_
    }
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Get-PythonInfo {
    param([string]$Python)
    if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { return $null }
    try {
        $script = "import json, platform, sys; print(json.dumps({'exe':sys.executable,'major':sys.version_info[0],'minor':sys.version_info[1],'version':sys.version.split()[0],'arch':platform.architecture()[0]}))"
        $raw = & $Python -c $script 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $raw) { return $null }
        return $raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function Find-Python {
    $candidates = New-Object System.Collections.Generic.List[string]

    if (Test-Command "py") {
        foreach ($ver in @("3.12", "3.11", "3.10")) {
            try {
                $exe = & py "-$ver" -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $exe) { $candidates.Add([string]$exe) }
            } catch {
            }
        }
    }

    foreach ($name in @("python", "python3")) {
        if (Test-Command $name) {
            try {
                $exe = & $name -c "import sys; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $exe) { $candidates.Add([string]$exe) }
            } catch {
            }
        }
    }

    $paths = @(
        "$env:LocalAppData\Programs\Python\Python312\python.exe",
        "$env:LocalAppData\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe"
    )
    foreach ($path in $paths) {
        if (Test-Path -LiteralPath $path) { $candidates.Add($path) }
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        $info = Get-PythonInfo $candidate
        if ($null -ne $info -and $info.major -eq 3 -and $info.minor -ge 10 -and $info.minor -le 12 -and $info.arch -eq "64bit") {
            return [string]$info.exe
        }
    }
    return $null
}

function Install-PythonIfMissing {
    $python = Find-Python
    if ($python) {
        $info = Get-PythonInfo $python
        Write-Log "Python OK: $($info.version) at $python"
        return $python
    }
    if ($CheckOnly) {
        Write-Log "Python missing: install Python 3.10-3.12 x64 before running app." "WARN"
        return $null
    }

    $versions = @($PythonVersion, "3.12.10", "3.12.9", "3.11.9") | Select-Object -Unique
    $candidates = foreach ($version in $versions) {
        [pscustomobject]@{
            Version = $version
            Url = "https://www.python.org/ftp/python/$version/python-$version-amd64.exe"
            Destination = Join-Path $DownloadDir ("python-{0}-amd64.exe" -f $version)
        }
    }
    $selected = Invoke-DownloadFirstAvailable -Candidates $candidates
    Invoke-Exe -FilePath $selected.Destination -Arguments @("/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1", "Include_pip=1", "Include_test=0", "SimpleInstall=1") -Name "Python $($selected.Version)"

    $python = Find-Python
    if (-not $python) {
        throw "Python was installed but could not be found. Open a new terminal and rerun START_HERE.bat."
    }
    $info = Get-PythonInfo $python
    Write-Log "Python installed: $($info.version) at $python"
    return $python
}

function Install-VCRedistIfNeeded {
    if ($SkipVCRedist) {
        Write-Log "Skipping VC++ Redistributable by request."
        return
    }
    if (Test-VCRedistX64) {
        Write-Log "VC++ Redistributable x64 OK."
        return
    }
    if ($CheckOnly) {
        Write-Log "VC++ Redistributable x64 missing or not detected." "WARN"
        return
    }
    if (-not (Test-IsAdmin)) {
        Write-Log "VC++ Redistributable may request administrator permission." "WARN"
    }
    $installer = Join-Path $DownloadDir "vc_redist.x64.exe"
    Invoke-Download -Url "https://aka.ms/vs/17/release/vc_redist.x64.exe" -Destination $installer
    Invoke-Exe -FilePath $installer -Arguments @("/install", "/quiet", "/norestart") -Name "Microsoft VC++ Redistributable x64"
}

function Install-FFmpegIfNeeded {
    if ($SkipFfmpeg) {
        Write-Log "Skipping FFmpeg by request."
        return
    }
    if (Test-Command "ffmpeg") {
        Write-Log "FFmpeg OK: available on PATH."
        return
    }
    $targetRoot = Join-Path $ToolsDir "ffmpeg"
    $targetBin = Join-Path $targetRoot "bin"
    if (Test-Path -LiteralPath (Join-Path $targetBin "ffmpeg.exe")) {
        Add-UserPath $targetBin
        Write-Log "FFmpeg OK: $targetBin"
        return
    }
    if ($CheckOnly) {
        Write-Log "FFmpeg missing. It is recommended for uploaded/conversion audio formats." "WARN"
        return
    }

    $zip = Join-Path $DownloadDir "ffmpeg-release-essentials.zip"
    $extract = Join-Path $DownloadDir "ffmpeg_extract"
    Invoke-Download -Url "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -Destination $zip

    $rootFull = [IO.Path]::GetFullPath($Root)
    foreach ($dir in @($extract, $targetRoot)) {
        $dirFull = [IO.Path]::GetFullPath($dir)
        if (-not $dirFull.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove directory outside project: $dirFull"
        }
        if (Test-Path -LiteralPath $dirFull) {
            Remove-Item -LiteralPath $dirFull -Recurse -Force
        }
    }

    Expand-Archive -LiteralPath $zip -DestinationPath $extract -Force
    $ffmpegExe = Get-ChildItem -LiteralPath $extract -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    if (-not $ffmpegExe) { throw "Could not find ffmpeg.exe in downloaded archive." }
    $innerBin = Split-Path -Parent $ffmpegExe.FullName
    $innerRoot = Split-Path -Parent $innerBin
    Copy-Item -LiteralPath $innerRoot -Destination $targetRoot -Recurse -Force
    Add-UserPath $targetBin
    Write-Log "FFmpeg installed: $targetBin"
}

function Update-ModelConfig {
    $modelRootFull = [IO.Path]::GetFullPath($ModelRoot)
    if ($CheckOnly) {
        Write-Log "Model root configured/check target: $modelRootFull"
        return
    }
    New-Item -ItemType Directory -Path $modelRootFull -Force | Out-Null
    $configPath = Join-Path $Root "model_paths.json"
    $config = $null
    if (Test-Path -LiteralPath $configPath) {
        try {
            $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
            $config = $null
        }
    }
    if ($null -eq $config) {
        $config = [pscustomobject]@{
            model_root = $modelRootFull
            recommended_model = "kokoro"
            models = [pscustomobject]@{}
        }
    }
    $config.model_root = $modelRootFull
    if (-not $config.models) {
        $config | Add-Member -MemberType NoteProperty -Name models -Value ([pscustomobject]@{})
    }
    $models = @{
        kokoro = @{
            path = (Join-Path $modelRootFull "Kokoro-Vietnamese")
            repo = "contextboxai/Kokoro-Vietnamese"
        }
        vieneu = @{
            path = (Join-Path $modelRootFull "VieNeu-TTS-v3-Turbo")
            repo = "pnnbao-ump/VieNeu-TTS-v3-Turbo"
        }
    }
    foreach ($key in $models.Keys) {
        if (-not $config.models.PSObject.Properties[$key]) {
            $config.models | Add-Member -MemberType NoteProperty -Name $key -Value ([pscustomobject]@{})
        }
        $config.models.$key | Add-Member -Force -MemberType NoteProperty -Name path -Value $models[$key].path
        $config.models.$key | Add-Member -Force -MemberType NoteProperty -Name repo -Value $models[$key].repo
    }
    $config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $configPath -Encoding UTF8
    Write-Log "Model config saved: $configPath"
}

function Install-AppVenv {
    param([string]$Python)
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    $venvRoot = Join-Path $Root ".venv"
    $venvInfo = Get-PythonInfo $venvPython
    $venvCompatible = $false
    if ($null -ne $venvInfo -and $venvInfo.major -eq 3 -and $venvInfo.minor -ge 10 -and $venvInfo.minor -le 12 -and $venvInfo.arch -eq "64bit") {
        $venvCompatible = $true
    }
    if ($CheckOnly) {
        if ($venvCompatible) {
            Write-Log "App venv OK: $venvPython"
        } elseif (Test-Path -LiteralPath $venvPython) {
            Write-Log "App venv exists but uses Python $($venvInfo.version). Installer will recreate it with Python 3.10-3.12." "WARN"
        } else {
            Write-Log "App venv missing: $venvPython" "WARN"
        }
        return $venvPython
    }
    if (-not $Python) {
        throw "Python is required before creating app venv."
    }
    if ((Test-Path -LiteralPath $venvPython) -and -not $venvCompatible) {
        $backupVenv = Join-Path $Root (".venv.backup-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
        Write-Log "Existing app venv is not in Python 3.10-3.12 range; moving it to $backupVenv"
        Move-Item -LiteralPath $venvRoot -Destination $backupVenv -Force
    }
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Invoke-Python -Python $Python -Arguments @("-m", "venv", $venvRoot) -Name "Create app virtual environment"
    }
    Invoke-Python -Python $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel") -Name "Upgrade app pip"
    Invoke-Python -Python $venvPython -Arguments @("-m", "pip", "install", "-r", (Join-Path $Root "requirements.txt")) -Name "Install app requirements"
    return $venvPython
}

function Install-ModelRuntimes {
    param([string]$VenvPython)
    if ($SkipModelRuntimes) {
        Write-Log "Skipping model runtime bootstrap by request."
        return
    }
    if ($CheckOnly) {
        foreach ($key in @("vieneu", "kokoro")) {
            $runtimePython = Join-Path $Root "runtimes\$key\.venv\Scripts\python.exe"
            if (Test-Path -LiteralPath $runtimePython) {
                Write-Log "Runtime $key OK: $runtimePython"
            } else {
                Write-Log "Runtime $key missing. It will be created on first load." "WARN"
            }
        }
        return
    }
    $code = @"
import app
for key in ("vieneu", "kokoro"):
    try:
        python, message = app.ensure_engine_runtime(key)
        print(f"[OK] {key}: {python}")
        if message:
            print(message)
    except Exception as exc:
        print(f"[WARN] {key} runtime was not fully prepared: {exc}")
"@
    Invoke-Python -Python $VenvPython -Arguments @("-c", $code) -Name "Bootstrap model runtimes"
}

function Install-GpuTorchIfRequested {
    if (-not $InstallGpuTorch) { return }
    if ($CheckOnly) {
        Write-Log "GPU torch install requested, but CheckOnly mode will not install packages."
        return
    }
    if (-not (Test-Command "nvidia-smi")) {
        Write-Log "nvidia-smi not found; skipping GPU torch install. Install NVIDIA driver first." "WARN"
        return
    }
    $runtimePythons = @(
        (Join-Path $Root "runtimes\vieneu\.venv\Scripts\python.exe"),
        (Join-Path $Root "runtimes\kokoro\.venv\Scripts\python.exe")
    ) | Where-Object { Test-Path -LiteralPath $_ }
    foreach ($python in $runtimePythons) {
        Invoke-Python -Python $python -Arguments @("-m", "pip", "install", "--upgrade", "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu118") -Name "Install CUDA 11.8 PyTorch into $python"
    }
}

function Stop-ExistingTtsProcesses {
    if ($CheckOnly) { return }
    $escapedRoot = [Regex]::Escape($Root)
    $processes = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -like "python*" -and $_.CommandLine -and (
            $_.CommandLine -match $escapedRoot -and (
                $_.CommandLine -like "*app.py*" -or
                $_.CommandLine -like "*kokoro_worker.py*" -or
                $_.CommandLine -like "*vieneu_worker.py*"
            )
        )
    }
    foreach ($proc in $processes) {
        Write-Log "Stopping existing TTS process before install: PID $($proc.ProcessId)"
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Start-TtsStudio {
    param([string]$VenvPython)
    if ($NoStart -or $CheckOnly) { return }
    $listeners = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" }
    foreach ($listener in $listeners) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
        if ($proc -and $proc.CommandLine -like "*TTS-Unified*app.py*") {
            Write-Log "Stopping existing TTS Studio process on port ${Port}: PID $($listener.OwningProcess)"
            Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
        } else {
            throw "Port $Port is already used by PID $($listener.OwningProcess). Close that app or rerun with -Port another_number."
        }
    }

    $appPath = Join-Path $Root "app.py"
    $stdout = Join-Path $Root "tts_server_$Port.log"
    $stderr = Join-Path $Root "tts_server_$Port.err.log"
    $process = Start-Process -FilePath $VenvPython -ArgumentList @($appPath, "--server-name", "127.0.0.1", "--server-port", "$Port") -WorkingDirectory $Root -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 4
    Write-Log "TTS Studio started: PID $($process.Id), URL http://127.0.0.1:$Port"
}

function Show-EnvironmentReport {
    Write-Log "Project root: $Root"
    Write-Log "Windows: $([Environment]::OSVersion.VersionString)"
    Write-Log "64-bit OS: $([Environment]::Is64BitOperatingSystem)"
    Write-Log "Admin: $(Test-IsAdmin)"
    Write-Log "winget: $(if (Test-Command 'winget') { 'available' } else { 'missing' })"
    Write-Log "Git: $(if (Test-Command 'git') { 'available' } else { 'optional/missing' })"
    Write-Log "FFmpeg: $(if (Test-Command 'ffmpeg') { 'available' } else { 'missing' })"
    Write-Log "NVIDIA GPU: $(if (Test-Command 'nvidia-smi') { 'nvidia-smi available' } else { 'not detected or driver missing' })"
    try {
        $drive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($Root).Substring(0,1))
        Write-Log ("Free space on project drive: {0:N1} GB" -f ($drive.Free / 1GB))
    } catch {
    }
}

try {
    Write-Log "TTS Studio beginner installer started."
    Show-EnvironmentReport

    if (-not [Environment]::Is64BitOperatingSystem) {
        throw "This installer requires 64-bit Windows."
    }

    $python = Install-PythonIfMissing
    Install-VCRedistIfNeeded
    Install-FFmpegIfNeeded
    Update-ModelConfig
    Stop-ExistingTtsProcesses
    $venvPython = Install-AppVenv -Python $python
    Install-ModelRuntimes -VenvPython $venvPython
    Install-GpuTorchIfRequested
    Start-TtsStudio -VenvPython $venvPython

    if ($CheckOnly) {
        Write-Log "Check finished. Rerun START_HERE.bat without -CheckOnly to install missing items."
    } else {
        Write-Log "Install finished. Open http://127.0.0.1:$Port"
    }
} catch {
    Write-Log $_.Exception.Message "ERROR"
    Write-Log "Installer failed. See: $InstallLog" "ERROR"
    exit 1
}
