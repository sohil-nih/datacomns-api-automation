"""
Live Federation API discovery for OpenAPI-driven contract tests.

Same HTTP and payload shape assumptions as ``discover_dcc`` (``GET /subject``, ``/sample``,
``/file``, ``/organization`` under the configured ``.../api/v1`` base). Reuses that
implementation; output keys match ``generate_cases_federation`` expectations.
"""
from __future__ import annotations

from framework.contract_runner.client import ContractAPIClient
from framework.contract_runner.dcc_discover import discover_dcc


def discover_federation(client: ContractAPIClient) -> dict:
    """
    Build path-parameter values and ``filter_examples`` for Federation contract cases.

    Delegates to ``discover_dcc`` because the Federation Resource API list shapes align
    with the DCC discovery flow for these endpoints.
    """
    return discover_dcc(client)
