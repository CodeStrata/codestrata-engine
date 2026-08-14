"""Persisted Community telemetry preference (Slices 19.4 / 20.9).

Explicit local consent survives CLI restarts. Default remains undecided/disabled.
Consent-v2 distinguishes lifecycle-only (V1_YES) from lifecycle+amd (V2_YES).
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from codestrata.telemetry.consent import TelemetrySessionConsent
from codestrata.telemetry.consent_scope import (
    CommunityConsentState,
    ConsentCapabilities,
    resolve_consent_capabilities,
    status_label,
)
from codestrata.telemetry.decisions import TelemetryDecision, TelemetryDecisionSource
from codestrata.telemetry.preferences import (
    load_preferences,
    mark_decision,
    mark_v2_upgrade_declined,
)


class TelemetryPreferenceState(StrEnum):
    """Legacy coarse preference labels (status/command compatibility)."""

    UNDECIDED = "undecided"
    ENABLED = "enabled"
    DISABLED = "disabled"


def preference_state(*, path: Path | None = None) -> TelemetryPreferenceState:
    caps = resolve_consent_capabilities(path=path)
    if caps.state is CommunityConsentState.UNDECIDED:
        return TelemetryPreferenceState.UNDECIDED
    if caps.state is CommunityConsentState.DISABLED:
        return TelemetryPreferenceState.DISABLED
    return TelemetryPreferenceState.ENABLED


def persist_preference(
    enabled: bool,
    *,
    path: Path | None = None,
    consent_scope: int | None = None,
) -> TelemetryPreferenceState:
    """Persist consent. Enabling defaults to v2 scope (consent_scope=2)."""

    mark_decision(bool(enabled), path=path, consent_scope=consent_scope)
    return (
        TelemetryPreferenceState.ENABLED
        if enabled
        else TelemetryPreferenceState.DISABLED
    )


def persist_v2_yes(*, path: Path | None = None) -> CommunityConsentState:
    mark_decision(True, path=path, consent_scope=2)
    return CommunityConsentState.V2_YES


def persist_v1_yes(*, path: Path | None = None) -> CommunityConsentState:
    """Test/migration helper — explicit lifecycle-only consent."""

    mark_decision(True, path=path, consent_scope=1)
    return CommunityConsentState.V1_YES


def persist_disabled(*, path: Path | None = None) -> CommunityConsentState:
    mark_decision(False, path=path)
    return CommunityConsentState.DISABLED


def decline_v2_upgrade(*, path: Path | None = None) -> CommunityConsentState:
    """Retain V1_YES and stop upgrade nagging."""

    prefs = load_preferences(path=path)
    if not bool(prefs.get("decision_made")) or not bool(prefs.get("enabled")):
        return resolve_consent_capabilities(prefs=prefs).state
    mark_v2_upgrade_declined(path=path)
    return CommunityConsentState.V1_YES


def consent_capabilities(*, path: Path | None = None) -> ConsentCapabilities:
    return resolve_consent_capabilities(path=path)


def consent_from_persisted_preference(
    *,
    path: Path | None = None,
) -> TelemetrySessionConsent | None:
    """Return session consent when an explicit local preference exists.

    V1_YES and V2_YES both authorize lifecycle transmission.
    Assessment-metadata authorization is derived separately via capabilities.
    """

    caps = resolve_consent_capabilities(path=path)
    if caps.state is CommunityConsentState.UNDECIDED:
        return None
    if caps.lifecycle_allowed:
        return TelemetrySessionConsent(
            decision=TelemetryDecision.ALLOWED_FOR_SESSION,
            source=TelemetryDecisionSource.PERSISTED_PREFERENCE,
            explicit=True,
            persisted=True,
            prior_consent_reused=True,
            installation_identity_required=False,
            transmission_authorized=True,
        )
    return TelemetrySessionConsent(
        decision=TelemetryDecision.DENIED_FOR_SESSION,
        source=TelemetryDecisionSource.PERSISTED_PREFERENCE,
        explicit=True,
        persisted=True,
        prior_consent_reused=True,
        installation_identity_required=False,
        transmission_authorized=False,
    )


def consent_status_payload(*, path: Path | None = None) -> dict[str, object]:
    """Machine-stable consent-v2 status (no identifying fields).

    Consumed by VS Code (Slice 20.10) and CLI ``telemetry status --json``.
    """

    caps = resolve_consent_capabilities(path=path)
    return {
        "assessment_metadata_allowed": caps.assessment_metadata_allowed,
        "lifecycle_allowed": caps.lifecycle_allowed,
        "schema_version": "1",
        "should_prompt_v2_upgrade": caps.should_prompt_v2_upgrade,
        "state": caps.state.value,
        "v2_upgrade_declined": caps.v2_upgrade_declined,
    }


def format_consent_status(*, path: Path | None = None) -> str:
    caps = resolve_consent_capabilities(path=path)
    label = status_label(caps.state)
    lines = [
        "Anonymous Community telemetry",
        "-----------------------------",
        f"Preference: {label}",
        "Default: Disabled (no silent telemetry)",
        "Scope: Local preference under CODESTRATA_HOME",
        (
            "Contents: Anonymous usage and privacy-safe assessment insights — "
            "no source code, repository names, file paths, findings, or credentials. "
            "This consent does not publish reports."
        ),
        f"Lifecycle telemetry: {'allowed' if caps.lifecycle_allowed else 'off'}",
        (
            "Assessment metadata 1.1: "
            f"{'allowed' if caps.assessment_metadata_allowed else 'off'}"
        ),
        "Change later: `codestrata telemetry enable|disable`",
        "",
    ]
    return "\n".join(lines)


def assessment_metadata_policy_for_session(
    *,
    path: Path | None = None,
    transmission_authorized: bool = False,
):
    """Authorize amd emission only for durable V2_YES with session transmission.

    Lifecycle consent (V1_YES) alone never enables assessment_metadata 1.1.
    """

    from codestrata.telemetry.assessment_metadata.policy import (
        authorized_assessment_metadata_emission_policy,
        default_assessment_metadata_emission_policy,
    )

    caps = resolve_consent_capabilities(path=path)
    if caps.assessment_metadata_allowed and transmission_authorized:
        return authorized_assessment_metadata_emission_policy()
    return default_assessment_metadata_emission_policy()


__all__ = [
    "TelemetryPreferenceState",
    "assessment_metadata_policy_for_session",
    "consent_capabilities",
    "consent_from_persisted_preference",
    "consent_status_payload",
    "decline_v2_upgrade",
    "format_consent_status",
    "persist_disabled",
    "persist_preference",
    "persist_v1_yes",
    "persist_v2_yes",
    "preference_state",
]
