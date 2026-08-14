"""Community consent-v2 state and capability derivation (Slice 20.9).

Canonical states:
  UNDECIDED | V1_YES | V2_YES | DISABLED

Capabilities:
  lifecycle_allowed — feature_invoked / feature_completed / operation_failed
  assessment_metadata_allowed — assessment_metadata 1.1 emission
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from codestrata.telemetry.preferences import load_preferences


class CommunityConsentState(StrEnum):
    UNDECIDED = "undecided"
    V1_YES = "v1_yes"
    V2_YES = "v2_yes"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ConsentCapabilities:
    """Derived collection capabilities from durable consent state."""

    state: CommunityConsentState
    lifecycle_allowed: bool
    assessment_metadata_allowed: bool
    should_prompt_fresh: bool
    should_prompt_v2_upgrade: bool
    v2_upgrade_declined: bool
    consent_scope: int | None

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "assessment_metadata_allowed": self.assessment_metadata_allowed,
            "consent_scope": self.consent_scope,
            "lifecycle_allowed": self.lifecycle_allowed,
            "should_prompt_fresh": self.should_prompt_fresh,
            "should_prompt_v2_upgrade": self.should_prompt_v2_upgrade,
            "state": self.state.value,
            "v2_upgrade_declined": self.v2_upgrade_declined,
        }


def normalize_consent_scope(value: object) -> int | None | object:
    """Return 1, 2, None, or a sentinel object for unsupported values.

    Unsupported values must never be treated as V2.
    """

    if value is None:
        return None
    if isinstance(value, bool):
        return object()  # invalid
    if isinstance(value, int):
        if value in (1, 2):
            return value
        return object()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = int(text)
        except ValueError:
            return object()
        if number in (1, 2):
            return number
        return object()
    return object()


def resolve_consent_capabilities(
    *,
    path: Path | None = None,
    prefs: dict[str, Any] | None = None,
) -> ConsentCapabilities:
    """Derive consent-v2 capabilities from preference dict or disk."""

    data = prefs if prefs is not None else load_preferences(path=path)
    decision_made = bool(data.get("decision_made"))
    enabled = bool(data.get("enabled"))
    raw_scope = normalize_consent_scope(data.get("consent_scope"))
    upgrade_declined = bool(data.get("v2_upgrade_declined"))

    # Unsupported scope → fail-safe UNDECIDED (never enable).
    if raw_scope is not None and not isinstance(raw_scope, int):
        return ConsentCapabilities(
            state=CommunityConsentState.UNDECIDED,
            lifecycle_allowed=False,
            assessment_metadata_allowed=False,
            should_prompt_fresh=True,
            should_prompt_v2_upgrade=False,
            v2_upgrade_declined=False,
            consent_scope=None,
        )

    scope: int | None = raw_scope if isinstance(raw_scope, int) else None

    if not decision_made:
        return ConsentCapabilities(
            state=CommunityConsentState.UNDECIDED,
            lifecycle_allowed=False,
            assessment_metadata_allowed=False,
            should_prompt_fresh=True,
            should_prompt_v2_upgrade=False,
            v2_upgrade_declined=False,
            consent_scope=scope,
        )

    if not enabled:
        return ConsentCapabilities(
            state=CommunityConsentState.DISABLED,
            lifecycle_allowed=False,
            assessment_metadata_allowed=False,
            should_prompt_fresh=False,
            should_prompt_v2_upgrade=False,
            v2_upgrade_declined=upgrade_declined,
            consent_scope=scope,
        )

    if scope == 2:
        return ConsentCapabilities(
            state=CommunityConsentState.V2_YES,
            lifecycle_allowed=True,
            assessment_metadata_allowed=True,
            should_prompt_fresh=False,
            should_prompt_v2_upgrade=False,
            v2_upgrade_declined=upgrade_declined,
            consent_scope=2,
        )

    # enabled + decision_made + scope in {None, 1} → legacy / explicit V1
    return ConsentCapabilities(
        state=CommunityConsentState.V1_YES,
        lifecycle_allowed=True,
        assessment_metadata_allowed=False,
        should_prompt_fresh=False,
        should_prompt_v2_upgrade=not upgrade_declined,
        v2_upgrade_declined=upgrade_declined,
        consent_scope=1 if scope == 1 else None,
    )


def status_label(state: CommunityConsentState) -> str:
    return {
        CommunityConsentState.UNDECIDED: "Not configured",
        CommunityConsentState.V1_YES: "Enabled (legacy v1 — lifecycle only)",
        CommunityConsentState.V2_YES: "Enabled (v2 — usage + assessment insights)",
        CommunityConsentState.DISABLED: "Disabled",
    }[state]


__all__ = [
    "CommunityConsentState",
    "ConsentCapabilities",
    "normalize_consent_scope",
    "resolve_consent_capabilities",
    "status_label",
]
