"""
DCC TC03 — file summary total (GET /file/summary vs Memgraph).

REST: ``/api/v1/file/summary`` → ``counts.total``

Cypher: ``memgraph_validation/cypher/file_summary_total.cypher``

Pair: ``memgraph_validation/pairs/file_summary_total.yaml``
"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework.memgraph.pairs import load_validation_pairs
from framework.memgraph.runner import run_validation_pair

_MEMGRAPH_ROOT = Path(__file__).resolve().parents[2] / "memgraph_validation"
_PAIR_ID = "dcc_file_summary_total"

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


def test_DCC_TC03_verify_file_summary(
    api_client,
    memgraph_client,
    require_live_api,
) -> None:
    assert _PAIR is not None, (
        f"Missing pair {_PAIR_ID!r} under projects/dcc/memgraph_validation/pairs/"
    )
    _, summary = run_validation_pair(_PAIR, memgraph_client, api_client)
    assert summary["pair_id"] == _PAIR_ID
