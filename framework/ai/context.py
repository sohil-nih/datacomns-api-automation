"""
Build structured context for LLM / RAG workflows (optional).

Keeps API surface small so you can add OpenAPI text + project metadata without importing AI SDKs here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from framework.config.loader import get_project_config


def build_project_context_bundle(slug: str) -> Dict[str, Any]:
    """
    Return a dict suitable for serializing to JSON or feeding a prompt.

    Keys:
      project_slug, display_name, base_url, api_prefix
      openapi_text: first N chars of OpenAPI file if present (truncate for token limits)
      openapi_path: path string if file exists
    """
    cfg = get_project_config(slug)
    out: Dict[str, Any] = {
        "project_slug": cfg.slug,
        "display_name": cfg.display_name,
        "base_url": cfg.base_url,
        "api_prefix": cfg.api_prefix,
        "openapi_path": str(cfg.openapi_path) if cfg.openapi_path else None,
        "openapi_text": None,
    }
    if cfg.openapi_path and cfg.openapi_path.is_file():
        raw = cfg.openapi_path.read_text(encoding="utf-8", errors="replace")
        max_chars = int(__import__("os").environ.get("DATACOMNS_AI_OPENAPI_MAX_CHARS", "120000"))
        out["openapi_text"] = raw[:max_chars]
        if len(raw) > max_chars:
            out["openapi_truncated"] = True
    return out
