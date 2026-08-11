"""Safe, privacy-preserving diagnostic views of a provider capability profile.

Mirrors ``diagnostics.py`` (Slice 11.2)/``configuration_diagnostics.py``
(Slice 11.3)/``execution_diagnostics.py`` (Slice 11.4). A capability profile
never carries prompts, credentials, model references, or SDK objects in the
first place, so this view is a straightforward, complete projection — it
exists so that callers (and the verification suite) have one stable,
documented shape to depend on rather than reaching into the dataclass
directly, and so that future capability fields can be added to the profile
without every caller needing to change.
"""

from __future__ import annotations

from typing import Any

from codestrata.ai.provider_contracts.capability_models import ProviderCapabilityProfile


def diagnostic_view_of_capability_profile(profile: ProviderCapabilityProfile) -> dict[str, Any]:
    """Return a safe, complete summary of a capability profile."""

    return {
        "limitations": sorted(profile.limitations),
        "provider_id": str(profile.provider_id),
        "reports_token_accounting": profile.reports_token_accounting,
        "reports_usage_metadata": profile.reports_usage_metadata,
        "schema_version": profile.schema_version,
        "supported_capability_ids": sorted(str(c) for c in profile.supported_capability_ids),
        "supports_retry_policy": profile.supports_retry_policy,
        "supports_streaming": profile.supports_streaming,
        "supports_structured_json": profile.supports_structured_json,
        "supports_timeout_policy": profile.supports_timeout_policy,
    }


__all__ = ["diagnostic_view_of_capability_profile"]
