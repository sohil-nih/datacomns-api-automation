#!/usr/bin/env bash
# DCC API performance run (positive OpenAPI cases only; reports under reports/dcc/perf).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:$PYTHONPATH}"
python -m framework.contract_runner.dcc_perf_cli "$@"
