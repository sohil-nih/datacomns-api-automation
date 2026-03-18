"""
DCC TC01 — verify organizations (GET /organization vs Memgraph).

REST: https://dcc-qa.ccdi.cancer.gov/api/v1/organization

Cypher: key ``DCC_TC01_verify_organizations`` in ``memgraph_validation/cypher/queries.yaml``.

Pair: ``memgraph_validation/pairs/organization_list_vs_study_personnel_institutions.yaml``
"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework.memgraph.pairs import load_validation_pairs
from framework.memgraph.runner import run_validation_pair

_MEMGRAPH_ROOT = Path(__file__).resolve().parents[2] / "memgraph_validation"
_PAIR_ID = "dcc_organization_vs_study_personnel_institutions"

pytestmark = [pytest.mark.smoke, pytest.mark.project_dcc, pytest.mark.memgraph_api]

_PAIR = next(
    (p for p in load_validation_pairs(_MEMGRAPH_ROOT) if p.id == _PAIR_ID),
    None,
)


def test_DCC_TC01_verify_organizations(
    api_client,
    memgraph_client,
    require_live_api,
) -> None:
    assert _PAIR is not None, (
        f"Missing pair {_PAIR_ID!r} under projects/dcc/memgraph_validation/pairs/"
    )
    _, summary = run_validation_pair(_PAIR, memgraph_client, api_client)
    assert summary["pair_id"] == _PAIR_ID
