"""Anonymous analytics event model and schema (Epic 10 Slice 10.1).

Contract categories only — no collection, persistence, or transmission.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
)


class AnalyticsCategory(StrEnum):
    """Bounded analytics category vocabulary."""

    RUNTIME = "runtime"
    ASSESSMENT = "assessment"
    REPOSITORY_AGGREGATES = "repository_aggregates"
    AI_USAGE = "ai_usage"
    VSCODE_USAGE = "vscode_usage"


class AnalyticsLifecycle(StrEnum):
    DEFINED = "defined"
    PROJECTED = "projected"
    VALIDATED = "validated"


APPROVED_ANALYTICS_CATEGORIES: frozenset[str] = frozenset(
    item.value for item in AnalyticsCategory
)

# Allowlisted analytics contract fields only.
APPROVED_ANALYTICS_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "event_type",
        "category",
        "client_name",
        "lifecycle",
        "schema_version",
        "policy_version",
        "privacy_projection_applied",
        "offline_mode",
        "ai_used",
        "operation_category",
        "result",
        "duration_bucket",
        "os_family",
        # Slice 10.3 runtime analytics fields (still no installation_id here).
        "cli_version",
        "architecture",
        "runtime_version",
        "release_adoption",
        # Slice 10.4 assessment analytics fields (still no installation_id here).
        "enabled_assessment_heads",
        "failure_category",
        "ai_requested",
        # Slice 10.5 repository aggregate fields (still no installation_id here).
        "language_mix",
        "rule_execution_summary",
        "rule_execution_by_head",
        # Slice 10.6 AI analytics fields (still no installation_id here).
        "capability",
        "provider_family",
        "model_family",
        "provider_ownership",
    }
)

FORBIDDEN_ANALYTICS_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "installation_id",
        "machine_id",
        "repository",
        "repository_name",
        "repository_url",
        "workspace",
        "workspace_uri",
        "document",
        "path",
        "filepath",
        "cwd",
        "source",
        "source_code",
        "finding",
        "findings",
        "evidence",
        "recommendation",
        "recommendations",
        "prompt",
        "response",
        "credential",
        "credentials",
        "secret",
        "token",
        "api_key",
        "authorization",
        "model_id",
        "provider",
        "exact_token_count",
        "token_count",
        "cost",
        "argv",
        "command_line",
        "exception",
        "stack_trace",
        "endpoint",
        "username",
        "email",
    }
)

_APPROVED_CLIENTS: frozenset[str] = frozenset({"codestrata_cli", "vscode_extension"})
_APPROVED_RESULTS: frozenset[str] = frozenset(
    {
        "success",
        "failure",
        "cancelled",
        "unknown",
        "defined",
        # Slice 10.6 AI analytics outcomes (additive).
        "unavailable",
        "skipped",
    }
)
_APPROVED_OPERATION_CATEGORIES: frozenset[str] = frozenset(
    {"assess", "report", "runtime", "extension", "other"}
)
_APPROVED_DURATION_BUCKETS: frozenset[str] = frozenset(
    {"lt_1s", "s_1_10", "s_10_60", "m_1_5", "gt_5m", "unknown"}
)
_APPROVED_OS_FAMILIES: frozenset[str] = frozenset(
    {"linux", "macos", "windows", "posix", "other"}
)
_APPROVED_ARCHITECTURES: frozenset[str] = frozenset({"x86_64", "arm64", "other"})
_APPROVED_FAILURE_CATEGORIES: frozenset[str] = frozenset(
    {
        "invalid_configuration",
        "invalid_repository",
        "assessment_failed",
        "report_generation_failed",
        "interrupted",
        "internal_failure",
        "unknown",
        # Slice 10.6 AI analytics failure categories (additive).
        "authentication_failed",
        "timeout",
        "rate_limited",
        "provider_unavailable",
        "request_rejected",
        "response_invalid",
        "unavailable",
    }
)

_APPROVED_AI_CAPABILITIES: frozenset[str] = frozenset({"modernization_advisor"})
_APPROVED_AI_PROVIDER_FAMILIES: frozenset[str] = frozenset(
    {"aws_bedrock", "openai", "openrouter", "unavailable"}
)
_APPROVED_AI_MODEL_FAMILIES: frozenset[str] = frozenset(
    {"amazon_nova_family", "gpt_family", "unavailable"}
)
_APPROVED_AI_PROVIDER_OWNERSHIPS: frozenset[str] = frozenset(
    {"customer_managed", "codestrata_managed", "unavailable"}
)
_APPROVED_ASSESSMENT_HEADS: frozenset[str] = frozenset(
    {
        "engineering_intelligence",
        "technology_inventory",
        "architecture_intelligence",
        "technical_debt_intelligence",
        "dependency_intelligence",
        "security_intelligence",
        "cloud_readiness",
        "ai_readiness",
        "modernization_assessment",
    }
)


@dataclass(frozen=True, slots=True)
class AnalyticsEvent:
    """Typed anonymous analytics event (contract model; not emitted yet)."""

    event_type: str
    category: AnalyticsCategory
    client_name: str = "codestrata_cli"
    lifecycle: AnalyticsLifecycle = AnalyticsLifecycle.DEFINED
    schema_version: str = COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION
    policy_version: str = "1.0"
    privacy_projection_applied: bool = True
    offline_mode: bool | None = None
    ai_used: bool | None = None
    ai_requested: bool | None = None
    operation_category: str | None = None
    result: str | None = None
    duration_bucket: str | None = None
    os_family: str | None = None
    cli_version: str | None = None
    architecture: str | None = None
    runtime_version: str | None = None
    release_adoption: str | None = None
    enabled_assessment_heads: tuple[str, ...] | None = None
    failure_category: str | None = None
    language_mix: tuple[dict[str, Any], ...] | None = None
    rule_execution_summary: dict[str, Any] | None = None
    rule_execution_by_head: tuple[dict[str, Any], ...] | None = None
    capability: str | None = None
    provider_family: str | None = None
    model_family: str | None = None
    provider_ownership: str | None = None

    def to_intake_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "category": self.category.value,
            "client_name": self.client_name,
            "event_type": self.event_type,
            "lifecycle": self.lifecycle.value,
            "policy_version": self.policy_version,
            "privacy_projection_applied": self.privacy_projection_applied,
            "schema_version": self.schema_version,
        }
        optional = {
            "ai_requested": self.ai_requested,
            "ai_used": self.ai_used,
            "architecture": self.architecture,
            "capability": self.capability,
            "cli_version": self.cli_version,
            "duration_bucket": self.duration_bucket,
            "enabled_assessment_heads": (
                list(self.enabled_assessment_heads)
                if self.enabled_assessment_heads is not None
                else None
            ),
            "failure_category": self.failure_category,
            "language_mix": (
                [dict(item) for item in self.language_mix]
                if self.language_mix is not None
                else None
            ),
            "model_family": self.model_family,
            "offline_mode": self.offline_mode,
            "operation_category": self.operation_category,
            "os_family": self.os_family,
            "provider_family": self.provider_family,
            "provider_ownership": self.provider_ownership,
            "release_adoption": self.release_adoption,
            "result": self.result,
            "rule_execution_by_head": (
                [dict(item) for item in self.rule_execution_by_head]
                if self.rule_execution_by_head is not None
                else None
            ),
            "rule_execution_summary": (
                dict(self.rule_execution_summary)
                if self.rule_execution_summary is not None
                else None
            ),
            "runtime_version": self.runtime_version,
        }
        for key, value in optional.items():
            if value is not None:
                payload[key] = value
        return {key: payload[key] for key in sorted(payload)}

    def to_stable_dict(self) -> dict[str, Any]:
        return self.to_intake_dict()


def illustrative_analytics_event(
    category: AnalyticsCategory = AnalyticsCategory.RUNTIME,
) -> AnalyticsEvent:
    """Return a contract-illustrative event (not collected or transmitted)."""

    return AnalyticsEvent(
        event_type=f"analytics_{category.value}_defined",
        category=category,
        client_name="codestrata_cli",
        lifecycle=AnalyticsLifecycle.DEFINED,
        privacy_projection_applied=True,
        offline_mode=True,
        ai_used=False,
        operation_category="runtime",
        result="defined",
        duration_bucket="unknown",
        os_family="other",
    )


__all__ = [
    "APPROVED_ANALYTICS_CATEGORIES",
    "APPROVED_ANALYTICS_FIELD_NAMES",
    "FORBIDDEN_ANALYTICS_FIELD_NAMES",
    "AnalyticsCategory",
    "AnalyticsEvent",
    "AnalyticsLifecycle",
    "illustrative_analytics_event",
    "_APPROVED_AI_CAPABILITIES",
    "_APPROVED_AI_MODEL_FAMILIES",
    "_APPROVED_AI_PROVIDER_FAMILIES",
    "_APPROVED_AI_PROVIDER_OWNERSHIPS",
    "_APPROVED_ARCHITECTURES",
    "_APPROVED_ASSESSMENT_HEADS",
    "_APPROVED_CLIENTS",
    "_APPROVED_DURATION_BUCKETS",
    "_APPROVED_FAILURE_CATEGORIES",
    "_APPROVED_OPERATION_CATEGORIES",
    "_APPROVED_OS_FAMILIES",
    "_APPROVED_RESULTS",
]
