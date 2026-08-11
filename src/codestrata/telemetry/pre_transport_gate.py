"""Authoritative pre-transport privacy gate (Slice 9.10).

Accepts only PrivacySafeTelemetryEvent, strictly revalidates, reconciles with
the public catalog, and never invokes transport or echoes rejected values.
"""

from __future__ import annotations

from typing import Any

from codestrata.telemetry.errors import TelemetryRuntimeError
from codestrata.telemetry.pre_transport_errors import (
    PreTransportPrivacyStatus,
    PreTransportReasonCode,
)
from codestrata.telemetry.pre_transport_models import (
    PreTransportPrivacyResult,
    accepted_result,
    rejected_result,
)
from codestrata.telemetry.pre_transport_policy import (
    CommunityTelemetryPreTransportPrivacyPolicy,
    default_pre_transport_policy,
)
from codestrata.telemetry.pre_transport_serialization import (
    canonical_event_bytes,
    serialized_size_bucket,
)
from codestrata.telemetry.pre_transport_validation import (
    PreTransportValidationFailure,
    assert_client_and_event_type,
    assert_field_names_safe,
    assert_versions,
    map_runtime_error,
    reconcile_payload_with_catalog,
)
from codestrata.telemetry.projection import (
    PrivacySafeTelemetryEvent,
    project_from_mapping,
)
from codestrata.telemetry.runtime_policy import (
    CommunityTelemetryRuntimePolicy,
    default_runtime_policy,
)


class PreTransportPrivacyGate:
    """Final privacy boundary immediately before TelemetryTransport.send()."""

    def __init__(
        self,
        *,
        policy: CommunityTelemetryPreTransportPrivacyPolicy | None = None,
        runtime_policy: CommunityTelemetryRuntimePolicy | None = None,
    ) -> None:
        self._policy = policy or default_pre_transport_policy()
        self._runtime_policy = runtime_policy or default_runtime_policy()

    def validate(self, event: Any) -> PreTransportPrivacyResult:
        return validate_event_before_transport(
            event,
            policy=self._policy,
            runtime_policy=self._runtime_policy,
        )


def validate_event_before_transport(
    event: Any,
    *,
    policy: CommunityTelemetryPreTransportPrivacyPolicy | None = None,
    runtime_policy: CommunityTelemetryRuntimePolicy | None = None,
) -> PreTransportPrivacyResult:
    """Validate a privacy-safe event for transport handoff — side-effect-free."""

    active = policy or default_pre_transport_policy()
    runtime = runtime_policy or default_runtime_policy()
    limitations = active.limitations
    try:
        if type(event) is not PrivacySafeTelemetryEvent:
            # Exact type only — reject subclasses that could carry extras.
            return rejected_result(
                status=PreTransportPrivacyStatus.INVALID_TYPE,
                reason=PreTransportReasonCode.INVALID_EVENT_TYPE,
                privacy_policy_version=active.policy_version,
                limitations=limitations,
            )

        stable = event.to_stable_dict()
        if not isinstance(stable, dict):
            return rejected_result(
                status=PreTransportPrivacyStatus.INTERNAL_FAILURE,
                reason=PreTransportReasonCode.INTERNAL_PRIVACY_FAILURE,
                privacy_policy_version=active.policy_version,
                limitations=limitations,
            )

        assert_field_names_safe(stable)
        assert_versions(
            stable,
            required_schema=active.required_event_schema_version,
            required_policy=active.required_runtime_policy_version,
        )
        event_type = assert_client_and_event_type(stable)

        field_count = len(stable)
        if field_count > active.max_property_count:
            return rejected_result(
                status=PreTransportPrivacyStatus.FIELD_LIMIT_EXCEEDED,
                reason=PreTransportReasonCode.TOO_MANY_FIELDS,
                privacy_policy_version=active.policy_version,
                limitations=limitations,
                event_type=event_type,
                schema_version=str(stable.get("schema_version")),
                runtime_policy_version=str(stable.get("runtime_policy_version")),
                field_count=field_count,
            )

        # Reconstruct through strict projection — unknown/forbidden/unsafe reject.
        reconstructed = project_from_mapping(dict(stable), policy=runtime)
        reconstructed_stable = reconstructed.to_stable_dict()
        if reconstructed_stable != {key: stable[key] for key in sorted(stable)}:
            return rejected_result(
                status=PreTransportPrivacyStatus.REJECTED,
                reason=PreTransportReasonCode.NONCANONICAL_SERIALIZATION,
                privacy_policy_version=active.policy_version,
                limitations=limitations,
                event_type=event_type,
                schema_version=str(stable.get("schema_version")),
                runtime_policy_version=str(stable.get("runtime_policy_version")),
                field_count=field_count,
            )

        catalog_schema = reconcile_payload_with_catalog(reconstructed_stable)
        encoded = canonical_event_bytes(reconstructed_stable)
        size_bucket = serialized_size_bucket(len(encoded))
        if len(encoded) > active.max_event_size_bytes:
            return rejected_result(
                status=PreTransportPrivacyStatus.EVENT_TOO_LARGE,
                reason=PreTransportReasonCode.EVENT_TOO_LARGE,
                privacy_policy_version=active.policy_version,
                limitations=limitations,
                event_type=event_type,
                schema_version=str(reconstructed_stable.get("schema_version")),
                runtime_policy_version=str(
                    reconstructed_stable.get("runtime_policy_version")
                ),
                catalog_schema_version=catalog_schema,
                field_count=field_count,
                serialized_size_bucket=size_bucket,
            )

        # Fresh accepted copy — never hand the original mutable-looking object through.
        accepted_event = PrivacySafeTelemetryEvent(
            fields={key: reconstructed_stable[key] for key in sorted(reconstructed_stable)}
        )
        return accepted_result(
            event=accepted_event,
            event_type=event_type,
            schema_version=str(reconstructed_stable["schema_version"]),
            runtime_policy_version=str(reconstructed_stable["runtime_policy_version"]),
            privacy_policy_version=active.policy_version,
            catalog_schema_version=catalog_schema,
            field_count=field_count,
            serialized_size_bucket=size_bucket,
            limitations=limitations,
        )
    except PreTransportValidationFailure as exc:
        status = _status_for_reason(exc.reason)
        return rejected_result(
            status=status,
            reason=exc.reason,
            privacy_policy_version=active.policy_version,
            limitations=limitations,
        )
    except TelemetryRuntimeError as exc:
        reason = map_runtime_error(exc)
        return rejected_result(
            status=_status_for_reason(reason),
            reason=reason,
            privacy_policy_version=active.policy_version,
            limitations=limitations,
        )
    except Exception:
        return rejected_result(
            status=PreTransportPrivacyStatus.INTERNAL_FAILURE,
            reason=PreTransportReasonCode.INTERNAL_PRIVACY_FAILURE,
            privacy_policy_version=active.policy_version,
            limitations=limitations,
        )


