"""
Load Memgraph/API validation pair definitions from YAML (per project).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class ValidationPair:
    """
    One scenario: Cypher + REST call + comparison rule.

    Loaded from ``memgraph_validation/pairs/*.yaml``.
    """

    id: str
    description: str
    tags: List[str]
    cypher: str
    cypher_parameters: Dict[str, Any]
    api_method: str
    api_path: str
    api_query: Dict[str, Any]
    api_body: Optional[Dict[str, Any]]
    comparison: Dict[str, Any]
    source_file: Path

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags


def _require(d: Dict[str, Any], key: str, path: Path) -> Any:
    if key not in d or d[key] is None:
        raise ValueError(f"{path}: missing required key {key!r}")
    return d[key]


def _load_one_yaml(path: Path, memgraph_root: Path) -> ValidationPair:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be a mapping")

    pid = str(_require(raw, "id", path))
    desc = str(raw.get("description") or "")
    tags = list(raw.get("tags") or [])
    if not tags:
        tags = ["memgraph_api"]

    cypher = raw.get("cypher")
    cypher_file = raw.get("cypher_file")
    if cypher_file:
        cy_path = memgraph_root / "cypher" / str(cypher_file)
        if not cy_path.is_file():
            raise FileNotFoundError(f"{path}: cypher_file not found: {cy_path}")
        cypher = cy_path.read_text(encoding="utf-8").strip()
    elif not cypher or not str(cypher).strip():
        raise ValueError(f"{path}: provide cypher or cypher_file")
    else:
        cypher = str(cypher).strip()

    params = dict(raw.get("cypher_parameters") or {})

    api = raw.get("api") or {}
    if not isinstance(api, dict):
        raise ValueError(f"{path}: api must be a mapping")
    method = str(api.get("method") or "GET").upper()
    api_path = str(_require(api, "path", path))
    api_query = dict(api.get("query") or api.get("params") or {})
    api_body = api.get("body")
    if api_body is not None and not isinstance(api_body, dict):
        raise ValueError(f"{path}: api.body must be a mapping or omitted")

    comp = raw.get("comparison") or {}
    if not isinstance(comp, dict) or not comp.get("type"):
        raise ValueError(f"{path}: comparison.type is required")

    return ValidationPair(
        id=pid,
        description=desc,
        tags=tags,
        cypher=cypher,
        cypher_parameters=params,
        api_method=method,
        api_path=api_path,
        api_query=api_query,
        api_body=api_body,
        comparison=comp,
        source_file=path,
    )


def load_validation_pairs(memgraph_validation_root: Path) -> List[ValidationPair]:
    """
    Load all ``pairs/*.yaml`` under ``memgraph_validation_root``.
    ``memgraph_validation_root`` is the folder containing ``pairs/`` and ``cypher/``.
    """
    pairs_dir = memgraph_validation_root / "pairs"
    if not pairs_dir.is_dir():
        return []
    paths = sorted({*pairs_dir.glob("*.yaml"), *pairs_dir.glob("*.yml")})
    out = [_load_one_yaml(p, memgraph_validation_root) for p in paths]
    return sorted(out, key=lambda p: p.id)


def pairs_by_tag(pairs: List[ValidationPair], tag: str) -> List[ValidationPair]:
    return [p for p in pairs if p.has_tag(tag)]
