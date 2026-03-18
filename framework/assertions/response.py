"""
Shared response assertions — one place to tune messages and status expectations.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx


def assert_status(
    response: httpx.Response,
    expected: int | tuple[int, ...],
    *,
    context: str = "",
) -> None:
    """Assert HTTP status; ``expected`` may be a single code or tuple of allowed codes."""
    allowed = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in allowed:
        body = _short_body(response)
        msg = f"Expected status in {allowed}, got {response.status_code}"
        if context:
            msg = f"{context}: {msg}"
        raise AssertionError(f"{msg}. Body (truncated): {body}")


def assert_json_content_type(response: httpx.Response) -> None:
    ct = (response.headers.get("content-type") or "").lower()
    if "application/json" not in ct and "json" not in ct:
        raise AssertionError(
            f"Expected JSON content-type, got {response.headers.get('content-type')!r}"
        )


def assert_successful_json(
    response: httpx.Response,
    *,
    expected_status: int = 200,
    context: str = "",
) -> Any:
    """
    Assert 200 (or override), JSON content-type, and return parsed JSON.

    Use this in smoke tests to avoid repeating the same three checks.
    """
    assert_status(response, expected_status, context=context)
    assert_json_content_type(response)
    try:
        return response.json()
    except json.JSONDecodeError as e:
        raise AssertionError(f"{context} Invalid JSON: {e}") from e


def _short_body(response: httpx.Response, max_len: int = 500) -> str:
    try:
        t = response.text
    except Exception:
        return "<unreadable>"
    t = t.replace("\n", " ").strip()
    return t[:max_len] + ("..." if len(t) > max_len else "")
