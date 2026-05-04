"""
Datacomns API Test Runner — Flask backend.

Runs DCC contract/perf CLIs and optional pytest DCC suites via subprocess + SSE stream.
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
ENVIRONMENTS: dict[str, str] = {
    "qa": "https://dcc-qa.ccdi.cancer.gov",
    "stage": "https://dcc-stage.ccdi.cancer.gov",
    "prod": "https://dcc.ccdi.cancer.gov",
}

SUITES: dict[str, list[str]] = {
    "dcc_contract": [sys.executable, "-m", "framework.contract_runner.dcc_cli"],
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

app = Flask(__name__)

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
    return render_template("index.html")


@app.route("/status")
def status():
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
    body = request.get_json(force=True, silent=True) or {}
    env_key = body.get("env", "qa")
    suite_key = body.get("suite", "dcc_contract")

    if env_key not in ENVIRONMENTS:
        return jsonify({"error": f"Unknown environment: {env_key}"}), 400
    if suite_key not in SUITES:
        return jsonify({"error": f"Unknown suite: {suite_key}"}), 400

    with _state["lock"]:
        if _state["status"] == "running":
            return jsonify({"error": "A run is already in progress"}), 409

        run_id = str(uuid.uuid4())
        base_host = ENVIRONMENTS[env_key]
        cmd = SUITES[suite_key]

        env = os.environ.copy()
        env["DATACOMNS_DCC_BASE_URL"] = base_host
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
    return f"event: {event}\ndata: {data}\n\n"
