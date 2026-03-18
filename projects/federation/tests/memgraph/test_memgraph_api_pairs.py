"""
Parametrized Memgraph Cypher + REST pairs from memgraph_validation/pairs/*.yaml.

Run smoke pairs:
  pytest projects/federation/tests/memgraph -m \"memgraph_api and smoke\" -v

Run all pairs:
  pytest projects/federation/tests/memgraph -m memgraph_api -v

Requires MEMGRAPH_* env and network to QA API unless skipped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework.memgraph.pairs import load_validation_pairs
from framework.memgraph.runner import run_validation_pair

# tests/memgraph -> parents[2] == federation project root
_ROOT = Path(__file__).resolve().parents[2] / "memgraph_validation"
_ALL_PAIRS = load_validation_pairs(_ROOT)


def _marks(p):
    m = [pytest.mark.memgraph_api, pytest.mark.project_federation]
    if p.has_tag("smoke"):
        m.append(pytest.mark.smoke)
    if p.has_tag("regression"):
        m.append(pytest.mark.regression)
    return m


@pytest.mark.parametrize(
    "pair",
    [pytest.param(p, id=p.id, marks=_marks(p)) for p in _ALL_PAIRS],
)
def test_memgraph_api_validation_pair(pair, memgraph_client, api_client, require_live_api):
    """Execute Cypher, call API, compare per pair.comparison."""
    _, summary = run_validation_pair(pair, memgraph_client, api_client)
    assert summary["pair_id"] == pair.id
    assert summary["graph_row_count"] >= 0
