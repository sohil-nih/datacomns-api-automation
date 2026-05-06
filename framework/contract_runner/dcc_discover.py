"""
Live DCC API discovery for OpenAPI-driven contract tests.

Calls list endpoints (``/subject``, ``/sample``, ``/file``, ``/organization``) to collect
real ``organization``, ``namespace``, entity ``name`` values and canned ``field`` keys for
count-by routes, plus ``filter_examples`` (query param → example value from live ``metadata``).
Output is merged into ``test_data`` passed to ``generate_cases_dcc``.
If the first ``/subject`` call fails or returns empty ``data``, returns an empty dict and
few generated cases can be built.
"""
from __future__ import annotations

from framework.contract_runner.client import ContractAPIClient
from framework.contract_runner.dcc_filter_extract import build_filter_examples_from_list_payloads


def _entity_triple(record: dict) -> tuple[str, str, str] | None:
    """Extract (organization, namespace_name, entity_name) from a list row's nested ``id`` object."""
    id_ = record.get("id")
    if not isinstance(id_, dict):
        return None
    ns = id_.get("namespace")
    if not isinstance(ns, dict):
        return None
    org = ns.get("organization")
    ns_name = ns.get("name")
    ent_name = id_.get("name")
    if org is None or ns_name is None or ent_name is None:
        return None
    return str(org), str(ns_name), str(ent_name)


def discover_dcc(client: ContractAPIClient) -> dict:
    """
    Build a dict of path-parameter values for positive generated cases.

    Requires ``client.base_url`` to include the API prefix (e.g. ends with ``/api/v1``).
    Paths used: ``GET /subject``, ``GET /sample``, ``GET /file``, ``GET /organization``.

    Returns:
        Keys such as ``organization``, ``namespace``, ``dcc_subject_name``, sample/file
        triples, ``dcc_organization_name``, fixed count-field strings for ``/by/`` routes,
        and ``filter_examples`` for list-endpoint query filters.
        Empty dict if discovery cannot read at least one subject row.
    """
    data: dict = {}
    list_params = {"page": 1, "per_page": 50}

    r_sub = client.get("/subject", list_params)
    if r_sub.status_code != 200:
        return data
    body_sub = r_sub.json()
    if not isinstance(body_sub, dict):
        return data
    rows_sub = body_sub.get("data")
    if not isinstance(rows_sub, list) or not rows_sub:
        return data
    first_sub = rows_sub[0]
    if not isinstance(first_sub, dict):
        return data
    triple = _entity_triple(first_sub)
    if not triple:
        return data
    org, ns, subj_name = triple
    data["organization"] = org
    data["namespace"] = ns
    data["dcc_subject_name"] = subj_name
    data["dcc_subject_count_field"] = "sex"
    data["dcc_sample_count_field"] = "disease_phase"
    data["dcc_file_count_field"] = "type"

    rows_samp: list | None = None
    r_samp = client.get("/sample", list_params)
    if r_samp.status_code == 200:
        b_s = r_samp.json()
        if isinstance(b_s, dict):
            dr = b_s.get("data")
            rows_samp = dr if isinstance(dr, list) else None
            if isinstance(dr, list) and dr and isinstance(dr[0], dict):
                t2 = _entity_triple(dr[0])
                if t2:
                    data["dcc_sample_organization"] = t2[0]
                    data["dcc_sample_namespace"] = t2[1]
                    data["dcc_sample_name"] = t2[2]

    rows_file: list | None = None
    r_file = client.get("/file", list_params)
    if r_file.status_code == 200:
        b_f = r_file.json()
        if isinstance(b_f, dict):
            dr = b_f.get("data")
            rows_file = dr if isinstance(dr, list) else None
            if isinstance(dr, list) and dr and isinstance(dr[0], dict):
                t3 = _entity_triple(dr[0])
                if t3:
                    data["dcc_file_organization"] = t3[0]
                    data["dcc_file_namespace"] = t3[1]
                    data["dcc_file_name"] = t3[2]

    r_org = client.get("/organization")
    if r_org.status_code == 200:
        orgs = r_org.json()
        if isinstance(orgs, list) and orgs:
            o0 = orgs[0]
            if isinstance(o0, dict):
                ident = o0.get("identifier")
                name = o0.get("name")
                data["dcc_organization_name"] = str(ident) if ident else (str(name) if name else None)
                if not data.get("dcc_organization_name"):
                    data.pop("dcc_organization_name", None)

    fe = build_filter_examples_from_list_payloads(rows_sub, rows_samp, rows_file)
    if fe:
        data["filter_examples"] = fe

    return data
