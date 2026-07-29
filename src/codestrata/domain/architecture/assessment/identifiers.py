"""Architecture assessment identifiers and constants (Phase 4.2.4)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

SECTION_ID = "assessment.architecture"
SECTION_SCHEMA_VERSION = "1.0.0"
ARCHITECTURE_ASSESSMENT_FILENAME = "architecture-assessment.json"


def build_limitation_id(*, category: str, summary: str) -> str:
    payload = f"{category.strip().lower()}|{summary.strip().lower()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"arch-limitation:{digest}"


def build_strength_id(*, title: str, evidence_ids: Sequence[str]) -> str:
    evidence = ",".join(sorted({item.strip() for item in evidence_ids if item.strip()}))
    payload = f"{title.strip().lower()}|{evidence}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"arch-strength:{digest}"


def build_trace_edge_id(*, relation: str, source_id: str, target_id: str) -> str:
    payload = f"{relation}|{source_id}|{target_id}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"trace:{digest}"


def build_configuration_fingerprint(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
