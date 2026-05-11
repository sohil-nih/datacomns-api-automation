"""DCC OpenAPI contract and performance CLIs (discover, generate, run)."""

from framework.contract_runner.dcc.discover import discover_dcc
from framework.contract_runner.dcc.generator import generate_cases_dcc

__all__ = ["discover_dcc", "generate_cases_dcc"]
