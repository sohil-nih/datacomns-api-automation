"""
Execute one validation pair: Cypher + HTTP + compare.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple


def _report_body_char_limit() -> int:
    """Max JSON chars stored in HTML report (API + DB). Override with DATACOMNS_REPORT_BODY_MAX_CHARS."""
    try:
        return max(500_000, int(os.environ.get("DATACOMNS_REPORT_BODY_MAX_CHARS", "50000000")))
    except ValueError:
        return 50_000_000

from framework.assertions.response import assert_successful_json
from framework.http.client import ApiClient
from framework.memgraph.client import MemgraphBoltClient
from framework.memgraph.compare import compare_results
from framework.memgraph.pairs import ValidationPair
from framework.reporting.run_context import record_api_db_comparison
from framework.response_print import print_memgraph_rows

_COMPARISON_WHAT: Dict[str, str] = {
    "list_length_match": "Memgraph row count vs API list length — must be equal.",
    "row_count_matches_api_list": "Same as list_length_match.",
    "api_identifiers_subset_of_graph": "Each API subject’s (organization, namespace, name) triple must exist in Memgraph rows.",
    "identifier_set_subset": "Same as api_identifiers_subset_of_graph.",
    "graph_min_rows_and_api_list_nonempty": "Memgraph has at least min_graph_rows; API list is non-empty.",
    "graph_min_rows_and_api_json_nonempty": "Memgraph has at least min_graph_rows; API returns non-empty JSON object or list.",
    "graph_min_rows_api_object": "Same as graph_min_rows_and_api_json_nonempty.",
    "graph_institutions_subset_of_dcc_organization_api": (
        "Each distinct Memgraph institution string must appear in the DCC /organization response "
        "(org name, identifier, short_name, metadata.institution[].value)."
    ),
    "dcc_institutions_in_api": "Same as graph_institutions_subset_of_dcc_organization_api.",
    "dcc_value_count_buckets_match": (
        "DCC aggregate JSON: API missing + values[].{value,count} must match Memgraph buckets "
        "(null/empty graph value ↔ API missing)."
    ),
    "dcc_tumor_grade_count_match": "Same as dcc_value_count_buckets_match.",
    "dcc_scalar_match": (
        "Single Memgraph aggregate (one row, one column) must equal an integer in the API JSON "
        "(configurable path, e.g. counts.total)."
    ),
    "graph_scalar_vs_api_json": "Same as dcc_scalar_match.",
    "graph_study_ids_in_dcc_namespace_api": (
        "Each distinct Memgraph study id (column) must appear as id.name in GET /namespace array."
    ),
    "dcc_namespace_study_ids_in_api": "Same as graph_study_ids_in_dcc_namespace_api.",
}


def _what_compared(comparison: Dict[str, Any]) -> str:
    t = (comparison.get("type") or "").strip().lower()
    return _COMPARISON_WHAT.get(t, f"Comparison rule: {t or 'unknown'}")


def _preview_json(data: Any, max_chars: int) -> str:
    try:
        s = json.dumps(data, indent=2, default=str)
    except (TypeError, ValueError):
        s = repr(data)
    if len(s) > max_chars:
        return s[:max_chars] + "\n... [truncated]"
    return s


def _what_data_compared_steps(pair: ValidationPair, graph_rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Plain-English steps for the report: DB side, API side, comparison rule.
    """
    ct = (pair.comparison.get("type") or "").strip().lower()
    api_ep = f"{pair.api_method} {pair.api_path}"
    if ct in (
        "graph_institutions_subset_of_dcc_organization_api",
        "dcc_institutions_in_api",
    ):
        col = pair.comparison.get("graph_column", "institution")
        nrows = len(graph_rows)
        nd = len(
            {str(r.get(col) or "").strip() for r in graph_rows if str(r.get(col) or "").strip()}
        )
        return [
            {
                "side": "database",
                "title": "Data from the database",
                "text": (
                    f'We read Memgraph column "{col}" from {nrows} row(s) returned by this pair’s Cypher query. '
                    f"There are {nd} distinct non-empty values — institution strings from study personnel in the graph."
                ),
            },
            {
                "side": "api",
                "title": "Data from the API (what the UI uses)",
                "text": (
                    f'We call {api_ep} and gather every organization string the API returns: '
                    f"name, identifier, short_name, and metadata.institution[].value for each org."
                ),
            },
            {
                "side": "rule",
                "title": "What we compare",
                "text": (
                    "Each distinct database institution must appear in that combined API string set "
                    "(trimmed, case-insensitive). PASSED = all found. FAILED = one or more DB values missing from the API."
                ),
            },
        ]
    if ct in ("list_length_match", "row_count_matches_api_list"):
        return [
            {
                "side": "database",
                "title": "Data from the database",
                "text": f"Number of rows from Memgraph: {len(graph_rows)}.",
            },
            {
                "side": "api",
                "title": "Data from the API",
                "text": f"We take a list from the JSON returned by {api_ep} and count its items.",
            },
            {
                "side": "rule",
                "title": "What we compare",
                "text": "Memgraph row count must equal API list length.",
            },
        ]
    if ct in ("api_identifiers_subset_of_graph", "identifier_set_subset"):
        return [
            {
                "side": "database",
                "title": "Data from the database",
                "text": "Triple (organization, namespace, subject_id) per Memgraph row.",
            },
            {
                "side": "api",
                "title": "Data from the API",
                "text": f"Each subject from {api_ep} with identifiers (org, namespace, name).",
            },
            {
                "side": "rule",
                "title": "What we compare",
                "text": "Every API triple must exist among the graph rows.",
            },
        ]
    if ct in ("graph_min_rows_and_api_list_nonempty",):
        return [
            {
                "side": "database",
                "title": "Data from the database",
                "text": f"Memgraph returned {len(graph_rows)} row(s); must meet min_graph_rows.",
            },
            {
                "side": "api",
                "title": "Data from the API",
                "text": f"List from {api_ep} must be non-empty.",
            },
            {
                "side": "rule",
                "title": "What we compare",
                "text": "Enough graph rows and at least one API list item.",
            },
        ]
    if ct in ("graph_min_rows_and_api_json_nonempty", "graph_min_rows_api_object"):
        return [
            {
                "side": "database",
                "title": "Data from the database",
                "text": f"{len(graph_rows)} Memgraph row(s).",
            },
            {
                "side": "api",
                "title": "Data from the API",
                "text": f"JSON from {api_ep} must be non-empty.",
            },
            {
                "side": "rule",
                "title": "What we compare",
                "text": "Minimum graph rows and non-empty API JSON.",
            },
        ]
    if ct in ("dcc_value_count_buckets_match", "dcc_tumor_grade_count_match"):
        return [
            {
                "side": "database",
                "title": "Data from the database",
                "text": "One row per distinct tumor_grade (and count of sample+study pairs); null grade → missing bucket.",
            },
            {
                "side": "api",
                "title": "Data from the API",
                "text": f"{api_ep} — fields missing + values[].",
            },
            {
                "side": "rule",
                "title": "What we compare",
                "text": "Per-bucket counts must match (Memgraph null/empty ↔ API missing).",
            },
        ]
    if ct in ("dcc_scalar_match", "graph_scalar_vs_api_json"):
        return [
            {
                "side": "database",
                "title": "Data from the database",
                "text": "Single aggregate row (e.g. COUNT DISTINCT file–sample–study tuples).",
            },
            {
                "side": "api",
                "title": "Data from the API",
                "text": f"{api_ep} — scalar total from JSON.",
            },
            {
                "side": "rule",
                "title": "What we compare",
                "text": "Memgraph aggregate must equal API integer (e.g. counts.total).",
            },
        ]
    if ct in ("graph_study_ids_in_dcc_namespace_api", "dcc_namespace_study_ids_in_api"):
        return [
            {
                "side": "database",
                "title": "Data from the database",
                "text": "Distinct study_id values from participant → study paths.",
            },
            {
                "side": "api",
                "title": "Data from the API",
                "text": f"{api_ep} — namespace catalog (id.name per entry).",
            },
            {
                "side": "rule",
                "title": "What we compare",
                "text": "Every graph study id must appear as some namespace id.name.",
            },
        ]
    return [
        {
            "side": "database",
            "title": "Database",
            "text": "See sample rows below.",
        },
        {
            "side": "api",
            "title": "API",
            "text": f"Endpoint {api_ep}.",
        },
        {
            "side": "rule",
            "title": "Rule",
            "text": _what_compared(pair.comparison),
        },
    ]


