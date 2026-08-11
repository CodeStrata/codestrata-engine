"""Bounded descriptive metadata for the public telemetry catalog (Slice 9.8).

Adjacent to authoritative enums/models — does not redefine names or values.
Reconciled by tests against ``events``, ``privacy``, and ``projection``.
"""

from __future__ import annotations

from codestrata.telemetry.catalog_models import (
    EventUsageStatus,
    FieldPrivacyClass,
    FieldRequiredness,
    FieldSource,
)
from codestrata.telemetry.events import RuntimeEventType

# Descriptive purposes keyed by authoritative event names.
EVENT_PURPOSE: dict[str, str] = {
    RuntimeEventType.APPLICATION_STARTED.value: (
        "Marks the start of a CLI process lifecycle for privacy-safe telemetry."
    ),
    RuntimeEventType.APPLICATION_COMPLETED.value: (
        "Marks successful or terminal completion of a CLI process lifecycle."
    ),
    RuntimeEventType.FEATURE_INVOKED.value: (
        "Records that a categorical feature or command operation began."
    ),
    RuntimeEventType.FEATURE_COMPLETED.value: (
        "Records that a categorical feature or command operation completed."
    ),
    RuntimeEventType.OPERATION_FAILED.value: (
        "Records that a categorical operation failed with a bounded failure category."
    ),
}

EVENT_LIFECYCLE_MEANING: dict[str, str] = {
    RuntimeEventType.APPLICATION_STARTED.value: "Process start (lifecycle may be start).",
    RuntimeEventType.APPLICATION_COMPLETED.value: (
        "Process completion (lifecycle may be complete)."
    ),
    RuntimeEventType.FEATURE_INVOKED.value: "Feature/operation start.",
    RuntimeEventType.FEATURE_COMPLETED.value: "Feature/operation completion.",
    RuntimeEventType.OPERATION_FAILED.value: "Feature/operation failure.",
}

EVENT_USAGE: dict[str, str] = {
    RuntimeEventType.APPLICATION_STARTED.value: (
        EventUsageStatus.SUPPORTED_BUT_NOT_CURRENTLY_EMITTED.value
    ),
    RuntimeEventType.APPLICATION_COMPLETED.value: (
        EventUsageStatus.SUPPORTED_BUT_NOT_CURRENTLY_EMITTED.value
    ),
    RuntimeEventType.FEATURE_INVOKED.value: (
        EventUsageStatus.EMITTED_BY_CURRENT_RUNTIME.value
    ),
    RuntimeEventType.FEATURE_COMPLETED.value: (
        EventUsageStatus.EMITTED_BY_CURRENT_RUNTIME.value
    ),
    RuntimeEventType.OPERATION_FAILED.value: (
        EventUsageStatus.EMITTED_BY_CURRENT_RUNTIME.value
    ),
}

ENUM_MEANINGS: dict[str, dict[str, str]] = {
    "event_type": {
        "application_started": "CLI application/process started.",
        "application_completed": "CLI application/process completed.",
        "feature_invoked": "A feature or command path was invoked.",
        "feature_completed": "A feature or command path completed.",
        "operation_failed": "An operation failed.",
    },
    "os_family": {
        "linux": "Linux family operating system.",
        "macos": "macOS family operating system.",
        "windows": "Windows family operating system.",
        "other": "Other or unclassified OS family.",
    },
    "arch_family": {
        "x86_64": "64-bit x86 architecture.",
        "arm64": "64-bit ARM architecture.",
        "other": "Other or unclassified architecture.",
    },
    "lifecycle": {
        "start": "Start of an operation or process.",
        "complete": "Successful/terminal completion.",
        "fail": "Failure terminal state.",
    },
    "result": {
        "success": "Operation succeeded.",
        "failure": "Operation failed.",
        "cancelled": "Operation cancelled.",
        "unknown": "Result not classified.",
    },
    "duration_bucket": {
        "lt_1s": "Coarse duration category under one second.",
        "s_1_10": "Coarse duration category from about 1s to 10s.",
        "s_10_60": "Coarse duration category from about 10s to 60s.",
        "m_1_5": "Coarse duration category from about 1m to 5m.",
        "gt_5m": "Coarse duration category greater than about 5m.",
    },
    "operation_category": {
        "assess": "Assessment-related operation.",
        "report": "Report-related operation.",
        "other": "Other categorical operation.",
    },
    "failure_category": {
        "validation": "Validation failure.",
        "timeout": "Timeout failure.",
        "unavailable": "Dependency or capability unavailable.",
        "internal": "Internal error category.",
        "unknown": "Unclassified failure.",
    },
}

