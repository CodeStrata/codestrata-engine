"""Immutable public telemetry catalog models (Slice 9.8)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class EventUsageStatus(StrEnum):
    EMITTED_BY_CURRENT_RUNTIME = "emitted_by_current_runtime"
    SUPPORTED_BUT_NOT_CURRENTLY_EMITTED = "supported_but_not_currently_emitted"


class FieldRequiredness(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


class FieldPrivacyClass(StrEnum):
    PUBLIC_CONSTANT = "public_constant"
    LOW_CARDINALITY_CATEGORY = "low_cardinality_category"
    BOOLEAN = "boolean"
    COARSE_BUCKET = "coarse_bucket"
    BOUNDED_VERSION = "bounded_version"
    BOUNDED_SET_OF_CATEGORIES = "bounded_set_of_categories"


class FieldSource(StrEnum):
    RUNTIME_CONSTANT = "runtime_constant"
    CLI_PACKAGE_METADATA = "cli_package_metadata"
    OPERATING_SYSTEM_CATEGORY = "operating_system_category"
    ARCHITECTURE_CATEGORY = "architecture_category"
    COMMAND_RUNTIME_CATEGORICAL_CONTEXT = "command_runtime_categorical_context"
    ASSESSMENT_CONFIGURATION_CATEGORY = "assessment_configuration_category"
    PRIMARY_OPERATION_RESULT = "primary_operation_result"
    PRIVACY_SAFE_DERIVED_BUCKET = "privacy_safe_derived_bucket"


@dataclass(frozen=True, slots=True)
class TelemetryCatalogEnumValue:
    value: str
    meaning: str

    def to_stable_dict(self) -> dict[str, Any]:
        return {"meaning": self.meaning, "value": self.value}


@dataclass(frozen=True, slots=True)
class TelemetryCatalogEnum:
    name: str
    values: tuple[TelemetryCatalogEnumValue, ...]
    unknown_value_behavior: str = "rejected"
    aliases: tuple[str, ...] = ()
    notes: str = ""

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "aliases": list(self.aliases),
            "name": self.name,
            "notes": self.notes,
            "unknown_value_behavior": self.unknown_value_behavior,
            "values": [item.to_stable_dict() for item in self.values],
        }


@dataclass(frozen=True, slots=True)
class TelemetryCatalogField:
    name: str
    field_type: str
    requiredness: str
    omitted_when_unavailable: bool
    enum_ref: str | None
    max_length: int | None
    privacy_classification: str
    source: str
    normalization: str
    bucketed: bool
    set_ordering_normalized: bool
    event_specific: bool
    transmitted_currently: bool
    example: Any
    notes: str = ""

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "bucketed": self.bucketed,
            "enum_ref": self.enum_ref,
            "event_specific": self.event_specific,
            "example": self.example,
            "field_type": self.field_type,
            "max_length": self.max_length,
            "name": self.name,
            "normalization": self.normalization,
            "notes": self.notes,
            "omitted_when_unavailable": self.omitted_when_unavailable,
            "privacy_classification": self.privacy_classification,
            "requiredness": self.requiredness,
            "set_ordering_normalized": self.set_ordering_normalized,
            "source": self.source,
            "transmitted_currently": self.transmitted_currently,
        }


@dataclass(frozen=True, slots=True)
class TelemetryCatalogEvent:
    name: str
    purpose: str
    lifecycle_meaning: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    prohibited_fields_note: str
    event_specific_constraints: tuple[str, ...]
    usage_status: str
    transmission_operational: bool
    privacy_notes: str
    limitations: tuple[str, ...]
    example: dict[str, Any]

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "event_specific_constraints": list(self.event_specific_constraints),
            "example": {key: self.example[key] for key in sorted(self.example)},
            "lifecycle_meaning": self.lifecycle_meaning,
            "limitations": list(self.limitations),
            "name": self.name,
            "optional_fields": list(self.optional_fields),
            "privacy_notes": self.privacy_notes,
            "prohibited_fields_note": self.prohibited_fields_note,
            "purpose": self.purpose,
            "required_fields": list(self.required_fields),
            "transmission_operational": self.transmission_operational,
            "usage_status": self.usage_status,
        }


@dataclass(frozen=True, slots=True)
class TelemetryCatalogRule:
    rule_id: str
    description: str

    def to_stable_dict(self) -> dict[str, Any]:
        return {"description": self.description, "rule_id": self.rule_id}


@dataclass(frozen=True, slots=True)
class TelemetryNeverCollectedCategory:
    category: str
    description: str

    def to_stable_dict(self) -> dict[str, Any]:
        return {"category": self.category, "description": self.description}


@dataclass(frozen=True, slots=True)
class TelemetryCatalog:
    schema_name: str
    schema_version: str
    catalog_id: str
    runtime_event_schema_version: str
    runtime_policy_version: str
    catalog_policy_version: str
    client_name: str
    transmission_status: str
    installation_identity_status: str
    consent_scope: str
    consent_persistence: str
    consent_expands_fields: bool
    privacy_filtering_required: bool
    max_event_size_bytes: int
    max_property_count: int
    max_string_length: int
    events: tuple[TelemetryCatalogEvent, ...]
    shared_fields: tuple[TelemetryCatalogField, ...]
    enums: tuple[TelemetryCatalogEnum, ...]
    cross_field_rules: tuple[TelemetryCatalogRule, ...]
    never_collected: tuple[TelemetryNeverCollectedCategory, ...]
    validation_behavior: tuple[str, ...]
    limitations: tuple[str, ...]
    change_policy: tuple[str, ...]

    def to_stable_dict(self) -> dict[str, Any]:
        return {
            "catalog_id": self.catalog_id,
            "catalog_policy_version": self.catalog_policy_version,
            "change_policy": list(self.change_policy),
            "client_name": self.client_name,
            "consent_expands_fields": self.consent_expands_fields,
            "consent_persistence": self.consent_persistence,
            "consent_scope": self.consent_scope,
            "cross_field_rules": [item.to_stable_dict() for item in self.cross_field_rules],
            "enums": [item.to_stable_dict() for item in self.enums],
            "events": [item.to_stable_dict() for item in self.events],
            "installation_identity_status": self.installation_identity_status,
            "limitations": list(self.limitations),
            "max_event_size_bytes": self.max_event_size_bytes,
            "max_property_count": self.max_property_count,
            "max_string_length": self.max_string_length,
            "never_collected": [item.to_stable_dict() for item in self.never_collected],
            "privacy_filtering_required": self.privacy_filtering_required,
            "runtime_event_schema_version": self.runtime_event_schema_version,
            "runtime_policy_version": self.runtime_policy_version,
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "shared_fields": [item.to_stable_dict() for item in self.shared_fields],
            "transmission_status": self.transmission_status,
            "validation_behavior": list(self.validation_behavior),
        }

    def to_stable_json(self, *, indent: int | None = 2) -> str:
        text = json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            indent=indent,
            ensure_ascii=True,
        )
        if indent is not None and not text.endswith("\n"):
            text += "\n"
        return text


__all__ = [
    "EventUsageStatus",
    "FieldPrivacyClass",
    "FieldRequiredness",
    "FieldSource",
    "TelemetryCatalog",
    "TelemetryCatalogEnum",
    "TelemetryCatalogEnumValue",
    "TelemetryCatalogEvent",
    "TelemetryCatalogField",
    "TelemetryCatalogRule",
    "TelemetryNeverCollectedCategory",
]
