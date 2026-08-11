"""Deterministic HTML fragment IDs for Epic 2 Slice 2.7 traceability.

Canonical entity IDs are preserved as the identity source; this helper only
produces valid, stable fragment identifiers for offline HTML navigation.
"""

from __future__ import annotations

import re

_SAFE_FRAGMENT = re.compile(r"[^A-Za-z0-9_.:\-]+")
_COLLAPSE_DASH = re.compile(r"-{2,}")


def safe_fragment_id(canonical_id: str) -> str:
    """Return a stable HTML fragment token derived from a canonical ID.

    Does not invent a new identity — characters invalid in fragment IDs are
    replaced deterministically. Empty input raises.
    """

    raw = str(canonical_id or "").strip()
    if not raw:
        raise ValueError("canonical_id must be non-blank")
    # Keep common ID shapes (UUID, finding:…, path:…) readable.
    cleaned = _SAFE_FRAGMENT.sub("-", raw)
    cleaned = _COLLAPSE_DASH.sub("-", cleaned).strip("-")
    if not cleaned:
        # Extremely exotic IDs — fall back to a deterministic hex digest of bytes.
        cleaned = "".join(f"{ord(ch):02x}" for ch in raw)[:64]
    # HTML IDs must not start with a digit in XML/XHTML; prefix if needed.
    if cleaned[0].isdigit():
        cleaned = f"id-{cleaned}"
    return cleaned


def evidence_anchor(evidence_id: str) -> str:
    return f"evidence-{safe_fragment_id(evidence_id)}"


def finding_anchor(finding_id: str) -> str:
    """Compatibility: preserves historical ``finding-{id}`` pattern."""

    return f"finding-{safe_fragment_id(finding_id)}"


def recommendation_anchor(recommendation_id: str) -> str:
    """Compatibility: preserves historical ``recommendation-{id}`` pattern."""

    return f"recommendation-{safe_fragment_id(recommendation_id)}"


def priority_action_anchor(action_id: str) -> str:
    return f"priority-action-{safe_fragment_id(action_id)}"


def roadmap_initiative_anchor(initiative_id: str) -> str:
    return f"roadmap-initiative-{safe_fragment_id(initiative_id)}"
