"""Bounded diagnostics helpers for non-interactive suppression (Slice 9.5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.non_interactive import NonInteractiveTelemetryDecision


@dataclass(frozen=True, slots=True)
class NonInteractiveTelemetryDiagnostics:
    """Safe suppression diagnostics — no env values, providers, or paths."""

    non_interactive_policy_version: str
    prompt_suppressed: bool
    suppression_reason: str
    automation_detected: bool
    stdin_interactive: bool
    output_mode: str
    decision: str
    decision_source: str
    transmission_authorized: bool
    prompted: bool
    attempts: int
    limitation_codes: tuple[str, ...]

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "attempts": self.attempts,
            "automation_detected": self.automation_detected,
            "decision": self.decision,
            "decision_source": self.decision_source,
            "limitation_codes": list(self.limitation_codes),
            "non_interactive_policy_version": self.non_interactive_policy_version,
            "output_mode": self.output_mode,
            "prompt_suppressed": self.prompt_suppressed,
            "prompted": self.prompted,
            "stdin_interactive": self.stdin_interactive,
            "suppression_reason": self.suppression_reason,
            "transmission_authorized": self.transmission_authorized,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def diagnostics_from_non_interactive(
    decision: NonInteractiveTelemetryDecision,
    *,
    prompted: bool = False,
    attempts: int = 0,
) -> NonInteractiveTelemetryDiagnostics:
    return NonInteractiveTelemetryDiagnostics(
        non_interactive_policy_version=decision.non_interactive_policy_version,
        prompt_suppressed=decision.prompt_suppressed,
        suppression_reason=decision.suppression_reason,
        automation_detected=decision.automation_detected,
        stdin_interactive=decision.stdin_interactive,
        output_mode=decision.output_mode,
        decision=decision.decision,
        decision_source=decision.decision_source,
        transmission_authorized=decision.consent.transmission_authorized,
        prompted=prompted,
        attempts=attempts,
        limitation_codes=decision.limitation_codes,
    )


__all__ = [
    "NonInteractiveTelemetryDiagnostics",
    "diagnostics_from_non_interactive",
]
