"""
HTTP client for contract runs: httpx with APIResponse shape matching the STS runner.

Functional and performance runners expect ``get(path, params) -> APIResponse``
with ``status_code``, ``body``, ``json()``, ``duration``.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Mapping
from urllib.parse import quote

import httpx

from framework.config.models import ProjectConfig


class APIResponse:
    """Single request outcome."""

    def __init__(self, status_code: int, body: str, json_data: dict | list | None, duration: float):
        self.status_code = status_code
        self.body = body
        self._json = json_data
        self.duration = duration

    def json(self) -> dict | list | None:
        return self._json

    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def is_not_found(self) -> bool:
        return self.status_code == 404

    def is_no_content(self) -> bool:
        return self.status_code == 204


def _build_query_string(params: dict | None) -> str:
    if not params:
        return ""
    query_parts = []
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, list):
            for item in v:
                query_parts.append(f"{k}={quote(str(item), safe='')}")
        else:
            query_parts.append(f"{k}={quote(str(v), safe='')}")
    if not query_parts:
        return ""
    return "?" + "&".join(query_parts)


class ContractAPIClient:
    """
    GET client rooted at base_url (e.g. https://host/api/v1).

    Paths from the generator are relative (e.g. ``/subject``).
    """

    def __init__(
        self,
        base_url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 60.0,
        verify: bool | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers = {"Accept": "application/json", "User-Agent": "datacomns-contract-runner/1.0"}
        if headers:
            self._headers.update(dict(headers))
        self._timeout = timeout
        if verify is None:
            verify = os.getenv("DATACOMNS_SSL_VERIFY", "true").lower() != "false"
        self._verify = verify

    @classmethod
    def from_project_config(
        cls,
        cfg: ProjectConfig,
        *,
        timeout: float = 60.0,
        verify: bool | None = None,
    ) -> ContractAPIClient:
        root = f"{cfg.base_url.rstrip('/')}{(cfg.api_prefix or '').rstrip('/')}"
        return cls(root, headers=cfg.default_headers, timeout=timeout, verify=verify)

    def get(self, path: str, params: dict | None = None) -> APIResponse:
        rel = path if path.startswith("/") else f"/{path}"
        url = self.base_url + rel + _build_query_string(params)
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=self._timeout, verify=self._verify) as client:
                r = client.get(url, headers=self._headers)
                body = r.text
                try:
                    j: dict | list | None = r.json()
                except json.JSONDecodeError:
                    j = None
                dur = time.perf_counter() - start
                return APIResponse(r.status_code, body, j, dur)
        except Exception as e:
            dur = time.perf_counter() - start
            return APIResponse(0, str(e), None, dur)
