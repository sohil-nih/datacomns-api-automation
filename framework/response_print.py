"""
Optional stdout logging of API and Memgraph results.

Toggle with ``DATACOMNS_PRINT_RESPONSES`` (see ``is_response_printing_enabled``).
``pytest.ini`` adds ``-s`` so stdout is visible. Set ``DATACOMNS_PRINT_RESPONSES=0``
to skip printing entirely.
"""

from __future__ import annotations

import json
import os
from typing import Any, List

_MAX_BODY_CHARS = 200_000
_MAX_MEMGRAPH_CHARS = 200_000


def is_response_printing_enabled() -> bool:
    """
    Printing is **on by default**.

    Set ``DATACOMNS_PRINT_RESPONSES`` to ``0``, ``off``, ``false``, or ``no`` to turn **off**.
    """
    v = os.environ.get("DATACOMNS_PRINT_RESPONSES", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def print_memgraph_rows(label: str, rows: List[Any]) -> None:
    if not is_response_printing_enabled():
        return
    print("\n" + "=" * 72, flush=True)
    print(f"[DATACOMNS_PRINT] Memgraph — {label}", flush=True)
    print("=" * 72, flush=True)
    try:
        text = json.dumps(rows, indent=2, default=str)
    except TypeError:
        text = repr(rows)
    if len(text) > _MAX_MEMGRAPH_CHARS:
        text = text[:_MAX_MEMGRAPH_CHARS] + f"\n... [truncated, {len(rows)} rows]"
    print(text, flush=True)
    print("=" * 72 + "\n", flush=True)


def print_http_response(method: str, response: Any) -> None:
    """Pretty-print API response body and status (httpx.Response)."""
    if not is_response_printing_enabled():
        return
    try:
        url = str(response.request.url)
    except Exception:
        url = "(unknown url)"
    print("\n" + "-" * 72, flush=True)
    print(f"[DATACOMNS_PRINT] API {method} {response.status_code} {url}", flush=True)
    print("-" * 72, flush=True)
    try:
        data = response.json()
        text = json.dumps(data, indent=2, default=str)
    except Exception:
        try:
            text = response.text
        except Exception:
            text = "<unreadable body>"
    if len(text) > _MAX_BODY_CHARS:
        text = text[:_MAX_BODY_CHARS] + "\n... [truncated]"
    print(text, flush=True)
    print("-" * 72 + "\n", flush=True)
