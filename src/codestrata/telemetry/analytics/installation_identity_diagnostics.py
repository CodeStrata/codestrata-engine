"""Bounded anonymous installation identity diagnostics (Epic 10 Slice 10.2).

Counters and versions only — never identifier values, filesystem paths,
exception text, or payload echo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.installation_identity_policy import (
    COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION,
    COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION,
)


@dataclass(frozen=True, slots=True)
class InstallationIdentityDiagnostics:
    """Safe installation-identity diagnostics."""

    policy_version: str
    schema_version: str
    identity_present: bool
    identity_valid: bool
    created: bool
    recovered: bool
    transmission_allowed: bool
    telemetry_consent_coupled: bool
    last_error_code: str | None
    limitation_codes: tuple[str, ...]

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "created": self.created,
            "identity_present": self.identity_present,
            "identity_valid": self.identity_valid,
            "last_error_code": self.last_error_code,
            "limitation_codes": list(self.limitation_codes),
            "policy_version": self.policy_version,
            "recovered": self.recovered,
            "schema_version": self.schema_version,
            "telemetry_consent_coupled": self.telemetry_consent_coupled,
            "transmission_allowed": self.transmission_allowed,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def empty_installation_identity_diagnostics(
    *,
    limitation_codes: tuple[str, ...] = (),
) -> InstallationIdentityDiagnostics:
    return InstallationIdentityDiagnostics(
        policy_version=COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_POLICY_VERSION,
        schema_version=COMMUNITY_ANONYMOUS_INSTALLATION_IDENTITY_SCHEMA_VERSION,
        identity_present=False,
        identity_valid=False,
        created=False,
        recovered=False,
        transmission_allowed=False,
        telemetry_consent_coupled=False,
        last_error_code=None,
        limitation_codes=tuple(sorted(set(limitation_codes))),
    )


__all__ = [
    "InstallationIdentityDiagnostics",
    "empty_installation_identity_diagnostics",
]
