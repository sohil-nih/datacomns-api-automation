"""Load and parse OpenAPI spec (JSON or YAML)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_spec(spec_path: str | Path) -> dict[str, Any]:
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
    return spec.get("paths") or {}


def get_schemas(spec: dict[str, Any]) -> dict[str, Any]:
    components = spec.get("components") or {}
    return components.get("schemas") or {}


def get_operations(spec: dict[str, Any], tag_filter: list[str] | None = None) -> list[tuple[str, str, dict]]:
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
    if base_path and path_template.startswith(base_path):
        return path_template[len(base_path) :] or "/"
    return path_template
