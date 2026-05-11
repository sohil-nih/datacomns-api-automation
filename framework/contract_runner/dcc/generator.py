"""
OpenAPI-driven GET case generation for the DCC REST API.

Walks the spec (``_iter_ops``), keeps **GET** only, and builds case dicts with ``path``,
``params``, ``expected_status``, ``operation_id``, ``summary``, ``tag``, ``negative``,
and optional pagination / schema-ref metadata consumed by ``run_functional_tests_dcc``.
List routes ``/subject``, ``/sample``, ``/file`` also get up to ``MAX_FILTER_EXTRA_CASES_PER_OP``
extra cases when ``test_data`` includes ``filter_examples`` from ``discover_dcc``.

Positive paths need ``test_data`` from ``discover_dcc`` (including optional ``filter_examples``
for list endpoints). Negative path cases use garbage segments; bad-query cases assume live DCC
returns **400** for invalid ``page`` / ``per_page``.
"""
from __future__ import annotations

from framework.contract_runner.generator_shared import (
    _fill_path_template,
    _get_schema_ref,
    _iter_ops,
    _negative_path_params,
    _path_params_from_spec,
    _query_params_from_spec,
    _response_codes,
)

BASE_PATH_DCC = "/api/v1"

# Root list paths that accept metadata filter query params (not ``/summary`` siblings).
LIST_PATH_TO_FILTER_RESOURCE: dict[str, str] = {
    "/api/v1/subject": "subject",
    "/api/v1/sample": "sample",
    "/api/v1/file": "file",
}

# Cap extra GETs per list operation from discovery-driven filters (avoid combinatorial blowup).
MAX_FILTER_EXTRA_CASES_PER_OP = 20


def _schema_type_set(schema: dict) -> set[str]:
    """Collect JSON Schema ``type`` strings, unwrapping one level of ``anyOf`` / ``oneOf``."""
    out: set[str] = set()
    if not schema or not isinstance(schema, dict):
        return out
    for key in ("anyOf", "oneOf"):
        opts = schema.get(key)
        if isinstance(opts, list):
            for sub in opts:
                if isinstance(sub, dict):
                    out |= _schema_type_set(sub)
            if out:
                return out
    t = schema.get("type")
    if isinstance(t, list):
        out.update(str(x) for x in t)
    elif t:
        out.add(str(t))
    return out


def _schema_has_integer(schema: dict) -> bool:
    """True if the schema allows integer (including via ``anyOf``)."""
    return "integer" in _schema_type_set(schema)


def _default_query_params_dcc(query_params: list[dict]) -> dict:
    """Defaults for list operations: honor ``default``, integer ``page``/``per_page``/``skip``, booleans."""
    out: dict = {}
    for p in query_params:
        name = p.get("name")
        if not name:
            continue
        schema = p.get("schema") or {}
        default = schema.get("default")
        if default is not None:
            out[name] = default
            continue
        types = _schema_type_set(schema)
        if "integer" in types:
            if name == "page":
                out[name] = 1
            elif name == "per_page":
                out[name] = 50
            elif "skip" in name.lower():
                out[name] = 0
            else:
                out[name] = 10
        elif "boolean" in types:
            out[name] = False
    return out


def _integer_page_per_page_names(query_params: list[dict]) -> set[str]:
    """Names ``page`` / ``per_page`` that are typed as integers in the spec."""
    out: set[str] = set()
    for p in query_params:
        if not isinstance(p, dict):
            continue
        name = p.get("name")
        if name not in ("page", "per_page"):
            continue
        if _schema_has_integer(p.get("schema") or {}):
            out.add(name)
    return out


def _has_page_and_per_page(query_params: list[dict]) -> bool:
    """True if both integer ``page`` and ``per_page`` exist (enables pagination extras)."""
    names = _integer_page_per_page_names(query_params)
    return "page" in names and "per_page" in names


def _query_param_names_from_spec(query_params: list[dict]) -> set[str]:
    """Declared query parameter names for this operation (e.g. ``sex``, ``page``)."""
    out: set[str] = set()
    for p in query_params:
        if isinstance(p, dict):
            n = p.get("name")
            if n:
                out.add(str(n))
    return out


