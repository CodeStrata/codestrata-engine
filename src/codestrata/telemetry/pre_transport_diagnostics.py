"""Bounded diagnostics helpers for the pre-transport privacy gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.pre_transport_models import PreTransportPrivacyResult
from codestrata.telemetry.pre_transport_policy import (
    COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION,
)


@dataclass(frozen=True, slots=True)
class PreTransportPrivacyDiagnostics:
    privacy_policy_version: str
    privacy_gate_attempts: int
    privacy_gate_accepted: int
    privacy_gate_rejected: int
    privacy_gate_failures: int
    last_privacy_result_category: str | None = None

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "last_privacy_result_category": self.last_privacy_result_category,
            "privacy_gate_accepted": self.privacy_gate_accepted,
            "privacy_gate_attempts": self.privacy_gate_attempts,
            "privacy_gate_failures": self.privacy_gate_failures,
            "privacy_gate_rejected": self.privacy_gate_rejected,
            "privacy_policy_version": self.privacy_policy_version,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def diagnostics_from_gate_result(
    result: PreTransportPrivacyResult,
    *,
    attempts: int,
    accepted: int,
    rejected: int,
    failures: int,
) -> PreTransportPrivacyDiagnostics:
    return PreTransportPrivacyDiagnostics(
        privacy_policy_version=(
            result.privacy_policy_version
            or COMMUNITY_TELEMETRY_PRE_TRANSPORT_PRIVACY_POLICY_VERSION
        ),
        privacy_gate_attempts=attempts,
        privacy_gate_accepted=accepted,
        privacy_gate_rejected=rejected,
        privacy_gate_failures=failures,
        last_privacy_result_category=result.status,
    )


__all__ = [
    "PreTransportPrivacyDiagnostics",
    "diagnostics_from_gate_result",
]
