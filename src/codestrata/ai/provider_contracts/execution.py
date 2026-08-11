"""Provider-contract execution status and its (documented, unwired) mapping.

``ProviderExecutionStatus`` is deliberately coarser than
``codestrata.reporting.modernization_models.AIExecutionStatus``. This module
must not import ``codestrata.reporting`` (see
``dependency_boundary.py``/architecture tests), so the mapping below
duplicates ``AIExecutionStatus`` values as string literals for documentation
and test purposes only. Nothing in this package or in Slice 11.2 reads or
writes real ``AIExecutionStatus`` values — that enum, and the reporting
pipeline that produces it, is completely untouched by this slice.

Mapping (documentation only — not applied anywhere at runtime). See
``engine/docs/ai-provider-contracts.md`` for the full table with notes; in
short: ``success`` -> ``succeeded``; ``unavailable`` -> ``not_requested``
(nothing was attempted); ``failed`` -> ``provider_failed`` (coarse — a real
adapter migration would use ``AIProviderError.category`` to choose a
finer-grained status, explicitly deferred past Slice 11.2); ``skipped`` ->
``not_requested`` (contract-level skip, e.g. capability unsupported).
"""

from __future__ import annotations

from enum import StrEnum

from codestrata.ai.provider_contracts.policy import ALLOWED_EXECUTION_STATUSES


class ProviderExecutionStatus(StrEnum):
    """Coarse outcome of a single :meth:`AIProvider.execute` call."""

    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    SKIPPED = "skipped"


assert tuple(s.value for s in ProviderExecutionStatus) == ALLOWED_EXECUTION_STATUSES, (
    "ProviderExecutionStatus enum values must exactly match policy.ALLOWED_EXECUTION_STATUSES"
)

# Documented mapping table (string literals only — see module docstring for
# why this is not implemented against the real AIExecutionStatus enum).
DOCUMENTED_AI_EXECUTION_STATUS_MAPPING: dict[str, str] = {
    "success": "succeeded",
    "unavailable": "not_requested",
    "failed": "provider_failed",
    "skipped": "not_requested",
}

assert set(DOCUMENTED_AI_EXECUTION_STATUS_MAPPING) == set(ALLOWED_EXECUTION_STATUSES)


__all__ = [
    "DOCUMENTED_AI_EXECUTION_STATUS_MAPPING",
    "ProviderExecutionStatus",
]
