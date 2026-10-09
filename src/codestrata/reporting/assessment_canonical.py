"""Project one analysis run through the canonical HTML views.

The projector copies this object. It does not rank hotspots, compute deltas,
or assign outcome movement. Records the analysis result does not carry stay
explicitly unknown.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from codestrata import __version__
from codestrata.application.assessment.canonical_records import (
    observation_from_sealed_metadata,
)
from codestrata.domain.contracts.comparison import (
    BoundDigests,
    ComparisonEnvelope,
    DriverDelta,
    seal_comparison,
)
from codestrata.domain.contracts.descriptors import launch_descriptors
from codestrata.domain.contracts.driver_manifest import outcome_driver_manifest_digest
from codestrata.domain.contracts.enums import (
    CauseAttribution,
    ChangedInputDimension,
    CompatibilityStatus,
    CoverageState,
    FreshnessState,
    HotspotListKind,
    OutcomeMovement,
    OwnershipScope,
    ResultStatus,
)
from codestrata.domain.contracts.envelope import (
    CapabilityCoverage,
    CapabilityFreshness,
    ComparisonRecord,
    EnvelopeBody,
    seal_envelope,
)
from codestrata.domain.contracts.facts import EvidenceRecord, GraphNodeRecord, GraphRecord
from codestrata.domain.contracts.hotspot import (
    ChangeSummary,
    EngineeringHotspot,
    OwnershipConcentration,
)
from codestrata.domain.contracts.identity_map import (
    canonical_finding_id,
    evidence_id,
    repository_subject_id,
)
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.rules.identifiers import validate_rule_id
from codestrata.models.analysis_result import AnalysisResult
from codestrata.models.finding import Finding
from codestrata.models.scan_comparison import ScanComparison
from codestrata.reporting.canonical_views import (
    CanonicalReportInput,
    CochangeView,
    project_canonical_html,
)
from codestrata.reporting.journey_observations import JourneyObservation, observe_repository

_EXTRACTOR = "codestrata.assessment-canonical.v1"
_MOVEMENT = {
    "favorable": OutcomeMovement.IMPROVED.value,
    "improved": OutcomeMovement.IMPROVED.value,
    "unfavorable": OutcomeMovement.DETERIORATED.value,
    "deteriorated": OutcomeMovement.DETERIORATED.value,
    "stable": OutcomeMovement.STABLE.value,
    "mixed": OutcomeMovement.MIXED.value,
    "insufficient": OutcomeMovement.INSUFFICIENT.value,
    "not_applicable": OutcomeMovement.NOT_APPLICABLE.value,
}
_CAUSE = {
    "source_only": CauseAttribution.SOURCE_ONLY,
    "feed_only": CauseAttribution.FEED_ONLY,
    "configuration_only": CauseAttribution.CONFIGURATION_ONLY,
    "mixed": CauseAttribution.MIXED,
    "undetermined": CauseAttribution.UNDETERMINED,
}
_DIMENSION = {
    "source": ChangedInputDimension.SOURCE,
    "feed": ChangedInputDimension.FEED,
    "configuration": ChangedInputDimension.CONFIGURATION,
    "ruleset": ChangedInputDimension.RULESET,
    "engine": ChangedInputDimension.ENGINE,
}


def canonical_report_from_analysis(
    result: AnalysisResult,
    *,
    customer_findings: Sequence[Any] | None = None,
) -> CanonicalReportInput:
    """Seal the canonical object for this analysis result."""

    key = _repository_key(result.repository.name)
    digest = _working_digest(result)
    revision = _source_revision(result)
    repo = repository_subject_id(key)
    observation = _journey_observation(result)
    if customer_findings:
        findings, evidence, finding_limits = _project_customer_findings(
            customer_findings,
            digest=digest,
            revision=revision,
            repository_id=repo,
        )
    else:
        findings, evidence, finding_limits = _project_findings(
            result.findings,
            digest=digest,
            revision=revision,
            repository_id=repo,
            repository_root=_repository_root(result),
        )
    hotspot_source = result.metadata.get("canonical_hotspots")
    if hotspot_source is None and observation is not None:
        hotspot_source = [item.model_dump(mode="json") for item in observation.hotspots]
    hotspots, hotspot_limits = _attached_models(
        hotspot_source,
        EngineeringHotspot,
        label="canonical_hotspots",
    )
    evidence = _cover_referenced_evidence(
        evidence,
        [eid for item in hotspots for eid in item.evidence_ids],
        digest=digest,
        revision=revision,
    )
    hotspots = _link_hotspots_to_findings(hotspots, findings)
    hotspots, link_limits = _keep_linked_hotspots(hotspots, {item.finding_id for item in findings})
    ownership_source = result.metadata.get("canonical_ownership")
    if ownership_source is None and observation is not None:
        ownership_source = [item.model_dump(mode="json") for item in observation.ownership]
    ownership, ownership_limits = _project_ownership(
        ownership_source,
        repository_id=repo,
        evidence_id_value=evidence[0].evidence_id,
    )
    evidence = _cover_referenced_evidence(
        evidence,
        [eid for item in ownership for eid in item.evidence_ids],
        digest=digest,
        revision=revision,
    )
    change_summary = _change_summary(result.comparison)
    if change_summary is None and observation is not None:
        change_summary = observation.change_summary
    comparison_record, comparison_envelope, comparison_limits = _project_comparison(result)
    limitations = (
        *finding_limits,
        *hotspot_limits,
        *link_limits,
        *ownership_limits,
        *comparison_limits,
        *_missing_inputs(hotspots, change_summary, observation),
    )
    body = EnvelopeBody(
        repository_subject_id=repo,
        source_revision=revision,
        working_state_digest=digest,
        descriptor_ids=tuple(item.descriptor_id for item in launch_descriptors()),
        outcome_driver_manifest_digest=outcome_driver_manifest_digest(),
        facts=(),
        evidence=evidence,
        graph=GraphRecord(
            graph_id=f"graph:{key}:analysis",
            nodes=(GraphNodeRecord(node_id=repo, kind="repository", subject_id=repo),),
            limitations=limitations,
        ),
        findings=findings,
        hotspots=hotspots,
        ownership=ownership,
        change_summary=change_summary,
        coverage=observation.coverage if observation is not None else _coverage(hotspots),
        freshness=observation.freshness if observation is not None else _freshness(hotspots),
        comparison=comparison_record,
        limitations=limitations,
    )
    return CanonicalReportInput(
        envelope=seal_envelope(body),
        comparison=comparison_envelope,
        cochange=_project_cochange(
            result.metadata.get("canonical_cochange")
            if result.metadata.get("canonical_cochange") is not None
            else (None if observation is None else observation.cochange)
        ),
        purpose="production",
        context_only_concern=_context_concern(result.comparison),
    )


def canonical_html_for_analysis(result: AnalysisResult) -> str:
    """Return the canonical HTML for this same analysis object."""

    return project_canonical_html(canonical_report_from_analysis(result))


def canonical_report_for_input(report_input: Any) -> CanonicalReportInput:
    """Return the canonical object for the report input already being written."""

    from codestrata.reporting.customer_universe import resolve_customer_findings

    if report_input.assessment_rule_evaluation is None:
        return canonical_report_from_analysis(report_input.analysis_result)
    return canonical_report_from_analysis(
        report_input.analysis_result,
        customer_findings=resolve_customer_findings(report_input),
    )


def canonical_html_for_report(report_input: Any) -> str:
    """Project the finding universe already written to the customer JSON report.

    Rule-evaluation findings are part of that run. They are copied with their
    source paths. Hotspot rank, deltas, and outcome movement stay on records
    the analysis result already carries.
    """

    return project_canonical_html(canonical_report_for_input(report_input))


def embed_canonical_views(html: str, canonical_html: str) -> str:
    """Insert the projector body into an existing HTML document."""

    inner = canonical_html.split("<body>\n", 1)[-1].rsplit("\n</body>", 1)[0]
    if "</body>" in html:
        return html.replace("</body>", inner + "\n</body>", 1)
    return html + "\n" + canonical_html


def _repository_root(result: AnalysisResult) -> Path | None:
    root = Path(result.repository.path)
    if root.is_dir():
        return root.resolve()
    return None


def _journey_observation(result: AnalysisResult) -> JourneyObservation | None:
    sealed = observation_from_sealed_metadata(result.metadata)
    if sealed is not None:
        return sealed
    root = _repository_root(result)
    if root is None:
        return None
    # Unsealed fixture/debug path only. Production assess seals records first.
    return observe_repository(root)


def _link_hotspots_to_findings(
    hotspots: tuple[EngineeringHotspot, ...],
    findings: Sequence[Any],
) -> tuple[EngineeringHotspot, ...]:
    linked: list[EngineeringHotspot] = []
    for hotspot in hotspots:
        ids = tuple(
            item.finding_id
            for item in findings
            if item.subject_id == hotspot.subject_id
            or str(item.subject_id).endswith("/" + hotspot.subject_id)
        )
        if ids:
            hotspot = hotspot.model_copy(update={"active_finding_ids": ids})
        linked.append(hotspot)
    return tuple(linked)


def _project_findings(
    findings: Sequence[Finding],
    *,
    digest: str,
    revision: str,
    repository_id: str,
    repository_root: Path | None = None,
) -> tuple[tuple[Any, ...], tuple[EvidenceRecord, ...], tuple[str, ...]]:
    from codestrata.domain.contracts.facts import FindingRecord

    records = []
    evidence: list[EvidenceRecord] = []
    limits: list[str] = []
    for finding in findings:
        rule_id, rule_limit = _rule_id(finding)
        if rule_limit:
            limits.append(rule_limit)
        subject = _finding_subject(finding, repository_id, repository_root)
        evidence_ids, rows = _finding_evidence(
            finding,
            digest=digest,
            revision=revision,
            subject=subject,
            repository_root=repository_root,
        )
        evidence.extend(rows)
        records.append(
            FindingRecord(
                finding_id=canonical_finding_id(
                    rule_id,
                    [subject],
                    occurrence_key=str(finding.id),
                ),
                rule_id=rule_id,
                subject_id=subject,
                result=_finding_result(finding),
                default_severity=finding.severity.value,
                effective_severity=_effective_severity(finding),
                confidence=_confidence(finding),
                evidence_ids=evidence_ids,
                occurrence_key=str(finding.id),
                override_provenance=_optional_text(finding.metadata.get("override_provenance")),
            )
        )
    if not evidence:
        evidence.append(
            _evidence(
                kind="source",
                digest=digest,
                revision=revision,
                locator=repository_id,
                limitation="analysis result has no finding evidence",
            )
        )
    return tuple(records), tuple(evidence), tuple(limits)


def _project_customer_findings(
    findings: Sequence[Any],
    *,
    digest: str,
    revision: str,
    repository_id: str,
) -> tuple[tuple[Any, ...], tuple[EvidenceRecord, ...], tuple[str, ...]]:
    """Copy the customer finding universe. Do not invent ranks or paths."""

    from codestrata.domain.contracts.facts import FindingRecord

    records = []
    evidence: list[EvidenceRecord] = []
    seen_evidence: set[str] = set()
    limits: list[str] = []
    for finding in findings:
        rule_id, rule_limit = _customer_rule_id(finding)
        if rule_limit:
            limits.append(rule_limit)
        paths = _customer_paths(finding)
        subject = paths[0] if paths else repository_id
        evidence_ids, rows = _customer_evidence(
            paths,
            digest=digest,
            revision=revision,
            subject=subject,
        )
        for row in rows:
            if row.evidence_id in seen_evidence:
                continue
            seen_evidence.add(row.evidence_id)
            evidence.append(row)
        occurrence = str(getattr(finding, "id", "") or "") or None
        severity = str(getattr(finding, "severity", "") or "unknown").strip().lower()
        base = getattr(finding, "base_severity", None)
        default_severity = (
            str(base).strip().lower() if isinstance(base, str) and base.strip() else severity
        )
        records.append(
            FindingRecord(
                finding_id=canonical_finding_id(
                    rule_id,
                    [subject],
                    occurrence_key=occurrence,
                ),
                rule_id=rule_id,
                subject_id=subject,
                result=ResultStatus.FAIL.value,
                default_severity=default_severity,
                effective_severity=severity,
                confidence=_customer_confidence(finding),
                evidence_ids=evidence_ids,
                occurrence_key=occurrence,
            )
        )
    if not evidence:
        evidence.append(
            _evidence(
                kind="source",
                digest=digest,
                revision=revision,
                locator=repository_id,
                limitation="analysis result has no finding evidence",
            )
        )
    return tuple(records), tuple(evidence), tuple(limits)


def _customer_rule_id(finding: Any) -> tuple[str, str | None]:
    raw = str(getattr(finding, "rule_id", "") or "")
    try:
        return validate_rule_id(raw), None
    except ValueError:
        category = str(getattr(finding, "category", "") or "assessment").replace("_", "-")
        fallback = f"assessment.{category}"
        try:
            return validate_rule_id(fallback), "finding_rule_id_not_canonical"
        except ValueError:
            return "assessment.unknown-rule", "finding_rule_id_not_canonical"


def _customer_paths(finding: Any) -> list[str]:
    paths: list[str] = []
    for row in getattr(finding, "evidence", ()) or ():
        raw: object
        if isinstance(row, dict):
            raw = row.get("path") or row.get("file_path") or row.get("relative_path")
        else:
            raw = getattr(row, "path", None) or getattr(row, "file_path", None)
        path = _usable_relative_path(raw)
        if path and path not in paths:
            paths.append(path)
    return paths


def _customer_evidence(
    paths: Sequence[str],
    *,
    digest: str,
    revision: str,
    subject: str,
) -> tuple[tuple[str, ...], tuple[EvidenceRecord, ...]]:
    if not paths:
        row = _evidence(
            kind="source",
            digest=digest,
            revision=revision,
            locator=f"{subject}:no-file",
            limitation="finding has no file evidence",
        )
        return (row.evidence_id,), (row,)
    rows = tuple(
        _evidence(
            kind="source",
            digest=digest,
            revision=revision,
            locator=path,
            relative_path=path,
        )
        for path in paths
    )
    return tuple(item.evidence_id for item in rows), rows


def _customer_confidence(finding: Any) -> str:
    raw = getattr(finding, "finding_confidence", None)
    if isinstance(raw, str) and raw.strip().lower() in {"high", "medium", "low", "unsupported"}:
        return raw.strip().lower()
    level = getattr(raw, "level", None)
    if level is not None:
        text = str(getattr(level, "value", level)).strip().lower()
        if text in {"high", "medium", "low", "unsupported"}:
            return text
    return "unsupported"


def _rule_id(finding: Finding) -> tuple[str, str | None]:
    raw = finding.rule_id or ""
    try:
        return validate_rule_id(raw), None
    except ValueError:
        fallback = f"assessment.{finding.category.value.replace('_', '-')}"
        return validate_rule_id(fallback), "finding_rule_id_not_canonical"


def _usable_relative_path(value: object, repository_root: Path | None = None) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if repository_root is not None:
        candidate = Path(raw)
        if candidate.is_absolute():
            try:
                raw = candidate.resolve().relative_to(repository_root).as_posix()
            except ValueError:
                return None
    path = raw.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if not path or path in {".", ".."} or path.startswith("../") or path.startswith("/"):
        return None
    if len(path) > 1 and path[1] == ":":
        return None
    return path


def _finding_subject(
    finding: Finding,
    repository_id: str,
    repository_root: Path | None = None,
) -> str:
    for item in finding.evidence:
        path = _usable_relative_path(item.file_path, repository_root)
        if path:
            return path
    return repository_id


def _finding_evidence(
    finding: Finding,
    *,
    digest: str,
    revision: str,
    subject: str,
    repository_root: Path | None = None,
) -> tuple[tuple[str, ...], tuple[EvidenceRecord, ...]]:
    rows: list[EvidenceRecord] = []
    for index, item in enumerate(finding.evidence):
        path = _usable_relative_path(item.file_path, repository_root)
        locator = path or f"{subject}:{index}"
        span = None if item.line_number is None else f"L{item.line_number}"
        rows.append(
            _evidence(
                kind="source",
                digest=digest,
                revision=revision,
                locator=locator,
                relative_path=path,
                span=span,
                limitation=None if path else "finding evidence has no file path",
            )
        )
    if rows:
        return tuple(item.evidence_id for item in rows), tuple(rows)
    row = _evidence(
        kind="source",
        digest=digest,
        revision=revision,
        locator=f"{subject}:no-file",
        limitation="finding has no file evidence",
    )
    return (row.evidence_id,), (row,)


def _finding_result(finding: Finding) -> str:
    raw = finding.metadata.get("result")
    if isinstance(raw, str):
        try:
            return ResultStatus(raw.strip().lower()).value
        except ValueError:
            pass
    return ResultStatus.FAIL.value


def _effective_severity(finding: Finding) -> str:
    raw = finding.metadata.get("effective_severity")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    return finding.severity.value


def _confidence(finding: Finding) -> str:
    raw = finding.metadata.get("confidence")
    if isinstance(raw, str) and raw.strip().lower() in {"high", "medium", "low", "unsupported"}:
        return raw.strip().lower()
    return "unsupported"


def _project_ownership(
    raw: object,
    *,
    repository_id: str,
    evidence_id_value: str,
) -> tuple[tuple[OwnershipConcentration, ...], tuple[str, ...]]:
    attached, limits = _attached_models(raw, OwnershipConcentration, label="canonical_ownership")
    if attached:
        return attached, limits
    return (
        (
            OwnershipConcentration(
                record_id=f"m25:{repository_id}:unmapped",
                scope=OwnershipScope.REPOSITORY,
                subject_id=repository_id,
                numerator=None,
                denominator=None,
                serialized_ratio=None,
                history_profile_id="missing",
                evidence_ids=(evidence_id_value,),
                status=ResultStatus.UNKNOWN,
                notes="Ownership mapping was not attached to this analysis result.",
            ),
        ),
        limits,
    )


def _project_cochange(raw: object) -> tuple[CochangeView, ...]:
    rows = []
    for item in _as_items(raw):
        if isinstance(item, CochangeView):
            rows.append(item)
            continue
        if not isinstance(item, Mapping):
            continue
        try:
            rows.append(
                CochangeView(
                    scope=str(item["scope"]),
                    left=str(item["left"]),
                    right=str(item["right"]),
                    support=_optional_int(item.get("support")),
                    union=_optional_int(item.get("union")),
                    jaccard=_optional_text(item.get("jaccard")),
                    supported_relation=_optional_bool(item.get("supported_relation")),
                    qualified_incomplete_window=bool(item.get("qualified_incomplete_window")),
                    unavailable_reason=_optional_text(item.get("unavailable_reason")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(rows)


def _change_summary(comparison: ScanComparison | None) -> ChangeSummary | None:
    if comparison is None:
        return None
    summary = comparison.change_summary
    if isinstance(summary, ChangeSummary):
        return summary
    return None


def _project_comparison(
    result: AnalysisResult,
) -> tuple[ComparisonRecord, ComparisonEnvelope | None, tuple[str, ...]]:
    comparison = result.comparison
    if comparison is None or not comparison.baseline_available:
        return (
            ComparisonRecord(
                has_baseline=False,
                movement=OutcomeMovement.NOT_APPLICABLE.value,
                reason_code="no_baseline",
                explanation="First run; delta and outcome movement unavailable.",
            ),
            None,
            (),
        )
    movement = _movement(comparison)
    compatibility, reasons = _compatibility(comparison)
    cause, dimensions = _cause(comparison)
    if (
        compatibility is CompatibilityStatus.INCOMPATIBLE
        and movement in {OutcomeMovement.IMPROVED.value, OutcomeMovement.STABLE.value}
    ):
        movement = OutcomeMovement.INSUFFICIENT.value
    record = ComparisonRecord(
        has_baseline=True,
        movement=movement,
        reason_code=compatibility.value,
        explanation=_comparison_explanation(compatibility, reasons, movement),
    )
    try:
        envelope = _seal_scan_comparison(
            comparison,
            movement=movement,
            compatibility=compatibility,
            reasons=reasons,
            cause=cause,
            dimensions=dimensions,
        )
    except (ValidationError, ValueError):
        return (
            ComparisonRecord(
                has_baseline=True,
                movement=OutcomeMovement.INSUFFICIENT.value,
                reason_code="comparison_projection_failed",
                explanation=(
                    "Scan comparison is present. Outcome movement stays insufficient "
                    "because the comparison envelope could not be sealed."
                ),
            ),
            None,
            ("comparison_projection_failed",),
        )
    return record, envelope, ()


def _seal_scan_comparison(
    comparison: ScanComparison,
    *,
    movement: str,
    compatibility: CompatibilityStatus,
    reasons: tuple[str, ...],
    cause: CauseAttribution,
    dimensions: tuple[ChangedInputDimension, ...],
) -> ComparisonEnvelope:
    deltas = tuple(_driver_delta(item, cause) for item in comparison.metric_deltas)
    excluded = tuple(item.driver_id for item in deltas if not item.compatible)
    coverage = ResultStatus.PASS
    if not deltas or any(item.coverage_status != "pass" for item in comparison.metric_deltas):
        coverage = ResultStatus.UNKNOWN
    candidate = _bound("candidate", comparison.current_timestamp, comparison.metric_deltas)
    baseline = None
    if compatibility is not CompatibilityStatus.NO_BASELINE:
        baseline = _bound("baseline", comparison.baseline_timestamp, comparison.metric_deltas)
    return seal_comparison(
        {
            "has_baseline": True,
            "compatibility": compatibility,
            "compatibility_reasons": reasons,
            "movement": OutcomeMovement(movement),
            "cause_attribution": cause,
            "changed_input_dimensions": dimensions,
            "controlled_equivalent_inputs": False,
            "baseline": baseline,
            "candidate": candidate,
            "driver_deltas": deltas,
            "excluded_driver_ids": excluded,
            "coverage_status": coverage,
            "notes": (
                "Bound digests hash the attached scan-comparison fields. "
                "Separate ruleset, package, and config bytes were not on this result.",
            ),
        }
    )


def _driver_delta(item: Any, cause: CauseAttribution) -> DriverDelta:
    return DriverDelta(
        driver_id=str(item.metric_name),
        comparison_unit=str(item.unit),
        base_value=_optional_text(item.base_value),
        candidate_value=_optional_text(item.candidate_value),
        delta=_optional_text(item.delta),
        compatible=bool(item.compatible),
        compatibility_reason=str(item.compatibility_reason or "unspecified"),
        cause=cause,
        outcome_role="outcome_driver",
        finding_lifecycle=None,
    )


def _bound(role: str, timestamp: str | None, deltas: Sequence[Any]) -> BoundDigests:
    payload = {
        "role": role,
        "timestamp": timestamp,
        "deltas": [item.model_dump(mode="json") for item in deltas],
    }
    shared = digest_canonical(payload)
    return BoundDigests(
        artifact_digest=digest_canonical({"part": "artifact", **payload}),
        ruleset_digest=digest_canonical({"part": "ruleset", **payload}),
        package_digest=digest_canonical({"part": "package", **payload}),
        config_digest=digest_canonical({"part": "config", **payload}),
        feed_digest=None,
        input_digest=shared,
        engine_version=__version__,
        dsl_version="1.0.0",
        outcome_driver_manifest_digest=outcome_driver_manifest_digest(),
    )


def _movement(comparison: ScanComparison) -> str:
    if comparison.compatibility_status.strip().lower() == "incompatible":
        return OutcomeMovement.INSUFFICIENT.value
    raw = comparison.summary.overall_movement
    if not raw:
        overall = comparison.outcome_verdicts.get("overall")
        raw = None if overall is None else overall.verdict
    token = _MOVEMENT.get(str(raw or "").strip().lower(), OutcomeMovement.INSUFFICIENT.value)
    return token


def _compatibility(
    comparison: ScanComparison,
) -> tuple[CompatibilityStatus, tuple[str, ...]]:
    raw = comparison.compatibility_status.strip().lower()
    if raw == "incompatible":
        status = CompatibilityStatus.INCOMPATIBLE
    elif raw == "unknown":
        status = CompatibilityStatus.UNKNOWN
    else:
        status = CompatibilityStatus.COMPATIBLE
    reasons = tuple(item for item in comparison.compatibility_reasons if item.strip())
    if status is CompatibilityStatus.INCOMPATIBLE and not reasons:
        reasons = ("incompatible",)
    if not reasons:
        reasons = (status.value,)
    return status, reasons


def _cause(
    comparison: ScanComparison,
) -> tuple[CauseAttribution, tuple[ChangedInputDimension, ...]]:
    attribution = comparison.cause_attribution
    if attribution is None:
        return CauseAttribution.UNDETERMINED, ()
    cause = _CAUSE.get(attribution.attribution, CauseAttribution.UNDETERMINED)
    dimensions = tuple(
        _DIMENSION[item]
        for item in attribution.changed_dimensions
        if item in _DIMENSION
    )
    isolated = {
        ChangedInputDimension.SOURCE,
        ChangedInputDimension.FEED,
        ChangedInputDimension.CONFIGURATION,
    }
    if len([item for item in dimensions if item in isolated]) > 1:
        cause = CauseAttribution.MIXED
    return cause, dimensions


def _comparison_explanation(
    compatibility: CompatibilityStatus,
    reasons: tuple[str, ...],
    movement: str,
) -> str:
    if compatibility is CompatibilityStatus.INCOMPATIBLE or movement in {
        OutcomeMovement.INSUFFICIENT.value,
        OutcomeMovement.NOT_APPLICABLE.value,
    }:
        return f"{compatibility.value} comparison; {', '.join(reasons)}"
    return f"Movement {movement} is copied from the scan comparison."


def _coverage(hotspots: tuple[EngineeringHotspot, ...]) -> tuple[CapabilityCoverage, ...]:
    if hotspots:
        partial = any(item.list_kind is HotspotListKind.PARTIAL_OR_UNKNOWN for item in hotspots)
        hotspot_coverage = _unknown_coverage(
            "quality.m22.hotspots",
            "partial_hotspot_list" if partial else "hotspot_records_attached",
        )
        if not partial:
            hotspot_coverage = CapabilityCoverage(
                capability_id="quality.m22.hotspots",
                capability_version="1.0.0",
                scope="repository",
                applicability="applicable",
                execution_state=CoverageState.COMPLETE,
                evaluated_count=len(hotspots),
                eligible_count=len(hotspots),
                coverage_ratio=None,
                coverage_reason="hotspot_records_attached",
            )
    else:
        hotspot_coverage = _unknown_coverage("quality.m22.hotspots", "m22_records_not_attached")
    return (
        hotspot_coverage,
        _unknown_coverage("security.m13.vulnerabilities", "feed_not_attached"),
    )


def _freshness(hotspots: tuple[EngineeringHotspot, ...]) -> tuple[CapabilityFreshness, ...]:
    if hotspots:
        window = hotspots[0].history_window
        git = _unknown_freshness(
            "quality.m22.hotspots",
            "git_head_not_attached",
            f"Hotspot history window is {window}. Git head was not attached to this result.",
        )
    else:
        git = _unknown_freshness(
            "quality.m22.hotspots",
            "git_history_not_attached",
            "Git history is not attached to this analysis result.",
        )
    return (
        git,
        _unknown_freshness(
            "security.m13.vulnerabilities",
            "feed_missing",
            "Vulnerability feed is not attached to this analysis result.",
        ),
    )


def _missing_inputs(
    hotspots: tuple[EngineeringHotspot, ...],
    change_summary: ChangeSummary | None,
    observation: JourneyObservation | None = None,
) -> tuple[str, ...]:
    if observation is not None:
        return observation.limitations
    limits = ["feed_not_attached"]
    if not hotspots:
        limits.append("m22_records_not_attached")
        limits.append("git_history_not_attached")
    if change_summary is None:
        limits.append("change_summary_not_attached")
    return tuple(limits)


def _context_concern(comparison: ScanComparison | None) -> str | None:
    if comparison is None:
        return None
    names = [
        item.concern_class
        for item in comparison.change_concerns
        if item.role == "context_only"
    ]
    if not names:
        return None
    return ", ".join(names)


def _attached_models[T: BaseModel](
    raw: object,
    model_cls: type[T],
    *,
    label: str,
) -> tuple[tuple[T, ...], tuple[str, ...]]:
    rows = []
    failed = False
    for item in _as_items(raw):
        if isinstance(item, model_cls):
            rows.append(item)
            continue
        if isinstance(item, Mapping):
            try:
                rows.append(model_cls.model_validate(dict(item)))
            except ValidationError:
                failed = True
            continue
        failed = True
    limits = (f"{label}_rejected",) if failed else ()
    return tuple(rows), limits


def _keep_linked_hotspots(
    hotspots: tuple[EngineeringHotspot, ...],
    finding_ids: set[str],
) -> tuple[tuple[EngineeringHotspot, ...], tuple[str, ...]]:
    kept = []
    dropped = False
    for item in hotspots:
        if set(item.active_finding_ids) - finding_ids:
            dropped = True
            continue
        kept.append(item)
    limits = ("hotspot_finding_link_missing",) if dropped else ()
    return tuple(kept), limits


def _cover_referenced_evidence(
    evidence: tuple[EvidenceRecord, ...],
    extra_ids: Sequence[str],
    *,
    digest: str,
    revision: str,
) -> tuple[EvidenceRecord, ...]:
    rows = list(evidence)
    have = {item.evidence_id for item in rows}
    for eid in extra_ids:
        if eid in have:
            continue
        rows.append(
            EvidenceRecord(
                evidence_id=eid,
                source_kind="source",
                working_state_digest=digest,
                source_revision=revision,
                extractor_version=_EXTRACTOR,
                limitation="identifier copied from an attached canonical record",
            )
        )
        have.add(eid)
    return tuple(rows)


def _evidence(
    *,
    kind: str,
    digest: str,
    revision: str,
    locator: str,
    relative_path: str | None = None,
    span: str | None = None,
    limitation: str | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id(kind=kind, working_state_digest=digest, locator=locator),
        source_kind=kind,
        working_state_digest=digest,
        source_revision=revision,
        extractor_version=_EXTRACTOR,
        relative_path=relative_path,
        span=span,
        limitation=limitation,
    )


def _repository_key(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", name.strip()).strip("-")
    return cleaned or "repository"


def _working_digest(result: AnalysisResult) -> str:
    """Canonical file-inventory digest for the assessed path list.

    SHA-256 of the sorted file-path list (newline-joined). This value is stored
    on the canonical envelope as ``working_state_digest``. It is not a
    file-content digest, and it is not the Git working-state digest sealed in
    analysis metadata. The field name stays so evidence IDs and the canonical
    schema do not change.
    """

    files = "\n".join(sorted(result.repository.files))
    material = files or result.repository.name or "repository"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _source_revision(result: AnalysisResult) -> str:
    metadata = result.repository.metadata
    for key in ("source_revision", "commit_sha", "git_head"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unavailable"


def _unknown_coverage(capability_id: str, reason: str) -> CapabilityCoverage:
    return CapabilityCoverage(
        capability_id=capability_id,
        capability_version="1.0.0",
        scope="repository",
        applicability="applicable",
        execution_state=CoverageState.UNKNOWN,
        evaluated_count=None,
        eligible_count=None,
        coverage_ratio=None,
        coverage_reason=reason,
        limitations=(reason,),
    )


def _unknown_freshness(
    capability_id: str,
    reason: str,
    explanation: str,
) -> CapabilityFreshness:
    return CapabilityFreshness(
        capability_id=capability_id,
        state=FreshnessState.UNKNOWN,
        reason_code=reason,
        explanation=explanation,
    )


def _as_items(raw: object) -> tuple[object, ...]:
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes, Mapping)):
        return (raw,)
    if isinstance(raw, Sequence):
        return tuple(raw)
    return (raw,)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected an integer, got {type(value).__name__}")


def _optional_bool(value: object) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"
