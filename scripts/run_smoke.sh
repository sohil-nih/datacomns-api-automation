#!/usr/bin/env bash
# Smoke suite: fast gate (includes offline config test + live API tests unless skipped)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:-}:$ROOT"
exec pytest projects/federation -m smoke "$@"
