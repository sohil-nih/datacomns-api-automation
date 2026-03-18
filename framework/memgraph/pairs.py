"""
Load Memgraph/API validation pair definitions from YAML (per project).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# memgraph_validation_root/cypher/<file> -> parsed query map (lazy)
_queries_yaml_cache: Dict[Path, Dict[str, str]] = {}


def _load_queries_yaml(queries_yaml_path: Path) -> Dict[str, str]:
    """Load a YAML file whose top-level string values are Cypher queries."""
    resolved = queries_yaml_path.resolve()
    if resolved not in _queries_yaml_cache:
        if not resolved.is_file():
            raise FileNotFoundError(f"Cypher queries YAML not found: {resolved}")
        with open(resolved, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, dict):
            raise ValueError(f"{resolved}: root must be a mapping of query_name -> cypher string")
        out: Dict[str, str] = {}
        for k, v in raw.items():
            if k is None or str(k).startswith("#"):
                continue
            if v is None:
                continue
            key = str(k)
            if isinstance(v, dict):
                raise ValueError(f"{resolved}: key {key!r} must be a string (block scalar), not a mapping")
            out[key] = str(v).strip()
            if not out[key]:
                raise ValueError(f"{resolved}: query {key!r} is empty")
        _queries_yaml_cache[resolved] = out
    return _queries_yaml_cache[resolved]


def clear_queries_yaml_cache() -> None:
    """Test hook: invalidate cached queries YAML."""
    _queries_yaml_cache.clear()


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
    cypher_query_key = raw.get("cypher_query_key")
    cypher_queries_yaml = raw.get("cypher_queries_yaml") or "queries.yaml"

    has_inline = bool(cypher and str(cypher).strip())
    has_file = bool(cypher_file)
    has_yaml_key = bool(cypher_query_key and str(cypher_query_key).strip())
    n = sum([has_inline, has_file, has_yaml_key])
    if n > 1:
        raise ValueError(
            f"{path}: use exactly one of inline cypher, cypher_file, or cypher_query_key"
        )
    if has_yaml_key:
        qyaml = memgraph_root / "cypher" / str(cypher_queries_yaml)
        bundle = _load_queries_yaml(qyaml)
        key = str(cypher_query_key).strip()
        if key not in bundle:
            raise KeyError(
                f"{path}: cypher_query_key {key!r} not in {qyaml} "
                f"(keys: {sorted(bundle.keys())})"
            )
        cypher = bundle[key]
    elif has_file:
        cy_path = memgraph_root / "cypher" / str(cypher_file)
        if not cy_path.is_file():
            raise FileNotFoundError(f"{path}: cypher_file not found: {cy_path}")
        cypher = cy_path.read_text(encoding="utf-8").strip()
    elif has_inline:
        cypher = str(cypher).strip()
    else:
        raise ValueError(
            f"{path}: provide cypher, cypher_file, or cypher_query_key (+ queries YAML)"
        )

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
