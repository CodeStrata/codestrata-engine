"""Contract-relevant terminology consistency scans."""

from __future__ import annotations

import json
import re

from verification.assessment_consistency.contract import (
    FORBIDDEN_QUALITY_CONCLUSIONS,
    HEALTHY_ZERO_FINDINGS_PATTERNS,
    TERMINOLOGY_FORBIDDEN,
)
from verification.assessment_consistency.models import (
    CheckResult,
    DefectCandidate,
    RepositoryBundle,
)

_PRECISION_RECALL = re.compile(
    r"\b(validation[_\s-]?precision|validation[_\s-]?recall|precision\s*/\s*recall)\b",
    re.I,
)


def check_terminology(
    bundles: list[RepositoryBundle],
) -> tuple[list[CheckResult], list[DefectCandidate]]:
    checks: list[CheckResult] = []
    defects: list[DefectCandidate] = []

    for bundle in bundles:
        # Customer-facing slices only — avoid scanning entire optional pack dumps.
        slices = {
            "executive_summary": bundle.assessment.get("executive_summary"),
            "summary": bundle.assessment.get("summary"),
            "roadmap": bundle.assessment.get("roadmap"),
            "findings_titles": [f.get("title") for f in bundle.findings],
            "recommendation_titles": [r.get("title") for r in bundle.recommendations],
        }
        blob = json.dumps(slices, sort_keys=True).lower()
        for term in TERMINOLOGY_FORBIDDEN:
            if term in blob:
                defects.append(
                    DefectCandidate(
                        classification="terminology",
                        repository_ids=[bundle.repository_id],
                        entity_id=term,
                        expected="canonical terminology without forbidden score language",
                        actual=f"found {term!r}",
                        handling="product_defect_for_sv13",
                    )
                )
        for pattern in HEALTHY_ZERO_FINDINGS_PATTERNS:
            if pattern in blob:
                defects.append(
                    DefectCandidate(
                        classification="terminology",
                        repository_ids=[bundle.repository_id],
                        entity_id="healthy_zero_findings",
                        expected="zero Findings not labeled healthy/ready",
                        actual=pattern,
                        handling="product_defect_for_sv13",
                    )
                )
        if _PRECISION_RECALL.search(blob):
            defects.append(
                DefectCandidate(
                    classification="terminology",
                    repository_ids=[bundle.repository_id],
                    entity_id="precision_recall",
                    expected="validation Precision/Recall outside customer report",
                    actual="matched",
                    release_impact="blocks_release",
                    handling="product_defect_for_sv13",
                )
            )
        for phrase in FORBIDDEN_QUALITY_CONCLUSIONS:
            if phrase in blob:
                defects.append(
                    DefectCandidate(
                        classification="terminology",
                        repository_ids=[bundle.repository_id],
                        entity_id="quality_comparison",
                        expected="no repository quality/maturity ranking language",
                        actual=phrase,
                        handling="product_defect_for_sv13",
                    )
                )

    checks.append(
        CheckResult(
            name="terminology_contract",
            ok=not any(d.classification == "terminology" for d in defects),
            detail="no forbidden maturity/health/precision customer terminology",
        )
    )
    return checks, defects
