"""
Binds Memgraph↔API validation events to the active pytest test (for HTML/JSON reports).

Uses a context var so ``run_validation_pair`` can record comparisons without pytest imports.
"""

from __future__ import annotations

import contextvars
from collections import defaultdict
from typing import Any, Dict, List, Optional

_ctx_nodeid: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "datacomns_report_nodeid", default=None
)
# nodeid -> list of comparison dicts (multiple pairs per test possible)
_comparisons: Dict[str, List[Dict[str, Any]]] = defaultdict(list)


def set_active_test_nodeid(nodeid: str) -> contextvars.Token[Optional[str]]:
    """Call at test start; reset with reset_active_test_nodeid(token)."""
    return _ctx_nodeid.set(nodeid)


def reset_active_test_nodeid(token: contextvars.Token[Optional[str]]) -> None:
    _ctx_nodeid.reset(token)


def record_api_db_comparison(event: Dict[str, Any]) -> None:
    """Append one API↔DB comparison outcome for the current test."""
    nid = _ctx_nodeid.get()
    if not nid:
        return
    _comparisons[nid].append(dict(event))


def take_comparisons_for_nodeid(nodeid: str) -> List[Dict[str, Any]]:
    """Detach and return comparisons for this test (called once per test from reporter)."""
    return list(_comparisons.pop(nodeid, []))


def clear_all_comparisons() -> None:
    _comparisons.clear()
