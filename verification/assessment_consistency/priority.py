"""Recommendation priority score/band consistency."""

from __future__ import annotations

from codestrata.domain.recommendations.priority import (
    BAND_HIGH_MIN,
    BAND_IMMEDIATE_MIN,
    BAND_MEDIUM_MIN,
    PRIORITY_SCORE_MAX,
    PRIORITY_SCORE_MIN,
    priority_for_score,
)
from verification.assessment_consistency.contract import PRIORITY_VOCAB
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    OutlierRecord,
    RepositoryBundle,
)


def check_priority(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate], list[OutlierRecord]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []
    outliers: list[OutlierRecord] = []

    for bundle in bundles:
        for rec in bundle.recommendations:
            pa = rec.get("priority_assessment")
            priority = str(rec.get("priority") or "").lower()
            score_raw = rec.get("priority_score")
            if isinstance(pa, dict):
                priority = str(pa.get("priority") or priority).lower()
                if pa.get("score") is not None:
                    score_raw = pa.get("score")
                policy = pa.get("policy_id")
                if not policy and pa.get("calibration_status") == "calibrated":
                    defects.append(
                        DefectCandidate(
                            classification="priority_policy",
                            repository_ids=[bundle.repository_id],
                            entity_id=str(rec.get("id")),
                            expected="policy_id when calibrated",
                            actual="missing",
                            handling="product_defect_for_sv13",
                        )
                    )
            if priority and priority not in PRIORITY_VOCAB:
                defects.append(
                    DefectCandidate(
                        classification="priority_policy",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(rec.get("id")),
                        expected=f"priority in {sorted(PRIORITY_VOCAB)}",
                        actual=priority,
                        handling="product_defect_for_sv13",
                    )
                )
            if score_raw is None:
                continue
            try:
                score = int(round(float(score_raw)))
            except (TypeError, ValueError):
                defects.append(
                    DefectCandidate(
                        classification="priority_policy",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(rec.get("id")),
                        expected="numeric score 0–100",
                        actual=repr(score_raw),
                        handling="product_defect_for_sv13",
                    )
                )
                continue
            if score < PRIORITY_SCORE_MIN or score > PRIORITY_SCORE_MAX:
                defects.append(
                    DefectCandidate(
                        classification="priority_policy",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(rec.get("id")),
                        expected=f"score in [{PRIORITY_SCORE_MIN},{PRIORITY_SCORE_MAX}]",
                        actual=str(score),
                        handling="product_defect_for_sv13",
                    )
                )
                continue
            expected = priority_for_score(score).value
            # compatibility: immediate may appear as critical in some fields
            if priority and priority != expected:
                if not (expected == "immediate" and priority == "critical"):
                    defects.append(
                        DefectCandidate(
                            classification="priority_policy",
                            repository_ids=[bundle.repository_id],
                            entity_id=str(rec.get("id")),
                            expected=f"priority={expected} for score={score}",
                            actual=priority,
                            release_impact="investigate",
                            handling="product_defect_for_sv13",
                        )
                    )
            rtype = str(rec.get("recommendation_type") or "").lower()
            if rtype == "legacy" and priority == "immediate":
                defects.append(
                    DefectCandidate(
                        classification="priority_policy",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(rec.get("id")),
                        expected="legacy Recommendations never Immediate without authority",
                        actual="immediate",
                        handling="product_defect_for_sv13",
                    )
                )
            if score >= BAND_IMMEDIATE_MIN:
                outliers.append(
                    OutlierRecord(
                        repository_id=bundle.repository_id,
                        metric="immediate_priority_score",
                        observed_value=score,
                        comparison_scope="recommendations",
                        expected_contract=f"score>={BAND_IMMEDIATE_MIN} → immediate",
                        contract_violation=False,
                        explanation=f"policy bands high>={BAND_HIGH_MIN} medium>={BAND_MEDIUM_MIN}",
                    )
                )

        # Priority Actions derive from recommendations when present.
        for pa in bundle.assessment.get("priority_actions") or []:
            if not isinstance(pa, dict):
                continue
            support = pa.get("supporting_recommendation_ids") or pa.get("recommendation_ids") or []
            if isinstance(support, list):
                rec_ids = {str(r.get("id")) for r in bundle.recommendations}
                for rid in support:
                    if str(rid) not in rec_ids and rec_ids:
                        defects.append(
                            DefectCandidate(
                                classification="priority_policy",
                                repository_ids=[bundle.repository_id],
                                entity_id=str(pa.get("id")),
                                expected="PA recommendation refs resolve",
                                actual=f"dangling={rid}",
                                handling="product_defect_for_sv13",
                            )
                        )

    checks.append(
        CheckResult(
            name="priority_score_band_reconcile",
            ok=not any("for score=" in d.expected for d in defects),
            detail="priority bands reconcile with 0–100 scores",
        )
    )
    checks.append(
        CheckResult(
            name="legacy_not_immediate",
            ok=not any("never Immediate" in d.expected for d in defects),
            detail="legacy Recommendations are not Immediate",
        )
    )
    return checks, defects, outliers
