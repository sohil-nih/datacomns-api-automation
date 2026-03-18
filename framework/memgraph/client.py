"""
Bolt client for Memgraph (Neo4j-compatible driver). Credentials from environment only.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase


def _serialize_value(value: Any) -> Any:
    """Convert driver types to JSON-safe / assert-friendly Python values."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    # Node, Relationship, Path — minimal representation
    if hasattr(value, "element_id"):
        return {"_type": "graph_element", "element_id": str(value.element_id)}
    return str(value)


class MemgraphBoltClient:
    """
    Thin wrapper: run Cypher and return list of row dicts (column -> value).
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        *,
        database: Optional[str] = None,
        connection_timeout_sec: float = 30.0,
        max_connection_pool_size: int = 10,
    ) -> None:
        self._uri = uri
        self._database = database or None
        self._driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=connection_timeout_sec,
            max_connection_pool_size=max_connection_pool_size,
        )

    def close(self) -> None:
        self._driver.close()

    def verify_connectivity(self) -> None:
        self._driver.verify_connectivity()

    def run_cypher(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        params = parameters or {}
        session_kw: Dict[str, Any] = {}
        if self._database:
            session_kw["database"] = self._database
        rows: List[Dict[str, Any]] = []
        with self._driver.session(**session_kw) as session:
            result = session.run(query, params)
            for record in result:
                rows.append({k: _serialize_value(record[k]) for k in record.keys()})
        return rows


def _client_from_uri_user_pass(
    uri: str,
    user: str,
    password: str,
    *,
    database: Optional[str] = None,
) -> MemgraphBoltClient:
    db = database if database is not None else (os.environ.get("MEMGRAPH_DATABASE") or None)
    timeout = float(os.environ.get("MEMGRAPH_CONNECTION_TIMEOUT_SEC", "30"))
    pool = int(os.environ.get("MEMGRAPH_MAX_POOL_SIZE", "10"))
    return MemgraphBoltClient(
        uri,
        user,
        password,
        database=db,
        connection_timeout_sec=timeout,
        max_connection_pool_size=pool,
    )


def _resolve_bolt_uri(
    uri_env: str,
    host_env: str,
    port_env: str,
    port_default: str = "7687",
) -> str:
    uri = (os.environ.get(uri_env) or "").strip()
    if uri:
        return uri
    host = (os.environ.get(host_env) or "").strip().rstrip("/")
    port = (os.environ.get(port_env) or port_default).strip()
    if not host:
        return ""
    return host if host.startswith("bolt") else f"bolt://{host}:{port}"


def memgraph_client_from_env(profile: Optional[str] = None) -> MemgraphBoltClient:
    """
    Build client from environment.

    ``profile="dcc"`` tries, in order: ``MEMGRAPH_DCC_URI`` / ``MEMGRAPH_DCC_HOST``,
    then shared ``MEMGRAPH_URI`` / ``MEMGRAPH_HOST``. Password:
    ``MEMGRAPH_DCC_PASSWORD`` or ``MEMGRAPH_PASSWORD``.
    """
    prof = (profile or "").strip().lower()
    if prof == "dcc":
        pwd = (
            os.environ.get("MEMGRAPH_DCC_PASSWORD")
            or os.environ.get("MEMGRAPH_PASSWORD")
            or ""
        ).strip()
        uri = _resolve_bolt_uri(
            "MEMGRAPH_DCC_URI", "MEMGRAPH_DCC_HOST", "MEMGRAPH_DCC_PORT"
        )
        if not uri:
            uri = _resolve_bolt_uri("MEMGRAPH_URI", "MEMGRAPH_HOST", "MEMGRAPH_PORT")
        if uri and pwd:
            user = os.environ.get("MEMGRAPH_DCC_USER") or os.environ.get(
                "MEMGRAPH_USER", "memgraph"
            )
            dcc_db = os.environ.get("MEMGRAPH_DCC_DATABASE")
            return _client_from_uri_user_pass(
                uri,
                user,
                pwd,
                database=dcc_db or os.environ.get("MEMGRAPH_DATABASE") or None,
            )
        if uri and not pwd:
            raise ValueError(
                "DCC Memgraph: MEMGRAPH_DCC_PASSWORD or MEMGRAPH_PASSWORD is required "
                "(Bolt URL is set but password is missing). Add to .env in repo root."
            )
        raise ValueError(
            "DCC Memgraph: set MEMGRAPH_DCC_URI (or MEMGRAPH_DCC_HOST) and password, "
            "or MEMGRAPH_URI + MEMGRAPH_PASSWORD for the same Bolt DB. "
            "Ensure .env exists next to pytest.ini and is loaded (copy from .env.example)."
        )

    uri = (os.environ.get("MEMGRAPH_URI") or "").strip()
    if not uri:
        host = (os.environ.get("MEMGRAPH_HOST") or "").strip().rstrip("/")
        port = (os.environ.get("MEMGRAPH_PORT") or "7687").strip()
        if not host:
            raise ValueError(
                "Set MEMGRAPH_URI (bolt://host:7687) or MEMGRAPH_HOST + optional MEMGRAPH_PORT"
            )
        if not host.startswith("bolt"):
            uri = f"bolt://{host}:{port}"
        else:
            uri = host
    user = os.environ.get("MEMGRAPH_USER", "memgraph")
    password = os.environ.get("MEMGRAPH_PASSWORD", "")
    if password is None or password == "":
        raise ValueError(
            "MEMGRAPH_PASSWORD is required (or set MEMGRAPH_DCC_* for DCC profile)"
        )
    return _client_from_uri_user_pass(uri, user, password)
