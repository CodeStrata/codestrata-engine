"""E10.1 / M28 versioned finding matching and compatible metric deltas.

Matches findings across two explicit compatible canonical states using stable
rule/subject/occurrence identity. Evaluates lifecycle states:
- new: finding newly established with compatible coverage
- resolved: finding absent only after complete compatible reevaluation
- improved: persistent finding whose violation magnitude decreased favorably
- worsened: persistent finding whose violation magnitude increased unfavorably
- unchanged: persistent binary violation, same magnitude, or message-only change
- unknown: incompatible rules, coverage loss/incomplete coverage, or unknown comparator

Standing rules:
- Absence under failed/incomplete coverage NEVER resolves a finding (marked UNKNOWN).
- Message-only changes keep identity (never treated as new/resolved).
- Severity overrides are configuration changes, not source fixes (distinguished cause).
- Persistent findings improve/worsen ONLY against a rule-declared compatible violation magnitude.
- A remaining binary violation is UNCHANGED.
- Without a comparable magnitude, intermediate movement is not invented.
- Old incompatible snapshots are explicitly unsupported/incompatible, never silently converted.
- Metric deltas (candidate - base) computed with pinned units and scope.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from codestrata.domain.contracts.enums import OutcomeMovement
from codestrata.models.analysis_result import AnalysisResult
from codestrata.models.finding import Finding
from codestrata.models.scan_comparison import (
    CauseAttribution,
    ChangeConcern,
    ComparedFinding,
    ComparisonSummary,
    GraphDelta,
    MetricDelta,
    OutcomeMovementVerdict,
    ScanComparison,
    SeverityChange,
    StaticBlastRadius,
)

LIFECYCLE_SCHEMA = "codestrata.m28-finding-lifecycle.v1"
LIFECYCLE_VERSION = "1.0.0"


class FindingLifecycleState(StrEnum):
    """M28 finding lifecycle states."""

    NEW = "new"
    RESOLVED = "resolved"
    IMPROVED = "improved"
    WORSENED = "worsened"
    UNCHANGED = "unchanged"
    UNKNOWN = "unknown"


class MagnitudeComparator(StrEnum):
    """Declared comparator for rule violation magnitude."""

    LOWER_IS_BETTER = "lower_is_better"
    HIGHER_IS_BETTER = "higher_is_better"
    UNKNOWN = "unknown"


class CompatibilityStatus(StrEnum):
    """Compatibility status between two canonical states."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    NO_BASELINE = "no_baseline"
    UNKNOWN = "unknown"


class RuleMagnitudeSpec(BaseModel):
    """Rule declaration of magnitude measurement and comparator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    is_binary: bool = True
    unit: str | None = None
    comparator: MagnitudeComparator = MagnitudeComparator.LOWER_IS_BETTER
    threshold: float | int | None = None
    condition_operator: str | None = None


class CanonicalFinding(BaseModel):
    """Normalized finding representation for M28 matching and lifecycle evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    finding_id: str
    rule_id: str
    rule_version: str | None = None
    category: str = "general"
    severity: str = "medium"
    title: str = ""
    description: str = ""
    file_path: str | None = None
    line_number: int | None = None
    occurrence_id: str | None = None
    identity_key: str | None = None
    magnitude: float | int | None = None
    is_binary: bool = True
    is_policy_override: bool = False
    evidence_digest: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalMetric(BaseModel):
    """Normalized metric record for M28 compatible delta calculation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str
    value: float | int | str | None = None
    unit: str
    scope: str = "repository"
    direction: str = "neutral"
    coverage_status: str = "pass"
    formula_version: str = "v1"
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalScanState(BaseModel):
    """Explicit canonical state for one scan run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_digest: str
    ruleset_version: str | None = None
    ruleset_digest: str | None = None
    config_digest: str | None = None
    feed_digest: str | None = None
    coverage_status: str = "pass"
    evaluated_rule_ids: frozenset[str] = Field(default_factory=frozenset)
    disabled_rule_ids: frozenset[str] = Field(default_factory=frozenset)
    findings: tuple[CanonicalFinding, ...] = ()
    metrics: tuple[CanonicalMetric, ...] = ()
    rename_map: dict[str, str] = Field(default_factory=dict)


