"""
Root pytest hooks: load .env once, register shared behavior.
"""

from pathlib import Path

import pytest

pytest_plugins = ["framework.reporting.autoreport"]

_root = Path(__file__).resolve().parent

# Load .env from repo root before any test imports project config
try:
    from dotenv import load_dotenv

    load_dotenv(_root / ".env")
except ImportError:
    pass


def pytest_configure(config: pytest.Config) -> None:
    """Ensure markers are registered (pytest.ini also lists them)."""
    config.addinivalue_line("markers", "smoke: fast deploy gate")
    config.addinivalue_line("markers", "regression: broader coverage")


@pytest.fixture(autouse=True)
def _datacomns_report_bind_test_nodeid(request):
    """So Memgraph↔API runs can attach comparison rows to this test in the HTML report."""
    try:
        from framework.reporting.run_context import (
            reset_active_test_nodeid,
            set_active_test_nodeid,
        )
    except ImportError:
        yield
        return
    tok = set_active_test_nodeid(request.node.nodeid)
    yield
    reset_active_test_nodeid(tok)


@pytest.fixture(autouse=True)
def _datacomns_show_printed_responses(request):
    """
    When response printing is on, disable capture via capsys (backup to ``-s`` in pytest.ini).
    """
    try:
        from framework.response_print import is_response_printing_enabled
    except ImportError:
        yield
        return
    if not is_response_printing_enabled():
        yield
        return
    try:
        capsys = request.getfixturevalue("capsys")
    except Exception:
        yield
        return
    with capsys.disabled():
        yield
