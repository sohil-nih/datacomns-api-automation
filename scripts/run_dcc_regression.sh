#!/usr/bin/env bash
# DCC Memgraph + API regression: TC01–TC05 (organization, tumor grade, file summary, sex count, namespace)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec pytest projects/dcc/tests/api_smoke -m dcc_regression -v "$@"
