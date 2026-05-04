#!/usr/bin/env bash
# OpenAPI-driven DCC contract suite (JSON + HTML under reports/dcc/contract).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:$PYTHONPATH}"
python -m framework.contract_runner.dcc_cli "$@"
