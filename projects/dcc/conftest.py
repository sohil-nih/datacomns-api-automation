"""
DCC project fixtures (Data Commons API + optional Memgraph for this stack).
"""

from __future__ import annotations

import os

import pytest

from framework.config.loader import get_project_config
from framework.http.client import ApiClient

PROJECT_SLUG = "dcc"


@pytest.fixture(scope="session")
def project_slug() -> str:
    return PROJECT_SLUG


@pytest.fixture(scope="session")
def project_config(project_slug: str):
    return get_project_config(project_slug)


@pytest.fixture(scope="session")
def api_client(project_config):
    timeout = float(os.environ.get("DATACOMNS_HTTP_TIMEOUT", "60"))
    return ApiClient.from_project_config(project_config, timeout_seconds=timeout)


@pytest.fixture
def require_live_api() -> None:
    if os.environ.get("DATACOMNS_SKIP_LIVE_TESTS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        pytest.skip("DATACOMNS_SKIP_LIVE_TESTS is set")