def _values_compared_line(graph_rows: List[Dict[str, Any]], comparison: Dict[str, Any]) -> str:
    ctype = (comparison.get("type") or "").strip().lower()
    if ctype in (
        "graph_institutions_subset_of_dcc_organization_api",
        "dcc_institutions_in_api",
    ):
        col = comparison.get("graph_column", "institution")
        vals = sorted(
            {str(r.get(col) or "").strip() for r in graph_rows if str(r.get(col) or "").strip()}
        )
        if not vals:
            return f"Column {col!r}: (no non-empty values in graph rows)"
        shown = vals[:35]
        extra = len(vals) - len(shown)
        tail = f" … and {extra} more distinct values" if extra else ""
        return f"Graph column {col!r} ({len(vals)} distinct): " + "; ".join(shown) + tail
    if ctype in ("list_length_match", "row_count_matches_api_list"):
        return f"Compared: Memgraph row count ({len(graph_rows)}) vs API list length."
    if ctype in ("api_identifiers_subset_of_graph", "identifier_set_subset"):
        return "Compared: API subject identifier triples vs graph columns (organization, namespace, subject_id)."
    if ctype in ("graph_min_rows_and_api_list_nonempty",):
        return f"Compared: graph has ≥min rows; API list non-empty (graph rows: {len(graph_rows)})."
    if ctype in ("graph_min_rows_and_api_json_nonempty", "graph_min_rows_api_object"):
        return f"Compared: graph has ≥min rows; API JSON non-empty (graph rows: {len(graph_rows)})."
    if ctype in ("dcc_value_count_buckets_match", "dcc_tumor_grade_count_match"):
        return (
            f"Compared: {len(graph_rows)} Memgraph bucket row(s) vs API missing + values[] counts."
        )
    if ctype in ("dcc_scalar_match", "graph_scalar_vs_api_json"):
        col = str(comparison.get("graph_scalar_column", "total"))
        return f"Compared: Memgraph {col!r} (1 row) vs API scalar path."
    if ctype in ("graph_study_ids_in_dcc_namespace_api", "dcc_namespace_study_ids_in_api"):
        col = str(comparison.get("graph_column", "namespace_name"))
        return (
            f"Compared: distinct Memgraph {col!r} ({len(graph_rows)} row(s)) vs /namespace id.name set."
        )
    return _what_compared(comparison)


