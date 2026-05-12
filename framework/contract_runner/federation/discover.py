"""
Live Federation API discovery for OpenAPI-driven contract tests.

Handles both **DCC-shaped** list payloads (``{ "data": [ ... ] }``) and **Aggregation Layer**
payloads (top-level JSON **array** of per-node blocks, each optional ``data`` list of harmonized rows).
Output keys match ``generate_cases_federation`` (same as ``discover_dcc``): ``organization``,
``namespace``, ``contract_*`` entity path fields, and ``filter_examples``.
"""
from __future__ import annotations

from framework.contract_runner.client import ContractAPIClient
from framework.contract_runner.entity_extract import entity_triple
from framework.contract_runner.filter_extract import build_filter_examples_from_list_payloads


def _merged_harmonized_rows(body: object) -> list[dict]:
    """
    Collect harmonized list rows from a ``/subject``-, ``/sample``-, or ``/file``-style response.

    - **Dict** body: use top-level ``data`` if it is a list of objects.
    - **List** body (AL): concatenate ``block["data"]`` for each block that has a list ``data``.
    """
    if isinstance(body, dict):
        dr = body.get("data")
        if isinstance(dr, list):
            return [r for r in dr if isinstance(r, dict)]
        return []
    if isinstance(body, list):
        out: list[dict] = []
        for block in body:
            if not isinstance(block, dict):
                continue
            inner = block.get("data")
            if isinstance(inner, list):
                for r in inner:
                    if isinstance(r, dict):
                        out.append(r)
        return out
    return []


def _first_triple_from_rows(rows: list[dict]) -> tuple[str, str, str] | None:
    for row in rows:
        t = entity_triple(row)
        if t:
            return t
    return None


def discover_federation(client: ContractAPIClient) -> dict:
    """
    Build path-parameter values and ``filter_examples`` for Federation contract cases.

    Uses ``GET /subject``, ``/sample``, ``/file``, ``/organization`` under ``client.base_url``.
    Supports harmonized ``{data:[]}`` and AL ``[{source, data:[]}, ...]`` list shapes.
    """
    data: dict = {}
    list_params = {"page": 1, "per_page": 50}

    r_sub = client.get("/subject", list_params)
    if r_sub.status_code != 200:
        return data
    rows_sub = _merged_harmonized_rows(r_sub.json())
    if not rows_sub:
        return data
    triple = _first_triple_from_rows(rows_sub)
    if not triple:
        return data
    org, ns, subj_name = triple
    data["organization"] = org
    data["namespace"] = ns
    data["contract_subject_name"] = subj_name
    data["contract_subject_count_field"] = "sex"
    data["contract_sample_count_field"] = "disease_phase"
    data["contract_file_count_field"] = "type"

    rows_samp: list | None = None
    r_samp = client.get("/sample", list_params)
    if r_samp.status_code == 200:
        merged = _merged_harmonized_rows(r_samp.json())
        if merged:
            rows_samp = merged
            t2 = _first_triple_from_rows(merged)
            if t2:
                data["contract_sample_organization"] = t2[0]
                data["contract_sample_namespace"] = t2[1]
                data["contract_sample_name"] = t2[2]

    rows_file: list | None = None
    r_file = client.get("/file", list_params)
    if r_file.status_code == 200:
        merged_f = _merged_harmonized_rows(r_file.json())
        if merged_f:
            rows_file = merged_f
            t3 = _first_triple_from_rows(merged_f)
            if t3:
                data["contract_file_organization"] = t3[0]
                data["contract_file_namespace"] = t3[1]
                data["contract_file_name"] = t3[2]

    r_org = client.get("/organization")
    if r_org.status_code == 200:
        orgs = r_org.json()
        if isinstance(orgs, list) and orgs:
            o0 = orgs[0]
            if isinstance(o0, dict):
                ident = o0.get("identifier")
                name = o0.get("name")
                data["contract_organization_name"] = str(ident) if ident else (str(name) if name else None)
                if not data.get("contract_organization_name"):
                    data.pop("contract_organization_name", None)

    fe = build_filter_examples_from_list_payloads(rows_sub, rows_samp, rows_file)
    if fe:
        data["filter_examples"] = fe

    return data
