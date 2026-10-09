"""M10/M11 finding counts from YAML-backed security matches."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.rules.results import RuleMatch
from codestrata.domain.security.ids import (
    RULE_AUTHENTICATION_DISABLED,
    RULE_CREDENTIAL_LITERAL,
    RULE_DEBUG_ENABLED,
    RULE_HOSTNAME_VERIFICATION_DISABLED,
    RULE_PERMISSIVE_CORS_ORIGIN,
    RULE_PLACEHOLDER_CREDENTIAL,
    RULE_PRIVATE_KEY_MATERIAL,
    RULE_TLS_VERIFICATION_DISABLED,
)

M10_RULES = frozenset(
    {
        RULE_PRIVATE_KEY_MATERIAL,
        RULE_CREDENTIAL_LITERAL,
        RULE_PLACEHOLDER_CREDENTIAL,
    }
)
M11_RULES = frozenset(
    {
        RULE_TLS_VERIFICATION_DISABLED,
        RULE_HOSTNAME_VERIFICATION_DISABLED,
        RULE_AUTHENTICATION_DISABLED,
        RULE_PERMISSIVE_CORS_ORIGIN,
        RULE_DEBUG_ENABLED,
    }
)


class SecurityFindingRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    subject_id: str
    path: str
    occurrence: str
    detector_id: str = ""
    safe_secret_type: str = ""
    redacted_span: str = ""
    line_start: int | None = Field(default=None, ge=1)
    security_context: str = "unknown"
    production_context_status: str = "unknown"
    default_severity: str
    effective_severity: str
    severity_basis: str = "yaml_catalog_default"


class SecurityMetricCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    m10_secret_findings: int = Field(ge=0)
    m10_private_key_findings: int = Field(ge=0)
    m10_credential_literal_findings: int = Field(ge=0)
    m10_placeholder_findings: int = Field(ge=0)
    m11_tls_disabled: int = Field(ge=0)
    m11_hostname_disabled: int = Field(ge=0)
    m11_auth_disabled: int = Field(ge=0)
    m11_permissive_cors: int = Field(ge=0)
    m11_debug_enabled: int = Field(ge=0)
    m11_debug_production: int = Field(ge=0)
    m11_debug_unknown_context: int = Field(ge=0)
    unknown_scope: int = Field(ge=0)


def _subject_id(match: RuleMatch) -> str:
    return "|".join(match.subject_keys)


def finding_from_match(match: RuleMatch) -> SecurityFindingRecord:
    evidence = match.evidence[0]
    attributes = dict(evidence.attributes)
    return SecurityFindingRecord(
        rule_id=str(match.rule_id),
        subject_id=_subject_id(match),
        path=attributes.get("path") or evidence.safe_location or "",
        occurrence=str(evidence.line_start or attributes.get("line_start") or "0"),
        detector_id=attributes.get("detector_id", ""),
        safe_secret_type=attributes.get("safe_secret_type", ""),
        redacted_span=attributes.get("redacted_span")
        or attributes.get("redacted_preview", "[REDACTED]"),
        line_start=evidence.line_start,
        security_context=attributes.get("security_context", "unknown"),
        production_context_status=attributes.get("production_context_status", "unknown"),
        default_severity=(match.base_severity or match.severity).value,
        effective_severity=match.severity.value,
        severity_basis=",".join(match.severity_basis) or "yaml_catalog_default",
    )


def unique_findings(matches: Sequence[RuleMatch]) -> tuple[SecurityFindingRecord, ...]:
    records = [finding_from_match(item) for item in matches]
    seen: set[tuple[str, str, str]] = set()
    unique: list[SecurityFindingRecord] = []
    for record in sorted(
        records, key=lambda item: (item.rule_id, item.path, item.occurrence, item.subject_id)
    ):
        key = (record.rule_id, record.subject_id, record.occurrence)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return tuple(unique)


def count_metrics(findings: Sequence[SecurityFindingRecord]) -> SecurityMetricCounts:
    def _count(rule_id: str) -> int:
        return sum(1 for item in findings if item.rule_id == rule_id)

    debug = [item for item in findings if item.rule_id == RULE_DEBUG_ENABLED]
    return SecurityMetricCounts(
        m10_secret_findings=sum(1 for item in findings if item.rule_id in M10_RULES),
        m10_private_key_findings=_count(RULE_PRIVATE_KEY_MATERIAL),
        m10_credential_literal_findings=_count(RULE_CREDENTIAL_LITERAL),
        m10_placeholder_findings=_count(RULE_PLACEHOLDER_CREDENTIAL),
        m11_tls_disabled=_count(RULE_TLS_VERIFICATION_DISABLED),
        m11_hostname_disabled=_count(RULE_HOSTNAME_VERIFICATION_DISABLED),
        m11_auth_disabled=_count(RULE_AUTHENTICATION_DISABLED),
        m11_permissive_cors=_count(RULE_PERMISSIVE_CORS_ORIGIN),
        m11_debug_enabled=len(debug),
        m11_debug_production=sum(
            1 for item in debug if item.production_context_status == "production"
        ),
        m11_debug_unknown_context=sum(
            1 for item in debug if item.production_context_status == "unknown"
        ),
        unknown_scope=sum(1 for item in findings if item.production_context_status == "unknown"),
    )
