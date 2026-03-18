#!/usr/bin/env bash
# Full regression for all registered project tests (expand paths as you add projects)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:-}:$ROOT"
exec pytest projects -m regression "$@"
