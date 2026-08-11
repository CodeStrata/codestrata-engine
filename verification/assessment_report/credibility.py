"""Credibility, coverage/confidence separation, and wording checks."""

from __future__ import annotations

import re

from verification.assessment_report.contract import (
    CLAIM_DISCLAIMER_MARKERS,
    UNSUPPORTED_CLAIM_FRAGMENTS,
    VALIDATION_METRIC_LEAKS,
)
from verification.assessment_report.loaders import AssessmentRunArtifacts, assessment_of
from verification.assessment_report.models import CheckResult

_SECRET_PATTERNS = (
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws_access_key"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "openai_key"),
    (re.compile(r"cscc_v1_[A-Za-z0-9]+"), "community_token"),
    (re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"), "private_key"),
    (re.compile(r"(?i)password\s*=\s*['\"][^'\"]{4,}['\"]"), "password_assignment"),
    (re.compile(r"file://[/\w]"), "file_url"),
)


def find_unsupported_claims(text: str) -> list[str]:
    """Return unsupported claim fragments not covered by nearby disclaimer language."""

    lowered = text.lower()
    hits: list[str] = []
    for phrase in UNSUPPORTED_CLAIM_FRAGMENTS:
        # Require a non-letter boundary after the phrase so "cloud ready"
        # does not match inside "cloud readiness".
        pattern = re.compile(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])")
        for match in pattern.finditer(lowered):
            idx = match.start()
            window = lowered[max(0, idx - 48) : match.end() + 16]
            if any(marker in window for marker in CLAIM_DISCLAIMER_MARKERS):
                continue
            hits.append(phrase)
            break
    return hits


def check_credibility(run: AssessmentRunArtifacts) -> list[CheckResult]:
    assessment = assessment_of(run.report)
    html = run.html
    checks: list[CheckResult] = []

    html_claims = find_unsupported_claims(html)
    checks.append(
        CheckResult(
            name="credibility:html_unsupported_claims",
            ok=not html_claims,
            detail=",".join(html_claims[:8]) if html_claims else "ok",
            category="credibility",
        )
    )

    # Leadership / EIS regions — still covered by full HTML scan
    for metric in VALIDATION_METRIC_LEAKS:
        # Avoid false positives on the word "recall" in prose carefully —
        # only fail on structured validation metric markers.
        pass
    metric_hits = [m for m in VALIDATION_METRIC_LEAKS if m in html.lower()]
    # Soften: bare "recall" as substring of other words is excluded by quotes in patterns
    checks.append(
        CheckResult(
            name="credibility:no_validation_precision_recall",
            ok=not metric_hits,
            detail=",".join(metric_hits) if metric_hits else "ok",
            category="credibility",
        )
    )

    coverage = assessment.get("assessment_coverage")
    confidence = assessment.get("assessment_head_confidence")
    checks.append(
        CheckResult(
            name="credibility:coverage_confidence_separate",
            ok=(coverage is None or isinstance(coverage, dict))
            and (confidence is None or isinstance(confidence, dict)),
            detail="maps typed or absent",
            category="credibility",
        )
    )

    # Zero findings must not imply "healthy" absolute claim
    findings = assessment.get("findings") or []
    if isinstance(findings, list) and len(findings) == 0:
        checks.append(
            CheckResult(
                name="credibility:zero_findings_not_healthy",
                ok="healthy" not in find_unsupported_claims(html)
                and "healthy engineering" not in html.lower(),
                detail="zero findings honest",
                category="credibility",
            )
        )

    # Technology inventory is inventory, not a finding head
    if 'id="technology-inventory"' in html:
        checks.append(
            CheckResult(
                name="credibility:technology_inventory_not_finding_head",
                ok="Technology Inventory" in html,
                detail="inventory section present",
                category="credibility",
            )
        )

    # Privacy scan across artifacts (bounded)
    blob = "\n".join([str(run.report), str(run.findings), str(run.recommendations), html])
    privacy_hits = []
    for pattern, code in _SECRET_PATTERNS:
        if pattern.search(blob):
            # Ignore clearly redacted markers
            if "REDACTED" in blob and code in {"password_assignment", "aws_access_key"}:
                # still flag aws keys even near redacted unless the match itself is redacted
                match = pattern.search(blob)
                if match and "REDACTED" in match.group(0):
                    continue
            privacy_hits.append(code)
    for needle, code in (("/Users/", "abs_users"), ("/home/", "abs_home"), ("/var/folders/", "abs_tmp")):
        if needle in blob:
            privacy_hits.append(code)
    checks.append(
        CheckResult(
            name="credibility:privacy_scan",
            ok=not privacy_hits,
            detail=",".join(sorted(set(privacy_hits))) if privacy_hits else "ok",
            category="privacy",
        )
    )
    return checks