def _resolve_path_params_dcc(path_template: str, path_params: list[dict], test_data: dict) -> dict | None:
    """
    Map ``discover_dcc`` keys to path parameter names, disambiguating by path shape.

    Handles ``field``, ``organization``, ``namespace``, ``name`` for subject/sample/file
    and organization-detail routes. Returns None if any required value is missing or
    an unknown path param appears.
    """
    if not path_params:
        return {}
    pt = path_template
    values: dict[str, str] = {}
    for p in path_params:
        name = p.get("name")
        if not name:
            continue
        if name == "field":
            if "/subject/" in pt and "/by/" in pt:
                v = test_data.get("dcc_subject_count_field")
            elif "/sample/" in pt and "/by/" in pt:
                v = test_data.get("dcc_sample_count_field")
            elif "/file/" in pt and "/by/" in pt:
                v = test_data.get("dcc_file_count_field")
            else:
                return None
            if not v:
                return None
            values[name] = str(v)
            continue
        if name == "organization":
            if "/sample/" in pt and "/by/" not in pt:
                v = test_data.get("dcc_sample_organization") or test_data.get("organization")
            elif "/file/" in pt and "/by/" not in pt:
                v = test_data.get("dcc_file_organization") or test_data.get("organization")
            else:
                v = test_data.get("organization")
            if not v:
                return None
            values[name] = str(v)
            continue
        if name == "namespace":
            if "/sample/" in pt and "/by/" not in pt:
                v = test_data.get("dcc_sample_namespace") or test_data.get("namespace")
            elif "/file/" in pt and "/by/" not in pt:
                v = test_data.get("dcc_file_namespace") or test_data.get("namespace")
            else:
                v = test_data.get("namespace")
            if not v:
                return None
            values[name] = str(v)
            continue
        if name == "name":
            if path_template == "/api/v1/organization/{name}":
                v = test_data.get("dcc_organization_name")
            elif "/subject/" in pt and "/by/" not in pt:
                v = test_data.get("dcc_subject_name")
            elif "/sample/" in pt and "/by/" not in pt:
                v = test_data.get("dcc_sample_name")
            elif "/file/" in pt and "/by/" not in pt:
                v = test_data.get("dcc_file_name")
            else:
                return None
            if not v:
                return None
            values[name] = str(v)
            continue
        return None
    if len(values) != len(path_params):
        return None
    return values


def _expected_invalid_path_status_dcc(path_template: str, response_codes: set[int]) -> int:
    """
    HTTP status expected when all path segments are invalid (DCC live behavior vs strict OpenAPI).

    Several templates are treated as **400** where the spec might list 404/422 only.
    """
    pt = path_template.rstrip("/")
    if "/by/" in pt and pt.endswith("/count") and 400 in response_codes:
        return 400
    if path_template == "/api/v1/organization/{name}":
        return 404
    if path_template == "/api/v1/namespace/{organization}/{namespace}":
        return 400
    if path_template in (
        "/api/v1/subject/{organization}/{namespace}/{name}",
        "/api/v1/sample/{organization}/{namespace}/{name}",
        "/api/v1/file/{organization}/{namespace}/{name}",
    ):
        return 400
    if 404 in response_codes:
        return 404
    if 422 in response_codes:
        return 422
    if 400 in response_codes:
        return 400
    return 404


def _expected_bad_query_status_dcc() -> int:
    """Live DCC returns 400 for out-of-range ``page`` / ``per_page`` in many list routes."""
    return 400


