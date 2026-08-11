"""Typed interactive consent prompt result (Slices 9.4–9.5)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.consent import TelemetrySessionConsent, default_session_consent
from codestrata.telemetry.prompt_eligibility import PromptEligibilityReason
from codestrata.telemetry.prompt_policy import (
    COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_VERSION,
)


@dataclass(frozen=True, slots=True)
class InteractiveConsentPromptResult:
    """Bounded prompt outcome — never includes raw answers or paths."""

    eligibility: bool
    eligibility_reason: str
    prompted: bool
    attempts: int
    decision: str
    decision_source: str
    consent: TelemetrySessionConsent
    safe_outcome: str
    prompt_policy_version: str = COMMUNITY_TELEMETRY_INTERACTIVE_CONSENT_POLICY_VERSION
    limitation_codes: tuple[str, ...] = ()

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "attempts": self.attempts,
            "consent": self.consent.to_stable_dict(),
            "decision": self.decision,
            "decision_source": self.decision_source,
            "eligibility": self.eligibility,
            "eligibility_reason": self.eligibility_reason,
            "limitation_codes": list(self.limitation_codes),
            "prompt_policy_version": self.prompt_policy_version,
            "prompted": self.prompted,
            "safe_outcome": self.safe_outcome,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def default_skipped_prompt_result(
    *,
    reason: PromptEligibilityReason,
    limitations: tuple[str, ...] = (),
    consent: TelemetrySessionConsent | None = None,
) -> InteractiveConsentPromptResult:
    """Suppression path — prompted=false, attempts=0 (not a prompt attempt)."""

    active = consent or default_session_consent()
    if active.decision.value == "non_interactive_disabled":
        outcome = "suppressed_non_interactive"
    elif active.explicit:
        outcome = "skipped_explicit_decision"
    else:
        outcome = "skipped_disabled_by_default"
    return InteractiveConsentPromptResult(
        eligibility=False,
        eligibility_reason=reason.value,
        prompted=False,
        attempts=0,
        decision=active.decision.value,
        decision_source=active.source.value,
        consent=active,
        safe_outcome=outcome,
        limitation_codes=tuple(sorted(set(limitations))),
    )


__all__ = [
    "InteractiveConsentPromptResult",
    "default_skipped_prompt_result",
]
