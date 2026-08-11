"""Models for SV.11 assessment consistency verification."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    repository_ids: list[str] = field(default_factory=list)
    classification: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DefectCandidate:
    classification: str
    repository_ids: list[str]
    entity_id: str | None
    expected: str
    actual: str
    reproducible: bool = True
    release_impact: str = "unknown"
    handling: str = "product_defect_for_sv13"
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def defect_id(self) -> str:
        repos = ",".join(sorted(self.repository_ids)[:3]) or "global"
        entity = self.entity_id or "none"
        return f"{self.classification}:{repos}:{entity}"


@dataclass
class OutlierRecord:
    repository_id: str
    metric: str
    observed_value: Any
    comparison_scope: str
    expected_contract: str
    contract_violation: bool
    explanation: str = ""
    defect_candidate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def outlier_id(self) -> str:
        return f"{self.repository_id}:{self.metric}"


@dataclass
class RepositoryBundle:
    """Privacy-safe in-memory view of one SV.10 repository + artifacts."""

    repository_id: str
    record: dict[str, Any]
    report: dict[str, Any]
    findings_doc: dict[str, Any]
    recommendations_doc: dict[str, Any]
    artifact_dir_name: str  # sha12 only — never absolute
    html_present: bool
    html_has_csp: bool | None = None

    @property
    def assessment(self) -> dict[str, Any]:
        assessment = self.report.get("assessment")
        return assessment if isinstance(assessment, dict) else {}

    @property
    def findings(self) -> list[dict[str, Any]]:
        items = self.assessment.get("findings")
        if isinstance(items, list):
            return [i for i in items if isinstance(i, dict)]
        items = self.findings_doc.get("findings")
        if isinstance(items, list):
            return [i for i in items if isinstance(i, dict)]
        return []

    @property
    def recommendations(self) -> list[dict[str, Any]]:
        items = self.assessment.get("deterministic_recommendations")
        if isinstance(items, list) and items:
            return [i for i in items if isinstance(i, dict)]
        items = self.recommendations_doc.get("recommendations")
        if isinstance(items, list):
            return [i for i in items if isinstance(i, dict)]
        return []


@dataclass
class ConsistencyReport:
    schema_name: str
    schema_version: str
    verification_id: str
    catalog_id: str | None
    repository_count: int
    included_repository_ids: list[str] = field(default_factory=list)
    qualified_revisions: dict[str, str] = field(default_factory=dict)
    language_distribution: dict[str, int] = field(default_factory=dict)
    ecosystem_distribution: dict[str, int] = field(default_factory=dict)
    tier_distribution: dict[str, int] = field(default_factory=dict)
    artifact_contract_checks: list[dict[str, Any]] = field(default_factory=list)
    schema_checks: list[dict[str, Any]] = field(default_factory=list)
    assessment_head_checks: list[dict[str, Any]] = field(default_factory=list)
    activation_checks: list[dict[str, Any]] = field(default_factory=list)
    coverage_checks: list[dict[str, Any]] = field(default_factory=list)
    confidence_checks: list[dict[str, Any]] = field(default_factory=list)
    finding_checks: list[dict[str, Any]] = field(default_factory=list)
    severity_checks: list[dict[str, Any]] = field(default_factory=list)
    recommendation_checks: list[dict[str, Any]] = field(default_factory=list)
    priority_checks: list[dict[str, Any]] = field(default_factory=list)
    traceability_checks: list[dict[str, Any]] = field(default_factory=list)
    limitation_checks: list[dict[str, Any]] = field(default_factory=list)
    terminology_checks: list[dict[str, Any]] = field(default_factory=list)
    consolidation_checks: list[dict[str, Any]] = field(default_factory=list)
    correlation_checks: list[dict[str, Any]] = field(default_factory=list)
    engineering_intelligence_input_ready: dict[str, bool] = field(default_factory=dict)
    outlier_records: list[dict[str, Any]] = field(default_factory=list)
    defect_candidates: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    determinism: dict[str, Any] = field(default_factory=dict)
    guards: list[str] = field(default_factory=list)
    verdict: str = "FAIL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
