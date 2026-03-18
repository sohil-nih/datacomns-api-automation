"""
Memgraph Bolt session fixture for cross-validation tests.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from framework.memgraph.client import memgraph_client_from_env

MEMGRAPH_VALIDATION_ROOT = Path(__file__).resolve().parents[2] / "memgraph_validation"


@pytest.fixture(scope="session")
def memgraph_validation_root() -> Path:
    return MEMGRAPH_VALIDATION_ROOT


@pytest.fixture(scope="session")
def memgraph_client():
    """
    Live Memgraph connection. Skips tests when env is missing or DB unreachable.

    - ``DATACOMNS_SKIP_MEMGRAPH_TESTS=1`` — skip all Memgraph pairs.
    - Missing ``MEMGRAPH_PASSWORD`` / URI — skip (e.g. CI without secrets).
    """
    if os.environ.get("DATACOMNS_SKIP_MEMGRAPH_TESTS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        pytest.skip("DATACOMNS_SKIP_MEMGRAPH_TESTS is set")

    client = None
    try:
        client = memgraph_client_from_env()
        client.verify_connectivity()
    except ValueError as e:
        pytest.skip(str(e))
    except Exception as e:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        pytest.skip(f"Memgraph not reachable: {e}")

    yield client

    try:
        client.close()
    except Exception:
        pass
