"""Architecture conclusion application service."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from typing import Any

from codestrata.application.architecture.conclusions.clustering import cluster_findings
from codestrata.application.architecture.conclusions.consolidator import consolidate_recommendations
from codestrata.application.architecture.conclusions.registry import (
    ArchitectureConclusionPolicyRegistry,
    ConclusionPolicyContext,
)
from codestrata.application.architecture.conclusions.relationships import (
    build_finding_relationships,
)
from codestrata.application.architecture.conclusions.result import (
    ArchitectureConclusionResult,
    ArchitectureConclusionTelemetry,
    ConclusionPolicyExecutionRecord,
)
from codestrata.domain.architecture.conclusions.enums import (
    ConclusionMateriality,
    ConclusionPolicyStatus,
)
from codestrata.domain.architecture.conclusions.models import (
    ArchitectureConclusion,
    ArchitectureSummary,
)
from codestrata.domain.findings import Finding


class ArchitectureConclusionService:
    def __init__(self, registry: ArchitectureConclusionPolicyRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> ArchitectureConclusionPolicyRegistry:
        return self._registry

    def list_policies(self, *, category: str | None = None) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "policy_id": meta.policy_id,
                "policy_version": meta.policy_version,
                "category": meta.category,
                "title": meta.title,
                "description": meta.description,
                "source_rule_ids": list(meta.source_rule_ids),
                "enterprise_only": meta.enterprise_only,
                "enabled_by_default": meta.enabled_by_default,
                "documentation_reference": meta.documentation_reference,
            }
            for meta in self._registry.list_policies(category=category)
        )

    def inspect_policy(self, policy_id: str) -> dict[str, Any]:
        meta = self._registry.get(policy_id).metadata
        return {
            "policy_id": meta.policy_id,
            "policy_version": meta.policy_version,
            "category": meta.category,
            "title": meta.title,
            "description": meta.description,
            "source_rule_ids": list(meta.source_rule_ids),
            "enterprise_only": meta.enterprise_only,
            "enabled_by_default": meta.enabled_by_default,
            "documentation_reference": meta.documentation_reference,
        }

    def build(
        self,
        *,
        repository_id: str,
        findings: Sequence[Finding],
        enabled_policy_ids: frozenset[str] | None = None,
        extraction_coverage: float | None = None,
        classification_coverage: float | None = None,
        enterprise_context_present: bool = False,
        graph_fingerprint: str = "",
        configuration_fingerprint: str = "",
    ) -> ArchitectureConclusionResult:
        started = time.perf_counter()
        architecture_findings = tuple(
            sorted(
                (
                    finding
                    for finding in findings
                    if finding.rule_id.startswith("architecture.")
                ),
                key=lambda item: (item.rule_id, item.id),
            )
        )
        relationships = build_finding_relationships(architecture_findings)
        clusters = cluster_findings(architecture_findings, relationships)

        conclusions: list[ArchitectureConclusion] = []
        records: list[ConclusionPolicyExecutionRecord] = []
        diagnostics: list[str] = []
        failures = 0

        enabled = enabled_policy_ids
        for policy in self._registry.policies():
            policy_id = policy.metadata.policy_id
            if enabled is not None and policy_id not in enabled:
                records.append(
                    ConclusionPolicyExecutionRecord(
                        policy_id=policy_id,
                        status=ConclusionPolicyStatus.SKIPPED,
                        message="disabled_by_configuration",
                    )
                )
                continue
            if policy.metadata.enterprise_only and not enterprise_context_present:
                records.append(
                    ConclusionPolicyExecutionRecord(
                        policy_id=policy_id,
                        status=ConclusionPolicyStatus.NOT_APPLICABLE,
                        message="enterprise_context_absent",
                    )
                )
                continue

            targets = clusters if clusters else (None,)
            # Insufficient-evidence policy runs once without a cluster.
            if policy_id.endswith("insufficient-evidence"):
                targets = (None,)

            produced_for_policy = 0
            statuses: list[ConclusionPolicyStatus] = []
            messages: list[str] = []
            last_message: str | None = None
            for cluster in targets:
                # Skip cluster-based policies when target is None except insufficient-evidence.
                if cluster is None and not policy_id.endswith("insufficient-evidence"):
                    if not policy_id.endswith("enterprise-nonconformance"):
                        continue
                context = ConclusionPolicyContext(
                    repository_id=repository_id,
                    findings=architecture_findings,
                    cluster=cluster,
                    extraction_coverage=extraction_coverage,
                    classification_coverage=classification_coverage,
                    enterprise_context_present=enterprise_context_present,
                    graph_fingerprint=graph_fingerprint,
                )
                try:
                    result = policy.evaluate(context)
                except Exception as error:  # noqa: BLE001 — isolate policy failures
                    failures += 1
                    statuses.append(ConclusionPolicyStatus.FAILED)
                    messages.append(f"{type(error).__name__}: policy_failed")
                    diagnostics.append(f"policy_failed:{policy_id}:{type(error).__name__}")
                    continue
                statuses.append(result.status)
                if result.message:
                    messages.append(result.message)
                if result.status is ConclusionPolicyStatus.FAILED:
                    failures += 1
                    diagnostics.append(f"policy_failed:{policy_id}:{result.message}")
                    continue
                for conclusion in result.conclusions:
                    conclusions.append(conclusion)
                    produced_for_policy += 1

            if produced_for_policy > 0:
                last_status = ConclusionPolicyStatus.SUCCEEDED
                last_message = f"produced_{produced_for_policy}"
            elif ConclusionPolicyStatus.FAILED in statuses:
                last_status = ConclusionPolicyStatus.FAILED
                last_message = next(
                    (
                        msg
                        for status, msg in zip(statuses, messages, strict=False)
                        if status is ConclusionPolicyStatus.FAILED
                    ),
                    messages[-1] if messages else None,
                )
            elif ConclusionPolicyStatus.SKIPPED in statuses:
                last_status = ConclusionPolicyStatus.SKIPPED
                last_message = next(
                    (
                        msg
                        for status, msg in zip(statuses, messages, strict=False)
                        if status is ConclusionPolicyStatus.SKIPPED
                    ),
                    messages[-1] if messages else None,
                )
            elif statuses:
                last_status = statuses[-1]
                last_message = messages[-1] if messages else None
            else:
                last_status = ConclusionPolicyStatus.NOT_APPLICABLE
                last_message = None

            records.append(
                ConclusionPolicyExecutionRecord(
                    policy_id=policy_id,
                    status=last_status,
                    message=last_message,
                    conclusion_count=produced_for_policy,
                )
            )

        # Deduplicate conclusions by ID (same policy+scope+findings).
        unique: dict[str, ArchitectureConclusion] = {}
        for conclusion in conclusions:
            unique[conclusion.conclusion_id] = conclusion
        ordered_conclusions = tuple(
            sorted(unique.values(), key=lambda item: (item.category, item.conclusion_id))
        )

        recommendation_groups = consolidate_recommendations(
            ordered_conclusions, architecture_findings
        )
        # Attach recommendation group IDs onto conclusions.
        groups_by_conclusion: dict[str, list[str]] = {}
        for group in recommendation_groups:
            # Match by source finding set.
            key = ",".join(group.source_finding_ids)
            groups_by_conclusion.setdefault(key, []).append(group.recommendation_group_id)

        attached: list[ArchitectureConclusion] = []
        for conclusion in ordered_conclusions:
            key = ",".join(conclusion.source_finding_ids)
            group_ids = tuple(sorted(groups_by_conclusion.get(key, ())))
            attached.append(
                conclusion.model_copy(update={"consolidated_recommendation_ids": group_ids})
            )
        ordered_conclusions = tuple(attached)

        material = sum(
            1
            for item in ordered_conclusions
            if item.materiality is ConclusionMateriality.MATERIAL
        )
        highest = None
        if ordered_conclusions:
            ranks = {
                "informational": 0,
                "low": 1,
                "medium": 2,
                "high": 3,
                "critical": 4,
            }
            highest = max(
                ordered_conclusions,
                key=lambda item: ranks.get(item.severity_summary.highest_severity, 0),
            ).severity_summary.highest_severity

        summary = ArchitectureSummary(
            conclusion_count=len(ordered_conclusions),
            finding_count=len(architecture_findings),
            material_conclusion_count=material,
            highest_severity=highest,
            business_impact="unknown",
            coverage_notes=tuple(
                note
                for note in (
                    f"extraction_coverage={extraction_coverage}"
                    if extraction_coverage is not None
                    else "",
                    f"classification_coverage={classification_coverage}"
                    if classification_coverage is not None
                    else "",
                )
                if note
            ),
            limitations=(
                "Conclusions interpret architecture findings; they are not new rule findings.",
                "Business impact remains unknown for repository-only assessments.",
            ),
            headline=(
                f"{len(ordered_conclusions)} architecture conclusion(s) from "
                f"{len(architecture_findings)} finding(s)"
            ),
        )

        duration_ms = int((time.perf_counter() - started) * 1000)
        telemetry = ArchitectureConclusionTelemetry(
            enabled=True,
            relationship_count=len(relationships),
            cluster_count=len(clusters),
            conclusion_count=len(ordered_conclusions),
            recommendation_group_count=len(recommendation_groups),
            policy_records=tuple(records),
            duration_ms=duration_ms,
            configuration_fingerprint=configuration_fingerprint
            or _fingerprint_config(enabled),
            graph_fingerprint=graph_fingerprint,
            enterprise_context_used=enterprise_context_present,
            failure_count=failures,
        )
        return ArchitectureConclusionResult(
            enabled=True,
            relationships=relationships,
            clusters=clusters,
            conclusions=ordered_conclusions,
            recommendation_groups=recommendation_groups,
            summary=summary,
            telemetry=telemetry,
            diagnostics=tuple(sorted(set(diagnostics))),
        )


def _fingerprint_config(enabled: frozenset[str] | None) -> str:
    payload = ",".join(sorted(enabled or ()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
