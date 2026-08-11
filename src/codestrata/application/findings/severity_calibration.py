"""Shared Finding severity calibration helper (Epic 5 Slice 5.13).

Preferred flow:

RuleMetadata / rule match severity
  → calibrate_finding_severity
  → Finding.severity (+ severity_assessment)

Does not consume confidence, precision/recall, duplicate counts, or correlation
counts. Does not calibrate Recommendation priority.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from codestrata.application.findings.severity_policies import (
    FindingSeverityPolicy,
    clamp_to_allowed,
    severity_policy_for_rule,
)
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.findings.models import Finding
from codestrata.domain.findings.severity import (
    FindingSeverityAssessment,
    FindingSeverityBasis,
    FindingSeverityComponents,
    RepositoryContextClass,
    SeverityCalibrationStatus,
    assessment_head_for_rule,
    compute_threshold_ratio,
    max_severity,
    min_severity,
    normalize_severity_token,
    severity_rank,
)
from codestrata.domain.rules.results import RuleMatch

_TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|testing|spec|__tests__|fixtures?|testdata|mocks?|samples?|examples?)(/|$)",
    re.IGNORECASE,
)
_DOC_PATH_RE = re.compile(
    r"(^|/)(docs?|documentation|readme|changelog|license)(/|$)|(\.md$)",
    re.IGNORECASE,
)
_GENERATED_PATH_RE = re.compile(
    r"(^|/)(generated|vendor|third_party|node_modules|\.venv|dist|build|target)(/|$)",
    re.IGNORECASE,
)
_CI_PATH_RE = re.compile(
    r"(^|/)\.github/workflows/|(^|/)(\.gitlab-ci|\.circleci|azure-pipelines)",
    re.IGNORECASE,
)


class SeverityCalibrationDiagnostics(dict):
    """Mutable diagnostics bag for optional CLI/summary use."""


def classify_repository_context(
    paths: Sequence[str] = (),
    *,
    metadata: Mapping[str, Any] | None = None,
) -> RepositoryContextClass:
    """Shared repository-context classifier for severity caps."""

    meta = dict(metadata or {})
    explicit = str(
        meta.get("repository_context")
        or meta.get("security_evidence_context")
        or meta.get("evidence_context")
        or ""
    ).strip().lower()
    if explicit:
        try:
            return RepositoryContextClass(explicit)
        except ValueError:
            # Map security context names.
            mapping = {
                "production": RepositoryContextClass.PRODUCTION,
                "test": RepositoryContextClass.TEST,
                "test_fixture": RepositoryContextClass.FIXTURE,
                "documentation": RepositoryContextClass.DOCUMENTATION,
                "sample": RepositoryContextClass.EXAMPLE,
                "generated": RepositoryContextClass.GENERATED,
                "dependency_metadata": RepositoryContextClass.VENDOR,
                "build_artifact": RepositoryContextClass.GENERATED,
                "ci_expression": RepositoryContextClass.CI,
                "mock_credential": RepositoryContextClass.EXAMPLE,
                "unknown": RepositoryContextClass.UNKNOWN,
            }
            if explicit in mapping:
                return mapping[explicit]

    normalized = [str(path).replace("\\", "/").strip().lower() for path in paths if path]
    if not normalized:
        return RepositoryContextClass.UNKNOWN
    if any(_CI_PATH_RE.search(path) for path in normalized):
        return RepositoryContextClass.CI
    if any(_DOC_PATH_RE.search(path) for path in normalized):
        return RepositoryContextClass.DOCUMENTATION
    if any(
        token in path
        for path in normalized
        for token in ("/fixture", "/fixtures/", "/testdata/", "/mocks/")
    ):
        return RepositoryContextClass.FIXTURE
    if any("/example" in path or "/samples/" in path for path in normalized):
        return RepositoryContextClass.EXAMPLE
    if any(_GENERATED_PATH_RE.search(path) for path in normalized):
        if any("vendor" in path or "third_party" in path or "node_modules" in path for path in normalized):
            return RepositoryContextClass.VENDOR
        return RepositoryContextClass.GENERATED
    if any(_TEST_PATH_RE.search(path) for path in normalized):
        return RepositoryContextClass.TEST
    return RepositoryContextClass.PRODUCTION


def calibrate_finding_severity(
    *,
    rule_id: str,
    emitted_severity: FindingSeverity | str,
    metadata: Mapping[str, Any] | None = None,
    evidence_paths: Sequence[str] = (),
    affected_subject_count: int | None = None,
    legacy: bool = False,
    policy: FindingSeverityPolicy | None = None,
) -> FindingSeverityAssessment:
    """Calibrate customer-facing Finding severity from deterministic inputs."""

    meta = dict(metadata or {})
    # Forbidden inputs — deliberately ignored even if present.
    for forbidden in (
        "finding_confidence",
        "rule_confidence",
        "precision",
        "recall",
        "duplicate_count",
        "correlation_count",
        "recommendation_priority",
    ):
        meta.pop(forbidden, None)

    severity = normalize_severity_token(emitted_severity)
    if legacy or str(rule_id).startswith("codestrata-rule-"):
        return FindingSeverityAssessment.legacy(
            severity=severity,
            limitations=(
                "Legacy Phase-1 Finding; severity preserved without Shared Rule recalibration.",
            ),
        )

    active = policy or severity_policy_for_rule(rule_id)
    if active is None:
        return FindingSeverityAssessment(
            severity=severity,
            basis=(FindingSeverityBasis.RULE_DEFAULT, FindingSeverityBasis.LEGACY_RULE),
            calibration_status=SeverityCalibrationStatus.PROVISIONAL,
            limitations=(
                f"No explicit severity policy for rule {rule_id}; emitted severity preserved.",
            ),
            component_summary=FindingSeverityComponents(
                base_severity=severity,
                calibrated_severity=severity,
                rule_id=rule_id,
                assessment_head=assessment_head_for_rule(rule_id),
                limitations_count=1,
            ),
            policy_id=None,
        )

    bases: list[FindingSeverityBasis] = list(active.default_bases)
    limitations: list[str] = list(active.limitations)
    calibrated = active.base_severity
    # Prefer rule-emitted severity when already within policy (rules apply bands/context).
    if severity in active.allowed_severities:
        calibrated = severity
        bases.append(FindingSeverityBasis.EXPLICIT_RULE_POLICY)

    threshold_ratio = None
    measured = meta.get("metric_value") or meta.get("measured_value") or meta.get("value")
    threshold = meta.get("threshold")
    if active.measurement_bands and measured is not None and threshold is not None:
        threshold_ratio = compute_threshold_ratio(measured, threshold)
        band_severity = _band_severity(active, threshold_ratio)
        if band_severity is not None:
            calibrated = band_severity
            bases.extend(
                (
                    FindingSeverityBasis.DETERMINISTIC_THRESHOLD_EXCEEDANCE,
                    FindingSeverityBasis.MEASUREMENT_BAND,
                    FindingSeverityBasis.THRESHOLD_MAGNITUDE,
                )
            )

    context = classify_repository_context(evidence_paths, metadata=meta)
    if context is RepositoryContextClass.PRODUCTION:
        bases.append(FindingSeverityBasis.PRODUCTION_CONTEXT)
    elif context in {
        RepositoryContextClass.TEST,
        RepositoryContextClass.FIXTURE,
        RepositoryContextClass.EXAMPLE,
        RepositoryContextClass.DOCUMENTATION,
    }:
        bases.append(FindingSeverityBasis.TEST_OR_FIXTURE_CONTEXT)
    cap = active.context_caps.get(context.value)
    if cap is not None and context is not RepositoryContextClass.PRODUCTION:
        calibrated = min_severity(calibrated, cap)
        bases.append(FindingSeverityBasis.CONTEXT_CAP)
        if context is RepositoryContextClass.UNKNOWN:
            limitations.append(
                "Repository context unknown; severity capped conservatively where policy requires."
            )

    # Scope escalation only when policy allows and subject count is material.
    if (
        active.scope_escalation
        and affected_subject_count is not None
        and affected_subject_count >= 5
        and FindingSeverity.HIGH in active.allowed_severities
    ):
        if severity_rank(calibrated) >= severity_rank(FindingSeverity.MEDIUM):
            calibrated = max_severity(calibrated, FindingSeverity.HIGH)
            bases.append(FindingSeverityBasis.BLAST_RADIUS)
            bases.append(FindingSeverityBasis.REPEATED_AFFECTED_SUBJECTS)

    calibrated = clamp_to_allowed(calibrated, active.allowed_severities)
    # Never invent Critical unless emitted and allowed.
    if (
        calibrated is FindingSeverity.CRITICAL
        and normalize_severity_token(emitted_severity) is not FindingSeverity.CRITICAL
    ):
        calibrated = FindingSeverity.HIGH if FindingSeverity.HIGH in active.allowed_severities else calibrated

    bases = list(dict.fromkeys(bases))
    return FindingSeverityAssessment(
        severity=calibrated,
        basis=tuple(bases),
        calibration_status=active.calibration_status,
        limitations=tuple(dict.fromkeys(limitations)),
        component_summary=FindingSeverityComponents(
            base_severity=active.base_severity,
            calibrated_severity=calibrated,
            rule_id=rule_id,
            assessment_head=assessment_head_for_rule(rule_id),
            production_context=context.value,
            threshold_ratio=threshold_ratio,
            affected_subject_count=affected_subject_count,
            directness=str(meta.get("directness") or "") or None,
            runtime_validation="unverified",
            limitations_count=len(set(limitations)),
        ),
        policy_id=active.policy_id,
    )


def calibrate_rule_match(match: RuleMatch) -> FindingSeverityAssessment:
    paths = tuple(
        item.safe_location for item in match.evidence if getattr(item, "safe_location", None)
    )
    metadata = {
        "subject_keys": ",".join(match.subject_keys or match.affected_entities),
    }
    # Surface common attributes from evidence messages is unsafe; use subject count only.
    return calibrate_finding_severity(
        rule_id=str(match.rule_id),
        emitted_severity=match.severity,
        metadata=metadata,
        evidence_paths=paths,
        affected_subject_count=len(match.affected_entities or match.subject_keys),
    )


def apply_severity_assessment(
    finding: Finding,
    assessment: FindingSeverityAssessment,
) -> Finding:
    """Attach assessment and set calibrated customer-facing severity."""

    metadata = dict(finding.metadata)
    metadata["base_severity"] = (
        assessment.component_summary.base_severity.value
        if assessment.component_summary.base_severity is not None
        else finding.severity.value
    )
    metadata["severity_calibration_status"] = assessment.calibration_status.value
    metadata["severity_policy_id"] = assessment.policy_id or ""
    # Preserve rule-emitted severity_basis (e.g. technical debt value>t*2).
    metadata["severity_calibration_basis"] = ",".join(
        item.value for item in assessment.basis
    )
    if assessment.component_summary.threshold_ratio:
        metadata["threshold_ratio"] = assessment.component_summary.threshold_ratio
    if assessment.component_summary.production_context:
        metadata["repository_context"] = assessment.component_summary.production_context
    updates: dict[str, Any] = {
        "severity": assessment.severity,
        "metadata": metadata,
        "severity_assessment": assessment,
        "base_severity": assessment.component_summary.base_severity or finding.severity,
    }
    # Preserve existing limitations; append severity limitations uniquely.
    if assessment.limitations:
        existing = list(finding.limitations)
        for item in assessment.limitations:
            if item not in existing:
                existing.append(item)
        updates["limitations"] = tuple(existing)
    return finding.model_copy(update=updates)


def calibrate_finding(finding: Finding, *, legacy: bool = False) -> Finding:
    """Recalibrate an existing Finding (e.g. after consolidation)."""

    paths = tuple(item.path for item in finding.evidence if item.path)
    is_legacy = legacy or str(finding.rule_id).startswith("codestrata-rule-")
    assessment = calibrate_finding_severity(
        rule_id=finding.rule_id,
        emitted_severity=finding.severity,
        metadata=finding.metadata,
        evidence_paths=paths,
        affected_subject_count=_subject_count(finding),
        legacy=is_legacy,
    )
    return apply_severity_assessment(finding, assessment)


def _subject_count(finding: Finding) -> int | None:
    raw = finding.metadata.get("subject_keys") or ""
    if not raw:
        return len(finding.evidence) or None
    parts = [part for part in str(raw).split(",") if part.strip()]
    return len(parts) or None


def _band_severity(
    policy: FindingSeverityPolicy,
    threshold_ratio: str | None,
) -> FindingSeverity | None:
    if threshold_ratio is None or not policy.measurement_bands:
        return None
    try:
        ratio = Decimal(threshold_ratio)
    except (InvalidOperation, ValueError):
        return None
    # Finding exists only when value > threshold ⇒ ratio > 1.
    if ratio <= 1:
        return None
    for band in policy.measurement_bands:
        lo = Decimal(band.min_ratio_exclusive)
        hi = (
            Decimal(band.max_ratio_inclusive)
            if band.max_ratio_inclusive is not None
            else None
        )
        if ratio > lo and (hi is None or ratio <= hi):
            return band.severity
    # > last band
    last = max(policy.measurement_bands, key=lambda item: Decimal(item.min_ratio_exclusive))
    if ratio > Decimal(last.min_ratio_exclusive):
        return last.severity
    return None
