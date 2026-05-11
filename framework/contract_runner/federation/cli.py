"""
CLI: Federation OpenAPI-driven contract tests (discover → generate → run GET cases → reports).

Uses ``config/projects.yaml`` entry ``federation`` for base URL (``DATACOMNS_FEDERATION_BASE_URL``),
``api_prefix``, headers, and OpenAPI path (default ``federation-v130.yaml``).

Environment:
  FEDERATION_CONTRACT_REPORT_DIR — default ``reports/federation/contract``
  FEDERATION_CONTRACT_EXCLUDE_PATHS — comma-separated OpenAPI path keys to skip (default: ``/subject-mapping``;
    CPI route not exposed on all environments). Set to empty to include all paths.
  FEDERATION_AL_EXPECTED_SOURCES — comma-separated node ``source`` labels; **defaults** to seven QA names
    in code when unset or blank. Set to ``none`` or ``-`` to disable roster checks. When enabled, any
    response whose JSON is a non-empty array of objects each with string ``source`` must include every
    listed name. Per-node ``errors`` in the body are allowed. HTTP must still be **200**.
  DATACOMNS_SSL_VERIFY — set ``false`` to disable TLS verification (not for production)
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
except ImportError:
    pass


def main_federation() -> None:
    """Parse argv, discover live ids, generate cases, run GETs, write JSON+HTML reports."""
    import argparse

    from framework.contract_runner.client import ContractAPIClient
    from framework.contract_runner.config import resolve_federation_openapi_path
    from framework.contract_runner.federation.discover import discover_federation
    from framework.contract_runner.federation.generator import generate_cases_federation
    from framework.contract_runner.loader import get_paths, load_spec
    from framework.contract_runner.reporters.html_report import write_html_report_federation
    from framework.contract_runner.reporters.report import aggregate_results, write_json_report
    from framework.contract_runner.runners.functional import (
        federation_al_expected_sources,
        run_functional_tests_dcc,
    )

    parser = argparse.ArgumentParser(description="Federation API OpenAPI contract test runner")
    parser.add_argument(
        "--spec",
        default=None,
        help="OpenAPI JSON/YAML (default: path from config/projects.yaml federation.openapi_relative)",
    )
    parser.add_argument("--base-url", default=None, help="Override API root (normally from project config)")
    parser.add_argument(
        "--report",
        default=None,
        help="Report directory (default: FEDERATION_CONTRACT_REPORT_DIR or reports/federation/contract)",
    )
    parser.add_argument("--tags", default=None, help="Comma-separated OpenAPI tags (default: all)")
    parser.add_argument(
        "--no-negative",
        action="store_true",
        help="Skip bad-query (page=0, per_page=0) and invalid-path cases (they still expect HTTP 200 for AL)",
    )
    parser.add_argument(
        "--strict-filter-data",
        action="store_true",
        help="Filter-driven list cases require non-empty data[] (stricter; may fail if env has sparse data)",
    )
    parser.add_argument("--quiet", action="store_true", help="Minimal console output")
    args = parser.parse_args()

    report_dir = args.report or os.getenv("FEDERATION_CONTRACT_REPORT_DIR", "reports/federation/contract")
    try:
        spec_path = Path(args.spec) if args.spec else resolve_federation_openapi_path()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    if not spec_path.exists():
        print(f"Spec not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    if args.base_url:
        client = ContractAPIClient(args.base_url.rstrip("/"))
    else:
        from framework.config.loader import get_project_config

        client = ContractAPIClient.from_project_config(get_project_config("federation"))

    tag_filter = [t.strip() for t in args.tags.split(",")] if args.tags else None
    quiet = args.quiet

    def log(msg: str) -> None:
        if not quiet:
            print(msg, flush=True)

    log(f"Loading spec from {spec_path}...")
    spec = load_spec(spec_path)
    log(f"Spec loaded: {len(get_paths(spec))} paths.")

    log(f"Client: base_url={client.base_url}")
    al_src = federation_al_expected_sources()
    if al_src:
        raw_e = os.getenv("FEDERATION_AL_EXPECTED_SOURCES")
        if raw_e is not None and raw_e.strip() and raw_e.strip().lower() not in ("none", "-"):
            log(f"AL source roster: {len(al_src)} expected source(s) from FEDERATION_AL_EXPECTED_SOURCES.")
        else:
            log(f"AL source roster: {len(al_src)} expected source(s) (default list; set env to override).")
    else:
        log("AL source roster: disabled (FEDERATION_AL_EXPECTED_SOURCES is none or -).")
    log("Running discovery...")
    test_data = discover_federation(client)
    discovery_info: dict | None = None
    if test_data:
        discovery_info = {}
        parts = []
        for key in sorted(test_data.keys()):
            v = test_data[key]
            if isinstance(v, dict):
                disp = f"<dict {len(v)} keys>"
            elif isinstance(v, str) and len(v) > 20:
                disp = v[:17] + "..."
            else:
                disp = v
            parts.append(f"{key}={disp!r}")
            discovery_info[key] = v
        log(f"Discovery: {', '.join(parts)}")
    else:
        log(
            "Discovery: no path/filter seed data (GET /subject not 200, empty harmonized rows, "
            "or unrecognized JSON shape)."
        )

    raw_exclude = os.getenv("FEDERATION_CONTRACT_EXCLUDE_PATHS", "/subject-mapping")
    exclude_paths = frozenset(p.strip() for p in raw_exclude.split(",") if p.strip())

    cases = generate_cases_federation(
        spec,
        test_data,
        include_negative=not args.no_negative,
        tag_filter=tag_filter,
        strict_non_empty_filter=args.strict_filter_data,
        exclude_paths=exclude_paths,
    )
    if not cases:
        print("No test cases generated (check discovery and tag filter)", file=sys.stderr)
        sys.exit(0)

    n_positive = sum(1 for c in cases if not c.get("negative"))
    n_negative = len(cases) - n_positive
    log(f"Generated {len(cases)} cases ({n_positive} positive, {n_negative} negative).")
    if not quiet:
        by_tag = Counter(c.get("tag") or "unknown" for c in cases)
        log(f"By tag: {', '.join(f'{t}={n}' for t, n in sorted(by_tag.items()))}.")

    def on_case_done(result: dict) -> None:
        status = "Pass" if result.get("passed") else "Fail"
        path = result.get("path_display") or result.get("path", "")
        duration = result.get("duration")
        duration_ms = f"{duration * 1000:.0f} ms" if duration is not None else "?"
        note = result.get("pagination_pair_display_note")
        neg = " [negative]" if result.get("negative") else ""
        suffix = (f" — {note}" if note else "") + neg
        if result.get("passed"):
            log(f"  [Pass] GET {path} ({duration_ms}){suffix}")
        else:
            err = (result.get("error") or "")[:80]
            log(f"  [Fail] GET {path} ({duration_ms}) - {err}{neg}")

    if quiet:
        print(f"Running {len(cases)} test cases...", flush=True)
    else:
        log(f"Running {len(cases)} test cases...")
    results = run_functional_tests_dcc(client, cases, on_case_done=on_case_done if not quiet else None)
    summary = aggregate_results(results)

    run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    json_path = Path(report_dir) / f"federation_contract_{run_id}.json"
    html_path = Path(report_dir) / f"federation_contract_{run_id}.html"
    write_json_report(summary, results, json_path)
    write_html_report_federation(
        summary,
        results,
        html_path,
        base_url=client.base_url,
        discovery_info=discovery_info,
        cases_generated={"total": len(cases), "positive": n_positive, "negative": n_negative},
    )
    if quiet:
        print(f"Report written: {json_path}, {html_path}", flush=True)
    else:
        log(f"Report written: {json_path}, {html_path}")

    passed = summary.get("passed", 0)
    total = summary.get("total", 0)
    print(f"Result: {passed}/{total} passed", flush=True)
    if summary.get("failed", 0) > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main_federation()
