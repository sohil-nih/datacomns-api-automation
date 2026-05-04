"""Paths and defaults for DCC contract runs (uses ``config/projects.yaml`` slug ``dcc``)."""
from __future__ import annotations

from pathlib import Path

from framework.config.loader import get_project_config

DCC_SLUG = "dcc"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_dcc_openapi_path() -> Path:
    cfg = get_project_config(DCC_SLUG)
    if cfg.openapi_path and cfg.openapi_path.is_file():
        return cfg.openapi_path
    raise FileNotFoundError(
        f"DCC OpenAPI file missing for project {DCC_SLUG!r}. "
        "Add projects/dcc/contracts/openapi.json (see openapi_relative in config/projects.yaml)."
    )
