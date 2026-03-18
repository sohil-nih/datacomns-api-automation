"""
Live smoke: GET /api/v1/subject with sex, race, and page filters.

Equivalent URL:
  https://dcc-qa.ccdi.cancer.gov/api/v1/subject?sex=M&race=Asian&page=1

Output is printed to the terminal even without ``-s`` (uses ``capsys.disabled()``).
"""

from __future__ import annotations

import json

import httpx
import pytest

from framework.assertions.response import assert_successful_json

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.project_federation,
]


def test_subject_filtered_sex_race_page(
    api_client, require_live_api, capsys: pytest.CaptureFixture[str]
) -> None:
    """GET /api/v1/subject?sex=M&race=Asian&page=1"""
    try:
        response = api_client.get(
            "/subject",
            params={
                "sex": "M",
                "race": "Asian",
                "page": 1,
            },
        )
    except httpx.ConnectError as exc:
        pytest.fail(
            f"Could not connect to API ({api_client.config.base_url}). "
            f"Check network or DATACOMNS_FEDERATION_BASE_URL. {exc}"
        )
    except httpx.TimeoutException as exc:
        pytest.fail(f"Request timed out: {exc}")

    data = assert_successful_json(response, context="subject?sex=M&race=Asian&page=1")
    assert isinstance(data, (dict, list)), f"Expected dict or list, got {type(data)}"

    # Bypass pytest stdout capture so JSON shows with plain: pytest ... -v
    with capsys.disabled():
        print("\n--- Response ---", flush=True)
        print(f"Status: {response.status_code}", flush=True)
        print(f"URL:    {response.request.url}", flush=True)
        print("Body:", flush=True)
        print(json.dumps(data, indent=2, default=str), flush=True)
        print("--- End response ---\n", flush=True)
