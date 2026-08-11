"""Analytics projection onto the anonymous analytics contract (Slice 10.1)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import (
    APPROVED_ANALYTICS_CATEGORIES,
    APPROVED_ANALYTICS_FIELD_NAMES,
    FORBIDDEN_ANALYTICS_FIELD_NAMES,
    AnalyticsEvent,
    AnalyticsLifecycle,
    _APPROVED_AI_CAPABILITIES,
    _APPROVED_AI_MODEL_FAMILIES,
    _APPROVED_AI_PROVIDER_FAMILIES,
    _APPROVED_AI_PROVIDER_OWNERSHIPS,
    _APPROVED_ARCHITECTURES,
    _APPROVED_ASSESSMENT_HEADS,
    _APPROVED_CLIENTS,
    _APPROVED_DURATION_BUCKETS,
    _APPROVED_FAILURE_CATEGORIES,
    _APPROVED_OPERATION_CATEGORIES,
    _APPROVED_OS_FAMILIES,
    _APPROVED_RESULTS,
)
from codestrata.telemetry.analytics.policy import (
    COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
    CommunityAnonymousAnalyticsPolicy,
    default_analytics_policy,
)

_BOOL_FIELDS = frozenset(
    {"offline_mode", "ai_used", "ai_requested", "privacy_projection_applied"}
)
_ENUM_FIELDS: dict[str, frozenset[str]] = {
    "category": APPROVED_ANALYTICS_CATEGORIES,
    "lifecycle": frozenset(item.value for item in AnalyticsLifecycle),
    "client_name": _APPROVED_CLIENTS,
    "result": _APPROVED_RESULTS,
    "operation_category": _APPROVED_OPERATION_CATEGORIES,
    "duration_bucket": _APPROVED_DURATION_BUCKETS,
    "os_family": _APPROVED_OS_FAMILIES,
    "architecture": _APPROVED_ARCHITECTURES,
    "failure_category": _APPROVED_FAILURE_CATEGORIES,
    "capability": _APPROVED_AI_CAPABILITIES,
    "provider_family": _APPROVED_AI_PROVIDER_FAMILIES,
    "model_family": _APPROVED_AI_MODEL_FAMILIES,
    "provider_ownership": _APPROVED_AI_PROVIDER_OWNERSHIPS,
}
_VERSIONISH_FIELDS = frozenset({"cli_version", "runtime_version", "release_adoption"})
_MAX_ASSESSMENT_HEADS = 9
_MAX_LANGUAGE_GROUPS = 6
_MAX_LANGUAGE_FILE_COUNT = 10_000
_MAX_RULE_COUNT = 10_000
_APPROVED_LANGUAGE_GROUPS = frozenset(
    {
        "python",
        "java",
        "javascript_typescript",
        "php",
        "csharp_dotnet",
        "unclassified",
    }
)
_RULE_SUMMARY_KEYS = frozenset({"attempted", "completed", "skipped", "failed"})


def _normalize_heads(value: Any, *, max_string_length: int) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if len(value) > _MAX_ASSESSMENT_HEADS:
        raise AnalyticsError(AnalyticsErrorCode.TOO_MANY_HEADS)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_HEAD)
        if item not in _APPROVED_ASSESSMENT_HEADS:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_HEAD)
        if _looks_unsafe(item, max_string_length=max_string_length):
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
        if item not in seen:
            seen.add(item)
            normalized.append(item)
    return sorted(normalized)


def _normalize_count(value: Any, *, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_RULE_COUNT)
    if value > maximum:
        raise AnalyticsError(AnalyticsErrorCode.INVALID_RULE_COUNT)
    return value


def _normalize_language_mix(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if len(value) > _MAX_LANGUAGE_GROUPS:
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
        if set(item.keys()) != {"count", "language_group"}:
            raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)
        group = item["language_group"]
        count = item["count"]
        if not isinstance(group, str) or group not in _APPROVED_LANGUAGE_GROUPS:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_LANGUAGE_GROUP)
        if group in seen:
            raise AnalyticsError(AnalyticsErrorCode.DUPLICATE_LANGUAGE_GROUP)
        seen.add(group)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_LANGUAGE_COUNT)
        if count > _MAX_LANGUAGE_FILE_COUNT:
            raise AnalyticsError(AnalyticsErrorCode.LANGUAGE_COUNT_EXCEEDED)
        if count == 0:
            continue
        rows.append({"count": count, "language_group": group})
    return sorted(rows, key=lambda row: row["language_group"])


def _normalize_rule_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if set(value.keys()) != _RULE_SUMMARY_KEYS:
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)
    attempted = _normalize_count(value["attempted"], maximum=_MAX_RULE_COUNT)
    completed = _normalize_count(value["completed"], maximum=_MAX_RULE_COUNT)
    skipped = _normalize_count(value["skipped"], maximum=_MAX_RULE_COUNT)
    failed = _normalize_count(value["failed"], maximum=_MAX_RULE_COUNT)
    if completed > attempted or failed > attempted or skipped > attempted:
        raise AnalyticsError(AnalyticsErrorCode.INCONSISTENT_RULE_COUNTS)
    return {
        "attempted": attempted,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
    }


def _normalize_rule_by_head(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
    if len(value) > _MAX_ASSESSMENT_HEADS:
        raise AnalyticsError(AnalyticsErrorCode.TOO_MANY_HEADS)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
        expected = {"assessment_head", "attempted", "completed", "failed", "skipped"}
        if set(item.keys()) != expected:
            raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)
        head = item["assessment_head"]
        if not isinstance(head, str) or head not in _APPROVED_ASSESSMENT_HEADS:
            raise AnalyticsError(AnalyticsErrorCode.INVALID_HEAD)
        if head in seen:
            raise AnalyticsError(AnalyticsErrorCode.DUPLICATE_HEAD)
        seen.add(head)
        summary = _normalize_rule_summary(
            {
                "attempted": item["attempted"],
                "completed": item["completed"],
                "skipped": item["skipped"],
                "failed": item["failed"],
            }
        )
        rows.append({"assessment_head": head, **summary})
    return sorted(rows, key=lambda row: row["assessment_head"])


@dataclass(frozen=True, slots=True)
class AnalyticsProjection:
    """Allowlisted, deterministic analytics payload (not persisted/transmitted)."""

    fields: dict[str, Any]

    def to_stable_dict(self) -> dict[str, Any]:
        return {key: self.fields[key] for key in sorted(self.fields)}

    def to_stable_json(self) -> str:
        return json.dumps(
            self.to_stable_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )


def _assert_field_allowed(name: str) -> None:
    if name in FORBIDDEN_ANALYTICS_FIELD_NAMES:
        raise AnalyticsError(AnalyticsErrorCode.UNSAFE_FIELD)
    if name not in APPROVED_ANALYTICS_FIELD_NAMES:
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)


def _looks_unsafe(value: Any, *, max_string_length: int) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) > max_string_length:
        return True
    if "\n" in value or "\r" in value:
        return True
    lowered = value.lower()
    needles = (
        "/users/",
        "/home/",
        "://",
        "file:",
        "password=",
        "secret=",
        "-----begin",
    )
    return any(needle in lowered for needle in needles)


def _normalize(key: str, value: Any, policy: CommunityAnonymousAnalyticsPolicy) -> Any:
    if key in _BOOL_FIELDS:
        if not isinstance(value, bool):
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
        return value
    if key == "enabled_assessment_heads":
        return _normalize_heads(value, max_string_length=policy.max_string_length)
    if key == "language_mix":
        return _normalize_language_mix(value)
    if key == "rule_execution_summary":
        return _normalize_rule_summary(value)
    if key == "rule_execution_by_head":
        return _normalize_rule_by_head(value)
    if key in _ENUM_FIELDS:
        if not isinstance(value, str) or value not in _ENUM_FIELDS[key]:
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
        return value
    if key in {"event_type", "schema_version", "policy_version"} | _VERSIONISH_FIELDS:
        if not isinstance(value, str) or not value or _looks_unsafe(
            value, max_string_length=policy.max_string_length
        ):
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
        if len(value) > policy.max_string_length:
            raise AnalyticsError(AnalyticsErrorCode.UNSAFE_VALUE)
        return value
    raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_FIELD)


def project_analytics_event(
    event: AnalyticsEvent,
    *,
    policy: CommunityAnonymousAnalyticsPolicy | None = None,
) -> AnalyticsProjection:
    """Project a typed analytics event into an allowlisted contract payload."""

    active = policy or default_analytics_policy()
    if not event.privacy_projection_applied:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    return project_analytics_from_mapping(event.to_intake_dict(), policy=active)


def project_analytics_from_mapping(
    payload: dict[str, Any],
    *,
    policy: CommunityAnonymousAnalyticsPolicy | None = None,
) -> AnalyticsProjection:
    """Project an untrusted mapping — reject unknown/forbidden fields strictly."""

    active = policy or default_analytics_policy()
    projected: dict[str, Any] = {
        "policy_version": active.policy_version,
        "schema_version": COMMUNITY_ANONYMOUS_ANALYTICS_SCHEMA_VERSION,
    }
    for key, value in payload.items():
        _assert_field_allowed(key)
        if key in {"schema_version", "policy_version"}:
            continue
        projected[key] = _normalize(key, value, active)

    if "event_type" not in projected:
        raise AnalyticsError(AnalyticsErrorCode.VALIDATION_FAILED)
    if "category" not in projected:
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_CATEGORY)
    if projected.get("category") not in APPROVED_ANALYTICS_CATEGORIES:
        raise AnalyticsError(AnalyticsErrorCode.UNKNOWN_CATEGORY)
    if projected.get("privacy_projection_applied") is not True:
        raise AnalyticsError(AnalyticsErrorCode.PRIVACY_REQUIRED)
    if "client_name" not in projected:
        projected["client_name"] = "codestrata_cli"
    if "lifecycle" not in projected:
        projected["lifecycle"] = AnalyticsLifecycle.PROJECTED.value

    if len(projected) > active.max_property_count:
        raise AnalyticsError(AnalyticsErrorCode.EVENT_TOO_LARGE)
    encoded = json.dumps(projected, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if len(encoded.encode("utf-8")) > active.max_event_size_bytes:
        raise AnalyticsError(AnalyticsErrorCode.EVENT_TOO_LARGE)

    return AnalyticsProjection(fields={key: projected[key] for key in sorted(projected)})


__all__ = [
    "AnalyticsProjection",
    "project_analytics_event",
    "project_analytics_from_mapping",
]
