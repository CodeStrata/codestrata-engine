"""Group repeated static-analysis observations into customer-facing findings."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from uuid import UUID, uuid5

from codestrata.models.enums import FindingSource, Severity
from codestrata.models.evidence import Evidence
from codestrata.models.finding import Finding
from codestrata.static_analysis.models import (
    StaticAnalysisGroup,
    StaticAnalysisObservation,
)
from codestrata.static_analysis.providers.pmd_normalization import (
    ensure_critical_high_not_suppressed,
    normalize_pmd_rule,
)
from codestrata.static_analysis.visibility import CustomerVisibility

# Stable namespace for deterministic group/finding UUIDs.
_GROUP_NAMESPACE = UUID("6f2c1d5a-8b3e-4f91-9c47-2a1d8e5b4c90")
_MAX_REPRESENTATIVE_LOCATIONS = 5


def observations_from_pmd_findings(
    findings: Sequence[Finding],
) -> list[StaticAnalysisObservation]:
    """Convert parser findings into normalized raw observations."""

    observations: list[StaticAnalysisObservation] = []
    for finding in findings:
        evidence = finding.evidence[0] if finding.evidence else None
        external_rule_id = str(finding.metadata.get("external_rule_id") or "") or None
        ruleset = str(finding.metadata.get("ruleset") or "") or None
        provider_priority = finding.metadata.get("original_priority")
        priority = provider_priority if isinstance(provider_priority, int) else None

        normalization = ensure_critical_high_not_suppressed(
            normalize_pmd_rule(
                external_rule_id=external_rule_id,
                ruleset=ruleset,
                provider_priority=priority,
            )
        )
        observation_id = _observation_id(
            rule_id=finding.rule_id or "PMD.UNKNOWN",
            file_path=evidence.file_path if evidence else "",
            line_number=evidence.line_number if evidence else None,
            column_number=evidence.column_number if evidence else None,
            message=finding.description,
        )
        observations.append(
            StaticAnalysisObservation(
                observation_id=observation_id,
                provider_id=str(finding.metadata.get("provider_id") or "pmd"),
                provider_name=str(finding.metadata.get("provider_name") or "PMD"),
                provider_version=(
                    str(finding.metadata.get("provider_version"))
                    if finding.metadata.get("provider_version") is not None
                    else None
                ),
                rule_id=finding.rule_id or "PMD.UNKNOWN",
                external_rule_id=external_rule_id,
                provider_priority=priority,
                provider_category=ruleset,
                normalized_category=normalization.category,
                normalized_severity=normalization.severity,
                customer_visibility=normalization.visibility,
                modernization_relevance=normalization.modernization_relevance,
                file_path=evidence.file_path if evidence else ".",
                line_number=evidence.line_number if evidence else None,
                column_number=evidence.column_number if evidence else None,
                end_line_number=evidence.end_line_number if evidence else None,
                end_column_number=evidence.end_column_number if evidence else None,
                message=finding.description,
                title=finding.title,
                mapping_rationale=normalization.rationale,
                metadata={
                    key: value
                    for key, value in finding.metadata.items()
                    if key
                    not in {
                        "args",
                        "command",
                        "executable_path",
                    }
                },
            )
        )
    return observations


def group_observations(
    observations: Sequence[StaticAnalysisObservation],
) -> tuple[list[StaticAnalysisGroup], list[Finding]]:
    """Group observations by remediation pattern and emit customer findings.

    Returns groups for all observations and customer-facing findings for groups
    that are not ``suppressed_from_html``.
    """

    buckets: dict[str, list[StaticAnalysisObservation]] = {}
    for observation in observations:
        key = _group_key(observation)
        buckets.setdefault(key, []).append(observation)

    groups: list[StaticAnalysisGroup] = []
    customer_findings: list[Finding] = []

    for key in sorted(buckets):
        members = sorted(
            buckets[key],
            key=lambda item: (
                item.file_path,
                item.line_number or 0,
                item.column_number or 0,
                item.observation_id,
            ),
        )
        primary = members[0]
        group_id = _group_id(key)
        for member in members:
            member.group_id = group_id

        files = sorted({item.file_path for item in members})
        locations = [
            {
                "file_path": item.file_path,
                "line_number": item.line_number,
                "column_number": item.column_number,
                "message": item.message,
            }
            for item in members[:_MAX_REPRESENTATIVE_LOCATIONS]
        ]
        visibility = _group_visibility(members)
        group = StaticAnalysisGroup(
            group_id=group_id,
            provider_id=primary.provider_id,
            provider_name=primary.provider_name,
            rule_id=primary.rule_id,
            title=primary.title,
            description=_group_description(primary, len(members), len(files)),
            category=primary.normalized_category,
            severity=primary.normalized_severity,
            customer_visibility=visibility,
            modernization_relevance=primary.modernization_relevance,
            occurrence_count=len(members),
            affected_file_count=len(files),
            representative_locations=locations,
            observation_ids=[item.observation_id for item in members],
            mapping_rationale=primary.mapping_rationale,
        )
        groups.append(group)

        if visibility == CustomerVisibility.SUPPRESSED_FROM_HTML:
            continue

        finding = Finding(
            id=uuid5(_GROUP_NAMESPACE, group_id),
            rule_id=group.rule_id,
            title=group.title,
            description=group.description,
            category=group.category,
            severity=group.severity,
            source=FindingSource.EXTERNAL_STATIC_ANALYSIS,
            evidence=[
                Evidence(
                    file_path=str(location["file_path"]),
                    line_number=location["line_number"]
                    if isinstance(location["line_number"], int)
                    else None,
                    column_number=location["column_number"]
                    if isinstance(location["column_number"], int)
                    else None,
                    description=str(location["message"]),
                )
                for location in locations
            ],
            affected_technologies=["Java"],
            metadata={
                "provider_id": group.provider_id,
                "provider_name": group.provider_name,
                "external_rule_id": primary.external_rule_id,
                "ruleset": primary.provider_category,
                "original_priority": primary.provider_priority,
                "group_id": group.group_id,
                "occurrence_count": group.occurrence_count,
                "affected_file_count": group.affected_file_count,
                "customer_visibility": visibility.value,
                "modernization_relevance": group.modernization_relevance.value,
                "mapping_rationale": group.mapping_rationale,
                "grouped": True,
            },
        )
        customer_findings.append(finding)

    groups.sort(
        key=lambda item: (
            _severity_rank(item.severity),
            item.rule_id,
            item.group_id,
        )
    )
    return groups, customer_findings


def visibility_counts(
    observations: Sequence[StaticAnalysisObservation],
    groups: Sequence[StaticAnalysisGroup],
) -> dict[str, int]:
    """Return summary counts used by HTML/JSON parity checks."""

    return {
        "raw_observation_count": len(observations),
        "grouped_finding_count": len(groups),
        "primary_count": sum(
            1 for item in groups if item.customer_visibility == CustomerVisibility.PRIMARY
        ),
        "supporting_count": sum(
            1 for item in groups if item.customer_visibility == CustomerVisibility.SUPPORTING
        ),
        "informational_count": sum(
            1 for item in groups if item.customer_visibility == CustomerVisibility.INFORMATIONAL
        ),
        "suppressed_from_html_count": sum(
            1
            for item in groups
            if item.customer_visibility == CustomerVisibility.SUPPRESSED_FROM_HTML
        ),
    }


def _group_key(observation: StaticAnalysisObservation) -> str:
    return "|".join(
        [
            observation.provider_id,
            observation.rule_id,
            observation.normalized_category.value,
            observation.normalized_severity.value,
            observation.customer_visibility.value,
        ]
    )


def _group_id(key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    return f"pmd-group-{digest}"


def _observation_id(
    *,
    rule_id: str,
    file_path: str,
    line_number: int | None,
    column_number: int | None,
    message: str,
) -> str:
    payload = f"{rule_id}|{file_path}|{line_number}|{column_number}|{message.strip().lower()}"
    digest = hashlib.sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    return f"pmd-obs-{digest}"


def _group_description(
    primary: StaticAnalysisObservation,
    occurrence_count: int,
    file_count: int,
) -> str:
    if occurrence_count == 1:
        return primary.message
    return (
        f"{primary.message} Occurs {occurrence_count} times across "
        f"{file_count} file{'s' if file_count != 1 else ''}."
    )


def _group_visibility(
    members: Sequence[StaticAnalysisObservation],
) -> CustomerVisibility:
    # Never suppress if any member is critical/high after normalization.
    if any(item.normalized_severity in {Severity.CRITICAL, Severity.HIGH} for item in members):
        return CustomerVisibility.PRIMARY

    ranks = {
        CustomerVisibility.PRIMARY: 0,
        CustomerVisibility.SUPPORTING: 1,
        CustomerVisibility.INFORMATIONAL: 2,
        CustomerVisibility.SUPPRESSED_FROM_HTML: 3,
    }
    return min(
        (item.customer_visibility for item in members),
        key=lambda value: ranks[value],
    )


def _severity_rank(severity: Severity) -> int:
    order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
    return order.get(severity, 99)
