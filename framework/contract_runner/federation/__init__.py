"""Federation Aggregation Layer OpenAPI contract (discover, generate, run)."""

from framework.contract_runner.federation.discover import discover_federation
from framework.contract_runner.federation.generator import generate_cases_federation

__all__ = ["discover_federation", "generate_cases_federation"]