def generate_cases_dcc(
    spec: dict,
    test_data: dict,
    base_path: str = BASE_PATH_DCC,
    tag_filter: list[str] | None = None,
    include_negative: bool = True,
    strict_non_empty_filter: bool = False,
) -> list[dict]:
    """
    Produce GET contract cases: positive 200s, optional pagination check, bad query, invalid path.

    Args:
        spec: Parsed OpenAPI document.
        test_data: Output of ``discover_dcc`` (may be empty).
        base_path: Prefix stripped from spec paths (default ``/api/v1``).
        tag_filter: If set, only operations whose ``tags`` overlap this list.
        include_negative: If False, skip bad-query and invalid-path cases.
        strict_non_empty_filter: If True, discovery-filter cases require non-empty ``data`` (stricter).

    Returns:
        List of case dicts for the functional runner.
    """
    cases: list[dict] = []

    for path_template, method, op in _iter_ops(spec, tag_filter):
        if path_template == "/":
            continue
        if method != "get":
            continue

        path_params = _path_params_from_spec(op)
        query_params = _query_params_from_spec(op)
        response_codes_set = _response_codes(op)
        operation_id = op.get("operationId") or f"{method}_{path_template}"
        summary = op.get("summary") or ""
        tags = op.get("tags") or []
        tag = tags[0] if tags else None
        schema_ref = _get_schema_ref(op)

        query_names = _query_param_names_from_spec(query_params)

        path_values = _resolve_path_params_dcc(path_template, path_params, test_data)
        if path_values is not None:
            path_str = _fill_path_template(path_template, path_values, base_path)
            query_vals = _default_query_params_dcc(query_params)
            cases.append({
                "path": path_str,
                "params": query_vals if query_vals else None,
                "expected_status": 200,
                "operation_id": operation_id,
                "summary": summary,
                "tag": tag,
                "negative": False,
                "response_schema_ref": schema_ref,
            })

            list_resource = LIST_PATH_TO_FILTER_RESOURCE.get(path_template)
            if list_resource:
                examples = (test_data.get("filter_examples") or {}).get(list_resource) or {}
                n_filter = 0
                for param_name in sorted(examples.keys()):
                    if n_filter >= MAX_FILTER_EXTRA_CASES_PER_OP:
                        break
                    if param_name not in query_names:
                        continue
                    val = examples[param_name]
                    if val is None or str(val).strip() == "":
                        continue
                    fq = dict(query_vals) if query_vals else {}
                    fq[param_name] = val
                    suffix = param_name.replace(".", "_").replace("/", "_")
                    filt_case: dict = {
                        "path": path_str,
                        "params": fq,
                        "expected_status": 200,
                        "operation_id": f"{operation_id}__filter_{suffix}",
                        "summary": f"{summary} (filter {param_name}={val!r})",
                        "filter_resource": list_resource,
                        "filter_param": param_name,
                        "filter_value": str(val),
                        "tag": tag,
                        "negative": False,
                        "response_schema_ref": schema_ref,
                    }
                    if strict_non_empty_filter:
                        filt_case["expect_non_empty_data"] = True
                    cases.append(filt_case)
                    n_filter += 1

            pp_names = _integer_page_per_page_names(query_params)
            if (
                200 in response_codes_set
                and "page" in pp_names
                and "per_page" in pp_names
            ):
                pag_q = dict(query_vals) if query_vals else {}
                pag_q["page"] = 1
                pag_q["per_page"] = 1
                cases.append({
                    "path": path_str,
                    "params": pag_q,
                    "expected_status": 200,
                    "operation_id": f"{operation_id}__pagination_positive",
                    "summary": f"{summary} (pagination: page=1, per_page=1)",
                    "tag": tag,
                    "negative": False,
                    "response_schema_ref": schema_ref,
                    "pagination_assert_max_items": 1,
                    "pagination_list_key": "data",
                })

            bqs = _expected_bad_query_status_dcc()
            if include_negative and _has_page_and_per_page(query_params):
                base_q = dict(query_vals) if query_vals else {}
                if "page" in pp_names:
                    cases.append({
                        "path": path_str,
                        "params": {**base_q, "page": 0},
                        "expected_status": bqs,
                        "operation_id": f"{operation_id}__bad_query_page",
                        "summary": f"{summary} (bad query: page=0)",
                        "tag": tag,
                        "negative": True,
                        "response_schema_ref": None,
                    })
                if "per_page" in pp_names:
                    cases.append({
                        "path": path_str,
                        "params": {**base_q, "per_page": 0},
                        "expected_status": bqs,
                        "operation_id": f"{operation_id}__bad_query_per_page",
                        "summary": f"{summary} (bad query: per_page=0)",
                        "tag": tag,
                        "negative": True,
                        "response_schema_ref": None,
                    })

        if include_negative and path_params and (404 in response_codes_set or 422 in response_codes_set or 400 in response_codes_set):
            expected = _expected_invalid_path_status_dcc(path_template, response_codes_set)
            neg_vals = _negative_path_params(path_template, path_params, test_data)
            if neg_vals is not None:
                path_str_neg = _fill_path_template(path_template, neg_vals, base_path)
                cases.append({
                    "path": path_str_neg,
                    "params": None,
                    "expected_status": expected,
                    "operation_id": operation_id,
                    "summary": f"{summary} (invalid param)",
                    "tag": tag,
                    "negative": True,
                    "response_schema_ref": None,
                })

    return cases
