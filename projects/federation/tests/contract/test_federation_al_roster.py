"""Offline tests for Federation Aggregation Layer source roster checks in the contract runner."""

from __future__ import annotations

import json

import pytest

from framework.contract_runner.client import APIResponse
from framework.contract_runner.runners.functional import check_response_body_for_case

pytestmark = [pytest.mark.smoke, pytest.mark.project_federation]


def test_al_roster_all_sources_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEDERATION_AL_EXPECTED_SOURCES", "A,B")
    body = [{"source": "A", "data": []}, {"source": "B", "errors": [{"kind": "x"}]}]
    resp = APIResponse(200, json.dumps(body), body, 0.01)
    ok, err = check_response_body_for_case(resp, {})
    assert ok is True
    assert err is None


def test_al_roster_missing_source_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEDERATION_AL_EXPECTED_SOURCES", "A,B,C")
    body = [{"source": "A"}, {"source": "B"}]
    resp = APIResponse(200, json.dumps(body), body, 0.01)
    ok, err = check_response_body_for_case(resp, {})
    assert ok is False
    assert err is not None
    assert "C" in err


def test_dict_response_skips_roster_even_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEDERATION_AL_EXPECTED_SOURCES", "PCDC,Treehouse")
    body = {"data": [], "metadata": {}}
    resp = APIResponse(200, json.dumps(body), body, 0.01)
    ok, err = check_response_body_for_case(resp, {})
    assert ok is True


def test_empty_env_skips_roster(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEDERATION_AL_EXPECTED_SOURCES", raising=False)
    body = [{"source": "OnlyOne"}]
    resp = APIResponse(200, json.dumps(body), body, 0.01)
    ok, err = check_response_body_for_case(resp, {})
    assert ok is True
