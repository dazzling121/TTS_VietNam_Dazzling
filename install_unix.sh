#!/usr/bin/env bash
set -Eeuo pipefail

CHECK_ONLY=0
NO_START=0
SKIP_FFMPEG=0
SKIP_MODEL_RUNTIMES=0
INSTALL_GPU_TORCH=0
PORT=7870
MODEL_ROOT="${HOME}/TTS/Models"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only|-CheckOnly) CHECK_ONLY=1 ;;
    --no-start|-NoStart) NO_START=1 ;;
    --skip-ffmpeg|-SkipFfmpeg) SKIP_FFMPEG=1 ;;
    --skip-model-runtimes|-SkipModelRuntimes) SKIP_MODEL_RUNTIMES=1 ;;
    --install-gpu-torch|-InstallGpuTorch) INSTALL_GPU_TORCH=1 ;;
    --port|-Port)
      PORT="${2:?Missing port value}"
      shift
      ;;
    --model-root|-ModelRoot)
      MODEL_ROOT="${2:?Missing model root value}"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
  shift
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
INSTALL_LOG="$LOG_DIR/install-$(date +%Y%m%d-%H%M%S).log"
LATEST_LOG="$LOG_DIR/install-latest.log"

log() {
  local level="${2:-INFO}"
  local line
  line="[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $1"
  echo "$line" >&2
  printf '%s\n' "$line" >> "$INSTALL_LOG"
  cp "$INSTALL_LOG" "$LATEST_LOG" 2>/dev/null || true
}

die() {
  log "$1" "ERROR"
  log "Installer failed. See: $INSTALL_LOG" "ERROR"
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

run_cmd() {
  local label="$1"
  shift
  log "Running: $label"
  "$@" 2>&1 | tee -a "$INSTALL_LOG"
  local status=${PIPESTATUS[0]}
  cp "$INSTALL_LOG" "$LATEST_LOG" 2>/dev/null || true
  if [[ $status -ne 0 ]]; then
    die "$label failed with exit code $status"
  fi
}

sudo_cmd() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

detect_os() {
  case "$(uname -s)" in
    Darwin) echo "macos" ;;
    Linux) echo "linux" ;;
    *) echo "unsupported" ;;
  esac
}

python_info() {
  local py="$1"
  "$py" - <<'PY' 2>/dev/null || true
import json, platform, sys
print(json.dumps({
    "exe": sys.executable,
    "version": sys.version.split()[0],
    "major": sys.version_info[0],
    "minor": sys.version_info[1],
    "arch": platform.machine(),
}))
PY
}

python_is_supported() {
  local py="$1"
  local result
  result="$("$py" - <<'PY' 2>/dev/null || true
import sys
ok = sys.version_info.major == 3 and 10 <= sys.version_info.minor <= 12
print("1" if ok else "0")
PY
)"
  [[ "$result" == "1" ]]
}

find_python() {
  local candidates=(python3.12 python3.11 python3.10 python3)
  local py
  for py in "${candidates[@]}"; do
    if command_exists "$py" && python_is_supported "$py"; then
      command -v "$py"
      return 0
    fi
  done
  return 1
}

install_macos_packages() {
  log "Detected macOS."
  if ! command_exists brew; then
    if [[ $CHECK_ONLY -eq 1 ]]; then
      log "Homebrew missing. It will be installed from brew.sh when running full install." "WARN"
      return
    fi
    log "Homebrew missing. Installing Homebrew from official script."
    run_cmd "Install Homebrew" /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi

  if command_exists brew; then
    eval "$($(command -v brew) shellenv)" || true
  elif [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)" || true
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)" || true
  fi

  if [[ $CHECK_ONLY -eq 1 ]]; then
    log "Homebrew: $(command -v brew 2>/dev/null || echo missing)"
    return
  fi

  local packages=(python@3.12 git)
  if [[ $SKIP_FFMPEG -eq 0 ]]; then
    packages+=(ffmpeg)
  fi
  run_cmd "Install macOS packages with Homebrew" brew install "${packages[@]}"
}

