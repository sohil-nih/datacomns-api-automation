"""
DCC TC05 — namespace catalog vs Memgraph study ids.

REST: ``GET /api/v1/namespace`` (root array; each entry has ``id.name``, ``id.organization``).

Memgraph: distinct ``study.study_id`` for studies reached via
participant → consent_group → study (see ``namespace_study_ids_from_participants.cypher``).

Rule: every such graph study id must appear as some namespace ``id.name`` in the API.

**Note:** The sex-count Cypher you may have seen for TC04 does not apply here; that pairs with
``/subject/by/sex/count``. This case validates the namespace catalog against graph study ids.

Pair: ``memgraph_validation/pairs/namespace_study_ids_vs_api.yaml``
"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework.memgraph.pairs import load_validation_pairs
from framework.memgraph.runner import run_validation_pair

_MEMGRAPH_ROOT = Path(__file__).resolve().parents[2] / "memgraph_validation"
_PAIR_ID = "dcc_namespace_study_ids_in_api"

pytestmark = [pytest.mark.smoke, pytest.mark.project_dcc, pytest.mark.memgraph_api]

_PAIR = next(
    (p for p in load_validation_pairs(_MEMGRAPH_ROOT) if p.id == _PAIR_ID),
    None,
)


def test_DCC_TC05_verify_namespace(
    api_client,
    memgraph_client,
    require_live_api,
) -> None:
    assert _PAIR is not None, (
        f"Missing pair {_PAIR_ID!r} under projects/dcc/memgraph_validation/pairs/"
    )
    _, summary = run_validation_pair(_PAIR, memgraph_client, api_client)
    assert summary["pair_id"] == _PAIR_ID