def _database_collected_note(graph_rows: List[Dict[str, Any]]) -> str:
    if not graph_rows:
        return "0 rows returned from the database query."
    keys = list(graph_rows[0].keys())
    kstr = ", ".join(str(k) for k in keys[:18])
    if len(keys) > 18:
        kstr += " …"
    return f"{len(graph_rows)} row(s) collected from DB; columns: {kstr}"


def _api_collected_note(api_json: Any) -> str:
    if api_json is None:
        return ""
    if isinstance(api_json, list):
        return f"API returned a JSON array ({len(api_json)} items) — same data the UI loads from this endpoint."
    if isinstance(api_json, dict):
        kk = list(api_json.keys())[:24]
        return (
            "API returned a JSON object — top-level keys: "
            + ", ".join(str(k) for k in kk)
            + (" …" if len(api_json) > len(kk) else "")
        )
    return "API response (see payload below)."


def _base_event(
    pair: ValidationPair,
    *,
    graph_rows: List[Dict[str, Any]],
    api_json: Any = None,
    api_method: str = "",
    api_path: str = "",
    api_http_status: Optional[int] = None,
) -> Dict[str, Any]:
    ev: Dict[str, Any] = {
        "what_compared": _what_compared(pair.comparison),
        "what_data_compared_steps": _what_data_compared_steps(pair, graph_rows),
        "values_compared_summary": _values_compared_line(graph_rows, pair.comparison),
        "graph_row_count": len(graph_rows),
        "database_collected_note": _database_collected_note(graph_rows),
        "graph_response_preview": _preview_json(graph_rows, _report_body_char_limit()),
        "api_method": api_method or pair.api_method,
        "api_path": api_path or pair.api_path,
    }
    if api_http_status is not None:
        ev["api_http_status"] = api_http_status
    if api_json is not None:
        ev["api_response_preview"] = _preview_json(api_json, _report_body_char_limit())
        ev["api_collected_note"] = _api_collected_note(api_json)
    else:
        ev["api_response_preview"] = ""
        ev["api_collected_note"] = "API response not available yet."
    return ev


