"""
DCC TC04 — subject count by sex (GET /subject/by/sex/count vs Memgraph).

REST: ``/api/v1/subject/by/sex/count``

Cypher: ``memgraph_validation/cypher/subject_by_sex_count.cypher``

Pair: ``memgraph_validation/pairs/subject_by_sex_count.yaml``
"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework.memgraph.pairs import load_validation_pairs
from framework.memgraph.runner import run_validation_pair

_MEMGRAPH_ROOT = Path(__file__).resolve().parents[2] / "memgraph_validation"
_PAIR_ID = "dcc_subject_by_sex_count"

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


def test_DCC_TC04_verify_subjects_count_by_sex(
    api_client,
    memgraph_client,
    require_live_api,
) -> None:
    assert _PAIR is not None, (
        f"Missing pair {_PAIR_ID!r} under projects/dcc/memgraph_validation/pairs/"
    )
    _, summary = run_validation_pair(_PAIR, memgraph_client, api_client)
    assert summary["pair_id"] == _PAIR_ID
