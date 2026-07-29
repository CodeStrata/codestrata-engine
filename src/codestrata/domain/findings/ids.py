"""Deterministic finding identity helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from codestrata.domain.graph.validation import require_nonblank


def build_finding_id(*, rule_id: str, subject_keys: Sequence[str] = ()) -> str:
    """Build a stable finding ID from rule identity and subject keys."""

    rule = require_nonblank(rule_id, label="rule_id")
    subjects = tuple(sorted({require_nonblank(item, label="subject_key") for item in subject_keys}))
    if not subjects:
        subjects = ("repository",)
    digest = hashlib.sha256("\n".join(subjects).encode("utf-8")).hexdigest()[:16]
    return f"finding:{rule}:{digest}"