class FindingLifecycleRecord(BaseModel):
    """Detailed record for one matched or unmatched finding under M28."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    identity_key: str
    rule_id: str
    lifecycle: FindingLifecycleState
    base_finding: CanonicalFinding | None = None
    candidate_finding: CanonicalFinding | None = None
    base_severity: str | None = None
    candidate_severity: str | None = None
    base_magnitude: float | int | None = None
    candidate_magnitude: float | int | None = None
    magnitude_delta: float | int | None = None
    comparator: str | None = None
    is_binary: bool = True
    is_policy_override: bool = False
    compatibility_status: CompatibilityStatus = CompatibilityStatus.COMPATIBLE
    compatibility_reasons: tuple[str, ...] = ()
    cause: str = "source"
    message_changed: bool = False
    location_moved: bool = False


class MetricDeltaRecord(BaseModel):
    """Deterministic metric delta calculation between two canonical states."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str
    unit: str
    scope: str
    base_value: float | int | str | None = None
    candidate_value: float | int | str | None = None
    delta: float | int | str | None = None
    direction: str = "neutral"
    compatible: bool = True
    compatibility_reason: str = "compatible"
    formula_version: str = "v1"
    evidence_ids: tuple[str, ...] = ()
    coverage_status: str = "pass"


class M28ComparisonResult(BaseModel):
    """Complete M28 finding lifecycle and compatible metric deltas."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = LIFECYCLE_SCHEMA
    schema_version: str = LIFECYCLE_VERSION
    base_artifact_digest: str
    candidate_artifact_digest: str
    matching_rule_version: str | None = None
    compatibility_status: CompatibilityStatus
    compatibility_reasons: tuple[str, ...] = ()
    findings: tuple[FindingLifecycleRecord, ...] = ()
    metric_deltas: tuple[MetricDeltaRecord, ...] = ()
    new_findings: tuple[FindingLifecycleRecord, ...] = ()
    resolved_findings: tuple[FindingLifecycleRecord, ...] = ()
    improved_findings: tuple[FindingLifecycleRecord, ...] = ()
    worsened_findings: tuple[FindingLifecycleRecord, ...] = ()
    unchanged_findings: tuple[FindingLifecycleRecord, ...] = ()
    unknown_findings: tuple[FindingLifecycleRecord, ...] = ()
    severity_changes: tuple[FindingLifecycleRecord, ...] = ()
    new_count: int = 0
    resolved_count: int = 0
    improved_count: int = 0
    worsened_count: int = 0
    unchanged_count: int = 0
    unknown_count: int = 0
    severity_override_count: int = 0
    empty_outcome: bool = False
    disabled_all: bool = False


def compute_finding_identity(
    finding: CanonicalFinding | Finding,
    *,
    rename_map: Mapping[str, str] | None = None,
    occurrence_index: int = 0,
) -> str:
    """Compute a stable finding identity that survives message edits and renames."""
    metadata = finding.metadata if isinstance(finding, (CanonicalFinding, Finding)) else {}
    explicit_key = metadata.get("identity_key")
    if explicit_key:
        key_str = str(explicit_key)
        if rename_map:
            for old_p, new_p in rename_map.items():
                if old_p in key_str:
                    key_str = key_str.replace(old_p, new_p)
        return key_str

    rule_id = finding.rule_id or "unknown_rule"
    subject = metadata.get("subject_id")

    if not subject:
        if isinstance(finding, CanonicalFinding):
            subject = finding.file_path or ""
        elif isinstance(finding, Finding):
            subject = finding.evidence[0].file_path if finding.evidence else ""

    if rename_map and subject in rename_map:
        subject = rename_map[subject]

    occurrence = metadata.get("occurrence_id")
    if occurrence is None:
        occurrence = occurrence_index

    pos_parts: list[str] = []
    if isinstance(finding, CanonicalFinding):
        if finding.line_number is not None:
            pos_parts.append(str(finding.line_number))
    elif isinstance(finding, Finding) and finding.evidence:
        ev = finding.evidence[0]
        if ev.line_number is not None:
            pos_parts.append(str(ev.line_number))

    pos_str = ":".join(pos_parts) if pos_parts else "0"
    return f"rule:{rule_id}::subject:{subject}::occ:{occurrence}::{pos_str}"


def canonical_state_from_analysis_result(
    result: AnalysisResult,
    *,
    artifact_digest: str | None = None,
    coverage_status: str | None = None,
    rename_map: Mapping[str, str] | None = None,
    rule_specs: Mapping[str, RuleMagnitudeSpec] | None = None,
) -> CanonicalScanState:
    """Build a CanonicalScanState from an in-memory AnalysisResult."""
    digest = artifact_digest or str(result.metadata.get("artifact_digest") or result.id)
    cov = coverage_status or str(result.metadata.get("coverage_status") or "pass")
    rule_specs = rule_specs or {}

    canonical_findings: list[CanonicalFinding] = []
    for idx, f in enumerate(result.findings):
        spec = rule_specs.get(f.rule_id or "")
        magnitude = f.metadata.get("violation_magnitude") or f.metadata.get("magnitude")
        if magnitude is None and f.evidence and f.evidence[0].detected_value:
            try:
                raw_val = f.evidence[0].detected_value
                magnitude = float(raw_val) if "." in raw_val else int(raw_val)
            except (ValueError, TypeError):
                magnitude = None

        is_binary = spec.is_binary if spec else (magnitude is None)
        is_override = bool(
            f.metadata.get("severity_override")
            or f.metadata.get("is_policy_override")
            or f.metadata.get("policy_override")
        )
        file_path = f.evidence[0].file_path if f.evidence else None
        line_num = f.evidence[0].line_number if f.evidence else None

        explicit_key = f.metadata.get("identity_key")
        ident_key = str(explicit_key) if explicit_key else compute_finding_identity(
            f, occurrence_index=idx
        )

        cf = CanonicalFinding(
            finding_id=str(f.id),
            rule_id=f.rule_id or "unknown",
            rule_version=str(f.metadata.get("rule_version") or result.ruleset_version or "1.0.0"),
            category=getattr(f.category, "value", str(f.category)),
            severity=getattr(f.severity, "value", str(f.severity)),
            title=f.title,
            description=f.description,
            file_path=file_path,
            line_number=line_num,
            occurrence_id=str(f.metadata.get("occurrence_id") or idx),
            identity_key=ident_key,
            magnitude=magnitude,
            is_binary=is_binary,
            is_policy_override=is_override,
            evidence_digest=str(f.metadata.get("evidence_digest") or ""),
            metadata=dict(f.metadata),
        )
        canonical_findings.append(cf)

    metrics_list: list[CanonicalMetric] = []
    metrics_dict = result.metadata.get("metrics")
    if isinstance(metrics_dict, Mapping):
        for name, meta in metrics_dict.items():
            if isinstance(meta, Mapping):
                metrics_list.append(
                    CanonicalMetric(
                        metric_name=name,
                        value=meta.get("value"),
                        unit=str(meta.get("unit") or "count"),
                        scope=str(meta.get("scope") or "repository"),
                        direction=str(meta.get("direction") or "neutral"),
                        coverage_status=str(meta.get("coverage_status") or "pass"),
                        formula_version=str(meta.get("formula_version") or "v1"),
                        evidence_ids=tuple(meta.get("evidence_ids") or ()),
                    )
                )

    evaluated_rules = frozenset(
        result.metadata.get("evaluated_rule_ids")
        or {f.rule_id for f in canonical_findings if f.rule_id}
    )
    disabled_rules = frozenset(result.metadata.get("disabled_rule_ids") or ())

    return CanonicalScanState(
        artifact_digest=digest,
        ruleset_version=result.ruleset_version,
        ruleset_digest=str(result.metadata.get("ruleset_digest") or ""),
        config_digest=str(result.metadata.get("config_digest") or ""),
        feed_digest=str(result.metadata.get("feed_digest") or ""),
        coverage_status=cov,
        evaluated_rule_ids=evaluated_rules,
        disabled_rule_ids=disabled_rules,
        findings=tuple(canonical_findings),
        metrics=tuple(metrics_list),
        rename_map=dict(rename_map or {}),
    )


def evaluate_finding_lifecycle(
    base: CanonicalScanState,
    candidate: CanonicalScanState,
    *,
    rule_specs: Mapping[str, RuleMagnitudeSpec] | None = None,
    finding_causes: Mapping[str, str] | None = None,
    feed_changed: bool = False,
    source_changed: bool = True,
) -> tuple[FindingLifecycleRecord, ...]:
    """Evaluate M28 finding lifecycle over two explicit compatible states."""
    rule_specs = rule_specs or {}
    finding_causes = finding_causes or {}
    rename_map = candidate.rename_map

    base_by_key: dict[str, CanonicalFinding] = {}
    for idx, f in enumerate(base.findings):
        key = compute_finding_identity(f, rename_map=rename_map, occurrence_index=idx)
        base_by_key[key] = f

    candidate_by_key: dict[str, CanonicalFinding] = {}
    for idx, f in enumerate(candidate.findings):
        key = compute_finding_identity(f, occurrence_index=idx)
        candidate_by_key[key] = f

    all_keys = sorted(set(base_by_key) | set(candidate_by_key))
    records: list[FindingLifecycleRecord] = []

    states_compatible = True
    incompatibility_reasons: list[str] = []
    if base.ruleset_version and candidate.ruleset_version:
        base_major = base.ruleset_version.split(".")[0]
        cand_major = candidate.ruleset_version.split(".")[0]
        if base_major != cand_major:
            states_compatible = False
            incompatibility_reasons.append("incompatible_ruleset_major_version")

    candidate_coverage_ok = candidate.coverage_status == "pass"

    for key in all_keys:
        bf = base_by_key.get(key)
        cf = candidate_by_key.get(key)

        if bf is None and cf is not None:
            spec = rule_specs.get(cf.rule_id)
            is_bin = spec.is_binary if spec else cf.is_binary
            rule_eval = cf.rule_id in base.evaluated_rule_ids or not base.evaluated_rule_ids
            if not states_compatible:
                lifecycle = FindingLifecycleState.UNKNOWN
                compat = CompatibilityStatus.INCOMPATIBLE
                reasons = tuple(incompatibility_reasons)
                cause = "configuration"
            elif base.coverage_status != "pass" and not rule_eval:
                lifecycle = FindingLifecycleState.UNKNOWN
                compat = CompatibilityStatus.UNKNOWN
                reasons = ("base_coverage_incomplete",)
                cause = "coverage"
            else:
                lifecycle = FindingLifecycleState.NEW
                compat = CompatibilityStatus.COMPATIBLE
                reasons = ()
                if key in finding_causes:
                    cause = finding_causes[key]
                elif cf.rule_id in finding_causes:
                    cause = finding_causes[cf.rule_id]
                elif cf.metadata.get("cause"):
                    cause = str(cf.metadata.get("cause"))
                elif cf.metadata.get("feed_driven") or cf.metadata.get("source") == "feed":
                    cause = "feed"
                elif feed_changed and not source_changed and (
                    cf.category.lower() == "security" or cf.rule_id.lower().startswith("cve")
                ):
                    cause = "feed"
                else:
                    cause = "source"

            records.append(
                FindingLifecycleRecord(
                    identity_key=key,
                    rule_id=cf.rule_id,
                    lifecycle=lifecycle,
                    candidate_finding=cf,
                    candidate_severity=cf.severity,
                    candidate_magnitude=cf.magnitude,
                    is_binary=is_bin,
                    compatibility_status=compat,
                    compatibility_reasons=reasons,
                    cause=cause,
                )
            )
            continue

        if bf is not None and cf is None:
            spec = rule_specs.get(bf.rule_id)
            is_bin = spec.is_binary if spec else bf.is_binary
            rule_reevaluated = (
                candidate_coverage_ok
                and (not candidate.evaluated_rule_ids or bf.rule_id in candidate.evaluated_rule_ids)
            )

            if not states_compatible:
                lifecycle = FindingLifecycleState.UNKNOWN
                compat = CompatibilityStatus.INCOMPATIBLE
                reasons = tuple(incompatibility_reasons)
                cause = "configuration"
            elif not rule_reevaluated:
                lifecycle = FindingLifecycleState.UNKNOWN
                compat = CompatibilityStatus.UNKNOWN
                reasons = ("incomplete_candidate_coverage",)
                cause = "coverage"
            else:
                lifecycle = FindingLifecycleState.RESOLVED
                compat = CompatibilityStatus.COMPATIBLE
                reasons = ()
                if key in finding_causes:
                    cause = finding_causes[key]
                elif bf.rule_id in finding_causes:
                    cause = finding_causes[bf.rule_id]
                elif bf.metadata.get("cause"):
                    cause = str(bf.metadata.get("cause"))
                elif bf.metadata.get("feed_driven") or bf.metadata.get("source") == "feed":
                    cause = "feed"
                elif (
                    bf.metadata.get("severity_override")
                    or (spec and getattr(spec, "disabled", False))
                ):
                    cause = "configuration"
                else:
                    cause = "source"

            records.append(
                FindingLifecycleRecord(
                    identity_key=key,
                    rule_id=bf.rule_id,
                    lifecycle=lifecycle,
                    base_finding=bf,
                    base_severity=bf.severity,
                    base_magnitude=bf.magnitude,
                    is_binary=is_bin,
                    compatibility_status=compat,
                    compatibility_reasons=reasons,
                    cause=cause,
                )
            )
            continue

        assert bf is not None and cf is not None
        spec = rule_specs.get(cf.rule_id)
        is_bin = spec.is_binary if spec else (cf.is_binary and bf.is_binary)
        comparator = spec.comparator if spec else MagnitudeComparator.UNKNOWN
        if not is_bin and comparator == MagnitudeComparator.UNKNOWN:
            meta_comp = cf.metadata.get("comparator") or bf.metadata.get("comparator")
            if meta_comp == "lower_is_better":
                comparator = MagnitudeComparator.LOWER_IS_BETTER
            elif meta_comp == "higher_is_better":
                comparator = MagnitudeComparator.HIGHER_IS_BETTER

        message_changed = (bf.title != cf.title) or (bf.description != cf.description)
        location_moved = (bf.file_path != cf.file_path) or (bf.line_number != cf.line_number)
        is_override = cf.is_policy_override or (
            bf.severity != cf.severity and cf.metadata.get("severity_override") is not None
        )

        if is_override:
            cause = "configuration"
        elif key in finding_causes:
            cause = finding_causes[key]
        elif cf.rule_id in finding_causes:
            cause = finding_causes[cf.rule_id]
        elif cf.metadata.get("cause"):
            cause = str(cf.metadata.get("cause"))
        elif cf.metadata.get("feed_driven") or cf.metadata.get("source") == "feed":
            cause = "feed"
        else:
            cause = "source"

        compat = CompatibilityStatus.COMPATIBLE
        reasons = ()

        if bf.rule_version and cf.rule_version:
            bf_maj = bf.rule_version.split(".")[0]
            cf_maj = cf.rule_version.split(".")[0]
            if bf_maj != cf_maj:
                compat = CompatibilityStatus.INCOMPATIBLE
                reasons = ("incompatible_rule_version",)

        if compat is CompatibilityStatus.INCOMPATIBLE:
            lifecycle = FindingLifecycleState.UNKNOWN
        elif is_bin:
            lifecycle = FindingLifecycleState.UNCHANGED
        elif bf.magnitude is None or cf.magnitude is None:
            lifecycle = FindingLifecycleState.UNCHANGED
        elif comparator is MagnitudeComparator.UNKNOWN:
            lifecycle = FindingLifecycleState.UNKNOWN
            reasons = ("unknown_comparator",)
        else:
            delta_val = cf.magnitude - bf.magnitude
            if delta_val == 0:
                lifecycle = FindingLifecycleState.UNCHANGED
            elif comparator is MagnitudeComparator.LOWER_IS_BETTER:
                lifecycle = (
                    FindingLifecycleState.IMPROVED
                    if delta_val < 0
                    else FindingLifecycleState.WORSENED
                )
            elif comparator is MagnitudeComparator.HIGHER_IS_BETTER:
                lifecycle = (
                    FindingLifecycleState.IMPROVED
                    if delta_val > 0
                    else FindingLifecycleState.WORSENED
                )
            else:
                lifecycle = FindingLifecycleState.UNCHANGED

        mag_delta = (
            (cf.magnitude - bf.magnitude)
            if (cf.magnitude is not None and bf.magnitude is not None)
            else None
        )

        records.append(
            FindingLifecycleRecord(
                identity_key=key,
                rule_id=cf.rule_id,
                lifecycle=lifecycle,
                base_finding=bf,
                candidate_finding=cf,
                base_severity=bf.severity,
                candidate_severity=cf.severity,
                base_magnitude=bf.magnitude,
                candidate_magnitude=cf.magnitude,
                magnitude_delta=mag_delta,
                comparator=comparator.value if comparator else None,
                is_binary=is_bin,
                is_policy_override=is_override,
                compatibility_status=compat,
                compatibility_reasons=reasons,
                cause=cause,
                message_changed=message_changed,
                location_moved=location_moved,
            )
        )

    return tuple(records)


def evaluate_metric_deltas(
    base: CanonicalScanState,
    candidate: CanonicalScanState,
) -> tuple[MetricDeltaRecord, ...]:
    """Calculate deterministic metric deltas (candidate - base) with pinned units and scope."""
    base_metrics = {m.metric_name: m for m in base.metrics}
    candidate_metrics = {m.metric_name: m for m in candidate.metrics}
    all_names = sorted(set(base_metrics) | set(candidate_metrics))

    deltas: list[MetricDeltaRecord] = []
    for name in all_names:
        bm = base_metrics.get(name)
        cm = candidate_metrics.get(name)

        if bm is None and cm is not None:
            deltas.append(
                MetricDeltaRecord(
                    metric_name=name,
                    unit=cm.unit,
                    scope=cm.scope,
                    candidate_value=cm.value,
                    direction=cm.direction,
                    compatible=True,
                    compatibility_reason="candidate_only",
                    formula_version=cm.formula_version,
                    evidence_ids=cm.evidence_ids,
                    coverage_status=cm.coverage_status,
                )
            )
            continue

        if bm is not None and cm is None:
            deltas.append(
                MetricDeltaRecord(
                    metric_name=name,
                    unit=bm.unit,
                    scope=bm.scope,
                    base_value=bm.value,
                    direction=bm.direction,
                    compatible=True,
                    compatibility_reason="base_only",
                    formula_version=bm.formula_version,
                    evidence_ids=bm.evidence_ids,
                    coverage_status=bm.coverage_status,
                )
            )
            continue

        assert bm is not None and cm is not None
        if bm.unit != cm.unit:
            deltas.append(
                MetricDeltaRecord(
                    metric_name=name,
                    unit=cm.unit,
                    scope=cm.scope,
                    base_value=bm.value,
                    candidate_value=cm.value,
                    compatible=False,
                    compatibility_reason=f"unit_mismatch: {bm.unit} vs {cm.unit}",
                    formula_version=cm.formula_version,
                )
            )
            continue

        if bm.scope != cm.scope:
            deltas.append(
                MetricDeltaRecord(
                    metric_name=name,
                    unit=cm.unit,
                    scope=cm.scope,
                    base_value=bm.value,
                    candidate_value=cm.value,
                    compatible=False,
                    compatibility_reason=f"scope_mismatch: {bm.scope} vs {cm.scope}",
                    formula_version=cm.formula_version,
                )
            )
            continue

        if bm.formula_version != cm.formula_version:
            deltas.append(
                MetricDeltaRecord(
                    metric_name=name,
                    unit=cm.unit,
                    scope=cm.scope,
                    base_value=bm.value,
                    candidate_value=cm.value,
                    compatible=False,
                    compatibility_reason=(
                        f"formula_version_mismatch: {bm.formula_version} vs {cm.formula_version}"
                    ),
                    formula_version=cm.formula_version,
                )
            )
            continue

        delta_val: float | int | str | None = None
        direction = "neutral"
        if (
            isinstance(bm.value, (int, float))
            and isinstance(cm.value, (int, float))
            and not isinstance(bm.value, bool)
            and not isinstance(cm.value, bool)
        ):
            if isinstance(bm.value, int) and isinstance(cm.value, int):
                delta_val = cm.value - bm.value
            else:
                try:
                    d_cand = Decimal(str(cm.value))
                    d_base = Decimal(str(bm.value))
                    delta_val = float(round(d_cand - d_base, 6))
                except InvalidOperation:
                    delta_val = round(float(cm.value) - float(bm.value), 6)

            if cm.direction == "lower_is_better":
                if delta_val < 0:
                    direction = "favorable"
                elif delta_val > 0:
                    direction = "unfavorable"
            elif cm.direction == "higher_is_better":
                if delta_val > 0:
                    direction = "favorable"
                elif delta_val < 0:
                    direction = "unfavorable"

        is_full_cov = bm.coverage_status == "pass" and cm.coverage_status == "pass"
        deltas.append(
            MetricDeltaRecord(
                metric_name=name,
                unit=cm.unit,
                scope=cm.scope,
                base_value=bm.value,
                candidate_value=cm.value,
                delta=delta_val,
                direction=direction,
                compatible=True,
                compatibility_reason="compatible",
                formula_version=cm.formula_version,
                evidence_ids=tuple(dict.fromkeys((*bm.evidence_ids, *cm.evidence_ids))),
                coverage_status="pass" if is_full_cov else "partial",
            )
        )

    return tuple(deltas)


def evaluate_m28(
    base: CanonicalScanState,
    candidate: CanonicalScanState,
    *,
    rule_specs: Mapping[str, RuleMagnitudeSpec] | None = None,
    finding_causes: Mapping[str, str] | None = None,
    feed_changed: bool = False,
    source_changed: bool = True,
) -> M28ComparisonResult:
    """Run complete M28 evaluation: finding lifecycles, metric deltas, and evidence."""
    rule_specs = rule_specs or {}
    findings = evaluate_finding_lifecycle(
        base,
        candidate,
        rule_specs=rule_specs,
        finding_causes=finding_causes,
        feed_changed=feed_changed,
        source_changed=source_changed,
    )
    metric_deltas = evaluate_metric_deltas(base, candidate)

    new_list = tuple(f for f in findings if f.lifecycle is FindingLifecycleState.NEW)
    resolved_list = tuple(f for f in findings if f.lifecycle is FindingLifecycleState.RESOLVED)
    improved_list = tuple(f for f in findings if f.lifecycle is FindingLifecycleState.IMPROVED)
    worsened_list = tuple(f for f in findings if f.lifecycle is FindingLifecycleState.WORSENED)
    unchanged_list = tuple(f for f in findings if f.lifecycle is FindingLifecycleState.UNCHANGED)
    unknown_list = tuple(f for f in findings if f.lifecycle is FindingLifecycleState.UNKNOWN)
    severity_changes = tuple(
        f
        for f in findings
        if f.base_severity is not None
        and f.candidate_severity is not None
        and f.base_severity != f.candidate_severity
    )
    severity_overrides = tuple(f for f in severity_changes if f.is_policy_override)

    empty_outcome = len(candidate.evaluated_rule_ids) == 0 and len(candidate.findings) == 0
    disabled_all = (
        len(candidate.disabled_rule_ids) > 0
        and len(candidate.evaluated_rule_ids - candidate.disabled_rule_ids) == 0
    )

    compat_status = CompatibilityStatus.COMPATIBLE
    compat_reasons: list[str] = []
    if base.ruleset_version and candidate.ruleset_version:
        if base.ruleset_version.split(".")[0] != candidate.ruleset_version.split(".")[0]:
            compat_status = CompatibilityStatus.INCOMPATIBLE
            compat_reasons.append("ruleset_major_version_incompatible")

    return M28ComparisonResult(
        schema_name=LIFECYCLE_SCHEMA,
        schema_version=LIFECYCLE_VERSION,
        base_artifact_digest=base.artifact_digest,
        candidate_artifact_digest=candidate.artifact_digest,
        matching_rule_version=candidate.ruleset_version or base.ruleset_version,
        compatibility_status=compat_status,
        compatibility_reasons=tuple(compat_reasons),
        findings=findings,
        metric_deltas=metric_deltas,
        new_findings=new_list,
        resolved_findings=resolved_list,
        improved_findings=improved_list,
        worsened_findings=worsened_list,
        unchanged_findings=unchanged_list,
        unknown_findings=unknown_list,
        severity_changes=severity_changes,
        new_count=len(new_list),
        resolved_count=len(resolved_list),
        improved_count=len(improved_list),
        worsened_count=len(worsened_list),
        unchanged_count=len(unchanged_list),
        unknown_count=len(unknown_list),
        severity_override_count=len(severity_overrides),
        empty_outcome=empty_outcome,
        disabled_all=disabled_all,
    )


def scan_comparison_from_m28(
    result: M28ComparisonResult,
    *,
    base_timestamp: str | None = None,
    candidate_timestamp: str | None = None,
    notes: Sequence[str] = (),
    fact_changes: Sequence[Any] = (),
    new_recommendations: Sequence[Any] = (),
    resolved_recommendations: Sequence[Any] = (),
    unchanged_recommendations: Sequence[Any] = (),
    priority_changes: Sequence[Any] = (),
    graph_delta: GraphDelta | None = None,
    blast_radius: StaticBlastRadius | None = None,
    change_summary: Any = None,
    change_concerns: Sequence[ChangeConcern] = (),
    outcome_verdicts: Mapping[str, OutcomeMovementVerdict] | None = None,
    cause_attribution: CauseAttribution | None = None,
) -> ScanComparison:
    """Project an M28ComparisonResult into the client-facing ScanComparison model."""
    def _to_compared_finding(rec: FindingLifecycleRecord) -> ComparedFinding:
        f = rec.candidate_finding or rec.base_finding
        assert f is not None
        return ComparedFinding(
            rule_id=rec.rule_id,
            title=f.title,
            category=f.category,
            severity=rec.candidate_severity or rec.base_severity or "medium",
            identity_key=rec.identity_key,
            lifecycle=rec.lifecycle.value,
            previous_severity=rec.base_severity,
            current_severity=rec.candidate_severity,
            previous_magnitude=rec.base_magnitude,
            current_magnitude=rec.candidate_magnitude,
            magnitude_delta=rec.magnitude_delta,
            comparator=rec.comparator,
            compatibility_status=rec.compatibility_status.value,
            compatibility_reasons=list(rec.compatibility_reasons),
            cause=rec.cause,
            is_policy_override=rec.is_policy_override,
            file_path=f.file_path,
            rule_version=f.rule_version,
        )

    new_findings = [_to_compared_finding(r) for r in result.new_findings]
    resolved_findings = [_to_compared_finding(r) for r in result.resolved_findings]
    improved_findings = [_to_compared_finding(r) for r in result.improved_findings]
    worsened_findings = [_to_compared_finding(r) for r in result.worsened_findings]
    unchanged_findings = [_to_compared_finding(r) for r in result.unchanged_findings]
    unknown_findings = [_to_compared_finding(r) for r in result.unknown_findings]

    sev_changes: list[SeverityChange] = []
    _rank = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    for rec in result.severity_changes:
        f = rec.candidate_finding or rec.base_finding
        assert f is not None
        p_rank = _rank.get((rec.base_severity or "").lower(), 0)
        c_rank = _rank.get((rec.candidate_severity or "").lower(), 0)
        direction: Literal["increased", "decreased"] = (
            "increased" if c_rank > p_rank else "decreased"
        )
        sev_changes.append(
            SeverityChange(
                rule_id=rec.rule_id,
                title=f.title,
                category=f.category,
                identity_key=rec.identity_key,
                previous_severity=rec.base_severity or "medium",
                current_severity=rec.candidate_severity or "medium",
                direction=direction,
                is_policy_override=rec.is_policy_override,
                cause=rec.cause,
            )
        )

    metric_deltas = [
        MetricDelta(
            metric_name=m.metric_name,
            unit=m.unit,
            scope=m.scope,
            base_value=m.base_value,
            candidate_value=m.candidate_value,
            delta=m.delta,
            direction=m.direction,
            compatible=m.compatible,
            compatibility_reason=m.compatibility_reason,
            formula_version=m.formula_version,
            evidence_ids=list(m.evidence_ids),
            coverage_status=m.coverage_status,
        )
        for m in result.metric_deltas
    ]

    all_compared_findings = [
        *new_findings,
        *resolved_findings,
        *improved_findings,
        *worsened_findings,
        *unchanged_findings,
        *unknown_findings,
    ]

    if outcome_verdicts is None:
        from codestrata.application.incremental.outcome_movement import (
            evaluate_outcome_movement,
        )

        cov_pass = result.compatibility_status == CompatibilityStatus.COMPATIBLE
        verdicts_map, overall_mov = evaluate_outcome_movement(
            compared_findings=all_compared_findings,
            metric_deltas=metric_deltas,
            baseline_available=True,
            is_empty_outcome=result.empty_outcome,
            disabled_all_scope=result.disabled_all,
            overall_coverage_pass=cov_pass,
        )
    else:
        verdicts_map = dict(outcome_verdicts)
        vals = [v.verdict for v in verdicts_map.values()]
        if any(x == "insufficient" for x in vals):
            overall_mov = OutcomeMovement.INSUFFICIENT
        elif any(x == "mixed" for x in vals):
            overall_mov = OutcomeMovement.MIXED
        elif any(x == "deteriorated" for x in vals) and any(x == "improved" for x in vals):
            overall_mov = OutcomeMovement.MIXED
        elif any(x == "deteriorated" for x in vals):
            overall_mov = OutcomeMovement.DETERIORATED
        elif any(x == "improved" for x in vals):
            overall_mov = OutcomeMovement.IMPROVED
        else:
            overall_mov = OutcomeMovement.STABLE

    overall_mov_val = overall_mov.value

    summary = ComparisonSummary(
        new_findings=len(new_findings),
        resolved_findings=len(resolved_findings),
        worsened_findings=len(worsened_findings),
        improved_findings=len(improved_findings),
        unchanged_findings=len(unchanged_findings),
        unknown_findings=len(unknown_findings),
        worsened_severities=sum(s.direction == "increased" for s in sev_changes),
        improved_severities=sum(s.direction == "decreased" for s in sev_changes),
        new_recommendations=len(new_recommendations),
        resolved_recommendations=len(resolved_recommendations),
        worsened_priorities=sum(
            getattr(p, "direction", "") == "increased" for p in priority_changes
        ),
        improved_priorities=sum(
            getattr(p, "direction", "") == "decreased" for p in priority_changes
        ),
        fact_changes=len(fact_changes),
        metric_deltas=len(metric_deltas),
        is_empty_outcome=result.empty_outcome,
        overall_movement=overall_mov_val,
        outcome_verdicts={k: v.verdict for k, v in verdicts_map.items()},
        affected_components=blast_radius.affected_component_count or 0 if blast_radius else 0,
        affected_tests=blast_radius.affected_test_count or 0 if blast_radius else 0,
        crossed_boundary_count=blast_radius.crossed_boundary_count or 0 if blast_radius else 0,
        high_concern_components=sum(
            1 for c in change_concerns if c.concern_class != "ordinary"
        ),
    )

    return ScanComparison(
        baseline_available=True,
        baseline_timestamp=base_timestamp,
        current_timestamp=candidate_timestamp,
        notes=list(notes),
        new_findings=new_findings,
        resolved_findings=resolved_findings,
        unchanged_findings=unchanged_findings,
        improved_findings=improved_findings,
        worsened_findings=worsened_findings,
        unknown_findings=unknown_findings,
        severity_changes=sev_changes,
        metric_deltas=metric_deltas,
        new_recommendations=list(new_recommendations),
        resolved_recommendations=list(resolved_recommendations),
        unchanged_recommendations=list(unchanged_recommendations),
        priority_changes=list(priority_changes),
        fact_changes=list(fact_changes),
        compatibility_status=result.compatibility_status.value,
        compatibility_reasons=list(result.compatibility_reasons),
        artifact_digests={
            "base": result.base_artifact_digest,
            "candidate": result.candidate_artifact_digest,
        },
        summary=summary,
        graph_delta=graph_delta,
        blast_radius=blast_radius,
        change_summary=change_summary,
        change_concerns=list(change_concerns),
        outcome_verdicts=verdicts_map,
        cause_attribution=cause_attribution,
    )
