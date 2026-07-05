#!/usr/bin/env bash
set -Eeuo pipefail

PORT=7870
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port|-Port)
      PORT="${2:?Missing port value}"
      shift
      ;;
    --dry-run|-DryRun)
      DRY_RUN=1
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
STOP_LOG="$LOG_DIR/stop-$(date +%Y%m%d-%H%M%S).log"
LATEST_LOG="$LOG_DIR/stop-latest.log"

log() {
  local level="${2:-INFO}"
  local line
  line="[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $1"
  echo "$line"
  printf '%s\n' "$line" >> "$STOP_LOG"
  cp "$STOP_LOG" "$LATEST_LOG" 2>/dev/null || true
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

stop_pid() {
  local pid="$1"
  local reason="$2"
  [[ -z "$pid" || "$pid" == "$$" ]] && return
  if ! ps -p "$pid" >/dev/null 2>&1; then
    return
  fi
  local cmd
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  log "Stopping PID $pid ($reason): $cmd"
  [[ $DRY_RUN -eq 1 ]] && return
  kill "$pid" 2>/dev/null || true
}

project_pids() {
  if command_exists pgrep; then
    pgrep -f "$ROOT/.*(app.py|kokoro_worker.py|vieneu_worker.py)" 2>/dev/null || true
  else
    ps ax -o pid= -o command= | awk -v root="$ROOT" '
      index($0, root) && ($0 ~ /app\.py|kokoro_worker\.py|vieneu_worker\.py/) { print $1 }
    '
  fi
}

log "TTS Studio safe stop started."
log "Project root: $ROOT"

pids="$(project_pids | sort -u || true)"

if [[ -n "$pids" ]]; then
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [[ "$cmd" == *"kokoro_worker.py"* || "$cmd" == *"vieneu_worker.py"* ]]; then
      stop_pid "$pid" "model worker"
    fi
  done <<< "$pids"

  sleep 0.5

  while read -r pid; do
    [[ -z "$pid" ]] && continue
    cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [[ "$cmd" == *"app.py"* ]]; then
      stop_pid "$pid" "web app"
    fi
  done <<< "$pids"
fi

if command_exists lsof; then
  port_pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$port_pids" ]]; then
    while read -r pid; do
      [[ -z "$pid" ]] && continue
      cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
      if [[ "$cmd" == *"$ROOT"* ]]; then
        stop_pid "$pid" "listener on port $PORT"
      else
        log "Port $PORT is used by a non-project process; not stopping PID $pid." "WARN"
      fi
    done <<< "$port_pids"
  fi
fi

sleep 0.5
remaining="$(project_pids | sort -u || true)"
if [[ -z "$remaining" ]]; then
  log "TTS Studio stopped. No project app/worker process remains."
else
  while read -r pid; do
    [[ -z "$pid" ]] && continue
    log "Still running PID $pid: $(ps -p "$pid" -o command= 2>/dev/null || true)" "WARN"
  done <<< "$remaining"
fi
