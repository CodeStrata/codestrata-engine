"""Stable report identifiers (Phase 5.12).

Report-facing IDs are content-derived so repeated runs with the same analytical
payload produce identical identifiers. Assessment domain models may still use
runtime UUIDs; this module remaps at the reporting boundary only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID, uuid5

# Fixed namespace for CodeStrata report entity IDs (not a secret).
_REPORT_ID_NAMESPACE = UUID("6b1f0c2e-9a47-4f8d-b3e1-2c8a7d5e4f10")


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value)).strip().lower()


def _evidence_fingerprint(evidence: Any) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for item in evidence or ():
        if isinstance(item, dict):
            rows.append(
                [
                    str(item.get("file_path") or item.get("path") or ""),
                    item.get("line_number"),
                    item.get("column_number"),
                    str(item.get("description") or item.get("excerpt") or ""),
                ]
            )
        else:
            rows.append(
                [
                    str(getattr(item, "file_path", getattr(item, "path", "")) or ""),
                    getattr(item, "line_number", None),
                    getattr(item, "column_number", None),
                    str(getattr(item, "description", getattr(item, "excerpt", "")) or ""),
                ]
            )
    rows.sort(key=lambda row: (row[0].lower(), row[1] if row[1] is not None else -1, str(row[3])))
    return rows


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def stable_finding_id(finding: Any) -> str:
    """Return a deterministic finding id for report JSON/HTML."""

    payload = {
        "kind": "finding",
        "rule_id": str(getattr(finding, "rule_id", "") or ""),
        "title": str(getattr(finding, "title", "") or ""),
        "description": str(getattr(finding, "description", "") or ""),
        "category": _enum_value(getattr(finding, "category", "")),
        "severity": _enum_value(getattr(finding, "severity", "")),
        "source": _enum_value(getattr(finding, "source", "")),
        "evidence": _evidence_fingerprint(getattr(finding, "evidence", ())),
        "affected_technologies": sorted(
            str(item) for item in (getattr(finding, "affected_technologies", ()) or ())
        ),
    }
    return str(uuid5(_REPORT_ID_NAMESPACE, _digest(payload)))


def stable_recommendation_id(recommendation: Any) -> str:
    """Return a deterministic recommendation id for report JSON/HTML."""

    payload = {
        "kind": "recommendation",
        "rule_id": str(getattr(recommendation, "rule_id", "") or ""),
        "title": str(getattr(recommendation, "title", "") or ""),
        "description": str(getattr(recommendation, "description", "") or ""),
        "rationale": str(getattr(recommendation, "rationale", "") or ""),
        "priority": _enum_value(getattr(recommendation, "priority", "")),
        "category": _enum_value(getattr(recommendation, "category", "")),
        "effort": _enum_value(getattr(recommendation, "effort", "")),
        "risk": _enum_value(getattr(recommendation, "risk", "")),
        "actions": list(getattr(recommendation, "actions", ()) or ()),
        "evidence": _evidence_fingerprint(getattr(recommendation, "evidence", ())),
    }
    return str(uuid5(_REPORT_ID_NAMESPACE, _digest(payload)))


def build_finding_id_map(findings: list[Any]) -> dict[str, str]:
    """Map runtime finding UUID strings to stable report ids."""

    return {
        str(getattr(finding, "id", "")): stable_finding_id(finding)
        for finding in findings
        if getattr(finding, "id", None) is not None
    }


def remap_related_finding_ids(
    related_finding_ids: Any,
    finding_id_map: dict[str, str],
) -> tuple[str, ...]:
    """Remap runtime finding IDs to stable report IDs; drop unknowns.

    Recommendations must reference finding ``id`` values (not rule IDs). Only
    IDs present in ``finding_id_map`` are kept, using the stable remapped form.
    """

    known = set(finding_id_map.values())
    remapped = {
        mapped
        for item in (related_finding_ids or ())
        if (mapped := finding_id_map.get(str(item))) is not None and mapped in known
    }
    return tuple(sorted(remapped))


def align_related_finding_ids(
    related_finding_ids: Any,
    *,
    allowed_finding_ids: set[str] | frozenset[str],
    alias_to_allowed: dict[str, str] | None = None,
) -> tuple[str, ...]:
    """Keep only related finding IDs that exist in the final customer finding set.

    ``alias_to_allowed`` remaps pre-dedupe / alternate IDs onto a surviving
    finding ID (for example when multiple findings collapse on rule+title).
    Unknown IDs are dropped; empty results are allowed.
    """

    aliases = alias_to_allowed or {}
    kept: set[str] = set()
    for item in related_finding_ids or ():
        candidate = str(item)
        if candidate in allowed_finding_ids:
            kept.add(candidate)
            continue
        remapped = aliases.get(candidate)
        if remapped is not None and remapped in allowed_finding_ids:
            kept.add(remapped)
    return tuple(sorted(kept))
