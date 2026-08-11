"""Build the privacy-first CLI telemetry preview (Slices 9.9–9.10).

Side-effect-free: no preferences, identity, env, network, transport, or files.
Uses the pre-transport privacy gate in validation-only mode.
"""

from __future__ import annotations

from codestrata.telemetry.catalog import build_privacy_first_telemetry_catalog
from codestrata.telemetry.catalog_policy import (
    PRIVACY_FIRST_TELEMETRY_CATALOG_ID,
    PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION,
)
from codestrata.telemetry.pre_transport_gate import validate_event_before_transport
from codestrata.telemetry.preview_examples import (
    illustrative_runtime_event,
    resolve_preview_event_name,
)
from codestrata.telemetry.preview_models import PrivacyFirstTelemetryPreview
from codestrata.telemetry.preview_policy import (
    CommunityTelemetryPreviewPolicy,
    PreviewPolicyError,
    default_preview_policy,
)
from codestrata.telemetry.preview_validation import reconcile_preview_against_catalog
from codestrata.telemetry.projection import project_runtime_event
from codestrata.telemetry.runtime_policy import (
    COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION,
    PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
    default_runtime_policy,
)


def build_privacy_first_telemetry_preview(
    *,
    event_name: str | None = None,
    policy: CommunityTelemetryPreviewPolicy | None = None,
) -> PrivacyFirstTelemetryPreview:
    """Construct an illustrative privacy-safe preview wrapper + projected event."""

    active = policy or default_preview_policy()
    selected = resolve_preview_event_name(event_name)
    intake = illustrative_runtime_event(selected)
    projected = project_runtime_event(intake, policy=default_runtime_policy())
    gate = validate_event_before_transport(
        projected,
        runtime_policy=default_runtime_policy(),
    )
    if not gate.accepted or gate.accepted_event is None:
        raise PreviewPolicyError(
            "illustrative event failed pre-transport privacy gate"
        )
    # Nested event is the accepted gated copy a future transport would receive.
    stable = gate.accepted_event.to_stable_dict()
    catalog = build_privacy_first_telemetry_catalog()
    catalog_event = next(item for item in catalog.events if item.name == selected)
    optional = set(catalog_event.optional_fields)
    omitted = tuple(sorted(field for field in optional if field not in stable))
    limitations = tuple(
        sorted(
            set(active.limitations)
            | {
                "pre_transport_privacy_gate_required",
                "pre_transport_privacy_gate_validated",
            }
        )
    )
    preview = PrivacyFirstTelemetryPreview(
        schema_name=active.preview_schema_name,
        schema_version=active.preview_schema_version,
        preview_type="illustrative",
        event_name=selected,
        event_usage_status=catalog_event.usage_status,
        event_schema_version=PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
        runtime_policy_version=COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION,
        preview_policy_version=active.policy_version,
        catalog_schema_version=PRIVACY_FIRST_TELEMETRY_CATALOG_SCHEMA_VERSION,
        catalog_id=PRIVACY_FIRST_TELEMETRY_CATALOG_ID,
        transmission_performed=False,
        transport_status="unavailable",
        consent_required_for_transmission=True,
        consent_scope="session",
        consent_persisted=False,
        installation_identity_used=False,
        privacy_filter_required=True,
        event=stable,
        omitted_optional_fields=omitted,
        limitations=limitations,
    )
    reconcile_preview_against_catalog(preview, catalog=catalog)
    encoded = preview.to_stable_json()
    if len(encoded.encode("utf-8")) > active.max_preview_size_bytes:
        raise PreviewPolicyError("preview exceeds maximum size")
    return preview


__all__ = [
    "build_privacy_first_telemetry_preview",
]
