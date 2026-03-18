"""
Regression: sample summary (aggregate) — same pattern as subject smoke, different resource.
"""

from __future__ import annotations

import httpx
import pytest

from framework.assertions.response import assert_successful_json

pytestmark = [
    pytest.mark.regression,
    pytest.mark.project_federation,
]


def test_sample_summary_returns_json_200(api_client, require_live_api) -> None:
    """
    GET /api/v1/sample/summary — validates Sample resource path (regression breadth).

    Note: list endpoints may use different pagination/filter names than ``limit``;
    use OpenAPI or discovery tests for param matrices.
    """
    try:
        response = api_client.get("/sample/summary")
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        pytest.fail(f"Request failed: {exc}")

    data = assert_successful_json(response, context="sample/summary")
    assert isinstance(data, (dict, list)), f"Expected dict or list, got {type(data)}"
