"""
CLI: concurrent performance run for DCC positive contract cases only.

Uses the same discovery and generation as ``dcc_cli``; writes under
``reports/dcc/perf`` by default (override with ``--report`` or ``DCC_PERF_REPORT_DIR``).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass


def main_dcc_perf() -> None:
    """Load spec + discovery, run concurrent GET perf on positive cases only, emit perf JSON/HTML.

    Optionally fails when ``--fail-on-error-rate`` is exceeded. Uses ``DCC_PERF_REPORT_DIR`` when
    ``--report`` is omitted.
    """
    import argparse

    from framework.config.loader import get_project_config
    from framework.contract_runner.client import ContractAPIClient
    from framework.contract_runner.config import resolve_dcc_openapi_path
    from framework.contract_runner.dcc_discover import discover_dcc
    from framework.contract_runner.dcc_generator import generate_cases_dcc
    from framework.contract_runner.loader import get_paths, load_spec
    from framework.contract_runner.reporters.perf_report import write_perf_html_report, write_perf_json_report
    from framework.contract_runner.runners.performance import run_perf_tests

    parser = argparse.ArgumentParser(description="DCC API performance runner (OpenAPI cases)")
    parser.add_argument("--spec", default=None, help="OpenAPI file (default: from project dcc config)")
    parser.add_argument("--base-url", default=None, help="Override API root")
    parser.add_argument("--report", default=None, help="Report directory")
    parser.add_argument("--tags", default=None, help="Comma-separated OpenAPI tags")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent threads")
    parser.add_argument("--iterations", type=int, default=5, help="Repeats per case")
    parser.add_argument("--ramp-up", type=float, default=0.0, help="Stagger starts over N seconds")
    parser.add_argument("--perf-threshold-ms", type=int, default=2000, help="Slow-request threshold in reports")
    parser.add_argument(
        "--fail-on-error-rate",
        type=float,
        default=None,
        metavar="PCT",
        help="Exit 1 if HTTP error rate exceeds this percent",
    )
    parser.add_argument(
        "--strict-filter-data",
        action="store_true",
        help="Filter-driven list cases require non-empty data[] (same as contract CLI)",
    )
    args = parser.parse_args()

    try:
        spec_path = Path(args.spec) if args.spec else resolve_dcc_openapi_path()
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    if not spec_path.exists():
        print(f"Spec not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    if args.base_url:
        client = ContractAPIClient(args.base_url.rstrip("/"))
    else:
        client = ContractAPIClient.from_project_config(get_project_config("dcc"))

    tag_filter = [t.strip() for t in args.tags.split(",")] if args.tags else None

    print(f"Loading spec: {spec_path}", flush=True)
    spec = load_spec(spec_path)
    print(f"Spec loaded: {len(get_paths(spec))} paths.", flush=True)

    print("Running discovery...", flush=True)
    test_data = discover_dcc(client)
    if not test_data:
        print(
            "Discovery returned no data. Check that the DCC API is reachable and /subject returns rows.",
            file=sys.stderr,
        )
        sys.exit(1)

    cases = generate_cases_dcc(
        spec,
        test_data,
        include_negative=False,
        tag_filter=tag_filter,
        strict_non_empty_filter=args.strict_filter_data,
    )
    if not cases:
        print("No test cases generated.", file=sys.stderr)
        sys.exit(1)
    print(f"Generated {len(cases)} positive cases.", flush=True)

    if args.report:
        report_dir = Path(args.report)
    else:
        report_dir = Path(os.getenv("DCC_PERF_REPORT_DIR", "reports/dcc/perf"))
    report_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = report_dir / f"dcc_perf_{run_id}.json"
    html_path = report_dir / f"dcc_perf_{run_id}.html"

    total_work = len(cases) * args.iterations
    print(
        f"Running {len(cases)} cases × {args.iterations} iteration(s) "
        f"= {total_work} requests with {args.concurrency} thread(s)...",
        flush=True,
    )
    completed = [0]

    def _on_done(result) -> None:
        """Progress callback: print every 50 completions (and the last) for long runs."""
        completed[0] += 1
        if completed[0] % 50 == 0 or completed[0] == total_work:
            print(f"  {completed[0]}/{total_work} requests done...", flush=True)

    raw_results, stats = run_perf_tests(
        client=client,
        cases=cases,
        concurrency=args.concurrency,
        iterations=args.iterations,
        ramp_up_seconds=args.ramp_up,
        perf_threshold_ms=args.perf_threshold_ms,
        on_request_done=_on_done,
    )

    write_perf_json_report(stats, raw_results, json_path)
    write_perf_html_report(
        stats,
        raw_results,
        html_path,
        base_url=client.base_url,
        title="DCC API Performance Report",
    )

    print("", flush=True)
    print("--- DCC Performance ---", flush=True)
    print(f"  Total requests : {stats.total_requests}", flush=True)
    print(f"  Wall time      : {stats.wall_time_s:.1f}s", flush=True)
    print(f"  Throughput     : {stats.throughput_rps:.1f} req/s", flush=True)
    print(f"  Errors         : {stats.error_count} ({stats.error_rate_pct:.1f}%)", flush=True)
    print(f"  Slow (>{args.perf_threshold_ms}ms): {stats.slow_count}", flush=True)
    print(
        f"  Latency        : avg={stats.avg_ms} p50={stats.p50_ms} p90={stats.p90_ms} "
        f"p95={stats.p95_ms} p99={stats.p99_ms} max={stats.max_ms} (ms)",
        flush=True,
    )
    print(f"  Reports        : {html_path}, {json_path}", flush=True)

    if args.fail_on_error_rate is not None and stats.error_rate_pct > args.fail_on_error_rate:
        print(
            f"\nFAIL: error rate {stats.error_rate_pct:.1f}% exceeds threshold "
            f"{args.fail_on_error_rate:.1f}%",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nDone.", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main_dcc_perf()
