"""Bounded diagnostics for CLI telemetry consent flags (Slice 9.6)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.cli_consent import CliTelemetryConsentSelection


@dataclass(frozen=True, slots=True)
class CliTelemetryConsentDiagnostics:
    """Safe flag diagnostics — no argv, paths, endpoints, or payloads."""

    cli_consent_policy_version: str
    explicit_flag_decision_present: bool
    allow_requested: bool
    deny_requested: bool
    conflict: bool
    decision: str | None
    decision_source: str | None
    persisted: bool
    prompt_skipped: bool
    prompt_attempts: int
    transmission_authorized: bool
    limitation_codes: tuple[str, ...]

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "allow_requested": self.allow_requested,
            "cli_consent_policy_version": self.cli_consent_policy_version,
            "conflict": self.conflict,
            "decision": self.decision,
            "decision_source": self.decision_source,
            "deny_requested": self.deny_requested,
            "explicit_flag_decision_present": self.explicit_flag_decision_present,
            "limitation_codes": list(self.limitation_codes),
            "persisted": self.persisted,
            "prompt_attempts": self.prompt_attempts,
            "prompt_skipped": self.prompt_skipped,
            "transmission_authorized": self.transmission_authorized,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def diagnostics_from_cli_selection(
    selection: CliTelemetryConsentSelection,
) -> CliTelemetryConsentDiagnostics:
    consent = selection.consent
    return CliTelemetryConsentDiagnostics(
        cli_consent_policy_version=selection.policy_version,
        explicit_flag_decision_present=selection.explicit_decision_present,
        allow_requested=selection.allow_requested,
        deny_requested=selection.deny_requested,
        conflict=selection.conflict,
        decision=None if consent is None else consent.decision.value,
        decision_source=None if consent is None else consent.source.value,
        persisted=False,
        prompt_skipped=not selection.prompt_required,
        prompt_attempts=0,
        transmission_authorized=(
            False if consent is None else consent.transmission_authorized
        ),
        limitation_codes=selection.limitation_codes,
    )


__all__ = [
    "CliTelemetryConsentDiagnostics",
    "diagnostics_from_cli_selection",
]
