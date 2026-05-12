#!/usr/bin/env bash
# Smoke suite: DCC fast gate (api_smoke + memgraph pairs tagged smoke, unless skipped)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:-}:$ROOT"
exec pytest projects/dcc -m smoke "$@"
