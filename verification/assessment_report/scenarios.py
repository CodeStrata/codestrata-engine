"""Negative / empty-state report scenarios (model-level)."""

from __future__ import annotations

from verification.assessment_report.credibility import find_unsupported_claims
from verification.assessment_report.models import CheckResult


def check_negative_scenarios() -> list[CheckResult]:
    """Model-level checks that empty/disabled states remain honest.

    Uses synthetic documents only — does not invent product fixtures.
    """

    checks: list[CheckResult] = []

    empty_html = """<!DOCTYPE html><html><head></head><body>
    <section id="assessment-results"><h2>Assessment Results</h2>
    <p>No findings were produced for enabled assessment heads.</p>
    <p>Limitations: coverage unavailable for disabled packs.</p>
    </section></body></html>"""
    checks.append(
        CheckResult(
            name="negative:A_no_findings_not_healthy",
            ok=not find_unsupported_claims(empty_html),
            detail="empty findings wording",
            category="negative",
        )
    )

    disabled = "Assessment head status: disabled. Coverage unavailable. Confidence unavailable."
    checks.append(
        CheckResult(
            name="negative:E_disabled_head_honest",
            ok="healthy" not in disabled.lower() and "production ready" not in disabled.lower(),
            detail="disabled ≠ healthy",
            category="negative",
        )
    )

    unavailable = "Confidence: unavailable because evidence mapping is deferred."
    checks.append(
        CheckResult(
            name="negative:H_unavailable_confidence",
            ok="unavailable" in unavailable.lower(),
            detail="unavailable confidence honest",
            category="negative",
        )
    )

    legacy = {"recommendation_type": "legacy", "id": "R-legacy", "title": "Legacy note"}
    checks.append(
        CheckResult(
            name="negative:I_legacy_marked",
            ok=str(legacy.get("recommendation_type")).lower() == "legacy",
            detail="legacy type present",
            category="negative",
        )
    )

    # Claim matcher disclaimer awareness
    negated = "This report does not claim the repository is production ready."
    checks.append(
        CheckResult(
            name="negative:disclaimer_aware_matcher",
            ok=not find_unsupported_claims(negated),
            detail="negated claim allowed",
            category="negative",
        )
    )
    absolute = "The repository is production ready for enterprise deployment."
    checks.append(
        CheckResult(
            name="negative:absolute_claim_detected",
            ok=bool(find_unsupported_claims(absolute)),
            detail="absolute claim flagged",
            category="negative",
        )
    )
    return checks