def run_validation_pair(
    pair: ValidationPair,
    memgraph: MemgraphBoltClient,
    api_client: ApiClient,
) -> Tuple[Any, Dict[str, Any]]:
    what = _what_compared(pair.comparison)
    ctype = (pair.comparison.get("type") or "").strip().lower()

    graph_rows: list = []
    try:
        graph_rows = memgraph.run_cypher(pair.cypher, pair.cypher_parameters)
    except Exception as e:
        record_api_db_comparison(
            {
                "pair_id": pair.id,
                "comparison_type": ctype,
                "verdict": "ERROR",
                "status": "error",
                "phase": "memgraph",
                "what_compared": what,
                "what_data_compared_steps": _what_data_compared_steps(pair, []),
                "values_compared_summary": "(database query failed — no rows collected)",
                "database_collected_note": "Database query failed before any rows were returned.",
                "api_collected_note": "Not collected (DB step failed).",
                "graph_response_preview": "",
                "api_response_preview": "",
                "detail": str(e)[:8000],
            }
        )
        raise

    print_memgraph_rows(f"pair={pair.id}", graph_rows)

    response = None
    try:
        if pair.api_method == "GET":
            response = api_client.get(pair.api_path, params=pair.api_query or None)
        elif pair.api_method == "POST":
            response = api_client.post(
                pair.api_path,
                json=pair.api_body,
                params=pair.api_query or None,
            )
        else:
            response = api_client.request(
                pair.api_method,
                pair.api_path,
                json=pair.api_body,
                params=pair.api_query or None,
            )
    except Exception as e:
        record_api_db_comparison(
            {
                **_base_event(pair, graph_rows=graph_rows),
                "pair_id": pair.id,
                "comparison_type": ctype,
                "verdict": "ERROR",
                "status": "error",
                "phase": "api_request",
                "detail": str(e)[:8000],
            }
        )
        raise

    if response.status_code >= 400:
        body = ""
        try:
            body = response.text[:800]
        except Exception:
            pass
        raw = {"http_status": response.status_code, "body_excerpt": body}
        record_api_db_comparison(
            {
                **_base_event(pair, graph_rows=graph_rows, api_json=raw, api_http_status=response.status_code),
                "pair_id": pair.id,
                "comparison_type": ctype,
                "verdict": "ERROR",
                "status": "error",
                "phase": "api_http",
                "detail": body,
            }
        )
        raise AssertionError(
            f"[{pair.id}] API {pair.api_method} {pair.api_path} -> {response.status_code}. Body: {body}"
        )

    try:
        api_json = assert_successful_json(response, expected_status=200, context=pair.id)
    except AssertionError as e:
        try:
            api_fail_body: Any = response.json()
        except Exception:
            api_fail_body = {"response_text_excerpt": (response.text or "")[:2500]}
        record_api_db_comparison(
            {
                **_base_event(
                    pair,
                    graph_rows=graph_rows,
                    api_json=api_fail_body,
                    api_http_status=response.status_code,
                ),
                "pair_id": pair.id,
                "comparison_type": ctype,
                "verdict": "ERROR",
                "status": "error",
                "phase": "api_json",
                "detail": str(e)[:8000],
            }
        )
        raise

    be = _base_event(
        pair,
        graph_rows=graph_rows,
        api_json=api_json,
        api_http_status=response.status_code,
    )

    try:
        compare_results(graph_rows, api_json, pair.comparison, pair_id=pair.id)
    except ValueError as e:
        record_api_db_comparison(
            {
                **be,
                "pair_id": pair.id,
                "comparison_type": ctype,
                "verdict": "ERROR",
                "status": "error",
                "phase": "compare_config",
                "detail": str(e)[:8000],
            }
        )
        raise
    except AssertionError as e:
        record_api_db_comparison(
            {
                **be,
                "pair_id": pair.id,
                "comparison_type": ctype,
                "verdict": "FAILED",
                "status": "mismatched",
                "detail": str(e)[:8000],
            }
        )
        raise

    record_api_db_comparison(
        {
            **be,
            "pair_id": pair.id,
            "comparison_type": ctype,
            "verdict": "PASSED",
            "status": "matched",
            "detail": "Rule satisfied: graph and API data are consistent for this pair.",
        }
    )

    summary = {
        "pair_id": pair.id,
        "graph_row_count": len(graph_rows),
        "api_status": response.status_code,
    }
    return api_json, summary
