"""
OpenAPI-driven GET case generation for the CCDI Federation Resource API.

Federation OpenAPI documents use **path keys without** a ``/api/v1`` prefix (the server
URL carries ``/api/v1``). This module mirrors ``dcc.generator`` with ``base_path`` ``""``
and templates like ``/subject`` instead of ``/api/v1/subject``.

Reuses query-default helpers from ``framework.contract_runner.dcc.generator``.
"""
from __future__ import annotations

from framework.contract_runner.dcc.generator import (
    MAX_FILTER_EXTRA_CASES_PER_OP,
    _default_query_params_dcc,
    _has_page_and_per_page,
    _integer_page_per_page_names,
    _query_param_names_from_spec,
)
from framework.contract_runner.generator_shared import (
    _fill_path_template,
    _get_schema_ref,
    _iter_ops,
    _negative_path_params,
    _path_params_from_spec,
    _query_params_from_spec,
    _response_codes,
)

# Spec paths are relative to servers.url (e.g. /api/v1); strip nothing for client-relative paths.
BASE_PATH_FEDERATION = ""

LIST_PATH_TO_FILTER_RESOURCE: dict[str, str] = {
    "/subject": "subject",
    "/sample": "sample",
    "/file": "file",
}


def _resolve_path_params_federation(path_template: str, path_params: list[dict], test_data: dict) -> dict | None:
    """Map discovery keys to path parameters (Federation path templates, no /api/v1 prefix)."""
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
                v = test_data.get("contract_subject_count_field")
            elif "/sample/" in pt and "/by/" in pt:
                v = test_data.get("contract_sample_count_field")
            elif "/file/" in pt and "/by/" in pt:
                v = test_data.get("contract_file_count_field")
            else:
                return None
            if not v:
                return None
            values[name] = str(v)
            continue
        if name == "organization":
            if "/sample/" in pt and "/by/" not in pt:
                v = test_data.get("contract_sample_organization") or test_data.get("organization")
            elif "/file/" in pt and "/by/" not in pt:
                v = test_data.get("contract_file_organization") or test_data.get("organization")
            else:
                v = test_data.get("organization")
            if not v:
                return None
            values[name] = str(v)
            continue
        if name == "namespace":
            if "/sample/" in pt and "/by/" not in pt:
                v = test_data.get("contract_sample_namespace") or test_data.get("namespace")
            elif "/file/" in pt and "/by/" not in pt:
                v = test_data.get("contract_file_namespace") or test_data.get("namespace")
            else:
                v = test_data.get("namespace")
            if not v:
                return None
            values[name] = str(v)
            continue
        if name == "name":
            if path_template == "/organization/{name}":
                v = test_data.get("contract_organization_name")
            elif "/subject/" in pt and "/by/" not in pt:
                v = test_data.get("contract_subject_name")
            elif "/sample/" in pt and "/by/" not in pt:
                v = test_data.get("contract_sample_name")
            elif "/file/" in pt and "/by/" not in pt:
                v = test_data.get("contract_file_name")
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


def generate_cases_federation(
    spec: dict,
    test_data: dict,
    base_path: str = BASE_PATH_FEDERATION,
    tag_filter: list[str] | None = None,
    include_negative: bool = True,
    strict_non_empty_filter: bool = False,
    exclude_paths: frozenset[str] | None = None,
) -> list[dict]:
    """Produce GET contract cases for Federation OpenAPI (paths like ``/subject``, not ``/api/v1/subject``).

    Aggregation Layer (AL): every case expects **HTTP 200** only (4xx/5xx including 504 fail the run).
    ``include_negative`` adds **bad query** (``page=0``, ``per_page=0``) and **invalid path** GETs using
    the same garbage segments as the DCC generator, but with ``expected_status`` **200** — the AL still
    responds 200 and may report node errors inside the JSON body.

    ``exclude_paths``: path templates to skip (e.g. CPI ``/subject-mapping`` not deployed on all gateways).
    """
    cases: list[dict] = []
    skip_paths = exclude_paths or frozenset()

    for path_template, method, op in _iter_ops(spec, tag_filter):
        if path_template == "/":
            continue
        if method != "get":
            continue
        if path_template in skip_paths:
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

        path_values = _resolve_path_params_federation(path_template, path_params, test_data)
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
                    "operation_id": f"{operation_id}__pagination_query",
                    "summary": f"{summary} (query: page=1, per_page=1)",
                    "tag": tag,
                    "negative": False,
                    "response_schema_ref": schema_ref,
                })

            if include_negative and _has_page_and_per_page(query_params):
                base_q = dict(query_vals) if query_vals else {}
                if "page" in pp_names:
                    cases.append({
                        "path": path_str,
                        "params": {**base_q, "page": 0},
                        "expected_status": 200,
                        "operation_id": f"{operation_id}__bad_query_page",
                        "summary": f"{summary} (bad query: page=0; AL expects 200)",
                        "tag": tag,
                        "negative": True,
                        "response_schema_ref": None,
                    })
                if "per_page" in pp_names:
                    cases.append({
                        "path": path_str,
                        "params": {**base_q, "per_page": 0},
                        "expected_status": 200,
                        "operation_id": f"{operation_id}__bad_query_per_page",
                        "summary": f"{summary} (bad query: per_page=0; AL expects 200)",
                        "tag": tag,
                        "negative": True,
                        "response_schema_ref": None,
                    })

        if include_negative and path_params and (
            404 in response_codes_set or 422 in response_codes_set or 400 in response_codes_set
        ):
            neg_vals = _negative_path_params(path_template, path_params, test_data)
            if neg_vals is not None:
                path_str_neg = _fill_path_template(path_template, neg_vals, base_path)
                cases.append({
                    "path": path_str_neg,
                    "params": None,
                    "expected_status": 200,
                    "operation_id": f"{operation_id}__invalid_path",
                    "summary": f"{summary} (invalid param; AL expects 200)",
                    "tag": tag,
                    "negative": True,
                    "response_schema_ref": None,
                })

    return cases
