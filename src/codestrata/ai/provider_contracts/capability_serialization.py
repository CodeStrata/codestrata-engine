"""Deterministic JSON serialization of capability profile diagnostic views.

Sorted keys, no timestamps, no wall-clock data, no credentials, no model
references — these functions serialize only the safe diagnostic view from
``capability_diagnostics.py``. Reuses the same canonical-JSON convention as
``serialization.py``/``configuration_serialization.py``/
``execution_serialization.py``.
"""

from __future__ import annotations

import json
from typing import Any

from codestrata.ai.provider_contracts.capability_diagnostics import (
    diagnostic_view_of_capability_profile,
)
from codestrata.ai.provider_contracts.capability_models import ProviderCapabilityProfile


def canonical_json(payload: dict[str, Any]) -> str:
    """Stable, sorted-key JSON serialization used for hashing/comparison."""

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def serialize_capability_profile_for_diagnostics(profile: ProviderCapabilityProfile) -> str:
    """Canonical JSON of the safe diagnostic view of a capability profile."""

    return canonical_json(diagnostic_view_of_capability_profile(profile))


__all__ = [
    "canonical_json",
    "diagnostic_view_of_capability_profile",
    "serialize_capability_profile_for_diagnostics",
]
