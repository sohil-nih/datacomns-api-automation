"""
DCC: Memgraph Cypher + REST pairs under memgraph_validation/pairs/.

  pytest projects/dcc/tests/memgraph_api -m \"memgraph_api and smoke\" -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from framework.memgraph.pairs import load_validation_pairs
from framework.memgraph.runner import run_validation_pair

_ROOT = Path(__file__).resolve().parents[2] / "memgraph_validation"
# DCC TC01 / TC02 run as named tests under api_smoke/
_NAMED_DCC_PAIR_IDS = frozenset(
    {
        "dcc_organization_vs_study_personnel_institutions",
        "dcc_sample_tumor_grade_count",
        "dcc_file_summary_total",
        "dcc_subject_by_sex_count",
        "dcc_namespace_study_ids_in_api",
    }
)
_ALL_PAIRS = [p for p in load_validation_pairs(_ROOT) if p.id not in _NAMED_DCC_PAIR_IDS]


def _marks(p):
    m = [pytest.mark.memgraph_api, pytest.mark.project_dcc]
    if p.has_tag("smoke"):
        m.append(pytest.mark.smoke)
    if p.has_tag("regression"):
        m.append(pytest.mark.regression)
    return m


@pytest.mark.parametrize(
    "pair",
    [pytest.param(p, id=p.id, marks=_marks(p)) for p in _ALL_PAIRS],
)
def test_dcc_memgraph_api_validation_pair(
    pair, memgraph_client, api_client, require_live_api
):
    _, summary = run_validation_pair(pair, memgraph_client, api_client)
    assert summary["pair_id"] == pair.id
