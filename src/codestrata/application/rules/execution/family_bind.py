"""Bind family envelopes to E03.3 launch-catalog projections.

Family envelopes remain the canonical analysis body. Common JSON/HTML/SARIF
adapters copy this mapped launch body; they do not recompute coverage or invent
a health score.
"""

from __future__ import annotations

from codestrata.application.evidence.inventory.facts import CapabilityApplicability
from codestrata.application.rules.execution.projections import JSON_SCHEMA, project_launch_json
from codestrata.domain.contracts.enums import CoverageState, ExecutionPurpose, ResultStatus
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.rules.execution_models import (
    LaunchEvidence,
    LaunchExecutionBody,
    LaunchRuleRecord,
)

COMPILER_VERSION = "1.0.0"


def launch_bind_fields(body: LaunchExecutionBody) -> dict[str, object]:
    """Fields every family projection must copy from the common adapters."""

    return {
        "launch_projection_schema": JSON_SCHEMA,
        "launch_catalog_body_digest": body.content_digest(),
        "launch_plan_digest": body.plan_digest,
        "launch_facts_digest": body.facts_digest,
        "launch_catalog": project_launch_json(body),
    }


def inventory_launch_body(envelope: object) -> LaunchExecutionBody:
    from codestrata.application.evidence.inventory.envelope import InventoryEnvelope

    if not isinstance(envelope, InventoryEnvelope):
        raise TypeError("inventory_launch_body expects InventoryEnvelope")
    records = [
        LaunchRuleRecord(
            rule_id=record.capability_id,
            rule_revision=record.version,
            plan_digest=envelope.body_digest,
            status=_inventory_status(record.error, record.applicability),
            coverage_state=_inventory_coverage(record.applicability, record.error, record.unknown),
            enabled=True,
            suppressed=False,
            reason=record.coverage_reason or ("inventory_error" if record.error else None),
            evidence=(),
        )
        for record in envelope.body.coverage
    ]
    return LaunchExecutionBody(
        compiler_version=COMPILER_VERSION,
        purpose=ExecutionPurpose.PREVIEW,
        plan_digest=envelope.body_digest,
        facts_digest=digest_canonical(envelope.body.registered_facts.model_dump(mode="json")),
        records=tuple(sorted(records, key=lambda item: item.rule_id)),
        limitations=envelope.body.limitations,
    )


def security_launch_body(envelope: object) -> LaunchExecutionBody:
    from codestrata.application.evidence.security.envelope import SecurityEnvelope

    if not isinstance(envelope, SecurityEnvelope):
        raise TypeError("security_launch_body expects SecurityEnvelope")
    records: list[LaunchRuleRecord] = []
    findings_by_rule: dict[str, list[LaunchEvidence]] = {}
    for finding in envelope.body.findings:
        path = finding.path if finding.path and not _looks_absolute(finding.path) else None
        findings_by_rule.setdefault(finding.rule_id, []).append(
            LaunchEvidence(
                subject_id=finding.subject_id,
                source_kind="security.yaml",
                relative_path=path,
                span=finding.redacted_span or None,
                extractor_version=envelope.body.yaml_runtime,
                attributes={
                    "detector_id": finding.detector_id,
                    "safe_secret_type": finding.safe_secret_type,
                },
            )
        )
    for capability in envelope.body.capabilities:
        records.append(
            LaunchRuleRecord(
                rule_id=capability.capability_id,
                rule_revision=capability.version,
                plan_digest=envelope.body_digest,
                status=None,
                coverage_state=CoverageState.COMPLETE,
                enabled=True,
                suppressed=False,
                reason="descriptive_capability",
                evidence=(),
            )
        )
    for rule_id, evidence in findings_by_rule.items():
        records.append(
            LaunchRuleRecord(
                rule_id=rule_id,
                rule_revision="1",
                plan_digest=envelope.body_digest,
                status=ResultStatus.FAIL,
                coverage_state=CoverageState.COMPLETE,
                enabled=True,
                suppressed=False,
                reason="yaml_hygiene_finding",
                evidence=tuple(evidence),
            )
        )
    return LaunchExecutionBody(
        compiler_version=COMPILER_VERSION,
        purpose=ExecutionPurpose.PREVIEW,
        plan_digest=envelope.body_digest,
        facts_digest=envelope.body.catalog_digest,
        records=tuple(sorted(records, key=lambda item: item.rule_id)),
        limitations=envelope.body.limitations,
    )


