"""Contract for SV.5 assessment report verification."""

from __future__ import annotations

from dataclasses import dataclass

ASSESSMENT_REPORT_VERIFICATION_ID = "assessment-report-verification"
ASSESSMENT_REPORT_VERIFICATION_VERSION = "1.0.0"

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "report.json",
    "findings.json",
    "recommendations.json",
    "report.html",
)

# R2 baseline reading order. Legacy leadership, executive-summary, and
# key-takeaways ids are not part of this hierarchy.
EXPECTED_SECTION_ORDER: tuple[tuple[str, str], ...] = (
    ("attention-first", "What deserves attention now"),
    ("assessment-results", "Current outcomes"),
    ("architecture-map", "Architecture Map"),
    ("engineering-hotspots", "Engineering Hotspots"),
    ("ownership-concentration", "Ownership concentration"),
    ("temporal-co-change", "Temporal co-change"),
    ("priority-actions", "Priority Actions"),
    ("coverage-and-trust", "Coverage & Trust"),
    ("technical-appendix", "Technical Appendix"),
)

# Soft absolute claims — disclaimer-aware matching applied in credibility.py
UNSUPPORTED_CLAIM_FRAGMENTS: tuple[str, ...] = (
    "production ready",
    "cloud ready",
    "ai ready",
    "agent ready",
    "enterprise ready",
    "modernization ready",
    "secure repository",
    "healthy engineering organization",
    "engineering health",
    "industry leading",
    "fully modernized",
    "low risk",
    "guaranteed",
    "will save",
    "rewrite required",
    "migration guaranteed",
)

# Negation / limitation prefixes that make soft claims acceptable when nearby
CLAIM_DISCLAIMER_MARKERS: tuple[str, ...] = (
    "not ",
    "no ",
    "never ",
    "without ",
    "cannot ",
    "does not ",
    "do not ",
    "unsupported",
    "unavailable",
    "limitation",
    "limited",
    "unknown",
    "not claimed",
    "does not claim",
    "no claim",
)

VALIDATION_METRIC_LEAKS: tuple[str, ...] = (
    "precision/recall",
    "precision_recall",
    '"precision"',
    '"recall"',
    "f1-score",
    "f1_score",
)


@dataclass(frozen=True, slots=True)
class ReportVerificationContract:
    verification_id: str = ASSESSMENT_REPORT_VERIFICATION_ID
    verification_version: str = ASSESSMENT_REPORT_VERIFICATION_VERSION
    assessment_schema_version: str = "1.2"
    required_artifacts: tuple[str, ...] = REQUIRED_ARTIFACTS
    section_order: tuple[tuple[str, str], ...] = EXPECTED_SECTION_ORDER
    local_fixture_relative: str = "test-fixtures/sample-js-app"
    catalog_relative: str = "validation/repository-catalog/catalog.json"
    notes: tuple[str, ...] = (
        "SV.5 verifies report quality/integrity of SV.4 assessment artifacts.",
        "Reuses product validators; does not create a second schema.",
        "Does not tune findings, recommendations, or redesign reports.",
        "SV.6 covers CLI UX; SV.12 covers deeper quality review.",
    )


def default_contract() -> ReportVerificationContract:
    return ReportVerificationContract()
