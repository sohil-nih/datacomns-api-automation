#!/usr/bin/env bash
# Double-click in Finder to start the Datacomns Test Runner UI (venv optional).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi
PYTHON="${PYTHON:-python3}"
"$PYTHON" launcher.py
