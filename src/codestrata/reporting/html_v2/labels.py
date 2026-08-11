"""Customer-facing completeness and limitation labels (Slice 2.7)."""

from __future__ import annotations

import re

_COMPLETENESS_LABELS: dict[str, str] = {
    "complete": "Complete evidence",
    "partial": "Partial evidence",
    "truncated": "Partial evidence",
    "legacy": "Legacy evidence",
    "unavailable": "Evidence unavailable",
}

# Deterministic, safe mappings for known machine-readable limitation codes.
_LIMITATION_LABELS: dict[str, str] = {
    "evidence_ref_mapping_deferred_for_pack": (
        "Detailed evidence mapping is not yet available for this assessment area."
    ),
    "snippet_omitted_unverified_redaction": (
        "Source preview was omitted because safe redaction could not be verified."
    ),
    "legacy_finding_evidence": (
        "This finding uses legacy evidence presentation without EvidenceRef mapping."
    ),
    "legacy_recommendation": (
        "This recommendation uses legacy traceability and may not link to findings."
    ),
}


def completeness_label(value: str | None) -> str:
    key = str(value or "").strip().lower()
    if not key:
        return "Evidence unavailable"
    return _COMPLETENESS_LABELS.get(key, key.replace("_", " ").title())


def limitation_label(value: str) -> str:
    """Map a limitation code or sentence to customer-readable text."""

    raw = str(value or "").strip()
    if not raw:
        return ""
    key = raw.lower().replace(" ", "_")
    if key in _LIMITATION_LABELS:
        return _LIMITATION_LABELS[key]
    if raw in _LIMITATION_LABELS:
        return _LIMITATION_LABELS[raw]
    # Already a sentence — keep as-is.
    if " " in raw or raw[:1].isupper():
        return raw
    # snake_case → readable text without fabricating interpretation.
    readable = re.sub(r"_+", " ", raw).strip()
    if readable:
        return readable[0].upper() + readable[1:]
    return raw
