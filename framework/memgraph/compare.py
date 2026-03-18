"""
Compare Memgraph row results with Federation API JSON using pair.comparison rules.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from framework.memgraph.jsonpath_util import first_existing_path


def _api_subject_identifier_triple(subject: Dict[str, Any]) -> Optional[Tuple[Any, Any, Any]]:
    """Extract (organization, namespace_name, subject_name) from API subject payload."""
    ids = subject.get("identifiers")
    if not isinstance(ids, list) or not ids:
        return None
    first = ids[0]
    if not isinstance(first, dict):
        return None
    v = first.get("value")
    if not isinstance(v, dict):
        return None
    ns = v.get("namespace")
    if not isinstance(ns, dict):
        return None
    org = ns.get("organization")
    ns_name = ns.get("name")
    name = v.get("name")
    if org is None and ns_name is None and name is None:
        return None
    return (org, ns_name, name)


def _normalize_cell(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def compare_results(
    graph_rows: List[Dict[str, Any]],
    api_json: Any,
    comparison: Dict[str, Any],
    *,
    pair_id: str = "",
) -> None:
    """
    Raise AssertionError with context if comparison fails.
    """
    ctype = (comparison.get("type") or "").strip().lower()

    if ctype in ("list_length_match", "row_count_matches_api_list"):
        _cmp_list_length(graph_rows, api_json, comparison, pair_id=pair_id)
    elif ctype in ("api_identifiers_subset_of_graph", "identifier_set_subset"):
        _cmp_identifier_subset(graph_rows, api_json, comparison, pair_id=pair_id)
    elif ctype == "graph_min_rows_and_api_list_nonempty":
        _cmp_graph_min_and_api_nonempty(graph_rows, api_json, comparison, pair_id=pair_id)
    elif ctype in ("graph_min_rows_and_api_json_nonempty", "graph_min_rows_api_object"):
        _cmp_graph_min_and_api_json_nonempty(graph_rows, api_json, comparison, pair_id=pair_id)
    elif ctype in (
        "graph_institutions_subset_of_dcc_organization_api",
        "dcc_institutions_in_api",
    ):
        _cmp_graph_institutions_subset_dcc_org_api(
            graph_rows, api_json, comparison, pair_id=pair_id
        )
    elif ctype in ("dcc_value_count_buckets_match", "dcc_tumor_grade_count_match"):
        _cmp_dcc_value_count_buckets(graph_rows, api_json, comparison, pair_id=pair_id)
    elif ctype in ("dcc_scalar_match", "graph_scalar_vs_api_json"):
        _cmp_dcc_scalar_match(graph_rows, api_json, comparison, pair_id=pair_id)
    elif ctype in (
        "graph_study_ids_in_dcc_namespace_api",
        "dcc_namespace_study_ids_in_api",
    ):
        _cmp_graph_study_ids_in_dcc_namespace_api(
            graph_rows, api_json, comparison, pair_id=pair_id
        )
    else:
        raise ValueError(
            f"{pair_id}: unknown comparison.type {ctype!r}. "
            "Supported: list_length_match, api_identifiers_subset_of_graph, "
            "graph_min_rows_and_api_list_nonempty, graph_min_rows_and_api_json_nonempty, "
            "graph_institutions_subset_of_dcc_organization_api, dcc_value_count_buckets_match, "
            "dcc_scalar_match, graph_study_ids_in_dcc_namespace_api"
        )


def _resolve_api_list(api_json: Any, comparison: Dict[str, Any]) -> List[Any]:
    paths = comparison.get("api_list_path")
    if paths is None:
        paths = [
            "data.subjects",
            "subjects",
            "data.results",
            "results",
            "data",
            "items",
        ]
    elif isinstance(paths, str):
        paths = [paths]
    else:
        paths = list(paths)
    raw = first_existing_path(api_json, paths)
    if raw is None:
        raise AssertionError(
            f"Could not resolve API list from paths {paths}. Top-level keys: "
            f"{list(api_json.keys()) if isinstance(api_json, dict) else type(api_json)}"
        )
    if not isinstance(raw, list):
        raise AssertionError(f"API path resolved to {type(raw).__name__}, expected list")
    return raw


def _cmp_list_length(
    graph_rows: List[Dict[str, Any]],
    api_json: Any,
    comparison: Dict[str, Any],
    *,
    pair_id: str,
) -> None:
    api_list = _resolve_api_list(api_json, comparison)
    g = len(graph_rows)
    a = len(api_list)
    if g != a:
        raise AssertionError(
            f"[{pair_id}] list_length_match: Memgraph row count {g} != API list length {a}. "
            f"Tune Cypher LIMIT/filters or api_list_path to match the same slice."
        )


def _cmp_identifier_subset(
    graph_rows: List[Dict[str, Any]],
    api_json: Any,
    comparison: Dict[str, Any],
    *,
    pair_id: str,
) -> None:
    org_k = comparison.get("graph_key_organization", "organization")
    ns_k = comparison.get("graph_key_namespace", "namespace")
    sid_k = comparison.get("graph_key_subject", "subject_id")

    graph_set: Set[Tuple[str, str, str]] = set()
    for row in graph_rows:
        t = (
            _normalize_cell(row.get(org_k)),
            _normalize_cell(row.get(ns_k)),
            _normalize_cell(row.get(sid_k)),
        )
        if any(t):
            graph_set.add(t)

    if not graph_set:
        raise AssertionError(
            f"[{pair_id}] Graph returned no identifier rows — check Cypher and column names "
            f"({org_k}, {ns_k}, {sid_k})."
        )

    api_list = _resolve_api_list(api_json, comparison)
    missing: List[Any] = []
    for subj in api_list:
        if not isinstance(subj, dict):
            continue
        triple = _api_subject_identifier_triple(subj)
        if triple is None:
            continue
        nt = (
            _normalize_cell(triple[0]),
            _normalize_cell(triple[1]),
            _normalize_cell(triple[2]),
        )
        if nt not in graph_set:
            missing.append(nt)

    if missing:
        sample = missing[:5]
        raise AssertionError(
            f"[{pair_id}] API subject identifier(s) not found in graph set (sample): {sample}. "
            f"Graph distinct rows (cap 5): {list(graph_set)[:5]}"
        )


def _cmp_graph_min_and_api_nonempty(
    graph_rows: List[Dict[str, Any]],
    api_json: Any,
    comparison: Dict[str, Any],
    *,
    pair_id: str,
) -> None:
    min_rows = int(comparison.get("min_graph_rows", 1))
    if len(graph_rows) < min_rows:
        raise AssertionError(
            f"[{pair_id}] Expected at least {min_rows} Memgraph rows, got {len(graph_rows)}"
        )
    api_list = _resolve_api_list(api_json, comparison)
    if len(api_list) < 1:
        raise AssertionError(f"[{pair_id}] Expected non-empty API list")


def _dcc_organization_api_all_strings(api_json: Any) -> Set[str]:
    """
    Flatten DCC GET /api/v1/organization payload: root list of orgs with
    name, identifier, and metadata.institution[].value.
    """
    if isinstance(api_json, list):
        roots: List[Any] = api_json
    elif isinstance(api_json, dict):
        raw = first_existing_path(
            api_json, ["data", "organizations", "organization", "items", "results"]
        )
        roots = raw if isinstance(raw, list) else []
    else:
        roots = []
    if not isinstance(roots, list):
        return set()
    out: Set[str] = set()
    for org in roots:
        if not isinstance(org, dict):
            continue
        for key in ("name", "identifier", "short_name"):
            v = _normalize_cell(org.get(key))
            if v:
                out.add(v)
        meta = org.get("metadata")
        if isinstance(meta, dict):
            insts = meta.get("institution")
            if isinstance(insts, list):
                for it in insts:
                    if isinstance(it, dict):
                        val = _normalize_cell(it.get("value"))
                        if val:
                            out.add(val)
    return out


def _cmp_graph_institutions_subset_dcc_org_api(
    graph_rows: List[Dict[str, Any]],
    api_json: Any,
    comparison: Dict[str, Any],
    *,
    pair_id: str,
) -> None:
    """
    Each non-empty Memgraph ``institution`` (or configured column) must appear in the
    union of organization names and metadata institution strings from the DCC API.
    Comparison is case-insensitive; whitespace trimmed.
    """
    col = comparison.get("graph_column", "institution")
    api_strings = _dcc_organization_api_all_strings(api_json)
    if not api_strings:
        raise AssertionError(
            f"[{pair_id}] DCC organization API yielded no strings to compare against"
        )
    api_lower = {s.lower() for s in api_strings if s}
    missing: List[str] = []
    seen_graph: Set[str] = set()
    for row in graph_rows:
        inst = _normalize_cell(row.get(col))
        if not inst:
            continue
        key = inst.lower()
        if key in seen_graph:
            continue
        seen_graph.add(key)
        if key not in api_lower:
            missing.append(inst)
    if not seen_graph:
        raise AssertionError(
            f"[{pair_id}] Memgraph returned no non-empty {col!r} rows — check Cypher/schema"
        )
    if missing:
        raise AssertionError(
            f"[{pair_id}] Graph institutions not found in DCC /organization payload "
            f"(sample): {missing[:15]}. API string count={len(api_strings)}."
        )


def _tumor_grade_bucket_key(v: Any) -> str:
    """Map null/empty tumor grade to API ``missing`` bucket; else normalized string key."""
    if v is None:
        return "__missing__"
    s = str(v).strip()
    return "__missing__" if not s else s


def _int_count(x: Any) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def _graph_rows_to_value_count_map(
    graph_rows: List[Dict[str, Any]],
    value_key: str,
    count_key: str,
) -> Dict[str, int]:
    m: Dict[str, int] = {}
    for row in graph_rows:
        k = _tumor_grade_bucket_key(row.get(value_key))
        m[k] = m.get(k, 0) + _int_count(row.get(count_key))
    return m


def _api_dcc_value_count_map(
    api_json: Any, comparison: Dict[str, Any], *, pair_id: str
) -> Dict[str, int]:
    missing_field = str(comparison.get("api_missing_field", "missing"))
    values_field = str(comparison.get("api_values_field", "values"))
    value_subkey = str(comparison.get("api_item_value_key", "value"))
    count_subkey = str(comparison.get("api_item_count_key", "count"))
    if not isinstance(api_json, dict):
        raise AssertionError(
            f"[{pair_id}] dcc_value_count_buckets_match: "
            f"expected API JSON object, got {type(api_json).__name__}"
        )
    m: Dict[str, int] = {"__missing__": _int_count(api_json.get(missing_field))}
    raw_list = api_json.get(values_field)
    if not isinstance(raw_list, list):
        raise AssertionError(
            f"[{pair_id}] dcc_value_count_buckets_match: "
            f".{values_field!r} must be a list, got {type(raw_list).__name__}"
        )
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        k = _tumor_grade_bucket_key(item.get(value_subkey))
        c = _int_count(item.get(count_subkey))
        if k == "__missing__":
            m["__missing__"] = m.get("__missing__", 0) + c
        else:
            m[k] = m.get(k, 0) + c
    return m


def _cmp_dcc_value_count_buckets(
    graph_rows: List[Dict[str, Any]],
    api_json: Any,
    comparison: Dict[str, Any],
    *,
    pair_id: str,
) -> None:
    """
    DCC-style JSON: ``{ "missing": N, "values": [ {"value": str|null, "count": N}, ... ] }``
    vs Memgraph rows with the same bucket keys (null/empty value ↔ ``missing``).

    Used for GET /api/v1/sample/by/tumor_grade/count and similar aggregate endpoints.
    """
    value_key = str(comparison.get("graph_value_key", "value"))
    count_key = str(comparison.get("graph_count_key", "count"))
    api_map = _api_dcc_value_count_map(api_json, comparison, pair_id=pair_id)
    graph_map = _graph_rows_to_value_count_map(graph_rows, value_key, count_key)
    all_keys = set(api_map) | set(graph_map)
    diffs: List[str] = []
    for k in sorted(all_keys, key=lambda x: (x == "__missing__", str(x).lower())):
        a = api_map.get(k, 0)
        g = graph_map.get(k, 0)
        if a != g:
            label = "(missing / null grade)" if k == "__missing__" else repr(k)
            diffs.append(f"{label}: API={a} Memgraph={g}")
    if diffs:
        sample = "; ".join(diffs[:12])
        more = f" … (+{len(diffs) - 12} more)" if len(diffs) > 12 else ""
        raise AssertionError(
            f"[{pair_id}] dcc_value_count_buckets_match: bucket counts differ — {sample}{more}"
        )


def _dcc_namespace_api_id_names(api_json: Any) -> Set[str]:
    """Collect each namespace ``id.name`` from GET /api/v1/namespace (root JSON array)."""
    if not isinstance(api_json, list):
        return set()
    out: Set[str] = set()
    for item in api_json:
        if not isinstance(item, dict):
            continue
        idobj = item.get("id")
        if isinstance(idobj, dict):
            n = _normalize_cell(idobj.get("name"))
            if n:
                out.add(n)
    return out


def _cmp_graph_study_ids_in_dcc_namespace_api(
    graph_rows: List[Dict[str, Any]],
    api_json: Any,
    comparison: Dict[str, Any],
    *,
    pair_id: str,
) -> None:
    """
    Each non-empty Memgraph value in ``graph_column`` (e.g. ``study_id`` / dbGaP id) must appear
    as ``id.name`` on some element of the DCC GET /namespace array.
    """
    col = str(comparison.get("graph_column", "namespace_name"))
    min_rows = int(comparison.get("min_graph_rows", 1))
    if len(graph_rows) < min_rows:
        raise AssertionError(
            f"[{pair_id}] Expected at least {min_rows} Memgraph row(s), got {len(graph_rows)}"
        )
    api_names = _dcc_namespace_api_id_names(api_json)
    if not api_names:
        raise AssertionError(
            f"[{pair_id}] DCC /namespace response has no id.name entries (expected root JSON array)"
        )
    missing: List[str] = []
    seen: Set[str] = set()
    for row in graph_rows:
        v = _normalize_cell(row.get(col))
        if not v:
            continue
        if v in seen:
            continue
        seen.add(v)
        if v not in api_names:
            missing.append(v)
    if not seen:
        raise AssertionError(
            f"[{pair_id}] Memgraph returned no non-empty {col!r} values — check Cypher/schema"
        )
    if missing:
        raise AssertionError(
            f"[{pair_id}] Study/namespace id(s) in Memgraph but not in GET /namespace id.name "
            f"(sample): {missing[:20]}{' …' if len(missing) > 20 else ''}. "
            f"API namespace count={len(api_names)}."
        )


def _cmp_dcc_scalar_match(
    graph_rows: List[Dict[str, Any]],
    api_json: Any,
    comparison: Dict[str, Any],
    *,
    pair_id: str,
) -> None:
    """
    Single aggregate from Memgraph (one row, one numeric column) vs a scalar in API JSON
    (e.g. GET /file/summary → ``counts.total``).
    """
    col = str(comparison.get("graph_scalar_column", "total"))
    paths = comparison.get("api_scalar_paths")
    if paths is None:
        paths = ["counts.total", "total", "data.total"]
    elif isinstance(paths, str):
        paths = [paths]
    else:
        paths = [str(p) for p in paths]
    if not graph_rows:
        raise AssertionError(f"[{pair_id}] dcc_scalar_match: Memgraph returned no rows")
    gval = graph_rows[0].get(col)
    try:
        g = int(gval)
    except (TypeError, ValueError):
        raise AssertionError(
            f"[{pair_id}] dcc_scalar_match: graph column {col!r} not an integer: {gval!r}"
        )
    api_val = first_existing_path(api_json, paths)
    if api_val is None:
        top = list(api_json.keys()) if isinstance(api_json, dict) else type(api_json).__name__
        raise AssertionError(
            f"[{pair_id}] dcc_scalar_match: API JSON has none of paths {paths} (top-level: {top})"
        )
    try:
        a = int(api_val)
    except (TypeError, ValueError):
        raise AssertionError(
            f"[{pair_id}] dcc_scalar_match: API value not int-coercible: {api_val!r}"
        )
    if a != g:
        raise AssertionError(
            f"[{pair_id}] dcc_scalar_match: Memgraph {col}={g} != API {paths[0]!r} (or first matching path)={a}"
        )


def _cmp_graph_min_and_api_json_nonempty(
    graph_rows: List[Dict[str, Any]],
    api_json: Any,
    comparison: Dict[str, Any],
    *,
    pair_id: str,
) -> None:
    """Memgraph returns rows; API returns non-empty dict or non-empty list."""
    min_rows = int(comparison.get("min_graph_rows", 1))
    if len(graph_rows) < min_rows:
        raise AssertionError(
            f"[{pair_id}] Expected at least {min_rows} Memgraph rows, got {len(graph_rows)}"
        )
    ok = False
    if isinstance(api_json, dict) and len(api_json) > 0:
        ok = True
    elif isinstance(api_json, list) and len(api_json) > 0:
        ok = True
    if not ok:
        raise AssertionError(
            f"[{pair_id}] API JSON expected non-empty object or list, got {type(api_json).__name__}"
        )
