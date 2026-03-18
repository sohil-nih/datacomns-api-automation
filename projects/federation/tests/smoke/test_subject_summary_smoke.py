"""
Smoke: Subject summary endpoint returns JSON 200.

First executable test for the framework — validates connectivity and basic contract.
"""

from __future__ import annotations

import httpx
import pytest

from framework.assertions.response import assert_successful_json

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.project_federation,
]


def test_subject_summary_returns_json_200(api_client, require_live_api) -> None:
    """
    GET /api/v1/subject/summary — lightweight aggregate; suitable for deploy smoke.

    If QA is down, you see connection error; use DATACOMNS_SKIP_LIVE_TESTS=1 to skip locally.
    """
    try:
        response = api_client.get("/subject/summary")
    except httpx.ConnectError as exc:
        pytest.fail(
            f"Could not connect to API ({api_client.config.base_url}). "
            f"Check VPN/network or set DATACOMNS_FEDERATION_BASE_URL. Underlying: {exc}"
        )
    except httpx.TimeoutException as exc:
        pytest.fail(f"Request timed out: {exc}")

    data = assert_successful_json(response, context="subject/summary")
    assert isinstance(data, (dict, list)), "Summary payload should be dict or list"
