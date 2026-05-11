"""
Datacomns API Test Runner — **Flask** backend for the local web UI.

**Flow:** POST ``/run`` starts a subprocess (contract CLIs, perf CLI, or pytest) with the suite’s
base-URL env var set from a host map (DCC vs Federation). The UI reads **Server-Sent Events** from
``/stream/<run_id>`` for live logs; ``/status`` exposes coarse state; POST ``/stop/<run_id>`` sends
SIGTERM to the process group.

``DCC_ENVIRONMENTS`` / ``FEDERATION_ENVIRONMENTS`` map short keys (qa/stage/prod) to API **host**
URLs only (no ``/api/v1``) — ``api_prefix`` comes from ``config/projects.yaml`` /
``ContractAPIClient.from_project_config``. ``SUITES`` maps UI suite ids to argv vectors
(``python -m`` …).
"""
from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Host only — ``config/projects.yaml`` adds ``api_prefix`` (/api/v1) via ContractAPIClient.
DCC_ENVIRONMENTS: dict[str, str] = {
    "qa": "https://dcc-qa.ccdi.cancer.gov",
    "stage": "https://dcc-stage.ccdi.cancer.gov",
    "prod": "https://dcc.ccdi.cancer.gov",
}

FEDERATION_ENVIRONMENTS: dict[str, str] = {
    "qa": "https://federation-qa.ccdi.cancer.gov",
    "stage": "https://federation-stage.ccdi.cancer.gov",
    "prod": "https://federation.ccdi.cancer.gov",
}

SUITES: dict[str, list[str]] = {
    "dcc_contract": [sys.executable, "-m", "framework.contract_runner.dcc_cli"],
    "federation_contract": [sys.executable, "-m", "framework.contract_runner.federation_cli"],
    "dcc_perf": [sys.executable, "-m", "framework.contract_runner.dcc_perf_cli"],
    "dcc_pytest_smoke": [
        sys.executable,
        "-m",
        "pytest",
        "projects/dcc/tests/api_smoke",
        "-v",
        "-m",
        "smoke and project_dcc",
    ],
    "dcc_pytest_regression": [
        sys.executable,
        "-m",
        "pytest",
        "projects/dcc/tests/api_smoke",
        "-v",
        "-m",
        "dcc_regression",
    ],
}

# Which env var receives the selected host URL for each suite (must match projects.yaml base_url_env).
SUITE_BASE_URL_ENV: dict[str, str] = {
    "dcc_contract": "DATACOMNS_DCC_BASE_URL",
    "dcc_perf": "DATACOMNS_DCC_BASE_URL",
    "dcc_pytest_smoke": "DATACOMNS_DCC_BASE_URL",
    "dcc_pytest_regression": "DATACOMNS_DCC_BASE_URL",
    "federation_contract": "DATACOMNS_FEDERATION_BASE_URL",
}


def _hosts_for_suite(suite_key: str) -> dict[str, str]:
    """Return qa/stage/prod host map for the suite (Federation contract uses Federation gateways)."""
    if suite_key == "federation_contract":
        return FEDERATION_ENVIRONMENTS
    return DCC_ENVIRONMENTS


app = Flask(__name__)

# In-memory coordinator for at most one run: protected by _state["lock"].
_state: dict = {
    "run_id": None,
    "status": "idle",
    "exit_code": None,
    "suite": None,
    "env": None,
    "started_at": None,
    "finished_at": None,
    "process": None,
    "output_queue": None,
    "stage": 0,
    "lock": threading.Lock(),
}


@app.route("/")
def index():
    """Serve the main HTML shell (``templates/index.html``)."""
    return render_template("index.html")


@app.route("/status")
def status():
    """JSON snapshot: run status, ids, suite/env keys, elapsed seconds, and progress ``stage``."""
    with _state["lock"]:
        elapsed = None
        if _state["started_at"] is not None:
            end = _state["finished_at"] or time.time()
            elapsed = round(end - _state["started_at"], 1)
        return jsonify({
            "status": _state["status"],
            "run_id": _state["run_id"],
            "exit_code": _state["exit_code"],
            "suite": _state["suite"],
            "env": _state["env"],
            "elapsed": elapsed,
            "stage": _state["stage"],
        })


