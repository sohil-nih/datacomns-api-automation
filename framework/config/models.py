"""Typed configuration for a single API project (no I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class ProjectConfig:
    """
    Resolved settings for one API project.

    All URL/path resolution is done in the loader; tests receive a ready-to-use config.
    """

    slug: str
    display_name: str
    base_url: str
    api_prefix: str
    default_headers: dict[str, str]
    openapi_path: Optional[Path]

    def url_for(self, path: str) -> str:
        """
        Build full URL: base_url + api_prefix + path.

        ``path`` should start with / (e.g. '/subject/summary'). If path is absolute http(s),
        it is returned unchanged.
        """
        p = path.strip()
        if p.startswith("http://") or p.startswith("https://"):
            return p
        if not p.startswith("/"):
            p = "/" + p
        base = self.base_url.rstrip("/")
        prefix = (self.api_prefix or "").rstrip("/")
        return f"{base}{prefix}{p}"
