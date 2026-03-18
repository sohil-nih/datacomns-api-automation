#!/usr/bin/env bash
# All tests under projects/ (smoke + regression + future markers)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:-}:$ROOT"
exec pytest projects "$@"
