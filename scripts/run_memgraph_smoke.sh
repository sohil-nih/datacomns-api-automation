#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec pytest projects/federation/tests/memgraph -m "memgraph_api and smoke" -v "$@"
