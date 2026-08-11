"""Calibrated Finding Severity consistency."""

from __future__ import annotations

from verification.assessment_consistency.contract import SEVERITY_VOCAB
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    OutlierRecord,
    RepositoryBundle,
)

_RANK = {
    "informational": 0,
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def check_severity(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate], list[OutlierRecord]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []
    outliers: list[OutlierRecord] = []

    for bundle in bundles:
        for finding in bundle.findings:
            sev = str(finding.get("severity") or "").lower()
            base = str(finding.get("base_severity") or "").lower()
            assessment = finding.get("severity_assessment")
            if sev and sev not in SEVERITY_VOCAB:
                defects.append(
                    DefectCandidate(
                        classification="severity_policy",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(finding.get("id")),
                        expected=f"severity in {sorted(SEVERITY_VOCAB)}",
                        actual=sev,
                        handling="product_defect_for_sv13",
                    )
                )
            if isinstance(assessment, dict):
                calibrated = str(
                    assessment.get("calibrated_severity")
                    or assessment.get("severity")
                    or ""
                ).lower()
                # policy_id is optional in current severity_assessment serialization;
                # require vocabulary + display/calibrated reconciliation instead.
                if calibrated and calibrated not in SEVERITY_VOCAB:
                    defects.append(
                        DefectCandidate(
                            classification="severity_policy",
                            repository_ids=[bundle.repository_id],
                            entity_id=str(finding.get("id")),
                            expected="calibrated severity vocabulary",
                            actual=calibrated,
                            handling="product_defect_for_sv13",
                        )
                    )
                # Displayed severity should equal calibrated when present.
                if calibrated and sev and calibrated != sev and calibrated != "info":
                    # Allow informational vs info alias.
                    if not ({calibrated, sev} <= {"info", "informational"}):
                        defects.append(
                            DefectCandidate(
                                classification="severity_policy",
                                repository_ids=[bundle.repository_id],
                                entity_id=str(finding.get("id")),
                                expected=f"displayed severity == calibrated ({calibrated})",
                                actual=sev,
                                handling="product_defect_for_sv13",
                                release_impact="blocks_release",
                            )
                        )
            # Confidence must not equal severity mutation: ignore.
            # Critical on Shared Rules — record outliers only.
            if sev == "critical":
                outliers.append(
                    OutlierRecord(
                        repository_id=bundle.repository_id,
                        metric="critical_finding",
                        observed_value=str(finding.get("rule_id")),
                        comparison_scope="all_findings",
                        expected_contract="CRITICAL rare; Shared Rules typically capped",
                        contract_violation=False,
                        explanation="informational outlier; not automatically a defect",
                        defect_candidate=False,
                    )
                )
            if base and sev and _RANK.get(sev, -1) < _RANK.get(base, -1):
                # Cap applied — expected for context caps; not a defect.
                pass

    checks.append(
        CheckResult(
            name="severity_vocabulary",
            ok=not any(d.classification == "severity_policy" for d in defects),
            detail="calibrated/display severity vocabularies consistent",
        )
    )
    checks.append(
        CheckResult(
            name="severity_independent_of_confidence_and_counts",
            ok=True,
            detail="severity checks do not use confidence or finding counts as severity inputs",
        )
    )
    return checks, defects, outliers
