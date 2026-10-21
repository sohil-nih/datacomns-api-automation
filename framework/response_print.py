"""
Optional stdout logging of API and Memgraph results, plus the per-run text log.

Toggle terminal printing with ``DATACOMNS_PRINT_RESPONSES`` (see
``is_response_printing_enabled``). ``pytest.ini`` adds ``-s`` so stdout is visible.
Set ``DATACOMNS_PRINT_RESPONSES=0`` to skip printing.

The text file under ``logs/`` is separate and stays on when terminal printing is off.
Set ``DATACOMNS_RUN_LOG=0`` to skip the file. See ``framework.run_log``.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Any, List, Optional

from framework.run_log import (
    active_test_nodeid,
    is_run_log_enabled,
    log_api_exchange,
    log_memgraph_rows,
    pretty_body,
)

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


def _memgraph_text(rows: List[Any]) -> str:
    try:
        return json.dumps(rows, indent=2, default=str)
    except TypeError:
        return repr(rows)


def _response_text(response: Any) -> str:
    try:
        data = response.json()
        return json.dumps(data, indent=2, default=str)
    except Exception:
        try:
            return response.text
        except Exception:
            return "<unreadable body>"


def _request_url(response: Any) -> str:
    try:
        return str(response.request.url)
    except Exception:
        return "(unknown url)"


def _request_body(response: Any) -> Optional[str]:
    """Decoded request payload. Headers are not read."""
    try:
        content = response.request.content
    except Exception:
        return None
    if not content:
        return None
    if isinstance(content, bytes):
        text = content.decode("utf-8", errors="replace")
    else:
        text = str(content)
    text = text.strip()
    return text or None


def _elapsed_ms(response: Any) -> Optional[float]:
    elapsed = getattr(response, "elapsed", None)
    if isinstance(elapsed, timedelta):
        return elapsed.total_seconds() * 1000
    return None


def _print_block(rule: str, heading: str, text: str, limit: int) -> None:
    if len(text) > limit:
        text = text[:limit] + "\n... [truncated]"
    print("\n" + rule * 72, flush=True)
    print(heading, flush=True)
    print(rule * 72, flush=True)
    print(text, flush=True)
    print(rule * 72 + "\n", flush=True)


def print_memgraph_rows(label: str, rows: List[Any]) -> None:
    if not is_response_printing_enabled() and not is_run_log_enabled():
        return
    text = _memgraph_text(rows)
    if is_response_printing_enabled():
        _print_block("=", f"[DATACOMNS_PRINT] Memgraph — {label}", text, _MAX_MEMGRAPH_CHARS)
    log_memgraph_rows(label=label, body=pretty_body(text), test=active_test_nodeid())


def print_http_response(method: str, response: Any) -> None:
    """Pretty-print API response body and status (httpx.Response), and append the run log."""
    if not is_response_printing_enabled() and not is_run_log_enabled():
        return
    url = _request_url(response)
    text = _response_text(response)
    if is_response_printing_enabled():
        _print_block(
            "-",
            f"[DATACOMNS_PRINT] API {method} {response.status_code} {url}",
            text,
            _MAX_BODY_CHARS,
        )
    log_api_exchange(
        lane="pytest",
        method=method,
        url=url,
        status=int(getattr(response, "status_code", 0) or 0),
        response_body=text,
        elapsed_ms=_elapsed_ms(response),
        request_body=_request_body(response),
        test=active_test_nodeid(),
    )
