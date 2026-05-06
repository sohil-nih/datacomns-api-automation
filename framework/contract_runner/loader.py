"""
OpenAPI document loading and path helpers.

``load_spec`` supports ``.json`` and YAML. Other functions expose ``paths``, ``components.schemas``,
and utilities used by the DCC case generator (e.g. stripping ``/api/v1`` from path templates).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_spec(spec_path: str | Path) -> dict[str, Any]:
    """Parse OpenAPI from disk; try JSON first, then YAML for ``.yaml`` / ``.yml`` or fallback."""
    path = Path(spec_path)
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")

    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    if suffix == ".json":
        raise RuntimeError("Spec file is not valid JSON.")
    if suffix in (".yaml", ".yml"):
        return yaml.safe_load(raw)

    return yaml.safe_load(raw)


def get_paths(spec: dict[str, Any]) -> dict[str, Any]:
    """Return the OpenAPI ``paths`` object (path string -> path item dict)."""
    return spec.get("paths") or {}


def get_schemas(spec: dict[str, Any]) -> dict[str, Any]:
    """Return ``components.schemas`` for optional schema lookups (generator uses refs lightly)."""
    components = spec.get("components") or {}
    return components.get("schemas") or {}


def get_operations(spec: dict[str, Any], tag_filter: list[str] | None = None) -> list[tuple[str, str, dict]]:
    """
    List every operation as ``(path_template, http_method, operation_dict)``.

    If ``tag_filter`` is set, only operations whose OpenAPI ``tags`` intersect it are included.
    """
    paths = get_paths(spec)
    out: list[tuple[str, str, dict]] = []
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
            out.append((path_template, method, op))
    return out


def normalize_path_for_base(path_template: str, base_path: str = "/v2") -> str:
    """
    Strip a leading API prefix from a filled path so it matches ``ContractAPIClient.base_url``.

    Example: template ``/api/v1/subject`` with ``base_path`` ``/api/v1`` -> ``/subject``.
    """
    if base_path and path_template.startswith(base_path):
        return path_template[len(base_path) :] or "/"
    return path_template
