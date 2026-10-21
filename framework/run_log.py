"""
One text log per process for raw API (and Memgraph) exchanges.

Each pytest session writes ``logs/pytest_<UTC>.log``. Contract and performance
clients write ``logs/<lane>_<UTC>.log`` (for example ``dcc-contract``). The file
records the target base URL, each request URL, status, elapsed time, and the
response body. Request headers are omitted.

On by default. Set ``DATACOMNS_RUN_LOG=0`` to disable.
``DATACOMNS_RUN_LOG_DIR`` overrides the directory (default ``logs/`` under the repo root).
``DATACOMNS_RUN_LOG_MAX_CHARS`` caps each body (default 5_000_000).
"""

from __future__ import annotations

import json
import os
import socket
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_MAX_CHARS = 5_000_000

_case_label: ContextVar[Optional[str]] = ContextVar("datacomns_run_log_case", default=None)

_guard = threading.Lock()
_lanes: dict[str, "_LaneLog"] = {}
_disabled_after_error = False


def is_run_log_enabled() -> bool:
    """File logging is on unless ``DATACOMNS_RUN_LOG`` is 0, off, false, or no."""
    v = os.environ.get("DATACOMNS_RUN_LOG", "").strip().lower()
    return v not in ("0", "false", "no", "off")


def _max_chars() -> int:
    raw = os.environ.get("DATACOMNS_RUN_LOG_MAX_CHARS", "").strip()
    if not raw:
        return _DEFAULT_MAX_CHARS
    try:
        return max(1_000, int(raw))
    except ValueError:
        return _DEFAULT_MAX_CHARS


def _log_dir() -> Path:
    override = os.environ.get("DATACOMNS_RUN_LOG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return _REPO_ROOT / "logs"


def _env_label(base_url: Optional[str]) -> str:
    label = (os.environ.get("DATACOMNS_ENV") or os.environ.get("CCDI_ENV") or "").strip()
    if label:
        return label
    blob = " ".join(
        part
        for part in (
            base_url or "",
            os.environ.get("DATACOMNS_DCC_BASE_URL", ""),
            os.environ.get("DATACOMNS_FEDERATION_BASE_URL", ""),
        )
        if part
    ).lower()
    if "qa" in blob:
        return "QA (inferred from URL host)"
    if "stage" in blob or "staging" in blob:
        return "Staging (inferred from URL host)"
    if "prod" in blob:
        return "Production (inferred from URL host)"
    if blob.strip():
        return "Custom / dev target"
    return "Unknown (set DATACOMNS_ENV or API base URLs)"


def _clip(text: str) -> str:
    limit = _max_chars()
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, {len(text)} chars; raise DATACOMNS_RUN_LOG_MAX_CHARS]"


def pretty_body(text: str) -> str:
    """Pretty-print JSON text. Non-JSON is returned unchanged."""
    stripped = text.strip()
    if not stripped:
        return text
    if stripped[0] not in "{[":
        return text
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return text
    return json.dumps(data, indent=2, default=str)


@contextmanager
def log_scope(label: str) -> Iterator[None]:
    """Attach a case label (operation id, summary) to exchanges on this thread."""
    token = _case_label.set(label)
    try:
        yield
    finally:
        _case_label.reset(token)


def current_case_label() -> Optional[str]:
    return _case_label.get()


