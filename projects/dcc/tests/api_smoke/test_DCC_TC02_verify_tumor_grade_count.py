"""
DCC TC02 — tumor grade sample counts (GET /sample/by/tumor_grade/count vs Memgraph).

REST: ``/api/v1/sample/by/tumor_grade/count``

Cypher: ``memgraph_validation/cypher/sample_tumor_grade_count.cypher``

Pair: ``memgraph_validation/pairs/sample_tumor_grade_count.yaml``
"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework.memgraph.pairs import load_validation_pairs
from framework.memgraph.runner import run_validation_pair

_MEMGRAPH_ROOT = Path(__file__).resolve().parents[2] / "memgraph_validation"
_PAIR_ID = "dcc_sample_tumor_grade_count"

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.regression,
    pytest.mark.dcc_regression,
    pytest.mark.project_dcc,
    pytest.mark.memgraph_api,
]

_PAIR = next(
    (p for p in load_validation_pairs(_MEMGRAPH_ROOT) if p.id == _PAIR_ID),
    None,
)


def test_DCC_TC02_verify_tumor_grade_count(
    api_client,
    memgraph_client,
    require_live_api,
) -> None:
    assert _PAIR is not None, (
        f"Missing pair {_PAIR_ID!r} under projects/dcc/memgraph_validation/pairs/"
    )
    _, summary = run_validation_pair(_PAIR, memgraph_client, api_client)
    assert summary["pair_id"] == _PAIR_ID
