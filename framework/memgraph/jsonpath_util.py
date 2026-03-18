"""
Navigate dict/list structures using dotted paths (e.g. data.subjects).
Supports numeric segments for list indices.
"""

from __future__ import annotations

from typing import Any, List, Optional, Union


def get_at_path(data: Any, path: Union[str, List[str], None]) -> Any:
    """
    ``path`` is dot-separated string or list of keys. Empty / None returns ``data``.
    Integer-like segments index into lists.
    """
    if path is None or path == "":
        return data
    if isinstance(path, str):
        parts = [p for p in path.split(".") if p]
    else:
        parts = list(path)
    cur: Any = data
    for part in parts:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            if part.isdigit():
                idx = int(part)
                cur = cur[idx] if 0 <= idx < len(cur) else None
            else:
                return None
        else:
            return None
    return cur


def first_existing_path(data: Any, paths: List[str]) -> Any:
    """Return first non-None navigated value, or None if none match."""
    for p in paths:
        v = get_at_path(data, p)
        if v is not None:
            return v
    return None
