#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "App virtual environment is missing. Run ./START_HERE.sh first."
  exit 1
fi

exec "$PYTHON" "$ROOT_DIR/app.py" --server-name 127.0.0.1 --server-port 7870
