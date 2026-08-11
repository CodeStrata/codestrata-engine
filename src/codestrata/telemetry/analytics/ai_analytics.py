"""Anonymous AI analytics local construction (Epic 10 Slice 10.6).

Construction-API only — not wired into assess or AI execution. Does not
transmit. Does not persist analytics payloads. Does not instantiate providers
or call the network. May ensure anonymous installation identity only when an
explicit construction API is invoked.
"""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.analytics.ai_analytics_diagnostics import (
    AIAnalyticsDiagnostics,
)
from codestrata.telemetry.analytics.ai_analytics_input import (
    AIAnalyticsInput,
    build_ai_analytics_input,
)
from codestrata.telemetry.analytics.ai_analytics_models import (
    AIAnalyticsEvent,
    build_ai_analytics_event,
)
from codestrata.telemetry.analytics.ai_analytics_policy import (
    COMMUNITY_AI_ANALYTICS_POLICY_URN,
    COMMUNITY_AI_ANALYTICS_SCHEMA_URN,
    CommunityAIAnalyticsPolicy,
    default_ai_analytics_policy,
)
from codestrata.telemetry.analytics.ai_analytics_projection import (
    AIAnalyticsProjection,
    project_ai_analytics_event,
)
from codestrata.telemetry.analytics.ai_analytics_validation import (
    validate_ai_analytics_event,
)
from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    ensure_anonymous_installation_identity,
    is_uuid_v4,
)


def collect_ai_analytics(
    *,
    aggregate: AIAnalyticsInput,
    home: Path | None = None,
    identity: AnonymousInstallationIdentity | None = None,
    policy: CommunityAIAnalyticsPolicy | None = None,
    privacy_projection_applied: bool = True,
) -> tuple[AIAnalyticsEvent, AIAnalyticsProjection, AIAnalyticsDiagnostics]:
    """Construct, project, and validate a local AI analytics envelope.

    Identity is resolved only when this explicit construction API is called
    without a provided identity. Failures raise bounded AnalyticsError codes.
    """

    active = policy or default_ai_analytics_policy()
    active.validate()
    attempts = 1
    try:
        resolved = identity
        if resolved is None:
            try:
                resolved, _, _ = ensure_anonymous_installation_identity(home=home)
            except Exception as error:  # noqa: BLE001 — bounded remapping only
                raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE) from error
        if not is_uuid_v4(resolved.installation_id):
            raise AnalyticsError(AnalyticsErrorCode.IDENTITY_UNAVAILABLE)

        event = build_ai_analytics_event(
            identity=resolved,
            aggregate=aggregate,
            privacy_projection_applied=privacy_projection_applied,
            policy=active,
        )
        projected = validate_ai_analytics_event(event, policy=active)
        diag = AIAnalyticsDiagnostics(
            attempts=attempts,
            projected=1,
            rejected=0,
            capability_category=event.capability,
            provider_family_category=event.provider_family,
            model_family_category=event.model_family,
            ownership_category=event.provider_ownership,
            outcome_category=event.outcome,
            duration_bucket_present=event.duration_bucket is not None,
            ai_used_present=event.ai_used is not None,
            limitation_codes=tuple(sorted(active.limitations)),
        )
        return event, projected, diag
    except AnalyticsError:
        raise


def project_from_typed_input(
    *,
    identity: AnonymousInstallationIdentity,
    aggregate: AIAnalyticsInput,
    policy: CommunityAIAnalyticsPolicy | None = None,
) -> AIAnalyticsProjection:
    """Project typed aggregate input only (no provider objects / prompts)."""

    event = build_ai_analytics_event(
        identity=identity,
        aggregate=aggregate,
        policy=policy,
    )
    return project_ai_analytics_event(event, policy=policy)


__all__ = [
    "COMMUNITY_AI_ANALYTICS_POLICY_URN",
    "COMMUNITY_AI_ANALYTICS_SCHEMA_URN",
    "AIAnalyticsEvent",
    "AIAnalyticsInput",
    "AIAnalyticsProjection",
    "CommunityAIAnalyticsPolicy",
    "build_ai_analytics_event",
    "build_ai_analytics_input",
    "collect_ai_analytics",
    "default_ai_analytics_policy",
    "project_from_typed_input",
]
