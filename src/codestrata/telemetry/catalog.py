"""Build the authoritative privacy-first telemetry catalog (Slice 9.8).

Consumes typed runtime models, enums, privacy allowlists, and bounded metadata.
Side-effect-free: no preferences, identity, env, network, or filesystem writes.
"""

from __future__ import annotations

from codestrata.telemetry.catalog_metadata import (
    CHANGE_POLICY,
    CROSS_FIELD_RULES,
    ENUM_MEANINGS,
    EVENT_LIFECYCLE_MEANING,
    EVENT_PURPOSE,
    EVENT_USAGE,
    FIELD_META,
    NEVER_COLLECTED,
    VALIDATION_BEHAVIOR,
)
from codestrata.telemetry.catalog_models import (
    TelemetryCatalog,
    TelemetryCatalogEnum,
    TelemetryCatalogEnumValue,
    TelemetryCatalogEvent,
    TelemetryCatalogField,
    TelemetryCatalogRule,
    TelemetryNeverCollectedCategory,
)
from codestrata.telemetry.catalog_policy import (
    CommunityTelemetryPublicCatalogPolicy,
    default_catalog_policy,
)
from codestrata.telemetry.events import (
    ArchFamily,
    DurationBucket,
    FailureCategory,
    Lifecycle,
    OperationCategory,
    OsFamily,
    ResultCategory,
    RuntimeEventType,
    RuntimeTelemetryEvent,
)
from codestrata.telemetry.privacy import APPROVED_FIELD_NAMES
from codestrata.telemetry.projection import project_runtime_event
from codestrata.telemetry.runtime_policy import (
    COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION,
    PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
    default_runtime_policy,
)

_ENUM_TYPES: dict[str, type] = {
    "event_type": RuntimeEventType,
    "os_family": OsFamily,
    "arch_family": ArchFamily,
    "lifecycle": Lifecycle,
    "result": ResultCategory,
    "duration_bucket": DurationBucket,
    "operation_category": OperationCategory,
    "failure_category": FailureCategory,
}

# Intake fields from RuntimeTelemetryEvent (excluding projection-injected versions).
_INTAKE_OPTIONAL = (
    "cli_version",
    "os_family",
    "arch_family",
    "lifecycle",
    "result",
    "duration_bucket",
    "operation_category",
    "enabled_assessment_heads",
    "offline_mode",
    "ai_used",
    "failure_category",
)
_INTAKE_REQUIRED = ("event_type", "client_name")
_PROJECTION_REQUIRED = ("schema_version", "runtime_policy_version")


def build_privacy_first_telemetry_catalog(
    *,
    policy: CommunityTelemetryPublicCatalogPolicy | None = None,
) -> TelemetryCatalog:
    """Construct the public catalog from authoritative runtime contracts."""

    active = policy or default_catalog_policy()
    runtime = default_runtime_policy()
    enums = _build_enums()
    shared_fields = _build_fields()
    events = _build_events()
    never_collected = tuple(
        TelemetryNeverCollectedCategory(category=name, description=desc)
        for name, desc in sorted(NEVER_COLLECTED, key=lambda item: item[0])
    )
    rules = tuple(
        TelemetryCatalogRule(rule_id=rule_id, description=description)
        for rule_id, description in sorted(CROSS_FIELD_RULES, key=lambda item: item[0])
    )
    return TelemetryCatalog(
        schema_name=active.catalog_schema_name,
        schema_version=active.catalog_schema_version,
        catalog_id=active.catalog_id,
        runtime_event_schema_version=PRIVACY_SAFE_RUNTIME_EVENT_SCHEMA_VERSION,
        runtime_policy_version=COMMUNITY_TELEMETRY_RUNTIME_POLICY_VERSION,
        catalog_policy_version=active.policy_version,
        client_name=active.client_name,
        transmission_status="not_operational",
        installation_identity_status="not_used",
        consent_scope="session",
        consent_persistence="none",
        consent_expands_fields=False,
        privacy_filtering_required=True,
        max_event_size_bytes=runtime.max_event_size_bytes,
        max_property_count=runtime.max_property_count,
        max_string_length=runtime.max_string_length,
        events=events,
        shared_fields=shared_fields,
        enums=enums,
        cross_field_rules=rules,
        never_collected=never_collected,
        validation_behavior=tuple(sorted(VALIDATION_BEHAVIOR)),
        limitations=active.limitations,
        change_policy=tuple(sorted(CHANGE_POLICY)),
    )


