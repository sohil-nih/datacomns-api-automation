"""Offline tests for Federation Aggregation Layer source roster checks in the contract runner."""

from __future__ import annotations

import json

import pytest

from framework.contract_runner.client import APIResponse
from framework.contract_runner.runners.functional import (
    DEFAULT_FEDERATION_AL_EXPECTED_SOURCES,
    check_response_body_for_case,
    federation_al_expected_sources,
)

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


def test_dict_response_skips_roster(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEDERATION_AL_EXPECTED_SOURCES", raising=False)
    body = {"data": [], "metadata": {}}
    resp = APIResponse(200, json.dumps(body), body, 0.01)
    ok, err = check_response_body_for_case(resp, {})
    assert ok is True


def test_unset_env_uses_default_missing_source_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEDERATION_AL_EXPECTED_SOURCES", raising=False)
    body = [{"source": "PCDC", "data": []}]
    resp = APIResponse(200, json.dumps(body), body, 0.01)
    ok, err = check_response_body_for_case(resp, {})
    assert ok is False
    assert err is not None
    assert "missing expected source" in (err or "").lower()


def test_unset_env_default_all_seven_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEDERATION_AL_EXPECTED_SOURCES", raising=False)
    body = [{"source": name, "data": []} for name in DEFAULT_FEDERATION_AL_EXPECTED_SOURCES]
    resp = APIResponse(200, json.dumps(body), body, 0.01)
    ok, err = check_response_body_for_case(resp, {})
    assert ok is True
    assert err is None


def test_env_none_disables_roster(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEDERATION_AL_EXPECTED_SOURCES", "none")
    body = [{"source": "OnlyOne"}]
    resp = APIResponse(200, json.dumps(body), body, 0.01)
    ok, err = check_response_body_for_case(resp, {})
    assert ok is True


def test_federation_al_expected_sources_respects_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEDERATION_AL_EXPECTED_SOURCES", " X , Y ")
    assert federation_al_expected_sources() == ["X", "Y"]
