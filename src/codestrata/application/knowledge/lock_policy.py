"""Assessment lock waits. Tests may cap the default hour-long poll."""

from __future__ import annotations

import os

LOCK_TIMEOUT_ENV = "CODESTRATA_KNOWLEDGE_LOCK_TIMEOUT_SECONDS"


def knowledge_lock_timeout_seconds(requested: float) -> float:
    """Cap a lock wait so a contended host directory cannot stall for an hour."""

    raw = os.environ.get(LOCK_TIMEOUT_ENV, "").strip()
    if not raw:
        return requested
    try:
        cap = float(raw)
    except ValueError:
        return requested
    return max(0.05, min(requested, cap))