def _build_enums() -> tuple[TelemetryCatalogEnum, ...]:
    items: list[TelemetryCatalogEnum] = []
    for name in sorted(_ENUM_TYPES):
        enum_cls = _ENUM_TYPES[name]
        meanings = ENUM_MEANINGS[name]
        values = tuple(
            TelemetryCatalogEnumValue(
                value=member.value,
                meaning=meanings[member.value],
            )
            for member in sorted(enum_cls, key=lambda item: item.value)
        )
        items.append(
            TelemetryCatalogEnum(
                name=name,
                values=values,
                unknown_value_behavior="rejected",
                aliases=(),
                notes=(
                    "Duration buckets are named categories only; exact duration "
                    "is not retained."
                    if name == "duration_bucket"
                    else ""
                ),
            )
        )
    return tuple(items)


def _build_fields() -> tuple[TelemetryCatalogField, ...]:
    fields: list[TelemetryCatalogField] = []
    for name in sorted(APPROVED_FIELD_NAMES):
        meta = FIELD_META[name]
        fields.append(
            TelemetryCatalogField(
                name=name,
                field_type=str(meta["type"]),
                requiredness=str(meta["requiredness"]),
                omitted_when_unavailable=bool(meta["omitted_when_unavailable"]),
                enum_ref=meta["enum_ref"] if meta["enum_ref"] is None else str(meta["enum_ref"]),
                max_length=meta["max_length"] if meta["max_length"] is None else int(meta["max_length"]),  # type: ignore[arg-type]
                privacy_classification=str(meta["privacy"]),
                source=str(meta["source"]),
                normalization=str(meta["normalization"]),
                bucketed=bool(meta["bucketed"]),
                set_ordering_normalized=bool(meta["set_ordering_normalized"]),
                event_specific=bool(meta["event_specific"]),
                transmitted_currently=False,
                example=meta["example"],
                notes=str(meta["notes"]),
            )
        )
    return tuple(fields)


def _build_events() -> tuple[TelemetryCatalogEvent, ...]:
    events: list[TelemetryCatalogEvent] = []
    required = tuple(sorted(set(_INTAKE_REQUIRED) | set(_PROJECTION_REQUIRED)))
    optional = tuple(sorted(_INTAKE_OPTIONAL))
    for event_type in sorted(RuntimeEventType, key=lambda item: item.value):
        name = event_type.value
        example_intake = RuntimeTelemetryEvent(event_type=event_type)
        projected = project_runtime_event(example_intake).to_stable_dict()
        # Illustrative optional fields for documentation clarity.
        illustrative = dict(projected)
        if name == RuntimeEventType.FEATURE_INVOKED.value:
            illustrative["operation_category"] = "assess"
            illustrative["lifecycle"] = "start"
            illustrative["ai_used"] = False
        elif name == RuntimeEventType.FEATURE_COMPLETED.value:
            illustrative["operation_category"] = "assess"
            illustrative["lifecycle"] = "complete"
            illustrative["result"] = "success"
            illustrative["duration_bucket"] = "s_1_10"
            illustrative["ai_used"] = False
        elif name == RuntimeEventType.OPERATION_FAILED.value:
            illustrative["operation_category"] = "assess"
            illustrative["lifecycle"] = "fail"
            illustrative["result"] = "failure"
            illustrative["failure_category"] = "unavailable"
        events.append(
            TelemetryCatalogEvent(
                name=name,
                purpose=EVENT_PURPOSE[name],
                lifecycle_meaning=EVENT_LIFECYCLE_MEANING[name],
                required_fields=required,
                optional_fields=optional,
                prohibited_fields_note=(
                    "Any field outside the approved allowlist is rejected. "
                    "Forbidden identity/path/credential field names are rejected."
                ),
                event_specific_constraints=(
                    "Shared event shape; no additional event-specific requiredness "
                    "is enforced by current validators.",
                ),
                usage_status=EVENT_USAGE[name],
                transmission_operational=False,
                privacy_notes=(
                    "Privacy projection is mandatory. Consent cannot expand fields. "
                    "Transport-bound events must pass the pre-transport privacy gate. "
                    "Cloud mapping is independently versioned. Default transport remains "
                    "unavailable; HTTP requires explicit configuration. "
                    "installation_id and wire event_id are not Engine catalog fields."
                ),
                limitations=(
                    "transmission_not_operational",
                    "installation_identity_not_used",
                    "http_transport_requires_explicit_configuration",
                    "cloud_mapping_independently_versioned",
                ),
                example={key: illustrative[key] for key in sorted(illustrative)},
            )
        )
    return tuple(events)


__all__ = [
    "build_privacy_first_telemetry_catalog",
]