FIELD_META: dict[str, dict[str, object]] = {
    "event_type": {
        "type": "enum",
        "requiredness": FieldRequiredness.REQUIRED.value,
        "omitted_when_unavailable": False,
        "enum_ref": "event_type",
        "max_length": None,
        "privacy": FieldPrivacyClass.LOW_CARDINALITY_CATEGORY.value,
        "source": FieldSource.COMMAND_RUNTIME_CATEGORICAL_CONTEXT.value,
        "normalization": "exact enum value",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "feature_invoked",
        "notes": "Required on every privacy-safe projected event.",
    },
    "client_name": {
        "type": "string",
        "requiredness": FieldRequiredness.REQUIRED.value,
        "omitted_when_unavailable": False,
        "enum_ref": None,
        "max_length": 64,
        "privacy": FieldPrivacyClass.PUBLIC_CONSTANT.value,
        "source": FieldSource.RUNTIME_CONSTANT.value,
        "normalization": "must equal codestrata_cli",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "codestrata_cli",
        "notes": "Only codestrata_cli is accepted in the current runtime.",
    },
    "cli_version": {
        "type": "string",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": None,
        "max_length": 32,
        "privacy": FieldPrivacyClass.BOUNDED_VERSION.value,
        "source": FieldSource.CLI_PACKAGE_METADATA.value,
        "normalization": "trimmed; path markers rejected; max 32 chars",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "0.2.0",
        "notes": "Package version string when supplied.",
    },
    "os_family": {
        "type": "enum",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": "os_family",
        "max_length": None,
        "privacy": FieldPrivacyClass.LOW_CARDINALITY_CATEGORY.value,
        "source": FieldSource.OPERATING_SYSTEM_CATEGORY.value,
        "normalization": "exact enum value",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "macos",
        "notes": "",
    },
    "arch_family": {
        "type": "enum",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": "arch_family",
        "max_length": None,
        "privacy": FieldPrivacyClass.LOW_CARDINALITY_CATEGORY.value,
        "source": FieldSource.ARCHITECTURE_CATEGORY.value,
        "normalization": "exact enum value",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "arm64",
        "notes": "",
    },
    "lifecycle": {
        "type": "enum",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": "lifecycle",
        "max_length": None,
        "privacy": FieldPrivacyClass.LOW_CARDINALITY_CATEGORY.value,
        "source": FieldSource.COMMAND_RUNTIME_CATEGORICAL_CONTEXT.value,
        "normalization": "exact enum value",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "start",
        "notes": "Shared optional field; not event-enforced by validators today.",
    },
    "result": {
        "type": "enum",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": "result",
        "max_length": None,
        "privacy": FieldPrivacyClass.LOW_CARDINALITY_CATEGORY.value,
        "source": FieldSource.PRIMARY_OPERATION_RESULT.value,
        "normalization": "exact enum value",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "success",
        "notes": "Shared optional field across the common event shape.",
    },
    "duration_bucket": {
        "type": "enum",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": "duration_bucket",
        "max_length": None,
        "privacy": FieldPrivacyClass.COARSE_BUCKET.value,
        "source": FieldSource.PRIVACY_SAFE_DERIVED_BUCKET.value,
        "normalization": "exact named category only; no exact duration retained",
        "bucketed": True,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "s_1_10",
        "notes": (
            "Runtime accepts only named categories. Exact durations are not "
            "collected by the privacy-first event model."
        ),
    },
    "operation_category": {
        "type": "enum",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": "operation_category",
        "max_length": None,
        "privacy": FieldPrivacyClass.LOW_CARDINALITY_CATEGORY.value,
        "source": FieldSource.COMMAND_RUNTIME_CATEGORICAL_CONTEXT.value,
        "normalization": "exact enum value",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "assess",
        "notes": "",
    },
    "enabled_assessment_heads": {
        "type": "array[string]",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": None,
        "max_length": 32,
        "privacy": FieldPrivacyClass.BOUNDED_SET_OF_CATEGORIES.value,
        "source": FieldSource.ASSESSMENT_CONFIGURATION_CATEGORY.value,
        "normalization": "sorted unique strings; path markers rejected; max 32 chars each",
        "bucketed": False,
        "set_ordering_normalized": True,
        "event_specific": False,
        "example": ["architecture", "security"],
        "notes": (
            "Omitted when empty. Bounded strings (max 32 chars; path markers "
            "rejected). There is no closed assessment-head enum in the runtime; "
            "examples are illustrative categorical names only."
        ),
    },
    "offline_mode": {
        "type": "boolean",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": None,
        "max_length": None,
        "privacy": FieldPrivacyClass.BOOLEAN.value,
        "source": FieldSource.COMMAND_RUNTIME_CATEGORICAL_CONTEXT.value,
        "normalization": "boolean only",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": True,
        "notes": "",
    },
    "ai_used": {
        "type": "boolean",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": None,
        "max_length": None,
        "privacy": FieldPrivacyClass.BOOLEAN.value,
        "source": FieldSource.COMMAND_RUNTIME_CATEGORICAL_CONTEXT.value,
        "normalization": "boolean only; no model IDs or token counts",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": False,
        "notes": "",
    },
    "failure_category": {
        "type": "enum",
        "requiredness": FieldRequiredness.OPTIONAL.value,
        "omitted_when_unavailable": True,
        "enum_ref": "failure_category",
        "max_length": None,
        "privacy": FieldPrivacyClass.LOW_CARDINALITY_CATEGORY.value,
        "source": FieldSource.PRIMARY_OPERATION_RESULT.value,
        "normalization": "exact enum value",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "unavailable",
        "notes": (
            "Shared optional field. Current validators do not require it only for "
            "operation_failed or forbid it on success."
        ),
    },
    "schema_version": {
        "type": "string",
        "requiredness": FieldRequiredness.REQUIRED.value,
        "omitted_when_unavailable": False,
        "enum_ref": None,
        "max_length": None,
        "privacy": FieldPrivacyClass.PUBLIC_CONSTANT.value,
        "source": FieldSource.RUNTIME_CONSTANT.value,
        "normalization": "injected by projection as runtime event schema version",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "1.0",
        "notes": "Always added by privacy projection.",
    },
    "runtime_policy_version": {
        "type": "string",
        "requiredness": FieldRequiredness.REQUIRED.value,
        "omitted_when_unavailable": False,
        "enum_ref": None,
        "max_length": None,
        "privacy": FieldPrivacyClass.PUBLIC_CONSTANT.value,
        "source": FieldSource.RUNTIME_CONSTANT.value,
        "normalization": "injected by projection from runtime policy",
        "bucketed": False,
        "set_ordering_normalized": False,
        "event_specific": False,
        "example": "1.0",
        "notes": "Always added by privacy projection.",
    },
}

