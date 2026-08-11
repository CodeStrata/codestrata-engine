"""Immutable privacy-first telemetry status model (Slice 9.7)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from codestrata.telemetry.status_policy import (
    PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_NAME,
    PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_VERSION,
)


class TelemetryRuntimeState(StrEnum):
    DISABLED_BY_DEFAULT = "disabled_by_default"


class TelemetryTransportStatus(StrEnum):
    UNAVAILABLE = "unavailable"


class LegacyCompatibilityState(StrEnum):
    """Bounded legacy relationship — no filesystem inspection values."""

    SEPARATE_NOT_INSPECTED = "separate_not_inspected"


@dataclass(frozen=True, slots=True)
class PrivacyFirstTelemetryStatus:
    """Side-effect-free status snapshot — no paths, IDs, endpoints, or env."""

    schema_name: str = PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_NAME
    schema_version: str = PRIVACY_FIRST_TELEMETRY_STATUS_SCHEMA_VERSION
    runtime_state: str = TelemetryRuntimeState.DISABLED_BY_DEFAULT.value
    default_decision: str = "disabled_by_default"
    consent_scope: str = "session"
    consent_persisted: bool = False
    prior_consent_reused: bool = False
    interactive_prompt_available: bool = True
    interactive_prompt_commands: tuple[str, ...] = ("assess",)
    interactive_prompt_default_deny: bool = True
    interactive_prompt_once_per_process: bool = True
    non_interactive_prompt_suppressed: bool = True
    explicit_allow_flag_available: bool = True
    explicit_deny_flag_available: bool = True
    flag_commands: tuple[str, ...] = ("assess",)
    flags_mutually_exclusive: bool = True
    flags_process_local: bool = True
    flags_not_saved: bool = True
    allow_does_not_imply_transmission: bool = True
    transport_status: str = TelemetryTransportStatus.UNAVAILABLE.value
    transmission_available: bool = False
    installation_identity_used: bool = False
    privacy_filter_required: bool = True
    status_side_effect_free: bool = True
    legacy_compatibility_state: str = LegacyCompatibilityState.SEPARATE_NOT_INSPECTED.value
    legacy_preference_authorizes_runtime: bool = False
    catalog_available: bool = True
    catalog_schema_version: str = "1.0.0"
    catalog_documentation_label: str = "telemetry-event-catalog"
    catalog_event_count: int = 0
    catalog_field_count: int = 0
    preview_available: bool = True
    preview_command: str = "codestrata telemetry preview"
    preview_local_only: bool = True
    preview_transmission_performed: bool = False
    privacy_gate_available: bool = True
    privacy_gate_required: bool = True
    privacy_policy_version: str = "1.0"
    policy_versions: tuple[tuple[str, str], ...] = ()
    limitation_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "interactive_prompt_commands",
            tuple(sorted(set(self.interactive_prompt_commands))),
        )
        object.__setattr__(
            self, "flag_commands", tuple(sorted(set(self.flag_commands)))
        )
        object.__setattr__(
            self,
            "policy_versions",
            tuple(sorted(self.policy_versions, key=lambda item: item[0])),
        )
        object.__setattr__(
            self, "limitation_codes", tuple(sorted(set(self.limitation_codes)))
        )

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "allow_does_not_imply_transmission": self.allow_does_not_imply_transmission,
            "catalog_available": self.catalog_available,
            "catalog_documentation_label": self.catalog_documentation_label,
            "catalog_event_count": self.catalog_event_count,
            "catalog_field_count": self.catalog_field_count,
            "catalog_schema_version": self.catalog_schema_version,
            "consent_persisted": self.consent_persisted,
            "consent_scope": self.consent_scope,
            "default_decision": self.default_decision,
            "explicit_allow_flag_available": self.explicit_allow_flag_available,
            "explicit_deny_flag_available": self.explicit_deny_flag_available,
            "flag_commands": list(self.flag_commands),
            "flags_mutually_exclusive": self.flags_mutually_exclusive,
            "flags_not_saved": self.flags_not_saved,
            "flags_process_local": self.flags_process_local,
            "installation_identity_used": self.installation_identity_used,
            "interactive_prompt_available": self.interactive_prompt_available,
            "interactive_prompt_commands": list(self.interactive_prompt_commands),
            "interactive_prompt_default_deny": self.interactive_prompt_default_deny,
            "interactive_prompt_once_per_process": (
                self.interactive_prompt_once_per_process
            ),
            "legacy_compatibility_state": self.legacy_compatibility_state,
            "legacy_preference_authorizes_runtime": (
                self.legacy_preference_authorizes_runtime
            ),
            "limitation_codes": list(self.limitation_codes),
            "non_interactive_prompt_suppressed": self.non_interactive_prompt_suppressed,
            "policy_versions": [
                {"name": name, "version": version}
                for name, version in self.policy_versions
            ],
            "preview_available": self.preview_available,
            "preview_command": self.preview_command,
            "preview_local_only": self.preview_local_only,
            "preview_transmission_performed": self.preview_transmission_performed,
            "prior_consent_reused": self.prior_consent_reused,
            "privacy_filter_required": self.privacy_filter_required,
            "privacy_gate_available": self.privacy_gate_available,
            "privacy_gate_required": self.privacy_gate_required,
            "privacy_policy_version": self.privacy_policy_version,
            "runtime_state": self.runtime_state,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "status_side_effect_free": self.status_side_effect_free,
            "transmission_available": self.transmission_available,
            "transport_status": self.transport_status,
        }

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


__all__ = [
    "LegacyCompatibilityState",
    "PrivacyFirstTelemetryStatus",
    "TelemetryRuntimeState",
    "TelemetryTransportStatus",
]
