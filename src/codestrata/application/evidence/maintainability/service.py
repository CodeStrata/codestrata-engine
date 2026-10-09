"""Orchestrate M22/M23 maintainability evidence. No repository execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.evidence.maintainability.derive import assemble_evidence
from codestrata.application.evidence.maintainability.envelope import (
    MaintainabilityEnvelope,
    MaintainabilityOperationalMetadata,
    seal_maintainability_envelope,
)
from codestrata.application.evidence.maintainability.models import (
    ComponentSpec,
    DependencyReleaseRecord,
    FindingReferenceInput,
    HistoryWindow,
    MaintainabilityEvidence,
    MaintainabilityThresholds,
    OwnershipReference,
)
from codestrata.application.evidence.quality.models import QualityEvidence


class MaintainabilityBudgets(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_components: int = Field(default=10_000, ge=1)
    max_findings: int = Field(default=10_000, ge=1)
    max_dependencies: int = Field(default=10_000, ge=1)


class MaintainabilityEvidenceService:
    """Join existing M16 facts with consumed M24 history and pinned dates."""

    def __init__(self, budgets: MaintainabilityBudgets | None = None) -> None:
        self._budgets = budgets or MaintainabilityBudgets()

    def collect(
        self,
        *,
        repository_id: str,
        quality: QualityEvidence,
        components: Sequence[ComponentSpec],
        history: HistoryWindow | None,
        catalog_digest: str = "",
        operational: MaintainabilityOperationalMetadata | None = None,
        centrality: Mapping[str, str] | None = None,
        reach: Mapping[str, str] | None = None,
        ownership: Mapping[str, OwnershipReference] | None = None,
        findings: Sequence[FindingReferenceInput] = (),
        dependencies: Sequence[DependencyReleaseRecord] = (),
        evaluation_time_unix: int | None = None,
        metadata_snapshot_digest: str = "",
        dependency_age_days: int = 730,
        hotspot_min_value: int = 0,
    ) -> tuple[MaintainabilityEvidence, MaintainabilityEnvelope]:
        notes: list[str] = []
        limited_components = tuple(components[: self._budgets.max_components])
        if len(components) > self._budgets.max_components:
            notes.append("component_budget_exceeded")
        limited_findings = tuple(findings[: self._budgets.max_findings])
        if len(findings) > self._budgets.max_findings:
            notes.append("finding_budget_exceeded")
        limited_deps = tuple(dependencies[: self._budgets.max_dependencies])
        if len(dependencies) > self._budgets.max_dependencies:
            notes.append("dependency_budget_exceeded")
        evidence = assemble_evidence(
            repository_id=repository_id,
            quality=quality,
            history=history,
            components=limited_components,
            centrality=centrality,
            reach=reach,
            ownership=ownership,
            findings=limited_findings,
            dependencies=limited_deps,
            evaluation_time_unix=evaluation_time_unix,
            metadata_snapshot_digest=metadata_snapshot_digest,
            thresholds=MaintainabilityThresholds(
                dependency_age_days=dependency_age_days,
                hotspot_min_value=hotspot_min_value,
            ),
            limitations=notes,
        )
        envelope = seal_maintainability_envelope(
            evidence=evidence,
            catalog_digest=catalog_digest,
            operational=operational,
        )
        return evidence, envelope


__all__ = ["MaintainabilityBudgets", "MaintainabilityEvidenceService"]
