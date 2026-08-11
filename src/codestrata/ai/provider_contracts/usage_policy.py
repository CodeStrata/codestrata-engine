"""Policy constants for provider usage metadata (Epic 11, Slice 11.5).

Mirrors the shape of ``policy.py``/``execution_policy.py``/
``capability_policy.py``. ``ALLOWED_USAGE_COMPLETION_STATUSES`` is
deliberately identical to ``policy.ALLOWED_EXECUTION_STATUSES`` (the same
four coarse outcomes: success/unavailable/failed/skipped) since
``ProviderUsageMetadata.completion_status`` records "what happened during
the call this usage was measured for" using the same vocabulary as
``ProviderExecutionStatus`` (see ``execution.py``) — this module asserts the
two stay in lockstep rather than silently drifting.

No cost, pricing, or billing field name is ever declared anywhere in this
package — usage is limited to token/latency/retry/completion-status
accounting.
"""

from __future__ import annotations

from codestrata.ai.provider_contracts.policy import ALLOWED_EXECUTION_STATUSES

POLICY_ID = "community-ai-provider-usage-policy:1.0"
CONTRACT_ID = "community-ai-provider-usage:1.0"
CONTRACT_VERSION = "1.0"

EPIC = "Epic 11: AI Provider Compatibility"
SLICE_ID = "11.5"
SLICE_TITLE = "Provider Usage Metadata and Capability Discovery"

# Intentionally identical to policy.ALLOWED_EXECUTION_STATUSES — see module
# docstring. Declared as its own tuple (rather than a bare re-export) so a
# future slice could diverge the two vocabularies with an explicit, reviewed
# change instead of an accidental one.
ALLOWED_USAGE_COMPLETION_STATUSES: tuple[str, ...] = ALLOWED_EXECUTION_STATUSES

# Field names that must never appear on ProviderUsageMetadata or any
# usage_* value object. Enforced by capability_validation-style checks and by
# the verification suite's dependency/attribute scan — not by a runtime
# check on this tuple itself (there is nothing to check at runtime: the
# dataclass simply never declares these fields).
FORBIDDEN_USAGE_FIELD_NAMES: tuple[str, ...] = (
    "cost",
    "cost_usd",
    "price",
    "pricing",
    "billing",
    "prompt",
    "prompt_text",
    "response",
    "response_text",
    "request_id",
    "exception",
    "exception_text",
    "traceback",
)

REQUIRED_COMPATIBILITY_REQUIREMENT_IDS: tuple[str, ...] = (
    "CR-1",
    "CR-2",
    "CR-3",
    "CR-4",
    "CR-5",
    "CR-6",
)

__all__ = [
    "ALLOWED_USAGE_COMPLETION_STATUSES",
    "CONTRACT_ID",
    "CONTRACT_VERSION",
    "EPIC",
    "FORBIDDEN_USAGE_FIELD_NAMES",
    "POLICY_ID",
    "REQUIRED_COMPATIBILITY_REQUIREMENT_IDS",
    "SLICE_ID",
    "SLICE_TITLE",
]
