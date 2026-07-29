"""Performance assessment identifiers and constants (Phase 4.9.5)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

SECTION_ID = "assessment.performance"
SCHEMA_NAME = "performance-assessment"
SECTION_SCHEMA_VERSION = "1.2.0"
PERFORMANCE_ASSESSMENT_FILENAME = "performance-assessment.json"
ARTIFACT_SCHEMA_ID = "codestrata.performance_assessment"

MAX_TRACEABILITY_ENTRIES = 12


def build_assessment_id(
    *,
    repository_id: str,
    status: str,
    configuration_fingerprint: str,
) -> str:
    payload = (
        f"{repository_id.strip()}|{SECTION_ID}|{SECTION_SCHEMA_VERSION}|"
        f"{status.strip()}|{configuration_fingerprint.strip()}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"performance-assessment:{digest}"


def build_limitation_id(*, category: str, summary: str) -> str:
    payload = f"{category.strip().lower()}|{summary.strip().lower()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"performance-limitation:{digest}"


def build_diagnostic_id(*, code: str, message: str) -> str:
    payload = f"{code.strip().lower()}|{message.strip().lower()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"performance-diagnostic:{digest}"


def build_trace_edge_id(*, relation: str, source_id: str, target_id: str) -> str:
    payload = f"{relation}|{source_id}|{target_id}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"performance-trace:{digest}"


def build_configuration_fingerprint(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_empty_section_fingerprint(
    *,
    repository_id: str,
    pack_enabled: bool,
    section_enabled: bool,
) -> str:
    """Deterministic fingerprint for empty/disabled foundation sections."""

    payload = (
        f"repository_id={repository_id.strip()}|"
        f"section_enabled={section_enabled}|"
        f"pack_enabled={pack_enabled}|"
        f"section_id={SECTION_ID}|"
        f"section_version={SECTION_SCHEMA_VERSION}"
    )
    return build_configuration_fingerprint(payload)


def sorted_mapping(values: Mapping[str, str] | None) -> dict[str, str]:
    if not values:
        return {}
    return {str(key): str(item) for key, item in sorted(values.items(), key=lambda pair: pair[0])}


def sorted_ids(values: Sequence[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(sorted({item.strip() for item in values if str(item).strip()}))
