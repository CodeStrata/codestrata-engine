"""Stable identifiers for modernization roadmap artifacts."""

from __future__ import annotations

from collections.abc import Sequence

from codestrata.domain.knowledge.identifiers import fingerprint_payload

ROADMAP_SECTION_ID = "assessment.roadmap"
ROADMAP_SECTION_VERSION = "1.0.0"
ROADMAP_SCHEMA_NAME = "modernization-roadmap"
ENGINE_VERSION = "1.0.0"


def build_initiative_id(
    *,
    phase: str,
    category: str,
    recommendation_ids: Sequence[str],
) -> str:
    digest = fingerprint_payload(
        {
            "phase": phase,
            "category": category,
            "recommendation_ids": sorted(recommendation_ids),
        }
    )[:16]
    return f"roadmap-initiative:{phase}:{category}:{digest}"


def build_phase_id(phase: str) -> str:
    return f"roadmap-phase:{phase.strip().lower()}"
