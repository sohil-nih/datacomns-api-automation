"""
Federation API project fixtures.

Adding a new project: copy this file, change PROJECT_SLUG, add entry in config/projects.yaml.
"""

from __future__ import annotations

import os

import pytest

from framework.config.loader import get_project_config
from framework.http.client import ApiClient

PROJECT_SLUG = "federation"


@pytest.fixture(scope="session")
def project_slug() -> str:
    """Stable slug matching config/projects.yaml."""
    return PROJECT_SLUG


@pytest.fixture(scope="session")
def project_config(project_slug: str):
    """Resolved URLs and metadata for this API project."""
    return get_project_config(project_slug)


@pytest.fixture(scope="session")
def api_client(project_config):
    """
    HTTP client with base URL + /api/v1 prefix from config.

    Timeout can be overridden per suite via env.
    """
    timeout = float(os.environ.get("DATACOMNS_HTTP_TIMEOUT", "60"))
    return ApiClient.from_project_config(project_config, timeout_seconds=timeout)


@pytest.fixture
def require_live_api() -> None:
    """
    Skip live HTTP tests when offline or in docs-only CI.

    Set DATACOMNS_SKIP_LIVE_TESTS=1 to skip.
    """
    if os.environ.get("DATACOMNS_SKIP_LIVE_TESTS", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        pytest.skip("DATACOMNS_SKIP_LIVE_TESTS is set")
