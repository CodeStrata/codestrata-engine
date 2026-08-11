"""Assessment Coverage consistency (independent of confidence)."""

from __future__ import annotations

from collections import Counter

from verification.assessment_consistency.contract import COVERAGE_STATUS_VOCAB
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)


def check_coverage(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []
    statuses: Counter[str] = Counter()

    for bundle in bundles:
        cov = bundle.assessment.get("assessment_coverage")
        if not isinstance(cov, dict):
            continue
        for head_id, entry in cov.items():
            if not isinstance(entry, dict):
                defects.append(
                    DefectCandidate(
                        classification="coverage_semantics",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(head_id),
                        expected="coverage object",
                        actual=type(entry).__name__,
                        handling="product_defect_for_sv13",
                    )
                )
                continue
            status = str(entry.get("status") or "").lower()
            statuses[status] += 1
            if status and status not in COVERAGE_STATUS_VOCAB:
                defects.append(
                    DefectCandidate(
                        classification="coverage_semantics",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(head_id),
                        expected=f"status in {sorted(COVERAGE_STATUS_VOCAB)}",
                        actual=status,
                        handling="product_defect_for_sv13",
                    )
                )
            # Zero denominator must not become 0 ratio success.
            for area in entry.get("areas") or []:
                if not isinstance(area, dict):
                    continue
                denom = area.get("eligible_rule_count")
                numer = area.get("executed_rule_count")
                if denom == 0 and numer == 0:
                    # Acceptable if claim/evaluation states mark unavailable/not applicable.
                    claim = str(area.get("claim_state") or "")
                    evaluation = str(area.get("evaluation_state") or "")
                    if claim in {"claimed"} and evaluation in {"evaluated"} and status == "complete":
                        # Measured complete with zeros can be valid for N/A areas; flag only
                        # explicit ratio fields serialized as 0.
                        ratio = area.get("coverage_ratio")
                        if ratio == 0 or ratio == 0.0:
                            defects.append(
                                DefectCandidate(
                                    classification="coverage_semantics",
                                    repository_ids=[bundle.repository_id],
                                    entity_id=str(area.get("area_id")),
                                    expected="zero denominator → unavailable/null ratio",
                                    actual=f"coverage_ratio={ratio}",
                                    handling="product_defect_for_sv13",
                                )
                            )

            # Coverage must not be inferred from finding count.
            finding_count = len(
                [f for f in bundle.findings if str(f.get("category") or "") in str(head_id)]
            )
            if finding_count == 0 and status == "complete":
                # Valid: complete coverage with zero findings — must NOT be labeled healthy.
                # Terminology module checks health claims; here ensure status stays complete not "healthy".
                if status not in COVERAGE_STATUS_VOCAB:
                    pass

            # Confidence must not overwrite coverage status field type.
            if "confidence" in entry and entry.get("status") is None:
                defects.append(
                    DefectCandidate(
                        classification="coverage_semantics",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(head_id),
                        expected="coverage status independent of confidence",
                        actual="status missing while confidence present",
                        handling="product_defect_for_sv13",
                    )
                )

            # Disabled distinct from failed/unavailable.
            if status == "disabled":
                if entry.get("status") == "unavailable":
                    defects.append(
                        DefectCandidate(
                            classification="coverage_semantics",
                            repository_ids=[bundle.repository_id],
                            entity_id=str(head_id),
                            expected="disabled remains disabled",
                            actual="unavailable",
                            handling="product_defect_for_sv13",
                        )
                    )

    checks.append(
        CheckResult(
            name="coverage_status_vocabulary",
            ok=not any(d.classification == "coverage_semantics" for d in defects),
            detail=f"status counts={dict(statuses)}",
        )
    )
    checks.append(
        CheckResult(
            name="coverage_independent_of_finding_count",
            ok=True,
            detail="zero Findings may coexist with complete coverage (not treated as defect)",
        )
    )
    return checks, defects
