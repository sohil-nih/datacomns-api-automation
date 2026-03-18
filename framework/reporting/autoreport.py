"""
Write a timestamped JSON + HTML report after every pytest session.

Disable: ``--no-datacomns-report`` or ``DATACOMNS_TEST_REPORT=0``.
Outputs a single ``reports/report_<YYYYMMDD_HHMMSS>_utc.html`` per run (UTC filename).
"""

from __future__ import annotations

import json
import os
import platform
import socket
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

import pytest

from framework.reporting.run_context import clear_all_comparisons, take_comparisons_for_nodeid

_MAX_SECTION_CHARS = 50_000
_MAX_LONGREPR_CHARS = 100_000

_session_start: float | None = None
_call_results: List[Dict[str, Any]] = []
_session_config: pytest.Config | None = None


def _reports_enabled(config: pytest.Config) -> bool:
    try:
        if config.getoption("--no-datacomns-report", default=False):
            return False
    except Exception:
        pass
    v = os.environ.get("DATACOMNS_TEST_REPORT", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _markers_from_keywords(keywords: Mapping[str, Any]) -> List[str]:
    skip = frozenset({"pytestmark"})
    names: List[str] = []
    for k in keywords:
        if k in skip:
            continue
        if k.endswith(".py") or "/" in k or k.startswith("@"):
            continue
        if len(k) > 120:
            continue
        names.append(k)
    return sorted(set(names))


def _sections_from_report(report: pytest.TestReport) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for heading, content in report.sections:
        body = content if len(content) <= _MAX_SECTION_CHARS else content[:_MAX_SECTION_CHARS] + "\n... [truncated]"
        out.append({"title": heading, "body": body})
    return out


def _location_tuple(report: pytest.TestReport) -> Tuple[str, Optional[int], str]:
    loc = getattr(report, "location", ("", None, ""))
    if len(loc) >= 3:
        path, lineno, domain = loc[0], loc[1], loc[2]
    else:
        path, lineno, domain = "", None, ""
    return (path or "", lineno, domain or "")


def _base_test_row(report: pytest.TestReport) -> Dict[str, Any]:
    path, lineno, domain = _location_tuple(report)
    props = [{"name": n, "value": str(v)} for n, v in report.user_properties]
    row: Dict[str, Any] = {
        "nodeid": report.nodeid,
        "file": path,
        "lineno": lineno,
        "domain": domain,
        "markers": _markers_from_keywords(report.keywords),
        "user_properties": props,
        "sections": _sections_from_report(report),
        "duration_sec": round(report.duration, 4) if report.duration else 0.0,
    }
    if hasattr(report, "wasxfail") and report.wasxfail:
        row["wasxfail"] = str(report.wasxfail)
    return row


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--no-datacomns-report",
        action="store_true",
        default=False,
        help="Disable automatic JSON/HTML reports under reports/",
    )


def pytest_configure(config: pytest.Config) -> None:
    global _session_config
    _session_config = config if _reports_enabled(config) else None


def pytest_sessionstart(session: pytest.Session) -> None:
    global _session_start, _call_results
    if not _reports_enabled(session.config):
        return
    _session_start = time.perf_counter()
    _call_results = []
    clear_all_comparisons()


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    cfg = _session_config
    if cfg is None or not _reports_enabled(cfg):
        return

    if report.when == "call":
        row = _base_test_row(report)
        row["outcome"] = report.outcome
        row["phase"] = "call"
        if report.outcome != "passed":
            try:
                lr = str(report.longrepr)
            except Exception:
                lr = repr(report.longrepr)
            row["longrepr"] = lr[:_MAX_LONGREPR_CHARS] + (
                "\n... [truncated]" if len(lr) > _MAX_LONGREPR_CHARS else ""
            )
        else:
            row["longrepr"] = None
        row["api_db_comparisons"] = take_comparisons_for_nodeid(report.nodeid)
        _call_results.append(row)
    elif report.when == "setup" and report.failed:
        row = _base_test_row(report)
        row["outcome"] = "error"
        row["phase"] = "setup"
        try:
            lr = str(report.longrepr)
        except Exception:
            lr = repr(report.longrepr)
        row["longrepr"] = lr[:_MAX_LONGREPR_CHARS] + (
            "\n... [truncated]" if len(lr) > _MAX_LONGREPR_CHARS else ""
        )
        row["api_db_comparisons"] = take_comparisons_for_nodeid(report.nodeid)
        _call_results.append(row)


