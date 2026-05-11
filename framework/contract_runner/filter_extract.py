"""
Harvest concrete query-filter values from harmonized list API rows for contract case generation.

Maps ``metadata`` shapes returned by ``GET /subject``, ``GET /sample``, and ``GET /file``
to OpenAPI query parameter names. Shared by DCC and Federation discovery (``filter_examples``)
and filter semantic checks in the functional runner.
"""
from __future__ import annotations

from typing import Any, Callable

_FILTER_MATCH_MODE: dict[str, dict[str, str]] = {
    "subject": {
        "associated_diagnosis_categories": "contains_ci",
    },
    "sample": {
        "diagnosis": "contains_ci",
        "diagnosis_category": "contains_ci",
    },
    "file": {
        "description": "contains_ci",
    },
}


def _as_query_string(v: Any) -> str | None:
    """Normalize a metadata leaf to a non-empty query string."""
    if v is None:
        return None
    if isinstance(v, bool):
        return str(v).lower()
    s = str(v).strip()
    return s if s else None


def _scalar_value(meta: dict, key: str) -> Any:
    """``metadata[key].value`` for singly wrapped fields."""
    block = meta.get(key)
    if not isinstance(block, dict):
        return None
    return block.get("value")


def _first_list_item_value(meta: dict, key: str) -> Any:
    """First ``item.value`` where ``metadata[key]`` is a list of dicts."""
    items = meta.get(key)
    if not isinstance(items, list) or not items:
        return None
    first = items[0]
    if not isinstance(first, dict):
        return None
    return first.get("value")


def _subject_row_filters(meta: dict) -> dict[str, str]:
    """One row's worth of subject list query params (only keys with values)."""
    out: dict[str, str] = {}
    for key in ("sex", "ethnicity", "vital_status"):
        v = _as_query_string(_scalar_value(meta, key))
        if v:
            out[key] = v
    rv = _first_list_item_value(meta, "race")
    v = _as_query_string(rv)
    if v:
        out["race"] = v
    av = _scalar_value(meta, "age_at_vital_status")
    v = _as_query_string(av)
    if v:
        out["age_at_vital_status"] = v
    deps = meta.get("depositions")
    if isinstance(deps, list) and deps:
        d0 = deps[0]
        if isinstance(d0, dict):
            dv = _as_query_string(d0.get("value"))
            if dv:
                out["depositions"] = dv
    ident = meta.get("identifiers")
    if isinstance(ident, list) and ident:
        i0 = ident[0]
        if isinstance(i0, dict):
            inner = i0.get("value")
            if isinstance(inner, dict):
                name = _as_query_string(inner.get("name"))
                if name:
                    out["identifiers"] = name
    cats = meta.get("associated_diagnosis_categories")
    if isinstance(cats, list) and cats:
        c0 = cats[0]
        if isinstance(c0, dict):
            cv = _as_query_string(c0.get("value"))
            if cv:
                out["associated_diagnosis_categories"] = cv
    elif isinstance(cats, dict):
        cv = _as_query_string(cats.get("value"))
        if cv:
            out["associated_diagnosis_categories"] = cv
    return out


