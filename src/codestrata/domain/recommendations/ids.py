"""Deterministic recommendation identity helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.graph.validation import require_nonblank


def build_recommendation_id(
    *,
    provider_id: str,
    related_finding_ids: Sequence[str] = (),
    subject_keys: Sequence[str] = (),
) -> str:
    """Build a stable recommendation ID from provider and finding/subject keys."""

    provider = require_nonblank(provider_id, label="provider_id")
    findings = tuple(
        sorted({require_nonblank(item, label="finding_id") for item in related_finding_ids})
    )
    subjects = tuple(sorted({require_nonblank(item, label="subject_key") for item in subject_keys}))
    material = (
        *findings,
        *subjects,
    )
    if not material:
        material = ("repository",)
    digest = hashlib.sha256("\n".join(material).encode("utf-8")).hexdigest()[:16]
    return f"recommendation:{provider}:{digest}"