install_linux_packages() {
  log "Detected Linux."
  if [[ $CHECK_ONLY -eq 1 ]]; then
    log "Package manager: $(command -v apt-get || command -v dnf || command -v pacman || command -v zypper || command -v apk || echo unknown)"
    return
  fi

  if command_exists apt-get; then
    run_cmd "apt-get update" sudo_cmd apt-get update
    local packages=(python3 python3-venv python3-pip git curl unzip build-essential)
    if [[ $SKIP_FFMPEG -eq 0 ]]; then packages+=(ffmpeg); fi
    run_cmd "Install Linux packages with apt" sudo_cmd apt-get install -y "${packages[@]}"
  elif command_exists dnf; then
    local packages=(python3 python3-pip git curl unzip gcc gcc-c++ make)
    if [[ $SKIP_FFMPEG -eq 0 ]]; then packages+=(ffmpeg); fi
    run_cmd "Install Linux packages with dnf" sudo_cmd dnf install -y "${packages[@]}"
  elif command_exists pacman; then
    local packages=(python python-pip git curl unzip base-devel)
    if [[ $SKIP_FFMPEG -eq 0 ]]; then packages+=(ffmpeg); fi
    run_cmd "Install Linux packages with pacman" sudo_cmd pacman -Sy --needed --noconfirm "${packages[@]}"
  elif command_exists zypper; then
    local packages=(python3 python3-pip git curl unzip gcc gcc-c++ make)
    if [[ $SKIP_FFMPEG -eq 0 ]]; then packages+=(ffmpeg); fi
    run_cmd "Install Linux packages with zypper" sudo_cmd zypper --non-interactive install "${packages[@]}"
  elif command_exists apk; then
    local packages=(python3 py3-pip git curl unzip build-base)
    if [[ $SKIP_FFMPEG -eq 0 ]]; then packages+=(ffmpeg); fi
    run_cmd "Install Linux packages with apk" sudo_cmd apk add "${packages[@]}"
  else
    die "No supported Linux package manager found. Install Python 3.10-3.12, pip, venv, git, curl, unzip, and FFmpeg manually."
  fi
}

show_report() {
  local os_name="$1"
  log "Project root: $ROOT"
  log "Detected OS: $os_name"
  log "Kernel: $(uname -a)"
  log "Architecture: $(uname -m)"
  log "Git: $(command -v git 2>/dev/null || echo missing)"
  log "FFmpeg: $(command -v ffmpeg 2>/dev/null || echo missing)"
  log "NVIDIA GPU: $(command -v nvidia-smi 2>/dev/null || echo not-detected)"
  log "Model root: $MODEL_ROOT"
}

ensure_python() {
  local py
  if py="$(find_python)"; then
    log "Python OK: $(python_info "$py")"
    echo "$py"
    return 0
  fi
  if [[ $CHECK_ONLY -eq 1 ]]; then
    log "Python 3.10-3.12 missing. Full install will try the OS package manager." "WARN"
    return 1
  fi
  die "Python 3.10-3.12 is still missing after package install."
}

venv_python_path() {
  echo "$ROOT/.venv/bin/python"
}

venv_is_supported() {
  local vpy
  vpy="$(venv_python_path)"
  [[ -x "$vpy" ]] && python_is_supported "$vpy"
}

install_app_venv() {
  local py="$1"
  local vpy
  vpy="$(venv_python_path)"

  if [[ $CHECK_ONLY -eq 1 ]]; then
    if venv_is_supported; then
      log "App venv OK: $vpy"
    elif [[ -x "$vpy" ]]; then
      log "App venv exists but is not Python 3.10-3.12. Full install will recreate it." "WARN"
    else
      log "App venv missing: $vpy" "WARN"
    fi
    return
  fi

  if [[ -x "$vpy" ]] && ! venv_is_supported; then
    local backup="$ROOT/.venv.backup-$(date +%Y%m%d-%H%M%S)"
    log "Existing app venv is incompatible; moving to $backup"
    mv "$ROOT/.venv" "$backup"
  fi
  if [[ ! -x "$vpy" ]]; then
    run_cmd "Create app virtual environment" "$py" -m venv "$ROOT/.venv"
  fi
  run_cmd "Upgrade app pip" "$vpy" -m pip install --upgrade pip setuptools wheel
  run_cmd "Install app requirements" "$vpy" -m pip install -r "$ROOT/requirements.txt"
}

update_model_config() {
  [[ $CHECK_ONLY -eq 1 ]] && return
  mkdir -p "$MODEL_ROOT"
  local vpy
  vpy="$(venv_python_path)"
  TTS_STUDIO_MODEL_ROOT="$MODEL_ROOT" "$vpy" - <<'PY'
import json, os
from pathlib import Path
root = Path(os.environ["TTS_STUDIO_MODEL_ROOT"]).expanduser()
config_path = Path("model_paths.json")
if config_path.exists():
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        config = {}
else:
    config = {}
config["model_root"] = str(root)
config.setdefault("recommended_model", "kokoro")
config.setdefault("models", {})
config["models"]["kokoro"] = {
    "path": str(root / "Kokoro-Vietnamese"),
    "repo": "contextboxai/Kokoro-Vietnamese",
}
config["models"]["vieneu"] = {
    "path": str(root / "VieNeu-TTS-v3-Turbo"),
    "repo": "pnnbao-ump/VieNeu-TTS-v3-Turbo",
}
config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
PY
  log "Model config saved to model_paths.json"
}

