"""
Configuration helpers for OpenAPI contract runs.

Resolve OpenAPI paths from ``config/projects.yaml`` for DCC and Federation contract CLIs.
"""
from __future__ import annotations

from pathlib import Path

from framework.config.loader import get_project_config

DCC_SLUG = "dcc"
FEDERATION_SLUG = "federation"


def repo_root() -> Path:
    """Return the datacomns-api-automation repository root (parent of ``framework/``)."""
    return Path(__file__).resolve().parents[2]


def resolve_dcc_openapi_path() -> Path:
    """
    Return the resolved path to the DCC OpenAPI spec (``openapi_relative`` for slug ``dcc``).

    Raises:
        FileNotFoundError: If the file is missing; add ``projects/dcc/contracts/openapi.json``.
    """
    cfg = get_project_config(DCC_SLUG)
    if cfg.openapi_path and cfg.openapi_path.is_file():
        return cfg.openapi_path
    raise FileNotFoundError(
        f"DCC OpenAPI file missing for project {DCC_SLUG!r}. "
        "Add projects/dcc/contracts/openapi.json (see openapi_relative in config/projects.yaml)."
    )


def resolve_federation_openapi_path() -> Path:
    """
    Return the resolved path to the Federation OpenAPI spec (``openapi_relative`` for slug ``federation``).

    Raises:
        FileNotFoundError: If the file is missing; set ``openapi_relative`` in ``config/projects.yaml``.
    """
    cfg = get_project_config(FEDERATION_SLUG)
    if cfg.openapi_path and cfg.openapi_path.is_file():
        return cfg.openapi_path
    raise FileNotFoundError(
        f"Federation OpenAPI file missing for project {FEDERATION_SLUG!r}. "
        "Set openapi_relative under federation in config/projects.yaml (e.g. projects/federation/contracts/federation-v130.yaml)."
    )
