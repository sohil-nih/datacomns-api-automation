#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec pytest projects/dcc/tests/memgraph_api -m "memgraph_api and smoke" -v "$@"
