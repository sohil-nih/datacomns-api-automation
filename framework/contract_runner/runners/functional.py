"""
Execute generated contract cases as **functional** GETs.

For each case dict from ``generate_cases_dcc``, calls ``ContractAPIClient.get`` (or the
pagination-pair path when ``pagination_pair_assert`` is set), compares the HTTP status to
``expected_status``, and optionally validates response shape (JSON equality, pagination limits,
OpenAPI-derived ``response_schema_ref``). Results are flat dicts suitable
for ``aggregate_results`` and HTML/JSON reporters.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from framework.contract_runner.client import APIResponse, ContractAPIClient, _build_query_string
from framework.contract_runner.dcc_filter_extract import filter_candidates_from_row, filter_match_mode

@dataclass(frozen=True)
class PaginationPairOutcome:
    """Outcome of a two-request pagination consistency check (params A vs B on the same path)."""

    ok: bool
    error: str | None
    duration_total: float
    actual_status: int
    b_executed: bool
    duration_a: float
    duration_b: float


def _pagination_pair_check(client: ContractAPIClient, case: dict) -> PaginationPairOutcome:
    """Run GET with ``pagination_pair_params_a`` then ``_b``; assert B[0] == A[1] when A has >=2 items."""
    path = case.get("path") or ""
    params_a = case.get("pagination_pair_params_a")
    params_b = case.get("pagination_pair_params_b")
    if params_a is None or params_b is None:
        return PaginationPairOutcome(
            ok=False,
            error="pagination_pair: missing pagination_pair_params_a or _b",
            duration_total=0.0,
            actual_status=0,
            b_executed=False,
            duration_a=0.0,
            duration_b=0.0,
        )

    resp_a = client.get(path, params_a)
    dur_a = resp_a.duration
    if resp_a.status_code != 200:
        return PaginationPairOutcome(
            ok=False,
            error=(
                f"pagination_pair A: expected 200, got {resp_a.status_code}"
                + (f": {resp_a.body[:200]}" if resp_a.body else "")
            ),
            duration_total=dur_a,
            actual_status=resp_a.status_code,
            b_executed=False,
            duration_a=dur_a,
            duration_b=0.0,
        )

    data_a = resp_a.json()
    if not isinstance(data_a, list) or len(data_a) < 2:
        return PaginationPairOutcome(
            ok=True,
            error=None,
            duration_total=dur_a,
            actual_status=resp_a.status_code,
            b_executed=False,
            duration_a=dur_a,
            duration_b=0.0,
        )

    resp_b = client.get(path, params_b)
    dur_b = resp_b.duration
    dur_total = dur_a + dur_b
    if resp_b.status_code != 200:
        return PaginationPairOutcome(
            ok=False,
            error=(
                f"pagination_pair B: expected 200, got {resp_b.status_code}"
                + (f": {resp_b.body[:200]}" if resp_b.body else "")
            ),
            duration_total=dur_total,
            actual_status=resp_b.status_code,
            b_executed=True,
            duration_a=dur_a,
            duration_b=dur_b,
        )

    data_b = resp_b.json()
    if not isinstance(data_b, list) or len(data_b) < 1:
        return PaginationPairOutcome(
            ok=False,
            error=f"pagination_pair B: expected non-empty JSON list, got {data_b!r}",
            duration_total=dur_total,
            actual_status=resp_b.status_code,
            b_executed=True,
            duration_a=dur_a,
            duration_b=dur_b,
        )
    if data_b[0] != data_a[1]:
        return PaginationPairOutcome(
            ok=False,
            error=f"pagination_pair: B[0] != A[1]: {data_b[0]!r} vs {data_a[1]!r}",
            duration_total=dur_total,
            actual_status=resp_b.status_code,
            b_executed=True,
            duration_a=dur_a,
            duration_b=dur_b,
        )
    return PaginationPairOutcome(
        ok=True,
        error=None,
        duration_total=dur_total,
        actual_status=resp_b.status_code,
        b_executed=True,
        duration_a=dur_a,
        duration_b=dur_b,
    )


def _path_with_query(path: str, params: dict | None) -> str:
    """Append serialized query string to ``path`` for display (uses shared query builder)."""
    return path + _build_query_string(params)


def run_functional_tests(
    client: ContractAPIClient,
    cases: list[dict],
    on_case_done: Callable[[dict], None] | None = None,
    perf_threshold_ms: int | None = None,
) -> list[dict]:
    """Run all cases; each result dict includes ``operation_id``, ``path``/``path_display``, ``passed``, ``duration``, ``perf_warning``.

    Case keys used: ``path``, ``params``, ``expected_status``, ``operation_id``, ``summary``,
    ``tag``, ``negative``, ``pagination_pair_assert``, ``pagination_pair_params_a``/``_b``,
    ``expected_json``, ``skip_oob_assert``, ``pagination_assert_max_items``,
    ``pagination_list_key``, ``response_schema_ref``, ``expect_non_empty_data``,
    ``filter_resource``, ``filter_param``, ``filter_value``.
    """
    results = []
    for case in cases:
        path = case.get("path") or ""
        params = case.get("params")
        expected_status = case.get("expected_status", 200)
        operation_id = case.get("operation_id", "")
        summary = case.get("summary", "")

        if case.get("pagination_pair_assert"):
            pair_out = _pagination_pair_check(client, case)
            params_a = case.get("pagination_pair_params_a")
            params_b = case.get("pagination_pair_params_b")
            path_a = _path_with_query(path, params_a) if params_a is not None else _path_with_query(path, params)
            path_b = _path_with_query(path, params_b) if params_b is not None else path_a
            display_note = None
            if pair_out.b_executed:
                path_display = path_b
                display_duration = pair_out.duration_b
            elif pair_out.ok:
                path_display = path_a
                display_duration = pair_out.duration_a
                display_note = "B not run (A had <2 items)"
            else:
                path_display = path_a
                display_duration = pair_out.duration_a
            perf_warning = (
                perf_threshold_ms is not None
                and display_duration is not None
                and display_duration * 1000 > perf_threshold_ms
            )
            result = {
                "operation_id": operation_id,
                "summary": summary,
                "path": path,
                "path_display": path_display,
                "pagination_pair_display_note": display_note,
                "pagination_pair_b_executed": pair_out.b_executed,
                "pagination_pair_wall_time": pair_out.duration_total,
                "duration_pair_a": pair_out.duration_a,
                "duration_pair_b": pair_out.duration_b,
                "params": params,
                "expected_status": expected_status,
                "actual_status": pair_out.actual_status,
                "passed": pair_out.ok,
                "duration": display_duration,
                "error": pair_out.error,
                "tag": case.get("tag"),
                "negative": case.get("negative", False),
                "perf_warning": perf_warning,
            }
            results.append(result)
            if on_case_done:
                on_case_done(result)
            continue

        response: APIResponse = client.get(path, params)

        passed = response.status_code == expected_status
        error = None
        if not passed:
            error = f"Expected {expected_status}, got {response.status_code}"
            if response.body:
                error += f": {response.body[:200]}"

        if passed and (
            expected_status == 200
            or case.get("expected_json") is not None
            or case.get("skip_oob_assert")
            or case.get("pagination_assert_max_items") is not None
            or case.get("expect_non_empty_data")
        ):
            shape_ok, shape_error = _check_basic_shape(response, case)
            if not shape_ok:
                passed = False
                error = shape_error
        semantic_note = None
        if passed and expected_status == 200 and case.get("filter_param"):
            sem_ok, sem_err, sem_note = _check_filter_semantics(response, case)
            if not sem_ok:
                passed = False
                error = sem_err
            semantic_note = sem_note

        path_display = _path_with_query(path, params)
        perf_warning = (
            perf_threshold_ms is not None
            and response.duration is not None
            and response.duration * 1000 > perf_threshold_ms
        )
        result = {
            "operation_id": operation_id,
            "summary": summary,
            "path": path,
            "path_display": path_display,
            "params": params,
            "expected_status": expected_status,
            "actual_status": response.status_code,
            "passed": passed,
            "duration": response.duration,
            "error": error,
            "tag": case.get("tag"),
            "negative": case.get("negative", False),
            "perf_warning": perf_warning,
        }
        if semantic_note:
            result["semantic_note"] = semantic_note
        results.append(result)
        if on_case_done:
            on_case_done(result)
    return results


def run_functional_tests_dcc(
    client: ContractAPIClient,
    cases: list[dict],
    on_case_done: Callable[[dict], None] | None = None,
) -> list[dict]:
    """DCC entrypoint; same as ``run_functional_tests`` without a perf threshold (CLI sets threshold there)."""
    return run_functional_tests(client, cases, on_case_done=on_case_done)


def _federation_al_expected_sources_from_env() -> list[str]:
    """Comma-separated ``FEDERATION_AL_EXPECTED_SOURCES``; empty or unset means skip AL roster checks."""
    raw = os.getenv("FEDERATION_AL_EXPECTED_SOURCES", "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _is_al_multi_source_roster(data: object) -> bool:
    """
    True when the body is a non-empty top-level JSON array of objects, each with a non-empty string ``source``.

    Used for Federation Aggregation Layer responses where each element is one data commons node.
    """
    if not isinstance(data, list) or len(data) < 1:
        return False
    for el in data:
        if not isinstance(el, dict):
            return False
        s = el.get("source")
        if not isinstance(s, str) or not s.strip():
            return False
    return True


def _check_federation_al_source_roster(data: object, expected: list[str]) -> tuple[bool, str | None]:
    """Assert every ``expected`` source string appears as ``source`` on some array element."""
    if not expected:
        return True, None
    if not isinstance(data, list):
        return False, "AL roster: internal error, expected list body"
    observed: set[str] = set()
    for el in data:
        if isinstance(el, dict):
            s = el.get("source")
            if isinstance(s, str):
                observed.add(s)
    missing = [e for e in expected if e not in observed]
    if missing:
        return (
            False,
            f"AL roster: missing expected source(s) {missing!r}; observed={sorted(observed)!r}",
        )
    return True, None


def _check_basic_shape(response: APIResponse, case: dict) -> tuple[bool, str | None]:
    """Validate body when status expectations are met: exact JSON, list length, or schema-ref coarse shape."""
    data = response.json()
    if case.get("expected_json") is not None:
        exp = case["expected_json"]
        if data is None:
            return False, f"Expected JSON {exp!r}, but response was not JSON or empty"
        if data != exp:
            return False, f"Expected JSON {exp!r}, got {data!r}"
        return True, None
    if case.get("skip_oob_assert") == "model_pvs_empty_permissible_values":
        if data is None:
            return False, "Expected JSON list for model-pvs skip_oob, but response was not JSON"
        if not isinstance(data, list):
            return False, f"Expected JSON array for model-pvs skip_oob, got {type(data).__name__}"
        if len(data) == 0:
            return (
                False,
                "Top-level JSON array is empty; expected at least one item with "
                "permissibleValues []. An empty response is unexpected for this scenario — "
                "please investigate.",
            )
        for i, item in enumerate(data):
            if not isinstance(item, dict) or item.get("permissibleValues") != []:
                return (
                    False,
                    f"Expected each item to have permissibleValues [], got {item!r} at index {i}",
                )
        return True, None
    max_items = case.get("pagination_assert_max_items")
    if max_items is not None:
        list_key = case.get("pagination_list_key")
        target = data
        if list_key and isinstance(data, dict):
            target = data.get(list_key)
        if isinstance(target, list) and len(target) > max_items:
            return (
                False,
                f"Pagination: response list length {len(target)} exceeds limit "
                f"(expected at most {max_items})",
            )
    if case.get("expect_non_empty_data"):
        if not isinstance(data, dict):
            return False, "expect_non_empty_data: response must be a JSON object with data[]"
        arr = data.get("data")
        if not isinstance(arr, list) or len(arr) < 1:
            return False, "expect_non_empty_data: top-level data[] must be non-empty"

    expected_sources = _federation_al_expected_sources_from_env()
    if expected_sources and data is not None and _is_al_multi_source_roster(data):
        ok_roster, err_roster = _check_federation_al_source_roster(data, expected_sources)
        if not ok_roster:
            return False, err_roster

    if data is None:
        return True, None
    schema_ref = case.get("response_schema_ref")
    if not schema_ref:
        return True, None

    if schema_ref in ("Entity", "Term", "Model", "Node", "PropertyResponse", "Tag"):
        if not isinstance(data, dict):
            return False, f"Expected object for {schema_ref}, got {type(data).__name__}"
        if schema_ref in ("Entity", "Term", "Node", "PropertyResponse", "Tag") and schema_ref != "Model":
            if "nanoid" not in data and "value" not in data and "key" not in data:
                return False, f"Expected nanoid/value/key in {schema_ref}"
        return True, None

    if isinstance(data, list):
        return True, None
    if isinstance(data, dict):
        return True, None
    if isinstance(data, int):
        return True, None
    return True, None


def _value_matches(expected: str, candidate: str, mode: str) -> bool:
    exp = str(expected).strip().lower()
    got = str(candidate).strip().lower()
    if mode == "contains_ci":
        return exp in got
    return got == exp


def _check_filter_semantics(response: APIResponse, case: dict) -> tuple[bool, str | None, str | None]:
    """
    Semantic check for generated ``__filter_*`` list cases.

    Returns:
        (ok, error, note) where note is set for informative pass situations.
    """
    data = response.json()
    if not isinstance(data, dict):
        return True, None, "semantic check skipped: response is not a JSON object"
    rows = data.get("data")
    if not isinstance(rows, list):
        return True, None, "semantic check skipped: response has no data[] list"
    if not rows:
        return True, None, "semantic check passed: empty data[]"

    resource = case.get("filter_resource")
    param = case.get("filter_param")
    expected = case.get("filter_value")
    if not resource or not param or expected is None:
        return True, None, "semantic check skipped: filter metadata missing"

    mode = filter_match_mode(str(resource), str(param))
    compared = 0
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        candidates = filter_candidates_from_row(str(resource), row, str(param))
        if not candidates:
            continue
        compared += 1
        if not any(_value_matches(str(expected), c, mode) for c in candidates):
            sample = candidates[:3]
            return (
                False,
                (
                    f"Filter semantic mismatch for {param}={expected!r} at data[{idx}] "
                    f"(mode={mode}); row candidates={sample!r}"
                ),
                None,
            )

    if compared == 0:
        return (
            False,
            (
                "Filter semantic check could not validate any rows for "
                f"{param}={expected!r}; no comparable candidate values were found in response data[]. "
                "Possible causes: response metadata shape drift or missing extractor mapping."
            ),
            None,
        )
    return True, None, f"semantic check passed: validated {compared} row(s)"


def check_response_body_for_case(response: APIResponse, case: dict) -> tuple[bool, str | None]:
    """Public wrapper around ``_check_basic_shape`` for reuse outside the main loop."""
    return _check_basic_shape(response, case)


def check_pagination_pair_for_case(client: ContractAPIClient, case: dict) -> tuple[bool, str | None]:
    """Return (ok, error) for a single case's pagination pair assertion."""
    out = _pagination_pair_check(client, case)
    return out.ok, out.error