def _status_for_reason(reason: PreTransportReasonCode) -> PreTransportPrivacyStatus:
    mapping = {
        PreTransportReasonCode.INVALID_EVENT_TYPE: PreTransportPrivacyStatus.INVALID_TYPE,
        PreTransportReasonCode.UNSUPPORTED_EVENT_SCHEMA: (
            PreTransportPrivacyStatus.UNSUPPORTED_SCHEMA
        ),
        PreTransportReasonCode.UNSUPPORTED_RUNTIME_POLICY: (
            PreTransportPrivacyStatus.UNSUPPORTED_POLICY
        ),
        PreTransportReasonCode.CATALOG_EVENT_MISSING: (
            PreTransportPrivacyStatus.CATALOG_MISMATCH
        ),
        PreTransportReasonCode.CATALOG_FIELD_MISSING: (
            PreTransportPrivacyStatus.CATALOG_MISMATCH
        ),
        PreTransportReasonCode.CATALOG_ENUM_MISMATCH: (
            PreTransportPrivacyStatus.CATALOG_MISMATCH
        ),
        PreTransportReasonCode.CATALOG_MISMATCH: PreTransportPrivacyStatus.CATALOG_MISMATCH,
        PreTransportReasonCode.FORBIDDEN_FIELD_NAME: PreTransportPrivacyStatus.UNSAFE_FIELD,
        PreTransportReasonCode.UNKNOWN_FIELD: PreTransportPrivacyStatus.UNSAFE_FIELD,
        PreTransportReasonCode.UNSAFE_FIELD_VALUE: PreTransportPrivacyStatus.UNSAFE_VALUE,
        PreTransportReasonCode.INVALID_EVENT_COMBINATION: (
            PreTransportPrivacyStatus.INVALID_EVENT_COMBINATION
        ),
        PreTransportReasonCode.TOO_MANY_FIELDS: (
            PreTransportPrivacyStatus.FIELD_LIMIT_EXCEEDED
        ),
        PreTransportReasonCode.EVENT_TOO_LARGE: PreTransportPrivacyStatus.EVENT_TOO_LARGE,
        PreTransportReasonCode.NONCANONICAL_SERIALIZATION: (
            PreTransportPrivacyStatus.REJECTED
        ),
        PreTransportReasonCode.INTERNAL_PRIVACY_FAILURE: (
            PreTransportPrivacyStatus.INTERNAL_FAILURE
        ),
    }
    return mapping.get(reason, PreTransportPrivacyStatus.REJECTED)


__all__ = [
    "PreTransportPrivacyGate",
    "validate_event_before_transport",
]