bootstrap_model_runtimes() {
  if [[ $SKIP_MODEL_RUNTIMES -eq 1 ]]; then
    log "Skipping model runtime bootstrap by request."
    return
  fi
  if [[ $CHECK_ONLY -eq 1 ]]; then
    for key in vieneu kokoro; do
      local rpy="$ROOT/runtimes/$key/.venv/bin/python"
      if [[ -x "$rpy" ]]; then
        log "Runtime $key OK: $rpy"
      else
        log "Runtime $key missing. It will be created on first load." "WARN"
      fi
    done
    return
  fi
  local vpy
  vpy="$(venv_python_path)"
  TTS_STUDIO_MODEL_ROOT="$MODEL_ROOT" run_cmd "Bootstrap model runtimes" "$vpy" - <<'PY'
import app
for key in ("vieneu", "kokoro"):
    try:
        python, message = app.ensure_engine_runtime(key)
        print(f"[OK] {key}: {python}")
        if message:
            print(message)
    except Exception as exc:
        print(f"[WARN] {key} runtime was not fully prepared: {exc}")
PY
}

install_gpu_torch_if_requested() {
  [[ $INSTALL_GPU_TORCH -eq 0 ]] && return
  [[ $CHECK_ONLY -eq 1 ]] && { log "GPU torch install requested; CheckOnly will not install." "WARN"; return; }
  local os_name="$1"
  local runtimes=("$ROOT/runtimes/vieneu/.venv/bin/python" "$ROOT/runtimes/kokoro/.venv/bin/python")
  for rpy in "${runtimes[@]}"; do
    [[ -x "$rpy" ]] || continue
    if [[ "$os_name" == "macos" ]]; then
      run_cmd "Install PyTorch for macOS runtime $rpy" "$rpy" -m pip install --upgrade torch torchaudio
    elif command_exists nvidia-smi; then
      run_cmd "Install CUDA 11.8 PyTorch for Linux runtime $rpy" "$rpy" -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cu118
    else
      log "nvidia-smi missing; skipping CUDA PyTorch install for $rpy." "WARN"
    fi
  done
}

stop_existing_tts() {
  [[ $CHECK_ONLY -eq 1 ]] && return
  local pids
  pids="$(pgrep -f "$ROOT/.*(app.py|kokoro_worker.py|vieneu_worker.py)" || true)"
  [[ -z "$pids" ]] && return
  while read -r pid; do
    [[ -z "$pid" || "$pid" == "$$" ]] && continue
    log "Stopping existing TTS process before install: PID $pid"
    kill "$pid" 2>/dev/null || true
  done <<< "$pids"
}

start_tts_studio() {
  [[ $NO_START -eq 1 || $CHECK_ONLY -eq 1 ]] && return
  local vpy
  vpy="$(venv_python_path)"
  local existing=""
  if command_exists lsof; then
    existing="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  fi
  if [[ -n "$existing" ]]; then
    while read -r pid; do
      [[ -z "$pid" ]] && continue
      local cmd
      cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
      if [[ "$cmd" == *"$ROOT"* && "$cmd" == *"app.py"* ]]; then
        log "Stopping existing TTS Studio process on port $PORT: PID $pid"
        kill "$pid" 2>/dev/null || true
      else
        die "Port $PORT is already used by PID $pid. Close it or run with --port another_number."
      fi
    done <<< "$existing"
  fi
  nohup "$vpy" "$ROOT/app.py" --server-name 127.0.0.1 --server-port "$PORT" > "$ROOT/tts_server_$PORT.log" 2> "$ROOT/tts_server_$PORT.err.log" &
  local pid=$!
  sleep 4
  log "TTS Studio started: PID $pid, URL http://127.0.0.1:$PORT"
}

main() {
  local os_name
  os_name="$(detect_os)"
  [[ "$os_name" == "unsupported" ]] && die "Unsupported OS: $(uname -s)"

  log "TTS Studio cross-platform installer started."
  show_report "$os_name"

  if [[ "$os_name" == "macos" ]]; then
    install_macos_packages
  else
    install_linux_packages
  fi

  local py=""
  py="$(ensure_python || true)"
  install_app_venv "$py"
  stop_existing_tts
  update_model_config
  bootstrap_model_runtimes
  install_gpu_torch_if_requested "$os_name"
  start_tts_studio

  if [[ $CHECK_ONLY -eq 1 ]]; then
    log "Check finished. Rerun ./START_HERE.sh without --check-only to install missing items."
  else
    log "Install finished. Open http://127.0.0.1:$PORT"
  fi
}

main "$@"
