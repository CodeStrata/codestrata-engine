"""CLI telemetry consent flag selection (Slice 9.6).

Maps ``--telemetry-allow`` / ``--telemetry-deny`` to process-local consent.
Never persists, never reads env/config equivalents, never transmits.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.cli_consent_policy import (
    COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION,
    TELEMETRY_FLAG_CONFLICT_MESSAGE,
    CommunityTelemetryCliConsentPolicy,
    default_cli_consent_policy,
)
from codestrata.telemetry.consent import (
    TelemetrySessionConsent,
    allow_session_consent_from_cli_flag,
    deny_session_consent_from_cli_flag,
)


class CliTelemetryConsentConflict(ValueError):
    """Raised when both allow and deny flags are supplied."""

    def __init__(self, message: str = TELEMETRY_FLAG_CONFLICT_MESSAGE) -> None:
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class CliTelemetryConsentSelection:
    """Bounded flag interpretation — no argv, paths, or environment."""

    policy_version: str
    allow_requested: bool
    deny_requested: bool
    explicit_decision_present: bool
    conflict: bool
    consent: TelemetrySessionConsent | None
    prompt_required: bool
    safe_status: str
    limitation_codes: tuple[str, ...] = ()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "allow_requested": self.allow_requested,
            "conflict": self.conflict,
            "consent": None if self.consent is None else self.consent.to_stable_dict(),
            "deny_requested": self.deny_requested,
            "explicit_decision_present": self.explicit_decision_present,
            "limitation_codes": list(self.limitation_codes),
            "policy_version": self.policy_version,
            "prompt_required": self.prompt_required,
            "safe_status": self.safe_status,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def select_cli_telemetry_consent(
    *,
    allow: bool = False,
    deny: bool = False,
    policy: CommunityTelemetryCliConsentPolicy | None = None,
    raise_on_conflict: bool = True,
) -> CliTelemetryConsentSelection:
    """Interpret CLI telemetry flags into a typed selection.

    When both flags are true and ``raise_on_conflict`` is True, raises
    ``CliTelemetryConsentConflict`` (CLI usage error — not fail-silent).
    """

    active = policy or default_cli_consent_policy()
    allow_requested = bool(allow)
    deny_requested = bool(deny)
    limitations = active.limitations

    if allow_requested and deny_requested:
        selection = CliTelemetryConsentSelection(
            policy_version=COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION,
            allow_requested=True,
            deny_requested=True,
            explicit_decision_present=False,
            conflict=True,
            consent=None,
            prompt_required=False,
            safe_status="conflict",
            limitation_codes=limitations,
        )
        if raise_on_conflict:
            raise CliTelemetryConsentConflict()
        return selection

    if allow_requested:
        consent = allow_session_consent_from_cli_flag()
        return CliTelemetryConsentSelection(
            policy_version=COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION,
            allow_requested=True,
            deny_requested=False,
            explicit_decision_present=True,
            conflict=False,
            consent=consent,
            prompt_required=False,
            safe_status="allowed_cli_flag",
            limitation_codes=limitations,
        )

    if deny_requested:
        consent = deny_session_consent_from_cli_flag()
        return CliTelemetryConsentSelection(
            policy_version=COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION,
            allow_requested=False,
            deny_requested=True,
            explicit_decision_present=True,
            conflict=False,
            consent=consent,
            prompt_required=False,
            safe_status="denied_cli_flag",
            limitation_codes=limitations,
        )

    return CliTelemetryConsentSelection(
        policy_version=COMMUNITY_TELEMETRY_CLI_CONSENT_POLICY_VERSION,
        allow_requested=False,
        deny_requested=False,
        explicit_decision_present=False,
        conflict=False,
        consent=None,
        prompt_required=True,
        safe_status="no_flags",
        limitation_codes=limitations,
    )


__all__ = [
    "CliTelemetryConsentConflict",
    "CliTelemetryConsentSelection",
    "select_cli_telemetry_consent",
]
