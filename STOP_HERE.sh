#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

case "$(uname -s)" in
  Darwin|Linux)
    bash "$ROOT_DIR/stop_tool_unix.sh" "$@"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    echo "Windows detected from a Unix-like shell."
    echo "Please run STOP_HERE.bat from Explorer or PowerShell for the Windows stop script."
    exit 1
    ;;
  *)
    echo "Unsupported operating system: $(uname -s)"
    exit 1
    ;;
esac
