"""
Shared DCC test fixtures (all suites under projects/dcc/tests/).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from framework.memgraph.client import memgraph_client_from_env

DCC_PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMGRAPH_VALIDATION_ROOT = DCC_PROJECT_ROOT / "memgraph_validation"

@pytest.fixture(scope="session")
def memgraph_validation_root() -> Path:
    return MEMGRAPH_VALIDATION_ROOT


@pytest.fixture(scope="session")
def memgraph_client():
    if os.environ.get("DATACOMNS_SKIP_MEMGRAPH_TESTS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        pytest.skip("DATACOMNS_SKIP_MEMGRAPH_TESTS is set")
    if os.environ.get("DATACOMNS_SKIP_MEMGRAPH_DCC_TESTS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        pytest.skip("DATACOMNS_SKIP_MEMGRAPH_DCC_TESTS is set")

    client = None
    try:
        client = memgraph_client_from_env("dcc")
        client.verify_connectivity()
    except ValueError as e:
        pytest.skip(str(e))
    except Exception as e:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        pytest.skip(f"DCC Memgraph not reachable: {e}")

    yield client

    try:
        client.close()
    except Exception:
        pass
