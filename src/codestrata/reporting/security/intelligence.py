"""Build Security Intelligence from existing report + findings (Epic 3 Slice 3.6).

Do NOT import from codestrata.reporting.html_v2 (circular import). Duck-type
findings/recommendations with Any + getattr.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from codestrata.domain.security.ids import (
    HYGIENE_RULE_IDS,
    RULE_AUTHENTICATION_DISABLED,
    RULE_CREDENTIAL_LITERAL,
    RULE_DEBUG_ENABLED,
    RULE_HOSTNAME_VERIFICATION_DISABLED,
    RULE_PERMISSIVE_CORS_ORIGIN,
    RULE_PLACEHOLDER_CREDENTIAL,
    RULE_PRIVATE_KEY_MATERIAL,
    RULE_TLS_VERIFICATION_DISABLED,
)
from codestrata.reporting.security.intelligence_models import (
    SecurityArtifactRow,
    SecurityConfigObservationRow,
    SecurityCoverageRow,
    SecurityFindingLink,
    SecurityIntelligenceSection,
    SecurityOverviewFact,
    SecurityRecommendationLink,
)
from codestrata.reporting.security.models import SecurityReportSection

_BASE_LIMITATIONS = (
    "Static repository assessment only.",
    "Runtime security was not evaluated.",
    "No penetration testing was performed.",
    "No DAST was performed.",
    "No full commercial SAST analysis was performed.",
    "No network exposure was assessed.",
    "No vulnerability database lookup was performed.",
    "No CVE analysis was performed.",
    "No compliance certification was performed.",
    "No cloud runtime configuration was inspected.",
    "Absence of findings does not prove absence of risk.",
    "Sensitive literal observations are not validated live credentials.",
)

_SOFT_CLAIM_FRAGMENTS = (
    "secure repository",
    "repository appears secure",
    "security posture is healthy",
    "secure implementation",
    "low security risk",
    "low risk",
    "production secure",
    "no vulnerabilities",
    "no security issues",
    "no significant security risks",
    "compliant",
    "hardened",
    "security passed",
    "safe to deploy",
    "vulnerability-free",
)

_UNSUPPORTED_FINDING_FRAGMENTS = (
    "cve",
    "vulnerability database",
    "penetration",
    "dast",
    "compliance certification",
    "hardened",
)

_EMPTY_FINDINGS_MESSAGE = (
    "No security findings were produced within the assessed repository scope. "
    "This assessment evaluated static repository evidence only. Absence of "
    "findings should not be interpreted as absence of security risk. Runtime, "
    "network, vulnerability, and penetration-testing coverage was not included."
)

_SAFE_STATUS_SUMMARY = (
    "Security assessment completed using static repository-sensitive evidence. "
    "Zero findings do not certify absence of security risk."
)

_CONFIDENCE_RANK = {
    "high": 3,
    "moderate": 2,
    "medium": 2,
    "limited": 1,
    "low": 1,
    "unavailable": 0,
    "unknown": 0,
}

_HYGIENE_RULE_IDS = frozenset(HYGIENE_RULE_IDS)

_ARTIFACT_RULES: dict[str, tuple[str, str]] = {
    RULE_PRIVATE_KEY_MATERIAL: ("Private key material", "private-key-material"),
    RULE_CREDENTIAL_LITERAL: ("Credential literal", "credential-literal"),
}

_CONFIG_RULES: dict[str, str] = {
    RULE_TLS_VERIFICATION_DISABLED: "TLS verification disabled",
    RULE_HOSTNAME_VERIFICATION_DISABLED: "Hostname verification disabled",
    RULE_AUTHENTICATION_DISABLED: "Authentication disabled",
    RULE_PERMISSIVE_CORS_ORIGIN: "Permissive CORS origin",
    RULE_DEBUG_ENABLED: "Debug mode enabled",
    RULE_PLACEHOLDER_CREDENTIAL: "Placeholder credential",
}

_CONFIG_TITLE_FRAGMENTS = (
    "tls",
    "hostname verification",
    "authentication disabled",
    "auth disabled",
    "cors",
    "debug",
    "placeholder credential",
)

_SECRET_BODY_MARKERS = (
    "begin private key",
    "begin rsa private key",
    "begin certificate",
    "begin openssh private key",
    "-----begin ",
)

_LONG_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{48,}={0,2}")
_KEY_VALUE_SECRET_RE = re.compile(
    r"(?i)(password|secret|api[_-]?key|token|private[_-]?key)\s*[=:]\s*\S+"
)


def build_security_intelligence(
    report: SecurityReportSection | None,
    *,
    findings: Sequence[Any] = (),
    recommendations: Sequence[Any] = (),
) -> SecurityIntelligenceSection | None:
    """Project Security Intelligence from existing deterministic artifacts."""

    if report is None:
        return None

    sec_findings = tuple(item for item in findings if _is_security_finding(item))
    sec_finding_ids = {
        str(getattr(item, "finding_id", "") or "")
        for item in sec_findings
        if str(getattr(item, "finding_id", "") or "").strip()
    }
    sec_recs = tuple(
        item
        for item in recommendations
        if _is_security_recommendation(item, sec_finding_ids)
    )

    finding_links = _finding_links(sec_findings, report)
    recommendation_links = _recommendation_links(sec_recs, report, sec_finding_ids)
    artifacts = _artifacts(sec_findings, report, finding_links)
    config_observations = _config_observations(sec_findings, report, finding_links)
    coverage_rows = _coverage_rows(report)
    overview = _overview(
        report,
        finding_links=finding_links,
        recommendation_links=recommendation_links,
        artifacts=artifacts,
        config_observations=config_observations,
    )
    limitations = _limitations(report, finding_links=finding_links)
    confidence, confidence_label = _confidence(
        report=report,
        finding_links=finding_links,
        limitations=limitations,
    )
    empty_message = None if finding_links else _EMPTY_FINDINGS_MESSAGE

    return SecurityIntelligenceSection(
        status=report.status,
        status_label=report.status_label,
        status_summary=_safe_status_summary(report.status_summary),
        confidence=confidence,
        confidence_label=confidence_label,
        overview_facts=overview,
        artifacts=artifacts,
        config_observations=config_observations,
        findings=finding_links,
        recommendations=recommendation_links,
        coverage_rows=coverage_rows,
        limitations=limitations,
        finding_count=len(finding_links),
        recommendation_count=len(recommendation_links),
        empty_findings_message=empty_message,
    )


def _is_security_finding(item: Any) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    rule_id = (getattr(item, "rule_id", None) or "").strip().lower()
    title = (getattr(item, "title", None) or "").strip().lower()
    if not (category == "security" or rule_id.startswith("security.")):
        return False
    haystack = f"{rule_id} {title}"
    if any(fragment in haystack for fragment in _UNSUPPORTED_FINDING_FRAGMENTS):
        return False
    if rule_id.startswith("security.") and rule_id not in _HYGIENE_RULE_IDS:
        return False
    return True


def _is_security_recommendation(
    item: Any,
    security_finding_ids: set[str],
) -> bool:
    category = (getattr(item, "category", None) or "").strip().lower()
    if category == "security":
        return True
    related = set(getattr(item, "related_finding_ids", ()) or ())
    return bool(related) and related.issubset(security_finding_ids)


def _safe_status_summary(text: str) -> str:
    lowered = text.lower()
    for fragment in _SOFT_CLAIM_FRAGMENTS:
        if fragment in lowered:
            return _SAFE_STATUS_SUMMARY
    return text


def _finding_links(
    findings: Sequence[Any],
    report: SecurityReportSection,
) -> tuple[SecurityFindingLink, ...]:
    if findings:
        rows = [
            SecurityFindingLink(
                finding_id=item.finding_id,
                title=item.title,
                severity=item.severity,
                confidence=_finding_confidence_label(item),
                evidence_ids=_evidence_ids(item),
                recommendation_ids=tuple(
                    getattr(item, "driven_recommendation_ids", ()) or ()
                ),
                path=_finding_path(item),
                rule_id=str(getattr(item, "rule_id", "") or "security.unknown"),
                evidence_completeness=(
                    str(getattr(item, "evidence_completeness", "") or "").strip()
                    or None
                ),
            )
            for item in findings
        ]
        rows.sort(
            key=lambda row: (
                row.severity.lower(),
                row.title.lower(),
                row.finding_id,
            )
        )
        return tuple(rows)

    # Prefer production findings; include additional when needed.
    report_findings = tuple(report.finding_summary.production_findings)
    if not report_findings:
        report_findings = tuple(report.finding_summary.additional_observations)
    elif report.finding_summary.additional_observations and not findings:
        # Include additional only when HTML findings empty and production alone
        # would under-represent the assessed set.
        report_findings = report_findings + tuple(
            report.finding_summary.additional_observations
        )
    if not report_findings:
        return ()
    rows = [
        SecurityFindingLink(
            finding_id=item.finding_id,
            title=item.title,
            severity=item.severity,
            confidence=item.confidence,
            evidence_ids=(),
            recommendation_ids=(),
            path=_safe_path(item.path),
            rule_id=item.rule_id,
            evidence_completeness=None,
        )
        for item in report_findings
        if _is_security_finding(item)
    ]
    rows.sort(
        key=lambda row: (row.severity.lower(), row.title.lower(), row.finding_id)
    )
    return tuple(rows)


def _finding_confidence_label(item: Any) -> str:
    direct = (getattr(item, "confidence", None) or "").strip().lower()
    if direct in _CONFIDENCE_RANK:
        if direct == "medium":
            return "moderate"
        if direct == "low":
            return "limited"
        return direct
    completeness = (getattr(item, "evidence_completeness", None) or "").strip().lower()
    if completeness in {"complete", "high"}:
        return "high"
    if completeness in {"partial", "moderate"}:
        return "moderate"
    if completeness in {"limited", "low"}:
        return "limited"
    if completeness in {"legacy", "unavailable", "unknown", ""}:
        return "unavailable"
    return "unavailable"


def _evidence_ids(item: Any) -> tuple[str, ...]:
    refs = getattr(item, "evidence_refs", None)
    if refs:
        return tuple(
            getattr(ref, "evidence_id", "")
            for ref in refs
            if getattr(ref, "evidence_id", None)
        )
    ids = getattr(item, "evidence_ids", None)
    if ids:
        return tuple(str(item_id).strip() for item_id in ids if str(item_id).strip())
    return ()


def _finding_path(item: Any) -> str | None:
    path = _safe_path(getattr(item, "path", None))
    if path:
        return path
    for ref in getattr(item, "evidence_refs", ()) or ():
        path = _safe_path(getattr(ref, "path", None))
        if path:
            return path
    for node in getattr(item, "affected_nodes", ()) or ():
        path = _safe_path(str(node))
        if path:
            return path
    return None


def _recommendation_links(
    recommendations: Sequence[Any],
    report: SecurityReportSection,
    security_finding_ids: set[str],
) -> tuple[SecurityRecommendationLink, ...]:
    if recommendations:
        rows = [
            SecurityRecommendationLink(
                recommendation_id=item.recommendation_id,
                title=item.title,
                priority=getattr(item, "priority", None),
                finding_ids=tuple(
                    fid
                    for fid in (getattr(item, "related_finding_ids", ()) or ())
                    if fid in security_finding_ids
                )
                or tuple(getattr(item, "related_finding_ids", ()) or ()),
                objective=(getattr(item, "summary", None) or None),
            )
            for item in recommendations
        ]
        rows.sort(key=lambda row: (row.title.lower(), row.recommendation_id))
        return tuple(rows)

    rows = [
        SecurityRecommendationLink(
            recommendation_id=item.recommendation_id,
            title=item.title,
            priority=None,
            finding_ids=(),
            objective=item.action or item.rationale or None,
        )
        for item in report.recommendations
    ]
    rows.sort(key=lambda row: (row.title.lower(), row.recommendation_id))
    return tuple(rows)


def _artifacts(
    findings: Sequence[Any],
    report: SecurityReportSection,
    finding_links: Sequence[SecurityFindingLink],
) -> tuple[SecurityArtifactRow, ...]:
    rows: list[SecurityArtifactRow] = []
    seen: set[tuple[str, str | None]] = set()

    sources: Sequence[Any] = findings if findings else finding_links
    if not sources:
        # Fallback to report finding views when HTML findings empty.
        sources = tuple(report.finding_summary.production_findings) + tuple(
            report.finding_summary.additional_observations
        )

    for item in sources:
        rule_id = (getattr(item, "rule_id", None) or "").strip().lower()
        mapping = _ARTIFACT_RULES.get(rule_id)
        if mapping is None:
            title = (getattr(item, "title", None) or "").strip().lower()
            if "private key" in title or "private-key" in rule_id:
                mapping = ("Private key material", "private-key-material")
            elif "credential literal" in title or "credential-literal" in rule_id:
                mapping = ("Credential literal", "credential-literal")
            elif "certificate" in title or "certificate" in rule_id:
                mapping = ("Certificate-like material", "certificate-like")
            else:
                continue
        classification, kind = mapping
        path = _finding_path(item)
        if path is None:
            path = _safe_path(getattr(item, "path", None))
        # Path-safe artifact signals only; omit absolute/unsafe paths entirely.
        if path is None and getattr(item, "path", None):
            continue
        key = (classification, path)
        if key in seen:
            continue
        seen.add(key)
        note = "Classification and relative path only; values are not shown"
        if report.coverage_summary.formats_represented and path:
            note = (
                f"{note}. Formats represented: "
                f"{', '.join(report.coverage_summary.formats_represented)}"
            )
        rows.append(
            SecurityArtifactRow(
                classification=classification,
                path=path,
                kind=kind,
                note=note,
            )
        )

    # If no path-safe artifact signals, omit the group.
    if not rows:
        return ()
    rows.sort(
        key=lambda row: (
            (row.classification or "").lower(),
            (row.path or "").lower(),
        )
    )
    return tuple(rows)


def _config_observations(
    findings: Sequence[Any],
    report: SecurityReportSection,
    finding_links: Sequence[SecurityFindingLink],
) -> tuple[SecurityConfigObservationRow, ...]:
    del finding_links  # reserved for future path linking via finding ids
    rows: list[SecurityConfigObservationRow] = []
    seen: set[tuple[str, str | None]] = set()

    sources: Sequence[Any] = findings if findings else ()
    if not sources:
        sources = tuple(report.finding_summary.production_findings) + tuple(
            report.finding_summary.additional_observations
        )

    for item in sources:
        rule_id = (getattr(item, "rule_id", None) or "").strip().lower()
        title = (getattr(item, "title", None) or "").strip()
        label = _CONFIG_RULES.get(rule_id)
        if label is None:
            lowered = f"{rule_id} {title}".lower()
            if not any(fragment in lowered for fragment in _CONFIG_TITLE_FRAGMENTS):
                continue
            label = title or rule_id
        path = _finding_path(item)
        if path is None:
            path = _safe_path(getattr(item, "path", None))
        key = (label, path)
        if key in seen:
            continue
        seen.add(key)
        ids = _evidence_ids(item)
        rows.append(
            SecurityConfigObservationRow(
                label=label,
                path=path,
                note=None,
                evidence_id=ids[0] if ids else None,
                redacted_snippet=_safe_redacted_snippet(item),
            )
        )

    rows.sort(key=lambda row: ((row.label or "").lower(), (row.path or "").lower()))
    return tuple(rows)


def _safe_redacted_snippet(item: Any) -> str | None:
    """Attach only EvidenceRefView.snippet_text when short and non-secret-like."""

    for ref in getattr(item, "evidence_refs", ()) or ():
        text = getattr(ref, "snippet_text", None)
        if not text:
            continue
        snippet = str(text).strip()
        if not snippet or len(snippet) > 120:
            continue
        lowered = snippet.lower()
        if any(marker in lowered for marker in _SECRET_BODY_MARKERS):
            continue
        if _LONG_BASE64_RE.search(snippet):
            continue
        if _KEY_VALUE_SECRET_RE.search(snippet):
            continue
        return snippet
    # Do not pull explanation/remediation as snippet — those may carry values.
    return None


def _overview(
    report: SecurityReportSection,
    *,
    finding_links: Sequence[SecurityFindingLink],
    recommendation_links: Sequence[SecurityRecommendationLink],
    artifacts: Sequence[SecurityArtifactRow],
    config_observations: Sequence[SecurityConfigObservationRow],
) -> tuple[SecurityOverviewFact, ...]:
    cov = report.coverage_summary
    facts: list[SecurityOverviewFact] = [
        SecurityOverviewFact(label="Assessment status", value=report.status_label),
        SecurityOverviewFact(
            label="Assessment scope",
            value=report.assessment_scope,
            note="Static repository-sensitive evidence only",
        ),
        SecurityOverviewFact(
            label="Security findings",
            value=str(len(finding_links)),
            note="Zero findings do not mean the repository is secure",
        ),
        SecurityOverviewFact(
            label="Security recommendations",
            value=str(len(recommendation_links)),
        ),
        SecurityOverviewFact(
            label="Candidate artifacts discovered",
            value=str(cov.candidate_artifacts_discovered),
            note="Candidates are not proof of secrets",
        ),
        SecurityOverviewFact(
            label="Artifacts inspected",
            value=str(cov.artifacts_inspected),
        ),
        SecurityOverviewFact(
            label="Configuration facts collected",
            value=str(cov.configuration_facts_collected),
            note="Fact counts only; values are not shown",
        ),
        SecurityOverviewFact(
            label="Rules executed",
            value=str(cov.rules_executed),
        ),
    ]
    if artifacts:
        facts.append(
            SecurityOverviewFact(
                label="Sensitive artifact inventory rows",
                value=str(len(artifacts)),
                note="Classification and relative path only",
            )
        )
    if config_observations:
        facts.append(
            SecurityOverviewFact(
                label="Configuration observations",
                value=str(len(config_observations)),
            )
        )
    return tuple(facts)


def _coverage_rows(
    report: SecurityReportSection,
) -> tuple[SecurityCoverageRow, ...]:
    cov = report.coverage_summary
    specs: tuple[tuple[str, int | str, str | None], ...] = (
        ("Evidence status", cov.evidence_status or "—", None),
        (
            "Candidate artifacts discovered",
            cov.candidate_artifacts_discovered,
            "Candidates are not proof of secrets",
        ),
        ("Artifacts inspected", cov.artifacts_inspected, None),
        ("Structured files parsed", cov.structured_files_parsed, None),
        (
            "Configuration facts collected",
            cov.configuration_facts_collected,
            "Values are not shown",
        ),
        ("Rules registered", cov.rules_registered, None),
        ("Rules executed", cov.rules_executed, None),
        (
            "Malformed files",
            cov.malformed_files,
            "Parse failures limit security hygiene coverage",
        ),
        ("Unsupported binaries", cov.unsupported_binaries, None),
        ("Skipped files", cov.skipped_files, None),
    )
    rows: list[SecurityCoverageRow] = []
    always_show = {
        "Evidence status",
        "Candidate artifacts discovered",
        "Artifacts inspected",
        "Rules executed",
    }
    for label, value, note in specs:
        if isinstance(value, int) and value <= 0 and label not in always_show:
            continue
        status = "available"
        if label == "Malformed files" and isinstance(value, int) and value > 0:
            status = "limited"
        elif label == "Evidence status" and str(value).lower() in {
            "partially_succeeded",
            "partial",
            "insufficient",
        }:
            status = "partial"
        display = (
            ", ".join(cov.source_roles_represented)
            if label == "Source roles" and cov.source_roles_represented
            else str(value)
        )
        rows.append(
            SecurityCoverageRow(
                label=label,
                status=status,
                display=display,
                note=note,
            )
        )
    if cov.source_roles_represented:
        rows.append(
            SecurityCoverageRow(
                label="Source roles represented",
                status="available",
                display=", ".join(cov.source_roles_represented),
                note=None,
            )
        )
    if cov.formats_represented:
        rows.append(
            SecurityCoverageRow(
                label="Formats represented",
                status="available",
                display=", ".join(cov.formats_represented),
                note=None,
            )
        )
    if cov.note:
        rows.append(
            SecurityCoverageRow(
                label="Coverage note",
                status="available",
                display=cov.note,
                note=None,
            )
        )
    rows.sort(key=lambda row: row.label.lower())
    return tuple(rows)


def _limitations(
    report: SecurityReportSection,
    *,
    finding_links: Sequence[SecurityFindingLink],
) -> tuple[str, ...]:
    notes: list[str] = list(_BASE_LIMITATIONS)
    for item in report.limitations:
        summary = (item.summary or "").strip()
        if not summary:
            continue
        lowered = summary.lower()
        if any(fragment in lowered for fragment in _SOFT_CLAIM_FRAGMENTS):
            continue
        if "phase " in lowered:
            continue
        notes.append(summary)
    if report.status in {"insufficient_evidence", "partially_succeeded"}:
        notes.append("Security coverage was partial for this assessment.")
    if report.status in {"disabled", "not_requested", "not_applicable", "failed"}:
        notes.append("Security analysis did not produce a complete assessment.")
    cov = report.coverage_summary
    if cov.malformed_files > 0 or cov.skipped_files > 0:
        notes.append(
            "Some files were malformed or skipped; security hygiene coverage "
            "may be incomplete."
        )
    if not finding_links:
        notes.append(
            "No security findings were produced within the assessed repository scope."
        )
    seen: set[str] = set()
    out: list[str] = []
    for note in notes:
        key = note.strip()
        if not key or key.lower() in seen:
            continue
        seen.add(key.lower())
        out.append(key)
    return tuple(out)


def _confidence(
    *,
    report: SecurityReportSection,
    finding_links: Sequence[SecurityFindingLink],
    limitations: Sequence[str],
) -> tuple[str, str]:
    ranks: list[int] = []
    for finding in finding_links:
        ranks.append(_CONFIDENCE_RANK.get(finding.confidence.lower(), 0))

    cov = report.coverage_summary
    if cov.malformed_files > 0 or cov.skipped_files > 0:
        ranks.append(1)
    if report.status in {"insufficient_evidence", "partially_succeeded", "failed"}:
        ranks.append(1)
    if limitations and not finding_links:
        ranks.append(0)

    if not ranks:
        return "unavailable", "Confidence unavailable"
    weakest = min(ranks)
    if weakest >= 3:
        return "high", "High confidence"
    if weakest == 2:
        return "moderate", "Moderate confidence"
    if weakest == 1:
        return "limited", "Limited confidence"
    return "unavailable", "Confidence unavailable"


def _safe_token(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\\", "/")
    if not text:
        return None
    if text.startswith("/") or text.startswith("file:"):
        return None
    if ".." in text.split("/"):
        return None
    if text.startswith("<") and text.endswith(">"):
        return None
    return text


def _safe_path(path: str | None) -> str | None:
    return _safe_token(path)