NEVER_COLLECTED: tuple[tuple[str, str], ...] = (
    ("repository_names", "Repository names are never collected."),
    ("repository_urls", "Repository URLs are never collected."),
    ("project_names", "Project names are never collected."),
    ("organization_names", "Organization names are never collected."),
    ("customer_identifiers", "Customer identifiers are never collected."),
    ("account_identifiers", "Account identifiers are never collected."),
    ("usernames", "Usernames are never collected."),
    ("email_addresses", "Email addresses are never collected."),
    ("ip_addresses", "IP addresses are never collected."),
    ("hostnames", "Hostnames are never collected."),
    ("cwd", "Current working directory is never collected."),
    ("file_paths", "File paths are never collected."),
    ("output_paths", "Output directory paths are never collected."),
    ("report_paths", "Report paths are never collected."),
    ("command_line", "Full command lines are never collected."),
    ("argv", "Raw argv is never collected."),
    ("environment_variable_values", "Environment-variable values are never collected."),
    ("source_code", "Source code is never collected."),
    ("findings", "Assessment Findings are never collected."),
    ("evidence", "Evidence objects are never collected."),
    ("recommendations", "Recommendations are never collected."),
    ("package_names", "Package names are never collected by the privacy-first runtime."),
    ("exception_messages", "Exception messages are never collected."),
    ("stack_traces", "Stack traces are never collected."),
    ("credentials", "Credentials are never collected."),
    ("secrets", "Secrets are never collected."),
    ("api_keys", "API keys are never collected."),
    ("authorization_headers", "Authorization headers are never collected."),
    ("cookies", "Cookies are never collected."),
    ("prompts", "AI prompts are never collected."),
    ("ai_responses", "AI responses are never collected."),
    ("exact_model_ids", "Exact model IDs are never collected."),
    ("exact_token_counts", "Exact token counts are never collected."),
    ("exact_cost", "Exact cost values are never collected."),
    (
        "installation_identity",
        "Installation identity is not used by the privacy-first runtime.",
    ),
    ("endpoint_urls", "Endpoint URLs are never collected as event fields."),
    ("queue_contents", "Queue contents are never collected as event fields."),
)