@app.route("/run", methods=["POST"])
def run():
    """Start a suite if idle: JSON body ``env`` + ``suite``; returns ``run_id``. 409 if already running."""
    body = request.get_json(force=True, silent=True) or {}
    env_key = body.get("env", "qa")
    suite_key = body.get("suite", "dcc_contract")

    hosts = _hosts_for_suite(suite_key)
    if env_key not in hosts:
        return jsonify({"error": f"Unknown environment: {env_key}"}), 400
    if suite_key not in SUITES:
        return jsonify({"error": f"Unknown suite: {suite_key}"}), 400

    with _state["lock"]:
        if _state["status"] == "running":
            return jsonify({"error": "A run is already in progress"}), 409

        run_id = str(uuid.uuid4())
        base_host = hosts[env_key]
        cmd = SUITES[suite_key]

        env = os.environ.copy()
        base_url_key = SUITE_BASE_URL_ENV.get(suite_key, "DATACOMNS_DCC_BASE_URL")
        env[base_url_key] = base_host
        env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            env=env,
            text=True,
            bufsize=1,
            start_new_session=True,
        )

        q: queue.Queue[str | None] = queue.Queue()

        _state.update({
            "run_id": run_id,
            "status": "running",
            "exit_code": None,
            "suite": suite_key,
            "env": env_key,
            "started_at": time.time(),
            "finished_at": None,
            "process": process,
            "output_queue": q,
            "stage": 0,
        })

    threading.Thread(
        target=_drain_process,
        args=(process, q, run_id, suite_key),
        daemon=True,
    ).start()

    return jsonify({"run_id": run_id})


@app.route("/stream/<run_id>")
def stream(run_id: str):
    """SSE stream of log lines as ``event: log``; final ``event: done`` with exit code (or stale marker)."""
    def generate():
        with _state["lock"]:
            current_id = _state["run_id"]
            q = _state["output_queue"]

        if current_id != run_id or q is None:
            yield _sse_event("done", json.dumps({"exit_code": None, "stale": True}))
            return

        while True:
            try:
                item = q.get(timeout=30)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue

            if item is None:
                with _state["lock"]:
                    ec = _state["exit_code"]
                    stage = _state["stage"]
                yield _sse_event("done", json.dumps({"exit_code": ec, "stage": stage}))
                return

            yield _sse_event("log", json.dumps({"line": item}))

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/stop/<run_id>", methods=["POST"])
def stop(run_id: str):
    """Send SIGTERM to the run's process group (best-effort); no-op if run id mismatches or not running."""
    with _state["lock"]:
        if _state["run_id"] != run_id:
            return jsonify({"error": "Run ID not found"}), 404
        process = _state["process"]
        if process is None or _state["status"] != "running":
            return jsonify({"error": "No active process"}), 409

    try:
        pgid = os.getpgid(process.pid)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    except Exception:
        try:
            process.terminate()
        except Exception:
            pass

    return jsonify({"ok": True})


def _drain_process(process: subprocess.Popen, q: queue.Queue, run_id: str, suite_key: str) -> None:
    """Background worker: push stdout lines to ``q``, wait for exit, then finalize ``_state`` and push ``None``."""
    try:
        for line in process.stdout:  # type: ignore[union-attr]
            q.put(line.rstrip("\n"))
    finally:
        process.wait()
        exit_code = process.returncode
        with _state["lock"]:
            if _state["run_id"] == run_id:
                _state["status"] = "done"
                _state["exit_code"] = exit_code
                _state["finished_at"] = time.time()
                _state["process"] = None
        q.put(None)


def _sse_event(event: str, data: str) -> str:
    """Format one Server-Sent Event frame (``event`` + ``data`` lines, blank line terminator)."""
    return f"event: {event}\ndata: {data}\n\n"