def _count_outcomes(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in rows:
        o = r.get("outcome") or "unknown"
        counts[o] = counts.get(o, 0) + 1
    return counts


def _host_from_env_url(env_key: str) -> Optional[str]:
    u = os.environ.get(env_key, "").strip()
    if not u:
        return None
    try:
        return urlparse(u).netloc or u[:120]
    except Exception:
        return u[:120]


def _execution_profile() -> Dict[str, Any]:
    dcc_h = _host_from_env_url("DATACOMNS_DCC_BASE_URL")
    fed_h = _host_from_env_url("DATACOMNS_FEDERATION_BASE_URL")
    label = (os.environ.get("DATACOMNS_ENV") or os.environ.get("CCDI_ENV") or "").strip()
    if not label:
        blob = f"{dcc_h or ''} {fed_h or ''}".lower()
        if "qa" in blob or "-qa." in blob:
            label = "QA (inferred from URL host)"
        elif "stage" in blob or "staging" in blob:
            label = "Staging (inferred from URL host)"
        elif "prod" in blob:
            label = "Production (inferred from URL host)"
        elif dcc_h or fed_h:
            label = "Custom / dev target"
        else:
            label = "Unknown (set DATACOMNS_ENV or API base URLs)"
    projects: List[str] = []
    if dcc_h:
        projects.append("DCC — Data Commons API")
    if fed_h:
        projects.append("Federation API")
    if not projects:
        projects.append("(no DATACOMNS_DCC_BASE_URL / DATACOMNS_FEDERATION_BASE_URL)")
    return {
        "environment_name": label,
        "dcc_api_host": dcc_h,
        "federation_api_host": fed_h,
        "projects": projects,
    }


def _build_session_block(
    session: pytest.Session,
    exitstatus: int,
    duration_sec: Optional[float],
) -> Dict[str, Any]:
    ex = _execution_profile()
    now_utc = datetime.now(timezone.utc)
    return {
        "date_utc_iso": now_utc.isoformat(),
        "testscollected": getattr(session, "testscollected", 0),
        "exitstatus": exitstatus,
        "duration_sec": duration_sec,
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "pytest_version": pytest.__version__,
        "execution": ex,
    }


def _comparison_metrics(tests: List[Dict[str, Any]]) -> Dict[str, int]:
    m = {"matched": 0, "mismatched": 0, "error": 0, "total_runs": 0}
    for t in tests:
        for c in t.get("api_db_comparisons") or []:
            m["total_runs"] += 1
            st = (c.get("status") or "").lower()
            if st == "matched":
                m["matched"] += 1
            elif st == "mismatched":
                m["mismatched"] += 1
            else:
                m["error"] += 1
    return m


def _html_escape_pre(text: str, limit: Optional[int] = _MAX_LONGREPR_CHARS) -> str:
    """If limit is None or <= 0, emit full text (payloads are already capped at capture time)."""
    if not text:
        return ""
    if limit is not None and limit > 0 and len(text) > limit:
        text = text[:limit] + "\n... [truncated]"
    return escape(text)


def _html_page(summary: Dict[str, Any]) -> str:
    rpt_file = escape(str(summary.get("report_filename") or "report_utc.html"))
    session = summary.get("session") or {}
    tests: List[Dict[str, Any]] = list(summary.get("tests") or [])
    counts = summary.get("counts") or {}
    total_dur = sum(float(t.get("duration_sec") or 0) for t in tests)
    ex = session.get("execution") or {}

    rows_sorted = sorted(
        tests,
        key=lambda x: (
            x.get("file") or "",
            x.get("nodeid") or "",
        ),
    )

    exit_ok = int(summary.get("exitstatus", 1)) == 0
    badge_class = "badge-ok" if exit_ok else "badge-fail"
    badge_text = "SESSION OK" if exit_ok else f"EXIT {summary.get('exitstatus')}"

    def dl_row(label: str, value: str) -> str:
        return f"<tr><th>{escape(label)}</th><td>{value}</td></tr>"

    projs = ex.get("projects") or []
    proj_html = "<ul class='projlist'>" + "".join(f"<li>{escape(str(p))}</li>" for p in projs) + "</ul>"

    session_table = (
        "<table class='meta'><tbody>"
        + dl_row("Date (UTC)", escape(str(session.get("date_utc_iso", ""))))
        + dl_row("Host", escape(str(session.get("hostname", ""))))
        + dl_row("Environment", escape(str(ex.get("environment_name", ""))))
        + dl_row("Project(s)", proj_html)
        + dl_row("Tests collected", escape(str(session.get("testscollected", "—"))))
        + "</tbody></table>"
    )

    n_pass = int(counts.get("passed", 0))
    n_fail = int(counts.get("failed", 0))
    n_skip = int(counts.get("skipped", 0))
    n_err = int(counts.get("error", 0))
    n_cases = len(tests)

    def kpi_tile(n: int, label: str, cls: str) -> str:
        return (
            f'<div class="kpi {cls}"><div class="kpi-num">{n}</div>'
            f'<div class="kpi-lbl">{escape(label)}</div></div>'
        )

    kpi_row = (
        kpi_tile(n_cases, "test cases executed", "kpi-neutral")
        + kpi_tile(n_pass, "passed", "kpi-pass")
        + kpi_tile(n_fail, "failed", "kpi-fail")
        + kpi_tile(n_skip, "skipped", "kpi-skip")
        + kpi_tile(n_err, "errored (setup/teardown)", "kpi-err")
    )

    def count_badge(key: str, label: str, cls: str) -> str:
        n = int(counts.get(key, 0))
        return f'<span class="stat {cls}"><span class="stat-n">{n}</span><span class="stat-l">{escape(label)}</span></span>'

    stats_row = (
        count_badge("passed", "passed", "st-pass")
        + count_badge("failed", "failed", "st-fail")
        + count_badge("skipped", "skipped", "st-skip")
        + count_badge("error", "errors", "st-err")
        + f'<span class="stat st-total"><span class="stat-n">{len(tests)}</span><span class="stat-l">total</span></span>'
        + f'<span class="stat st-time"><span class="stat-n">{total_dur:.3f}s</span><span class="stat-l">sum durations</span></span>'
    )

    def _verdict_display(c: Dict[str, Any]) -> Tuple[str, str]:
        v = (c.get("verdict") or "").upper()
        if v in ("PASSED", "FAILED", "ERROR"):
            st = c.get("status", "")
            cls = "cmp-pass" if st == "matched" else ("cmp-fail" if st == "mismatched" else "cmp-err")
            return v, cls
        st = str(c.get("status", ""))
        if st == "matched":
            return "PASSED", "cmp-pass"
        if st == "mismatched":
            return "FAILED", "cmp-fail"
        return "ERROR", "cmp-err"

    cmp_table_body: List[str] = []
    for t in rows_sorted:
        for c in t.get("api_db_comparisons") or []:
            vd, st_cls = _verdict_display(c)
            gprev = (c.get("graph_response_preview") or "").strip() or "(no database payload captured)"
            aprev = (c.get("api_response_preview") or "").strip() or "(no API payload captured)"
            det = str(c.get("detail") or "").strip()
            if vd == "PASSED":
                mismatch_cell = '<span class="muted">No mismatch — comparison passed.</span>'
            elif vd == "FAILED":
                mismatch_cell = f'<pre class="cell-json mismatch-pre">{_html_escape_pre(det, None)}</pre>' if det else "—"
            else:
                mismatch_cell = f'<pre class="cell-json mismatch-pre err-pre">{_html_escape_pre(det, None)}</pre>' if det else escape(str(c.get("phase", "error")))

            cmp_table_body.append(
                "<tr>"
                f'<td class="payload-col"><pre class="cell-json api-cell">{_html_escape_pre(aprev, None)}</pre></td>'
                f'<td class="payload-col"><pre class="cell-json db-cell">{_html_escape_pre(gprev, None)}</pre></td>'
                f'<td class="status-col"><span class="{st_cls} status-pill">{escape(vd)}</span></td>'
                f"<td class='mismatch-col'>{mismatch_cell}</td>"
                "</tr>"
            )

    test_names_ran = []
    for tt in tests:
        nid = str(tt.get("nodeid") or "")
        if "::" in nid:
            test_names_ran.append(nid.split("::")[-1])
        elif nid:
            test_names_ran.append(nid)
    ran_list = (
        "<ul class='ran-tests'>" + "".join(f"<li><code>{escape(n)}</code></li>" for n in test_names_ran[:12]) + "</ul>"
        if test_names_ran
        else ""
    )
    if cmp_table_body:
        cmp_table_html = (
            '<table class="tbl cmp-data">'
            "<thead><tr>"
            "<th>API response <span class='th-sub'>(parsed JSON from REST)</span></th>"
            "<th>Database response <span class='th-sub'>(Memgraph / Cypher rows)</span></th>"
            "<th>Pass / Fail</th>"
            "<th>Mismatch or error detail</th>"
            "</tr></thead><tbody>"
            + "".join(cmp_table_body)
            + "</tbody></table>"
        )
    else:
        cmp_table_html = (
            '<table class="tbl cmp-data"><thead><tr>'
            "<th>API response</th><th>Database response</th><th>Pass / Fail</th><th>Mismatch detail</th>"
            "</tr></thead><tbody><tr>"
            '<td colspan="4" class="cmp-empty-row">'
            "<p><strong>No comparison rows</strong> — not an error. This session did not run "
            "<code>run_validation_pair</code> (Memgraph + DCC API check).</p>"
            + (f"<p><strong>Tests executed:</strong></p>{ran_list}" if ran_list else "")
            + "<p>Example to fill this table:</p>"
            "<pre class='cmd'>pytest projects/dcc/tests/api_smoke/test_DCC_TC01_verify_organizations.py -v</pre>"
            "</td></tr></tbody></table>"
        )

    cmp_section = (
        "<h2>API vs database comparison</h2>"
        "<p class='hint'>Parsed <strong>API</strong> vs <strong>database</strong> payloads; "
        "<strong>PASSED</strong> / <strong>FAILED</strong> / <strong>ERROR</strong>; mismatch detail on failure.</p>"
        + cmp_table_html
    )

    css = """
:root { --bg:#f8f9fa; --fg:#1a1a1a; --bd:#dee2e6; --th:#e9ecef;
  --pass:#198754; --fail:#dc3545; --skip:#fd7e14; --err:#6f42c1; --card:#fff; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#121416; --fg:#e9ecef; --bd:#343a40; --th:#212529; --card:#1c1f23; }
}
body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:var(--bg);color:var(--fg);line-height:1.45;}
.wrap{max-width:1400px;margin:0 auto;padding:1.25rem 1.5rem 2rem;}
h1{font-size:1.5rem;margin:0 0 .5rem;}
.top{display:flex;flex-wrap:wrap;align-items:center;gap:.75rem 1.25rem;margin-bottom:1rem;}
.badge{font-weight:700;padding:.35rem .75rem;border-radius:6px;font-size:.85rem;}
.badge-ok{background:#d1e7dd;color:var(--pass);}
@media (prefers-color-scheme: dark){ .badge-ok{background:#0f5132;color:#d1e7dd;} }
.badge-fail{background:#f8d7da;color:var(--fail);}
@media (prefers-color-scheme: dark){ .badge-fail{background:#842029;color:#f8d7da;} }
.meta{font-size:.9rem;width:100%;background:var(--card);border:1px solid var(--bd);border-radius:8px;}
.meta th{text-align:left;padding:.5rem .75rem;width:11rem;vertical-align:top;border-bottom:1px solid var(--bd);background:var(--th);}
.meta td{padding:.5rem .75rem;border-bottom:1px solid var(--bd);word-break:break-word;}
.meta tr:last-child th,.meta tr:last-child td{border-bottom:none;}
.mono{font-family:ui-monospace,monospace;font-size:.82rem;}
.mono.wrap{white-space:pre-wrap;}
h2{font-size:1.1rem;margin:1.25rem 0 .5rem;}
.stats{display:flex;flex-wrap:wrap;gap:.65rem;margin:1rem 0;}
.stat{display:inline-flex;align-items:baseline;gap:.35rem;padding:.4rem .85rem;border-radius:8px;background:var(--card);border:1px solid var(--bd);}
.stat-n{font-weight:800;font-size:1.15rem;}
.stat-l{font-size:.75rem;opacity:.85;text-transform:uppercase;}
.st-pass .stat-n{color:var(--pass);} .st-fail .stat-n{color:var(--fail);}
.st-skip .stat-n{color:var(--skip);} .st-err .stat-n{color:var(--err);}
.tbl{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--bd);border-radius:8px;overflow:hidden;}
.tbl thead th{background:var(--th);padding:.55rem .6rem;text-align:left;font-size:.8rem;border-bottom:2px solid var(--bd);position:sticky;top:0;z-index:2;}
.tbl td{padding:.5rem .6rem;border-bottom:1px solid var(--bd);vertical-align:top;font-size:.85rem;}
.tbl tbody tr:nth-child(even):not(.filehdr){background:rgba(0,0,0,.02);}
@media (prefers-color-scheme: dark){ .tbl tbody tr:nth-child(even):not(.filehdr){background:rgba(255,255,255,.03);} }
.filehdr td{background:var(--th);font-weight:600;font-size:.88rem;padding:.45rem .6rem;}
.t-pass .oc{color:var(--pass);font-weight:600;}
.t-failed .oc,.t-error .oc{color:var(--fail);font-weight:600;}
.t-skipped .oc{color:var(--skip);font-weight:600;}
.mk{display:inline-block;background:var(--th);padding:.1rem .35rem;border-radius:4px;margin:1px;font-size:.75rem;}
.small{font-size:.78rem;opacity:.95;}
details{margin:.35rem 0;}
details summary{cursor:pointer;font-weight:600;font-size:.82rem;}
pre.trace,pre.cap{white-space:pre-wrap;word-break:break-word;font-size:11px;margin:.35rem 0 0;padding:.5rem;background:var(--bg);border:1px solid var(--bd);border-radius:4px;max-height:28rem;overflow:auto;}
.failbox summary{color:var(--fail);}
.xfail{font-size:.85rem;color:var(--skip);}
.exec{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:1.25rem;
  box-shadow:0 1px 3px rgba(0,0,0,.06);}
.exec h2{margin-top:0;font-size:1.15rem;}
.kpi-row{display:flex;flex-wrap:wrap;gap:.75rem;margin:1rem 0;justify-content:flex-start;}
.kpi{min-width:7.5rem;padding:.85rem 1rem;border-radius:10px;border:1px solid var(--bd);text-align:center;background:var(--card);}
.kpi-num{font-size:1.75rem;font-weight:800;line-height:1.1;}
.kpi-lbl{font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;opacity:.88;margin-top:.25rem;}
.kpi-pass .kpi-num{color:var(--pass);} .kpi-fail .kpi-num{color:var(--fail);}
.kpi-skip .kpi-num{color:var(--skip);} .kpi-err .kpi-num{color:var(--err);}
.kpi-neutral .kpi-num{color:var(--fg);}
.subh{font-size:.95rem;margin:1rem 0 .5rem;}
.rid{font-size:1rem;font-weight:600;}
.muted{opacity:.75;font-size:.85rem;}
.projlist{margin:.25rem 0;padding-left:1.25rem;}
.hint{font-size:.85rem;opacity:.9;max-width:100%;}
.th-sub{font-weight:400;opacity:.75;text-transform:none;}
.cmp-data .payload-col{min-width:18rem;width:38%;vertical-align:top;}
.cmp-data .status-col{text-align:center;vertical-align:middle;min-width:5.5rem;}
.cmp-data .mismatch-col{min-width:12rem;max-width:22%;vertical-align:top;}
.cell-json{font-family:ui-monospace,monospace;font-size:9.5px;line-height:1.35;margin:0;padding:.5rem;
  max-height:22rem;overflow:auto;white-space:pre-wrap;word-break:break-word;
  background:var(--bg);border:1px solid var(--bd);border-radius:6px;}
.api-cell{border-top:3px solid #6f42c1;}
.db-cell{border-top:3px solid #0d6efd;}
.status-pill{display:inline-block;padding:.35rem .65rem;border-radius:8px;font-weight:800;font-size:.95rem;}
.cmp-pass.status-pill{background:#d1e7dd;color:#0f5132;}
.cmp-fail.status-pill{background:#f8d7da;color:#842029;}
.cmp-err.status-pill{background:#e7d5f5;color:#4a148c;}
@media (prefers-color-scheme: dark){
  .cmp-pass.status-pill{background:#0f5132;color:#d1e7dd;}
  .cmp-fail.status-pill{background:#58151c;color:#f8d7da;}
  .cmp-err.status-pill{background:#3d2a4d;color:#e9ecef;}
}
.mismatch-pre{max-height:20rem;border-color:var(--fail);}
.err-pre{border-color:var(--err);}
.what-inline{margin-top:.5rem;padding:.4rem;font-size:.75rem;background:var(--th);border-radius:4px;line-height:1.35;}
.cmp-empty-row{padding:1rem 1.25rem;font-size:.9rem;}
.ran-tests{margin:.35rem 0 .75rem;padding-left:1.25rem;}
pre.cmd{font-size:.82rem;padding:.6rem .85rem;background:var(--bg);border:1px solid var(--bd);border-radius:6px;overflow:auto;}
.colsub{font-size:.75rem;opacity:.88;margin:0 0 .4rem;}
.missing{color:var(--skip);font-size:.85rem;}
.rptfile{font-size:.9rem;margin:.35rem 0 0;}
"""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{rpt_file}</title>
<style>{css}</style></head><body><div class="wrap">
<div class="exec">
<h1>Test execution report</h1>
<p class="meta-line"><span class="badge {badge_class}">{escape(badge_text)}</span></p>
<p class="rptfile"><strong>Report file (UTC):</strong> <code>{rpt_file}</code></p>
<div class="kpi-row">{kpi_row}</div>
</div>
<h2>Environment</h2>
{session_table}
<h2>Output summary</h2>
<div class="stats">{stats_row}</div>
{cmp_section}
</div></body></html>"""


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not _reports_enabled(session.config):
        return
    opt = session.config.option
    if getattr(opt, "collectonly", False) or getattr(opt, "showfixtures", False):
        return

    root = Path(session.config.rootpath)
    out_dir = root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stamp = f"report_{ts}_utc"

    duration_sec: Optional[float] = None
    if _session_start is not None:
        duration_sec = round(time.perf_counter() - _session_start, 3)

    session_block = _build_session_block(session, exitstatus, duration_sec)
    tests_list = list(_call_results)
    cmp_metrics = _comparison_metrics(tests_list)

    summary: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "exitstatus": exitstatus,
        "duration_sec": duration_sec,
        "pytest_version": pytest.__version__,
        "session": session_block,
        "tests": tests_list,
        "counts": _count_outcomes(_call_results),
        "comparison_metrics": cmp_metrics,
    }

    html_path = out_dir / f"{stamp}.html"
    summary["report_filename"] = html_path.name

    try:
        html_path.write_text(_html_page(summary), encoding="utf-8")
    except OSError as e:
        tr = session.config.pluginmanager.get_plugin("terminalreporter")
        if tr:
            tr.write_line(f"[datacomns] Could not write report: {e}", red=True)
        return

    rel_html = html_path.relative_to(root)
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    if tr:
        tr.write_sep("=", f"Report: {rel_html}")