class _LaneLog:
    def __init__(self, lane: str, path: Path, handle, base_url: Optional[str]) -> None:
        self.lane = lane
        self.path = path
        self._handle = handle
        self._lock = threading.Lock()
        self._n = 0
        self._write_header(base_url)

    def _write_header(self, base_url: Optional[str]) -> None:
        started = datetime.now(timezone.utc).isoformat()
        lines = [
            "===== datacomns run log =====",
            f"lane: {self.lane}",
            f"started_utc: {started}",
            f"environment: {_env_label(base_url)}",
            f"base_url: {base_url or '(see each request URL)'}",
            f"DATACOMNS_DCC_BASE_URL: {os.environ.get('DATACOMNS_DCC_BASE_URL', '').strip() or '(unset)'}",
            f"DATACOMNS_FEDERATION_BASE_URL: {os.environ.get('DATACOMNS_FEDERATION_BASE_URL', '').strip() or '(unset)'}",
            f"hostname: {socket.gethostname()}",
            f"body_max_chars: {_max_chars()}",
            "note: JSON bodies are pretty-printed. Request headers are not recorded.",
            "=============================",
            "",
        ]
        self._handle.write("\n".join(lines))
        self._handle.flush()

    def section(self, lines: list[str]) -> None:
        with self._lock:
            self._n += 1
            numbered = list(lines)
            if numbered:
                numbered[0] = f"#{self._n} {numbered[0]}"
            block = "\n".join(
                [
                    "-" * 80,
                    *numbered,
                    "-" * 80,
                    "",
                ]
            )
            self._handle.write(block)
            self._handle.flush()


def _open_lane(lane: str, base_url: Optional[str]) -> Optional[_LaneLog]:
    global _disabled_after_error
    if not is_run_log_enabled() or _disabled_after_error:
        return None
    with _guard:
        existing = _lanes.get(lane)
        if existing is not None:
            return existing
        try:
            directory = _log_dir()
            directory.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in lane) or "run"
            path = directory / f"{safe}_{stamp}.log"
            handle = path.open("w", encoding="utf-8")
            opened = _LaneLog(lane, path, handle, base_url)
        except OSError as exc:
            _disabled_after_error = True
            print(f"[datacomns] Could not open run log: {exc}", flush=True)
            return None
        _lanes[lane] = opened
        print(f"[datacomns] Run log: {path}", flush=True)
        return opened


def opened_log_paths() -> list[Path]:
    """Paths opened in this process, in open order."""
    with _guard:
        return [lane.path for lane in _lanes.values()]


def note_pytest_test(nodeid: str) -> None:
    """Write a banner when a pytest test starts, before its requests."""
    lane = _open_lane("pytest", None)
    if lane is None:
        return
    lane.section([f"TEST {nodeid}"])


def log_api_exchange(
    *,
    lane: str,
    method: str,
    url: str,
    status: int,
    response_body: str,
    elapsed_ms: Optional[float] = None,
    request_body: Optional[str] = None,
    base_url: Optional[str] = None,
    test: Optional[str] = None,
) -> None:
    """Append one HTTP exchange. No-op when run logging is disabled."""
    opened = _open_lane(lane, base_url)
    if opened is None:
        return
    lines = [f"API {method} {url}"]
    if test:
        lines.append(f"test: {test}")
    case = current_case_label()
    if case:
        lines.append(f"case: {case}")
    if request_body:
        lines.append("REQUEST BODY:")
        lines.append(_clip(pretty_body(request_body)))
    lines.append(f"status: {status}")
    if elapsed_ms is not None:
        lines.append(f"elapsed_ms: {elapsed_ms:.1f}")
    lines.append("RESPONSE:")
    lines.append(_clip(pretty_body(response_body)))
    opened.section(lines)


def log_memgraph_rows(*, label: str, body: str, test: Optional[str] = None) -> None:
    """Append Memgraph rows captured during a pytest run."""
    opened = _open_lane("pytest", None)
    if opened is None:
        return
    lines = [f"MEMGRAPH {label}"]
    if test:
        lines.append(f"test: {test}")
    lines.append("ROWS:")
    lines.append(_clip(body))
    opened.section(lines)


def active_test_nodeid() -> Optional[str]:
    """Pytest nodeid bound by the report fixture, if a test is running."""
    try:
        from framework.reporting.run_context import current_test_nodeid
    except ImportError:
        return None
    return current_test_nodeid()


def log_lane_for_base_url(base_url: str) -> str:
    """Pick a log filename lane from the API host (federation before dcc)."""
    host = urlparse(base_url).netloc.lower()
    if "federation" in host:
        return "federation-contract"
    if "dcc" in host:
        return "dcc-contract"
    return "contract"
