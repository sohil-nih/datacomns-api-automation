"""
Smoke (offline): registry and project config load without calling the API.

Runs in CI without VPN; proves framework wiring is correct.
"""

from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.project_federation,
]


def test_federation_project_is_registered_and_has_base_url(project_config) -> None:
    """config/projects.yaml + env resolution must yield a valid base URL."""
    assert project_config.slug == "federation"
    assert project_config.base_url.startswith("https://") or project_config.base_url.startswith(
        "http://"
    )
    assert project_config.api_prefix == "/api/v1"