def supply_chain_launch_body(envelope: object) -> LaunchExecutionBody:
    from codestrata.application.evidence.supply_chain.envelope import SupplyChainEnvelope

    if not isinstance(envelope, SupplyChainEnvelope):
        raise TypeError("supply_chain_launch_body expects SupplyChainEnvelope")
    records: list[LaunchRuleRecord] = []
    for record in envelope.body.coverage:
        records.append(
            LaunchRuleRecord(
                rule_id=record.capability_id,
                rule_revision="1",
                plan_digest=envelope.body_digest,
                status=_supply_status(record.error, record.matching_status),
                coverage_state=_count_coverage(
                    record.error, record.unknown, record.matching_status
                ),
                enabled=True,
                suppressed=False,
                reason=record.coverage_reason,
                evidence=(),
            )
        )
    if envelope.body.matches:
        records.append(
            LaunchRuleRecord(
                rule_id="security.known_vulnerability",
                rule_revision="1",
                plan_digest=envelope.body_digest,
                status=ResultStatus.FAIL,
                coverage_state=_matching_coverage(envelope.body.matching.status.value),
                enabled=True,
                suppressed=False,
                reason="pinned_feed_match",
                evidence=tuple(
                    LaunchEvidence(
                        subject_id=item.finding_id,
                        source_kind="supply_chain.yaml",
                        relative_path=_relative_or_none(item.lock_path),
                        extractor_version=envelope.body.yaml_runtime,
                        attributes={
                            "advisory_id": item.advisory_id,
                            "package_name": item.package_name,
                            "resolved_version": item.resolved_version,
                        },
                    )
                    for item in envelope.body.matches
                ),
            )
        )
    disallowed = [
        item for item in envelope.body.licenses if item.decision.value == "disallowed"
    ]
    if disallowed:
        records.append(
            LaunchRuleRecord(
                rule_id="license.disallowed",
                rule_revision="1",
                plan_digest=envelope.body_digest,
                status=ResultStatus.FAIL,
                coverage_state=CoverageState.COMPLETE,
                enabled=True,
                suppressed=False,
                reason="configured_deny",
                evidence=tuple(
                    LaunchEvidence(
                        subject_id=item.package_name,
                        source_kind="license.yaml",
                        relative_path=_relative_or_none(item.lock_path),
                        extractor_version=envelope.body.yaml_runtime,
                        attributes={
                            "expression": item.normalized_expression or item.raw_expression
                        },
                    )
                    for item in disallowed
                ),
            )
        )
    return LaunchExecutionBody(
        compiler_version=COMPILER_VERSION,
        purpose=ExecutionPurpose.PREVIEW,
        plan_digest=envelope.body_digest,
        facts_digest=envelope.body.catalog_digest,
        records=tuple(sorted(records, key=lambda item: item.rule_id)),
        limitations=envelope.body.limitations,
    )


