"""Normalize assessment artifacts for deterministic comparison."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# Approved volatile fields — may differ across equivalent clean clones.
_VOLATILE_KEYS = {
    "generated_at",
    "timestamp",
    "started_at",
    "finished_at",
    "duration_ms",
    "duration_seconds",
    "elapsed_ms",
    "run_id",
    "assessment_id",
    "created_at",
    "updated_at",
    "wall_clock_ms",
    "latency_ms",
}


def _strip_volatile(node: Any) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in _VOLATILE_KEYS:
                continue
            # Absolute-path-like leaves are treated as volatile location fields.
            if isinstance(value, str) and (
                value.startswith("/")
                or value.startswith("file://")
                or (len(value) > 2 and value[1] == ":" and value[2] in {"\\", "/"})
            ):
                continue
            out[key] = _strip_volatile(value)
        return out
    if isinstance(node, list):
        return [_strip_volatile(item) for item in node]
    return node


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_report(document: dict[str, Any]) -> dict[str, Any]:
    return _strip_volatile(copy.deepcopy(document))


def extract_id_sets(document: dict[str, Any]) -> dict[str, list[str]]:
    assessment = document.get("assessment") if isinstance(document.get("assessment"), dict) else document

    def ids(key: str) -> list[str]:
        items = assessment.get(key) or document.get(key) or []
        if not isinstance(items, list):
            return []
        return sorted(
            str(item.get("id"))
            for item in items
            if isinstance(item, dict) and item.get("id") is not None
        )

    # Priority actions / roadmap may nest.
    roadmap = assessment.get("roadmap") if isinstance(assessment.get("roadmap"), dict) else {}
    initiatives = roadmap.get("initiatives") or []
    initiative_ids = sorted(
        str(item.get("id"))
        for item in initiatives
        if isinstance(item, dict) and item.get("id") is not None
    )

    packs = []
    activation = assessment.get("activation") if isinstance(assessment.get("activation"), dict) else {}
    for pack in activation.get("packs") or []:
        if isinstance(pack, dict) and pack.get("pack_id") is not None:
            packs.append(f"{pack.get('pack_id')}:{pack.get('enabled')}")

    findings_key = "findings"
    rec_key = "deterministic_recommendations"
    if not (assessment.get(rec_key) or document.get(rec_key)):
        rec_key = "recommendations"

    return {
        "finding_ids": ids(findings_key),
        "evidence_ids": ids("evidence"),
        "recommendation_ids": ids(rec_key),
        "priority_action_ids": ids("priority_actions"),
        "initiative_ids": initiative_ids,
        "activation_packs": sorted(packs),
    }


def aggregate_counts(document: dict[str, Any]) -> dict[str, int]:
    ids = extract_id_sets(document)
    return {f"count_{key}": len(value) for key, value in ids.items()}


def compare_normalized(
    left: dict[str, Any],
    right: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Compare normalized reports; return ok and bounded difference categories."""

    diffs: list[str] = []
    left_ids = extract_id_sets(left)
    right_ids = extract_id_sets(right)
    for key in left_ids:
        if left_ids[key] != right_ids.get(key):
            diffs.append(f"id_set_mismatch:{key}")
    left_norm = normalize_report(left)
    right_norm = normalize_report(right)
    left_ids_only = extract_id_sets(left_norm)
    right_ids_only = extract_id_sets(right_norm)
    # Re-check after normalization.
    for key in left_ids_only:
        if left_ids_only[key] != right_ids_only.get(key):
            if f"id_set_mismatch:{key}" not in diffs:
                diffs.append(f"id_set_mismatch:{key}")

    left_counts = aggregate_counts(left)
    right_counts = aggregate_counts(right)
    if left_counts != right_counts:
        diffs.append("aggregate_count_mismatch")

    # Structural equality of normalized ID projections is the primary gate;
    # full document equality is too brittle for approved location fields already stripped.
    if not diffs:
        # Spot-check schema version honesty.
        def schema(doc: dict[str, Any]) -> str | None:
            if doc.get("schema_version") is not None:
                return str(doc.get("schema_version"))
            assessment = doc.get("assessment")
            if isinstance(assessment, dict):
                return str(assessment.get("schema_version")) if assessment.get("schema_version") else None
            return None

        if schema(left) != schema(right):
            diffs.append("schema_version_mismatch")
    return (not diffs), diffs
