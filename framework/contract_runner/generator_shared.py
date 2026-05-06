"""
Shared OpenAPI parsing helpers for DCC case generation.

Extracts path/query parameters, response codes, and 200 JSON schema ref names from each
operation. ``_iter_ops`` drives the main loop in ``dcc_generator``; ``_fill_path_template``
substitutes path params and normalizes against ``/api/v1``.
"""
from __future__ import annotations

from urllib.parse import quote

from .loader import get_paths, normalize_path_for_base


def _path_params_from_spec(operation: dict) -> list[dict]:
    """Parameters with ``in: path`` for this operation."""
    params = operation.get("parameters") or []
    return [p for p in params if isinstance(p, dict) and p.get("in") == "path"]


def _query_params_from_spec(operation: dict) -> list[dict]:
    """Parameters with ``in: query`` (e.g. ``page``, ``per_page``)."""
    params = operation.get("parameters") or []
    return [p for p in params if isinstance(p, dict) and p.get("in") == "query"]


def _response_codes(operation: dict) -> set[int]:
    """Numeric HTTP status codes declared under ``operation.responses``."""
    responses = operation.get("responses") or {}
    return {int(k) for k in responses if str(k).isdigit()}


def _fill_path_template(template: str, path_param_values: dict[str, str], base_path: str = "/v2") -> str:
    """Replace ``{name}`` placeholders with encoded values, then strip ``base_path`` prefix."""
    path = template
    for key, value in path_param_values.items():
        path = path.replace("{" + key + "}", quote(str(value), safe=""))
    return normalize_path_for_base(path, base_path)


def _get_schema_ref(operation: dict) -> str | None:
    """
    Short schema name from the 200 response ``application/json`` schema ``$ref`` (or first ``anyOf``).

    Used only for coarse body checks in the functional runner (not full JSON Schema validation).
    """
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
    """Path param dict where every segment is a fixed invalid string (for negative URL cases)."""
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
    """
    Yield ``(path_template, method, operation_dict)`` for each HTTP operation in the spec.

    Optional ``tag_filter`` restricts to operations tagged with at least one listed tag.
    """
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