def _sample_row_filters(meta: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    scalars = (
        "disease_phase",
        "library_selection_method",
        "library_strategy",
        "library_source_material",
        "preservation_method",
        "tumor_grade",
        "specimen_molecular_analyte_type",
        "tissue_type",
        "tumor_classification",
        "diagnosis",
        "tumor_tissue_morphology",
    )
    for key in scalars:
        v = _as_query_string(_scalar_value(meta, key))
        if v:
            out[key] = v
    for key in ("age_at_diagnosis", "age_at_collection"):
        v = _as_query_string(_scalar_value(meta, key))
        if v:
            out[key] = v
    av = _first_list_item_value(meta, "anatomical_sites")
    v = _as_query_string(av)
    if v:
        out["anatomical_sites"] = v
    deps = meta.get("depositions")
    if isinstance(deps, list) and deps:
        d0 = deps[0]
        if isinstance(d0, dict):
            dv = _as_query_string(d0.get("value"))
            if dv:
                out["depositions"] = dv
    ident = meta.get("identifiers")
    if isinstance(ident, list) and ident:
        i0 = ident[0]
        if isinstance(i0, dict):
            inner = i0.get("value")
            if isinstance(inner, dict):
                name = _as_query_string(inner.get("name"))
                if name:
                    out["identifiers"] = name
    dcat = meta.get("diagnosis_category")
    if isinstance(dcat, list) and dcat:
        c0 = dcat[0]
        if isinstance(c0, dict):
            dv = _as_query_string(c0.get("value"))
            if dv:
                out["diagnosis_category"] = dv
    elif isinstance(dcat, dict):
        dv = _as_query_string(dcat.get("value"))
        if dv:
            out["diagnosis_category"] = dv
    return out


def _file_row_filters(meta: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    v = _as_query_string(_scalar_value(meta, "type"))
    if v:
        out["type"] = v
    v = _as_query_string(_scalar_value(meta, "size"))
    if v:
        out["size"] = v
    desc = _scalar_value(meta, "description")
    v = _as_query_string(desc)
    if v:
        out["description"] = v
    chk = meta.get("checksums")
    if isinstance(chk, dict):
        inner = chk.get("value")
        if isinstance(inner, dict):
            md5 = _as_query_string(inner.get("md5"))
            if md5:
                out["checksums"] = md5
    deps = meta.get("depositions")
    if isinstance(deps, list) and deps:
        d0 = deps[0]
        if isinstance(d0, dict):
            dv = _as_query_string(d0.get("value"))
            if dv:
                out["depositions"] = dv
    unh = meta.get("unharmonized")
    if isinstance(unh, dict):
        fn = unh.get("file_name")
        if isinstance(fn, dict):
            fv = _as_query_string(fn.get("value"))
            if fv:
                out["metadata.unharmonized.file_name"] = fv
    return out


def _metadata_from_row(row: dict) -> dict:
    meta = row.get("metadata")
    return meta if isinstance(meta, dict) else {}


def filter_match_mode(resource: str, param: str) -> str:
    """Match mode for semantic checks: ``exact_ci`` (default) or ``contains_ci``."""
    return _FILTER_MATCH_MODE.get(resource, {}).get(param, "exact_ci")


def filter_candidates_from_row(resource: str, row: dict, param: str) -> list[str]:
    """
    Candidate row values for a filter parameter.

    Returns one or more normalized strings extracted from row ``metadata``.
    Empty list means there is no known mapping/value for this row+param.
    """
    meta = _metadata_from_row(row)
    out: list[str] = []
    if not meta:
        return out

    def add(v: Any) -> None:
        s = _as_query_string(v)
        if s:
            out.append(s)

    if resource == "subject":
        if param in ("sex", "ethnicity", "vital_status", "age_at_vital_status"):
            add(_scalar_value(meta, param))
        elif param == "race":
            add(_first_list_item_value(meta, "race"))
        elif param == "depositions":
            deps = meta.get("depositions")
            if isinstance(deps, list):
                for d in deps:
                    if isinstance(d, dict):
                        add(d.get("value"))
        elif param == "identifiers":
            ident = meta.get("identifiers")
            if isinstance(ident, list):
                for i0 in ident:
                    if isinstance(i0, dict):
                        inner = i0.get("value")
                        if isinstance(inner, dict):
                            add(inner.get("name"))
        elif param == "associated_diagnosis_categories":
            cats = meta.get("associated_diagnosis_categories")
            if isinstance(cats, list):
                for c in cats:
                    if isinstance(c, dict):
                        add(c.get("value"))
            elif isinstance(cats, dict):
                add(cats.get("value"))
    elif resource == "sample":
        if param in (
            "disease_phase",
            "library_selection_method",
            "library_strategy",
            "library_source_material",
            "preservation_method",
            "tumor_grade",
            "specimen_molecular_analyte_type",
            "tissue_type",
            "tumor_classification",
            "diagnosis",
            "tumor_tissue_morphology",
            "age_at_diagnosis",
            "age_at_collection",
        ):
            add(_scalar_value(meta, param))
        elif param == "anatomical_sites":
            vals = meta.get("anatomical_sites")
            if isinstance(vals, list):
                for v in vals:
                    if isinstance(v, dict):
                        add(v.get("value"))
        elif param == "depositions":
            deps = meta.get("depositions")
            if isinstance(deps, list):
                for d in deps:
                    if isinstance(d, dict):
                        add(d.get("value"))
        elif param == "identifiers":
            ident = meta.get("identifiers")
            if isinstance(ident, list):
                for i0 in ident:
                    if isinstance(i0, dict):
                        inner = i0.get("value")
                        if isinstance(inner, dict):
                            add(inner.get("name"))
        elif param == "diagnosis_category":
            vals = meta.get("diagnosis_category")
            if isinstance(vals, list):
                for v in vals:
                    if isinstance(v, dict):
                        add(v.get("value"))
            elif isinstance(vals, dict):
                add(vals.get("value"))
    elif resource == "file":
        if param in ("type", "size", "description"):
            add(_scalar_value(meta, param))
        elif param == "checksums":
            chk = meta.get("checksums")
            if isinstance(chk, dict):
                inner = chk.get("value")
                if isinstance(inner, dict):
                    add(inner.get("md5"))
                    add(inner.get("checksum_value"))
        elif param == "depositions":
            deps = meta.get("depositions")
            if isinstance(deps, list):
                for d in deps:
                    if isinstance(d, dict):
                        add(d.get("value"))
        elif param == "metadata.unharmonized.file_name":
            unh = meta.get("unharmonized")
            if isinstance(unh, dict):
                fn = unh.get("file_name")
                if isinstance(fn, dict):
                    add(fn.get("value"))
    return out


def _merge_rows(
    rows: list[dict],
    row_extractor: Callable[[dict], dict[str, str]],
    max_rows: int = 50,
) -> dict[str, str]:
    """First non-empty value per param across up to ``max_rows`` list rows."""
    merged: dict[str, str] = {}
    for row in rows[:max_rows]:
        if not isinstance(row, dict):
            continue
        meta = row.get("metadata")
        if not isinstance(meta, dict):
            continue
        partial = row_extractor(meta)
        for k, v in partial.items():
            if k not in merged and v:
                merged[k] = v
    return merged


def build_filter_examples_from_list_payloads(
    subject_rows: list | None,
    sample_rows: list | None,
    file_rows: list | None,
) -> dict[str, dict[str, str]]:
    """
    Build ``filter_examples`` for ``discover_dcc``.

    Keys are ``subject``, ``sample``, ``file``; each value maps OpenAPI query param name to
    one example string taken from live responses (stable across environments).
    """
    out: dict[str, dict[str, str]] = {}
    if isinstance(subject_rows, list) and subject_rows:
        s = _merge_rows(subject_rows, _subject_row_filters)
        if s:
            out["subject"] = s
    if isinstance(sample_rows, list) and sample_rows:
        s = _merge_rows(sample_rows, _sample_row_filters)
        if s:
            out["sample"] = s
    if isinstance(file_rows, list) and file_rows:
        s = _merge_rows(file_rows, _file_row_filters)
        if s:
            out["file"] = s
    return out
