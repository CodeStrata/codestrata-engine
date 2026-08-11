"""Status model and factory tests (Slice 9.7)."""

from __future__ import annotations

from codestrata.telemetry.status import build_privacy_first_telemetry_status
from codestrata.telemetry.status_diagnostics import diagnostics_from_status
from codestrata.telemetry.status_models import LegacyCompatibilityState


def test_status_model_defaults() -> None:
    status = build_privacy_first_telemetry_status()
    assert status.schema_name == "privacy-first-telemetry-status"
    assert status.schema_version == "1.0.0"
    assert status.runtime_state == "disabled_by_default"
    assert status.default_decision == "disabled_by_default"
    assert status.consent_scope == "session"
    assert status.consent_persisted is False
    assert status.prior_consent_reused is False
    assert status.interactive_prompt_commands == ("assess",)
    assert status.flag_commands == ("assess",)
    assert status.transport_status == "unavailable"
    assert status.transmission_available is False
    assert status.installation_identity_used is False
    assert status.privacy_filter_required is True
    assert status.status_side_effect_free is True
    assert (
        status.legacy_compatibility_state
        == LegacyCompatibilityState.SEPARATE_NOT_INSPECTED.value
    )
    assert status.legacy_preference_authorizes_runtime is False
    assert status.catalog_available is True
    assert status.catalog_schema_version == "1.0.0"
    assert status.catalog_documentation_label == "telemetry-event-catalog"
    assert status.catalog_event_count == 5
    assert status.catalog_field_count == 15
    assert status.preview_available is True
    assert status.preview_command == "codestrata telemetry preview"
    assert status.preview_local_only is True
    assert status.preview_transmission_performed is False
    assert status.privacy_gate_available is True
    assert status.privacy_gate_required is True
    assert status.privacy_policy_version == "1.0"
    policy_names = {name for name, _ in status.policy_versions}
    assert "catalog" in policy_names
    assert "preview" in policy_names
    assert "pre_transport_privacy" in policy_names
    assert "transport" in policy_names
    assert "assessment_isolation" in policy_names
    assert "event_catalog_deferred_to_slice_9_8" not in status.limitation_codes
    assert "preview_command_deferred_to_slice_9_9" not in status.limitation_codes
    assert "cloud_transport_not_implemented" not in status.limitation_codes
    assert "http_transport_requires_explicit_configuration" in status.limitation_codes
    assert "assessment_isolation_primary_authoritative" in status.limitation_codes


def test_stable_dict_excludes_sensitive_keys() -> None:
    payload = build_privacy_first_telemetry_status().to_stable_dict()
    forbidden_keys = {
        "installation_id",
        "endpoint",
        "endpoint_url",
        "queue",
        "queue_depth",
        "argv",
        "home",
        "cwd",
        "path",
    }
    assert forbidden_keys.isdisjoint(payload.keys())
    blob = payload.to_stable_json() if False else str(payload)
    for needle in ("/users/", "https://", "password", "55555555"):
        assert needle not in blob.lower()
    assert list(payload.keys()) == sorted(payload.keys())
    assert "installation_id" not in payload
    assert payload["installation_identity_used"] is False


def test_diagnostics_bounded() -> None:
    diag = diagnostics_from_status(build_privacy_first_telemetry_status())
    assert diag.transmission_available is False
    assert diag.installation_identity_used is False
    payload = diag.to_stable_dict()
    assert "installation_id" not in payload
    assert "endpoint" not in payload
    assert "55555555" not in diag.to_stable_json()
