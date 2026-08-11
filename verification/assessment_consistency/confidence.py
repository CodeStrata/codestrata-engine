"""Confidence concept consistency (distinct from coverage)."""

from __future__ import annotations

from collections import Counter

from verification.assessment_consistency.contract import CONFIDENCE_LEVEL_VOCAB
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)


def _level(obj: object) -> str | None:
    if isinstance(obj, dict):
        level = obj.get("level")
        return str(level).lower() if level is not None else None
    if obj is None:
        return None
    return str(obj).lower()


def check_confidence(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []
    levels: Counter[str] = Counter()

    for bundle in bundles:
        # Finding Confidence
        for finding in bundle.findings:
            fc = finding.get("finding_confidence")
            level = _level(fc)
            if level:
                levels[level] += 1
                if level not in CONFIDENCE_LEVEL_VOCAB:
                    defects.append(
                        DefectCandidate(
                            classification="confidence_semantics",
                            repository_ids=[bundle.repository_id],
                            entity_id=str(finding.get("id")),
                            expected=f"level in {sorted(CONFIDENCE_LEVEL_VOCAB)}",
                            actual=level,
                            handling="product_defect_for_sv13",
                        )
                    )
            # Confidence not inferred from severity: if severity critical and confidence missing entirely — ok;
            # if finding_confidence equals severity string as sole level wrongly — rare.
            sev = str(finding.get("severity") or "").lower()
            if level and sev and level == sev and sev not in CONFIDENCE_LEVEL_VOCAB:
                defects.append(
                    DefectCandidate(
                        classification="confidence_semantics",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(finding.get("id")),
                        expected="confidence level enum distinct from severity",
                        actual=f"level={level} severity={sev}",
                        handling="product_defect_for_sv13",
                    )
                )
            rc = finding.get("rule_confidence")
            rlevel = _level(rc)
            if rlevel and rlevel not in CONFIDENCE_LEVEL_VOCAB:
                defects.append(
                    DefectCandidate(
                        classification="confidence_semantics",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(finding.get("rule_id")),
                        expected=f"rule confidence in {sorted(CONFIDENCE_LEVEL_VOCAB)}",
                        actual=rlevel,
                        handling="product_defect_for_sv13",
                    )
                )

        # Head confidence
        head_conf = bundle.assessment.get("assessment_head_confidence")
        if isinstance(head_conf, dict):
            for head_id, entry in head_conf.items():
                level = _level(entry)
                if level:
                    levels[f"head:{level}"] += 1
                    if level not in CONFIDENCE_LEVEL_VOCAB:
                        defects.append(
                            DefectCandidate(
                                classification="confidence_semantics",
                                repository_ids=[bundle.repository_id],
                                entity_id=str(head_id),
                                expected=f"head confidence in {sorted(CONFIDENCE_LEVEL_VOCAB)}",
                                actual=level,
                                handling="product_defect_for_sv13",
                            )
                        )
                # Zero findings must not fabricate High head confidence without coverage basis.
                if isinstance(entry, dict) and level == "high":
                    summary = entry.get("component_summary") or {}
                    finding_count = summary.get("finding_count")
                    coverage_state = str(summary.get("coverage_state") or "")
                    if finding_count == 0 and coverage_state not in {
                        "complete",
                        "partial",
                        "",
                    }:
                        defects.append(
                            DefectCandidate(
                                classification="confidence_semantics",
                                repository_ids=[bundle.repository_id],
                                entity_id=str(head_id),
                                expected="no High confidence from empty findings alone",
                                actual=f"high with finding_count=0 coverage={coverage_state}",
                                handling="product_defect_for_sv13",
                            )
                        )

        # Recommendation confidence
        for rec in bundle.recommendations:
            rc = rec.get("recommendation_confidence")
            level = _level(rc)
            if level and level not in CONFIDENCE_LEVEL_VOCAB:
                defects.append(
                    DefectCandidate(
                        classification="confidence_semantics",
                        repository_ids=[bundle.repository_id],
                        entity_id=str(rec.get("id")),
                        expected=f"recommendation confidence in {sorted(CONFIDENCE_LEVEL_VOCAB)}",
                        actual=level,
                        handling="product_defect_for_sv13",
                    )
                )

        # Coverage and confidence maps must both exist as separate objects.
        if "assessment_coverage" in bundle.assessment and "assessment_head_confidence" in bundle.assessment:
            if bundle.assessment["assessment_coverage"] is bundle.assessment["assessment_head_confidence"]:
                defects.append(
                    DefectCandidate(
                        classification="confidence_semantics",
                        repository_ids=[bundle.repository_id],
                        entity_id="coverage_confidence_conflation",
                        expected="separate coverage and confidence objects",
                        actual="identical object identity",
                        handling="product_defect_for_sv13",
                    )
                )

    checks.append(
        CheckResult(
            name="confidence_vocabulary",
            ok=not any(d.classification == "confidence_semantics" for d in defects),
            detail=f"observed level tokens sample={dict(list(levels.items())[:12])}",
        )
    )
    checks.append(
        CheckResult(
            name="coverage_confidence_separation",
            ok=not any(d.entity_id == "coverage_confidence_conflation" for d in defects),
            detail="assessment_coverage and assessment_head_confidence remain distinct",
        )
    )
    return checks, defects
