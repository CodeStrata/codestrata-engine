"""Report envelope manifest construction (Phase 5.12)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from codestrata import __version__
from codestrata.reporting.contract.constants import (
    ASSESSMENT_JSON_REPORT_VERSION,
    ASSESSMENT_JSON_SCHEMA_VERSION,
    CORE_ENABLED_SECTIONS,
    OPTIONAL_ASSESSMENT_SECTIONS,
    REPORT_CONTRACT_VERSION,
    REPORT_HTML_VERSION,
    VOLATILE_JSON_PATHS,
)


def build_report_manifest(
    *,
    generation_mode: str,
    repository_id: str | None,
    scan_id: str | None,
    assessment: Mapping[str, Any],
    generated_at: datetime | str | None = None,
    enabled_sections: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build the top-level report manifest (additive under schema 1.2)."""

    present_optional = [
        key for key in OPTIONAL_ASSESSMENT_SECTIONS if key in assessment and assessment[key]
    ]
    sections = (
        list(enabled_sections)
        if enabled_sections is not None
        else [
            *CORE_ENABLED_SECTIONS,
            *present_optional,
        ]
    )
    # Stable unique order.
    ordered: list[str] = []
    for key in (*CORE_ENABLED_SECTIONS, *OPTIONAL_ASSESSMENT_SECTIONS):
        if key in sections and key not in ordered:
            ordered.append(key)
    for key in sections:
        if key not in ordered:
            ordered.append(key)

    generated = generated_at
    if isinstance(generated_at, datetime):
        generated = generated_at.isoformat().replace("+00:00", "Z")

    return {
        "contract_version": REPORT_CONTRACT_VERSION,
        "schema_version": ASSESSMENT_JSON_SCHEMA_VERSION,
        "report_version": ASSESSMENT_JSON_REPORT_VERSION,
        "html_report_version": REPORT_HTML_VERSION,
        "codestrata_version": __version__,
        "product_name": "CodeStrata",
        "edition": "community",
        "report_type": "engineering_assessment",
        "brand_report_name": "Engineering Assessment",
        "repository_id": repository_id,
        "scan_id": scan_id,
        "enabled_sections": ordered,
        "generation_mode": str(generation_mode).strip().lower(),
        "generated_at": generated,
        "volatile_fields": list(VOLATILE_JSON_PATHS),
    }
