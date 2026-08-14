"""Safe rule-id filter for assessment_metadata projection (Slice 20.8).

Engine-side first line of defense. Platform validation remains second line.
"""

from __future__ import annotations

import re

from codestrata.domain.rules.identifiers import validate_rule_id

_CONTROL_OR_SPACE = re.compile(r"[\x00-\x1f\x7f\s]")
_URLISH = re.compile(r"(://)|(@)|(\.\./)|(https?)|(git@)", re.IGNORECASE)


def is_safe_assessment_metadata_rule_id(rule_id: str) -> bool:
    """Return True when ``rule_id`` may appear in amd finding_aggregates."""

    if not isinstance(rule_id, str):
        return False
    raw = rule_id.strip()
    if not raw or len(raw) > 128:
        return False
    if _CONTROL_OR_SPACE.search(raw):
        return False
    lowered = raw.lower()
    if lowered.startswith("pmd.") or lowered.startswith("provider:"):
        return False
    if _URLISH.search(lowered):
        return False
    if "/" in lowered or "\\" in lowered:
        return False
    try:
        validate_rule_id(raw)
    except ValueError:
        return False
    return True


def normalize_safe_rule_id(rule_id: str) -> str | None:
    """Return normalized safe rule_id or None when excluded."""

    if not is_safe_assessment_metadata_rule_id(rule_id):
        return None
    return rule_id.strip().lower()
