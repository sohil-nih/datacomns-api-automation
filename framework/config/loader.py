"""
Load project definitions from config/projects.yaml and environment.

Single source of truth for base URLs per project — avoids duplicating URLs in every test file.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

import yaml

from framework.config.models import ProjectConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROJECTS_FILE = _REPO_ROOT / "config" / "projects.yaml"


def _deep_merge_headers(*dicts: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for d in dicts:
        if d:
            out.update({str(k): str(v) for k, v in d.items()})
    return out


def _optional_headers_from_env(env_key: Optional[str]) -> dict[str, str]:
    if not env_key:
        return {}
    raw = os.environ.get(env_key)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        return {}


@lru_cache(maxsize=1)
def _raw_registry() -> dict[str, Any]:
    if not _PROJECTS_FILE.is_file():
        raise FileNotFoundError(
            f"Missing {_PROJECTS_FILE}. Restore config/projects.yaml or create it."
        )
    with open(_PROJECTS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("projects") or {}


def list_project_slugs() -> List[str]:
    """Slugs defined in projects.yaml (for discovery / AI context)."""
    return sorted(_raw_registry().keys())


def get_project_config(slug: str) -> ProjectConfig:
    """
    Resolve ``ProjectConfig`` for ``slug``.

    Raises:
        KeyError: unknown slug
    """
    projects = _raw_registry()
    if slug not in projects:
        raise KeyError(
            f"Unknown project slug {slug!r}. Defined: {list(projects.keys())}. "
            "Add an entry in config/projects.yaml and a folder under projects/."
        )
    row: dict[str, Any] = projects[slug]

    base_url_env = row.get("base_url_env") or ""
    default_base = (row.get("default_base_url") or "").rstrip("/")
    from_env = os.environ.get(base_url_env)
    if not from_env and slug == "federation":
        from_env = os.environ.get("DATACOMNS_CCDI_FEDERATION_BASE_URL")
    base_url = (from_env or default_base).rstrip("/")
    if not base_url:
        raise ValueError(f"Project {slug!r}: no base URL (set {base_url_env} or default_base_url)")

    api_prefix = row.get("api_prefix") or ""
    if api_prefix and not api_prefix.startswith("/"):
        api_prefix = "/" + api_prefix

    openapi_rel = row.get("openapi_relative")
    openapi_path: Optional[Path] = None
    if openapi_rel:
        candidate = (_REPO_ROOT / openapi_rel).resolve()
        if candidate.is_file():
            openapi_path = candidate

    headers_env_key = row.get("optional_headers_env")
    default_headers = _optional_headers_from_env(headers_env_key)

    return ProjectConfig(
        slug=slug,
        display_name=str(row.get("display_name") or slug),
        base_url=base_url,
        api_prefix=api_prefix,
        default_headers=default_headers,
        openapi_path=openapi_path,
    )


def clear_config_cache() -> None:
    """For tests that mutate projects.yaml mid-run; rarely needed."""
    _raw_registry.cache_clear()