CROSS_FIELD_RULES: tuple[tuple[str, str], ...] = (
    (
        "shared_event_shape",
        (
            "The current privacy-first runtime applies one shared typed event shape "
            "to all event types. Event-specific requiredness beyond event_type and "
            "client_name is not enforced by validators today."
        ),
    ),
    (
        "client_name_fixed",
        "client_name must equal codestrata_cli; other clients are rejected.",
    ),
    (
        "projection_injects_versions",
        (
            "Privacy projection always injects schema_version and "
            "runtime_policy_version onto the privacy-safe payload."
        ),
    ),
    (
        "empty_heads_omitted",
        "enabled_assessment_heads is omitted from intake when empty.",
    ),
    (
        "unknown_enum_rejected",
        "Unknown enum values are rejected (no silent forward compatibility).",
    ),
    (
        "consent_cannot_expand_fields",
        "Session consent cannot expand the approved field set or bypass projection.",
    ),
)

VALIDATION_BEHAVIOR: tuple[str, ...] = (
    "unknown_fields_rejected",
    "forbidden_field_names_rejected",
    "unsafe_value_shapes_rejected",
    "path_like_values_rejected_where_applicable",
    "secret_like_values_rejected_where_applicable",
    "enum_values_bounded",
    "extra_fields_forbidden",
    "invalid_combinations_rejected_where_modeled",
    "values_not_echoed_in_errors",
    "consent_does_not_bypass_validation",
)

CHANGE_POLICY: tuple[str, ...] = (
    "code_change_required",
    "catalog_artifact_update_required",
    "tests_required",
    "privacy_review_required",
    "schema_or_policy_version_review_required",
    "runtime_event_schema_remains_1_0_unless_serialized_event_changes",
)


__all__ = [
    "CHANGE_POLICY",
    "CROSS_FIELD_RULES",
    "ENUM_MEANINGS",
    "EVENT_LIFECYCLE_MEANING",
    "EVENT_PURPOSE",
    "EVENT_USAGE",
    "FIELD_META",
    "NEVER_COLLECTED",
    "VALIDATION_BEHAVIOR",
]
