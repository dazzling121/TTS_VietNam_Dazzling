#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "TTS Studio has not been installed yet."
  echo "Please run ./START_HERE.sh one time first."
  exit 1
fi

export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

echo "Starting TTS Studio..."
echo "Local URL: http://127.0.0.1:7870"
echo

exec "$PYTHON" "$ROOT_DIR/app.py" --server-name 127.0.0.1 --server-port 7870 "$@"
