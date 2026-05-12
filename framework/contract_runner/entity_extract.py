"""
Extract entity identifiers from harmonized list rows (``id.namespace`` + ``id.name``).

Shared by DCC and Federation discovery.
"""
from __future__ import annotations


def entity_triple(record: dict) -> tuple[str, str, str] | None:
    """Return ``(organization, namespace_name, entity_name)`` from a list row's nested ``id`` object."""
    id_ = record.get("id")
    if not isinstance(id_, dict):
        return None
    ns = id_.get("namespace")
    if not isinstance(ns, dict):
        return None
    org = ns.get("organization")
    ns_name = ns.get("name")
    ent_name = id_.get("name")
    if org is None or ns_name is None or ent_name is None:
        return None
    return str(org), str(ns_name), str(ent_name)
