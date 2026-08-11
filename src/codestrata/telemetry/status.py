"""Side-effect-free privacy-first telemetry status factory (Slices 9.7–9.9).

Builds status from immutable policies and capability constants only.
Never accepts home, preferences, identity, endpoint, queue, repository, or env.
"""

from __future__ import annotations

from codestrata.telemetry.assessment_isolation_policy import (
    COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION,
)
from codestrata.telemetry.catalog import build_privacy_first_telemetry_catalog
from codestrata.telemetry.catalog_policy import (
    COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_VERSION,
    PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION,
)
from codestrata.telemetry.cli_consent_policy import (
    COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION,
)
from codestrata.telemetry.consent_policy import (
    COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_VERSION,
)
from codestrata.telemetry.non_interactive_policy import (
    COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_VERSION,
)
from codestrata.telemetry.preview_policy import (
    COMMUNITY_TELEMETRY_PREVIEW_POLICY_VERSION,
)
from codestrata.telemetry.pre_transport_policy import (
    COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION,
)
from codestrata.telemetry.prompt_policy import (
    COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_VERSION,
)
from codestrata.telemetry.runtime_policy import (
    COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION,
)
from codestrata.telemetry.status_models import (
    LegacyCompatibilityState,
    PrivacyFirstTelemetryStatus,
    TelemetryRuntimeState,
    TelemetryTransportStatus,
)
from codestrata.telemetry.status_policy import (
    COMMUNITY_TELEMETRY_STATUS_POLICY_VERSION,
    CommunityTelemetryStatusPolicy,
    default_status_policy,
)
from codestrata.telemetry.transport_policy import (
    COMMUNITY_TELEMETRY_TRANSPORT_POLICY_VERSION,
)


def build_privacy_first_telemetry_status(
    *,
    policy: CommunityTelemetryStatusPolicy | None = None,
) -> PrivacyFirstTelemetryStatus:
    """Construct the authoritative privacy-first telemetry status snapshot."""

    active = policy or default_status_policy()
    catalog = build_privacy_first_telemetry_catalog()
    policy_versions: tuple[tuple[str, str], ...] = (
        ("assessment_isolation", COMMUNITY_TELEMETRY_ASSESSMENT_ISOLATION_POLICY_VERSION),
        ("catalog", COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_VERSION),
        ("cli_consent", COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION),
        ("interactive_consent", COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_VERSION),
        ("non_interactive", COMMUNITY_TELEMETRY_NON_INTERACTIVE_POLICY_VERSION),
        ("pre_transport_privacy", COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION),
        ("preview", COMMUNITY_TELEMETRY_PREVIEW_POLICY_VERSION),
        ("runtime", COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION),
        ("session_consent", COMMUNITY_TELEMETRY_SESSION_CONSENT_POLICY_VERSION),
        ("status", COMMUNITY_TELEMETRY_STATUS_POLICY_VERSION),
        ("transport", COMMUNITY_TELEMETRY_TRANSPORT_POLICY_VERSION),
    )
    public_limitations = (
        "assessment_isolation_primary_authoritative",
        "http_transport_requires_explicit_configuration",
        "operational_transport_not_configured_by_default",
        "vscode_cursor_integration_not_implemented",
    )
    return PrivacyFirstTelemetryStatus(
        schema_name=active.status_schema_name,
        schema_version=active.status_schema_version,
        runtime_state=TelemetryRuntimeState.DISABLED_BY_DEFAULT.value,
        default_decision=active.default_runtime_decision,
        consent_scope=active.consent_scope,
        consent_persisted=active.consent_persisted,
        prior_consent_reused=active.prior_consent_reused,
        interactive_prompt_available=True,
        interactive_prompt_commands=active.prompt_command_scope,
        interactive_prompt_default_deny=True,
        interactive_prompt_once_per_process=True,
        non_interactive_prompt_suppressed=True,
        explicit_allow_flag_available=True,
        explicit_deny_flag_available=True,
        flag_commands=active.cli_flag_command_scope,
        flags_mutually_exclusive=True,
        flags_process_local=True,
        flags_not_saved=True,
        allow_does_not_imply_transmission=True,
        transport_status=TelemetryTransportStatus.UNAVAILABLE.value,
        transmission_available=active.transmission_available,
        installation_identity_used=active.installation_identity_used,
        privacy_filter_required=active.privacy_filtering_required,
        status_side_effect_free=active.status_side_effect_free,
        legacy_compatibility_state=LegacyCompatibilityState.SEPARATE_NOT_INSPECTED.value,
        legacy_preference_authorizes_runtime=False,
        catalog_available=True,
        catalog_schema_version=PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION,
        catalog_documentation_label="telemetry-event-catalog",
        catalog_event_count=len(catalog.events),
        catalog_field_count=len(catalog.shared_fields),
        preview_available=True,
        preview_command="codestrata telemetry preview",
        preview_local_only=True,
        preview_transmission_performed=False,
        privacy_gate_available=True,
        privacy_gate_required=True,
        privacy_policy_version=COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION,
        policy_versions=policy_versions,
        limitation_codes=public_limitations,
    )


__all__ = [
    "build_privacy_first_telemetry_status",
]