def quality_launch_body(envelope: object) -> LaunchExecutionBody:
    from codestrata.application.evidence.quality.envelope import QualityEnvelope

    if not isinstance(envelope, QualityEnvelope):
        raise TypeError("quality_launch_body expects QualityEnvelope")
    body = envelope.body
    records = [
        LaunchRuleRecord(
            rule_id=record.capability_id,
            rule_revision="1",
            plan_digest=envelope.body_digest,
            status=_quality_status(record.error, record.full_scope_status),
            coverage_state=_quality_coverage(
                record.error, record.unknown, record.full_scope_status
            ),
            enabled=True,
            suppressed=False,
            reason=record.coverage_reason,
            evidence=(),
        )
        for record in body.coverage
    ]
    complex_evidence = [
        LaunchEvidence(
            subject_id=item.qualified_name,
            source_kind="quality.yaml",
            relative_path=_relative_or_none(item.path),
            extractor_version=body.yaml_runtime,
            attributes={
                "cyclomatic": str(item.cyclomatic),
                "formula": item.cyclomatic_version,
            },
        )
        for item in body.functions
        if item.cyclomatic is not None and item.cyclomatic > body.thresholds.complexity
    ]
    if complex_evidence:
        records.append(
            LaunchRuleRecord(
                rule_id="quality.complexity",
                rule_revision="1",
                plan_digest=envelope.body_digest,
                status=ResultStatus.FAIL,
                coverage_state=CoverageState.COMPLETE,
                enabled=True,
                suppressed=False,
                reason="complexity_above_threshold",
                evidence=tuple(complex_evidence),
            )
        )
    return LaunchExecutionBody(
        compiler_version=COMPILER_VERSION,
        purpose=ExecutionPurpose.PREVIEW,
        plan_digest=envelope.body_digest,
        facts_digest=body.catalog_digest,
        records=tuple(sorted(records, key=lambda item: item.rule_id)),
        limitations=body.limitations,
    )


def _supply_status(error: int, matching_status: str | None) -> ResultStatus | None:
    if error:
        return ResultStatus.ERROR
    if matching_status == "not_applicable":
        return ResultStatus.NOT_APPLICABLE
    return None


def _count_coverage(error: int, unknown: int, matching_status: str | None) -> CoverageState:
    if error:
        return CoverageState.ERROR
    if matching_status == "not_applicable":
        return CoverageState.NOT_APPLICABLE
    if matching_status == "unknown" or unknown:
        return CoverageState.UNKNOWN
    return CoverageState.COMPLETE


def _matching_coverage(status: str) -> CoverageState:
    if status == "unknown":
        return CoverageState.UNKNOWN
    if status == "not_applicable":
        return CoverageState.NOT_APPLICABLE
    return CoverageState.COMPLETE


def _quality_status(error: int, full_scope_status: str) -> ResultStatus | None:
    if error:
        return ResultStatus.ERROR
    if full_scope_status == "not_applicable":
        return ResultStatus.NOT_APPLICABLE
    return None


def _quality_coverage(error: int, unknown: int, full_scope_status: str) -> CoverageState:
    if error:
        return CoverageState.ERROR
    if full_scope_status == "not_applicable":
        return CoverageState.NOT_APPLICABLE
    if full_scope_status in {"unknown", "partial"} or unknown:
        return CoverageState.UNKNOWN
    return CoverageState.COMPLETE


def _relative_or_none(value: str) -> str | None:
    if not value or _looks_absolute(value):
        return None
    return value


def _inventory_status(error: int, applicability: CapabilityApplicability) -> ResultStatus | None:
    if error:
        return ResultStatus.ERROR
    if applicability is CapabilityApplicability.NOT_APPLICABLE:
        return ResultStatus.NOT_APPLICABLE
    return None


def _inventory_coverage(
    applicability: CapabilityApplicability,
    error: int,
    unknown: int,
) -> CoverageState:
    if error:
        return CoverageState.ERROR
    if applicability is CapabilityApplicability.NOT_APPLICABLE:
        return CoverageState.NOT_APPLICABLE
    if applicability is CapabilityApplicability.UNKNOWN or unknown:
        return CoverageState.UNKNOWN
    return CoverageState.COMPLETE


def _looks_absolute(value: str) -> bool:
    if value.startswith("/") and not value.startswith("./"):
        return True
    lowered = value.lower()
    return any(marker in lowered for marker in (":\\", ":/", "\\\\"))
