"""
Single HTTP client for all API projects — avoids duplicating timeouts, headers, and URL rules.

Use :meth:`ApiClient.from_project_config` in project conftest fixtures.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

import httpx

from framework.config.models import ProjectConfig
from framework.response_print import print_http_response


class ApiClient:
    """
    Thin wrapper around httpx with project-scoped base URL and default headers.

    All request paths are relative to ``config.api_prefix`` unless you pass an absolute URL.
    """

    def __init__(
        self,
        config: ProjectConfig,
        *,
        timeout_seconds: float = 60.0,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._config = config
        self._timeout = timeout_seconds
        merged = dict(config.default_headers)
        if extra_headers:
            merged.update(dict(extra_headers))
        self._headers = merged

    @property
    def config(self) -> ProjectConfig:
        """Resolved project configuration (base URL, prefix, headers)."""
        return self._config

    @classmethod
    def from_project_config(
        cls,
        config: ProjectConfig,
        *,
        timeout_seconds: float = 60.0,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> "ApiClient":
        return cls(config, timeout_seconds=timeout_seconds, extra_headers=extra_headers)

    def _url(self, path: str) -> str:
        return self._config.url_for(path)

    def get(
        self,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> httpx.Response:
        h = dict(self._headers)
        if headers:
            h.update(headers)
        with httpx.Client(timeout=self._timeout) as client:
            r = client.get(self._url(path), params=params, headers=h)
            print_http_response("GET", r)
            return r

    def post(
        self,
        path: str,
        *,
        json: Any = None,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> httpx.Response:
        h = dict(self._headers)
        h.setdefault("Content-Type", "application/json")
        if headers:
            h.update(headers)
        with httpx.Client(timeout=self._timeout) as client:
            r = client.post(self._url(path), json=json, params=params, headers=h)
            print_http_response("POST", r)
            return r

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> httpx.Response:
        """Generic method for uncommon verbs (PUT, PATCH, DELETE)."""
        h = dict(self._headers)
        if headers:
            h.update(headers)
        with httpx.Client(timeout=self._timeout) as client:
            r = client.request(
                method.upper(),
                self._url(path),
                json=json,
                params=params,
                headers=h,
            )
            print_http_response(method.upper(), r)
            return r
