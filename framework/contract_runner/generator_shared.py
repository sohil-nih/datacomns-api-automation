"""Shared OpenAPI helpers used by ``dcc_generator`` (no STS-specific case generation)."""

from __future__ import annotations

from urllib.parse import quote

from .loader import get_paths, normalize_path_for_base


def _path_params_from_spec(operation: dict) -> list[dict]:
    params = operation.get("parameters") or []
    return [p for p in params if isinstance(p, dict) and p.get("in") == "path"]


def _query_params_from_spec(operation: dict) -> list[dict]:
    params = operation.get("parameters") or []
    return [p for p in params if isinstance(p, dict) and p.get("in") == "query"]


def _response_codes(operation: dict) -> set[int]:
    responses = operation.get("responses") or {}
    return {int(k) for k in responses if str(k).isdigit()}


def _fill_path_template(template: str, path_param_values: dict[str, str], base_path: str = "/v2") -> str:
    path = template
    for key, value in path_param_values.items():
        path = path.replace("{" + key + "}", quote(str(value), safe=""))
    return normalize_path_for_base(path, base_path)


def _get_schema_ref(operation: dict) -> str | None:
    responses = operation.get("responses") or {}
    r200 = responses.get("200") or responses.get(200)
    if not r200 or not isinstance(r200, dict):
        return None
    content = r200.get("content") or {}
    json_content = content.get("application/json") or {}
    schema = json_content.get("schema")
    if not schema or not isinstance(schema, dict):
        return None
    ref = schema.get("$ref")
    if ref:
        return ref.split("/")[-1]
    any_of = schema.get("anyOf") or schema.get("oneOf")
    if any_of and isinstance(any_of, list) and len(any_of) > 0:
        first = any_of[0]
        if isinstance(first, dict) and first.get("$ref"):
            return first["$ref"].split("/")[-1]
    return None


def _negative_path_params(path_template: str, path_params: list[dict], test_data: dict) -> dict | None:
    if not path_params:
        return {}
    invalid = "invalid_nonexistent_xyz"
    values = {}
    for p in path_params:
        name = p.get("name")
        if not name:
            continue
        values[name] = invalid
    return values


def _iter_ops(spec: dict, tag_filter: list[str] | None):
    paths = get_paths(spec)
    for path_template, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            if tag_filter:
                op_tags = op.get("tags") or []
                if not set(op_tags) & set(tag_filter):
                    continue
            yield path_template, method, op
