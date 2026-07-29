"""Technical debt assessment identifiers and constants (Phase 4.3.1)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

SECTION_ID = "assessment.technical_debt"
SECTION_SCHEMA_VERSION = "1.2.0"
TECHNICAL_DEBT_ASSESSMENT_FILENAME = "technical-debt-assessment.json"


def build_limitation_id(*, category: str, summary: str) -> str:
    payload = f"{category.strip().lower()}|{summary.strip().lower()}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"td-limitation:{digest}"


def build_trace_edge_id(*, relation: str, source_id: str, target_id: str) -> str:
    payload = f"{relation}|{source_id}|{target_id}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"td-trace:{digest}"


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


def build_hotspot_id(
    *,
    path: str,
    source_unit: str,
    source_role: str,
) -> str:
    """Stable hotspot identity from path + source unit + role."""

    payload = (
        f"{path.strip().replace(chr(92), '/')}|"
        f"{source_unit.strip()}|"
        f"{source_role.strip().lower()}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"td-hotspot:{digest}"
