#!/usr/bin/env python3
"""
Datacomns Test Runner **launcher**: picks a free localhost port, starts the Flask app in ``ui/app.py``,
waits until ``/status`` responds, then opens the default browser. Handles SIGINT/SIGTERM by terminating
the child ``flask run`` process.

Usage from repo root: ``python launcher.py`` (requires Flask: ``pip install flask``).
"""
from __future__ import annotations

import importlib.util
import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
UI_APP = PROJECT_ROOT / "ui" / "app.py"
DEFAULT_PORT = 5678


def _port_free(port: int) -> bool:
    """Return True if nothing is listening on ``127.0.0.1:port`` (best-effort TCP connect probe)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) != 0


def _find_port(start: int = DEFAULT_PORT) -> int:
    """First free port at or above ``start`` (increment if the default is busy)."""
    port = start
    while not _port_free(port):
        print(f"Port {port} in use, trying {port + 1}…")
        port += 1
    return port


def _wait_for_server(url: str, timeout: float = 20.0) -> bool:
    """Poll ``{url}/status`` until HTTP succeeds or ``timeout`` seconds elapse."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{url}/status", timeout=1)
            return True
        except Exception:
            time.sleep(0.25)
    return False


def _check_flask() -> None:
    """Exit with message if the ``flask`` package is not importable."""
    if importlib.util.find_spec("flask") is None:
        print("\nFlask is not installed. Run: pip install flask\n")
        sys.exit(1)


def main() -> None:
    """Spawn ``flask --app ui/app.py run`` on a free port, open the UI, and block until interrupted."""

    os.chdir(PROJECT_ROOT)
    _check_flask()
    port = _find_port()
    url = f"http://localhost:{port}"
    python = sys.executable
    env = os.environ.copy()
    env["FLASK_APP"] = str(UI_APP)
    env["FLASK_ENV"] = "production"
    cmd = [python, "-m", "flask", "--app", str(UI_APP), "run", "--port", str(port), "--no-reload"]
    print(f"Starting Datacomns Test Runner on {url} …")
    server = subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), env=env, stdout=sys.stdout, stderr=sys.stderr)

    def _shutdown(signum=None, frame=None):
        """Terminate the Flask child process and exit cleanly on signals."""

        print("\nShutting down…")
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    if _wait_for_server(url):
        print(f"Server ready → opening {url}")
        webbrowser.open(url)
    else:
        print(f"Server did not respond in time. Open {url} manually.")
    try:
        server.wait()
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()
