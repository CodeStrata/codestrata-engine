"""Map Shared Rule ``RuleEvidence`` onto lightweight ``EvidenceRef`` envelopes."""

from __future__ import annotations

from codestrata.domain.evidence.language.identifiers import stable_evidence_id
from codestrata.domain.rules.enums import RuleEvidenceKind
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.results import RuleMatch
from codestrata.application.traceability.evidence_confidence import (
    apply_parent_confidence_bounds,
    derive_evidence_confidence_for_rule_evidence,
)
from codestrata.domain.traceability import (
    EvidenceKind,
    EvidenceLocation,
    EvidenceMeasurement,
    EvidenceProductionMode,
    EvidenceRef,
    GraphKind,
    GraphReference,
    GraphReferenceKind,
    LocationKind,
    LocationPrecision,
    MeasurementComparisonResult,
    MeasurementScope,
    MeasurementValueType,
    RedactedSnippet,
    SnippetRedactionLevel,
    SnippetSourceKind,
    ThresholdOperator,
    TraceabilityValidationError,
    normalize_traceability_path,
)
from codestrata.security.redaction import redact_secrets

# Packs fully wired in Slice 2.2. Others remain legacy/empty at the mapper.
TRACEABLE_PACK_PREFIXES: tuple[str, ...] = (
    "security.",
    "dependency.",
    "technical_debt.",
    "architecture.",
)

_KIND_MAP: dict[RuleEvidenceKind, EvidenceKind] = {
    RuleEvidenceKind.FILE_LOCATION: EvidenceKind.FILE_LOCATION,
    RuleEvidenceKind.SYMBOL: EvidenceKind.OTHER,
    RuleEvidenceKind.PACKAGE: EvidenceKind.DECLARATION,
    RuleEvidenceKind.MODULE: EvidenceKind.OTHER,
    RuleEvidenceKind.DEPENDENCY: EvidenceKind.DECLARATION,
    RuleEvidenceKind.GRAPH_NODE: EvidenceKind.GRAPH,
    RuleEvidenceKind.GRAPH_EDGE: EvidenceKind.GRAPH,
    RuleEvidenceKind.CONFIGURATION_KEY: EvidenceKind.CONFIGURATION,
    RuleEvidenceKind.REPOSITORY_FACT: EvidenceKind.REPOSITORY_FACT,
    RuleEvidenceKind.ENTERPRISE_RELATIONSHIP: EvidenceKind.GRAPH,
    RuleEvidenceKind.ASSESSMENT_ARTIFACT: EvidenceKind.ARTIFACT,
}


def pack_is_traceable(rule_id: str, provenance: str) -> bool:
    rule = str(rule_id)
    prov = str(provenance)
    return any(
        rule.startswith(prefix) or prov.startswith(prefix) or prov.startswith(prefix.rstrip("."))
        for prefix in TRACEABLE_PACK_PREFIXES
    )


def evidence_ref_from_rule_evidence(
    item: RuleEvidence,
    *,
    rule_id: str,
    rule_version: str | None = None,
    pack_id: str | None = None,
    production_mode: EvidenceProductionMode = EvidenceProductionMode.DIRECT,
) -> EvidenceRef | None:
    """Convert one RuleEvidence item to EvidenceRef, or ``None`` if unusable."""

    attrs = dict(item.attributes)
    limitations: list[str] = []

    evidence_id = _resolve_evidence_id(item, attrs=attrs, rule_id=rule_id)
    location, location_limits = _map_location(item)
    limitations.extend(location_limits)

    snippet, snippet_limits = _map_snippet(item, attrs=attrs)
    limitations.extend(snippet_limits)

    measurement = _map_measurement(attrs)
    graph_ref = _map_graph(item)

    parent_ids = _parent_ids(attrs, evidence_id=evidence_id)
    provider_id = attrs.get("provider_id") or None
    provider_version = attrs.get("provider_version") or None
    analyzer_id = attrs.get("analyzer_id") or None
    analyzer_version = attrs.get("analyzer_version") or None
    kind = _KIND_MAP.get(item.kind, EvidenceKind.OTHER)
    evidence_confidence = derive_evidence_confidence_for_rule_evidence(
        item,
        kind=kind,
        production_mode=production_mode,
        location=location,
        snippet=snippet,
        has_measurement=measurement is not None,
        has_graph=graph_ref is not None,
        provider_id=provider_id,
        provider_version=provider_version,
        parent_evidence_ids=parent_ids,
        envelope_limitations=tuple(limitations),
    )

    try:
        return EvidenceRef(
            evidence_id=evidence_id,
            kind=kind,
            production_mode=production_mode,
            pack_id=pack_id or attrs.get("pack_id") or None,
            provider_id=provider_id,
            provider_version=provider_version,
            analyzer_id=analyzer_id,
            analyzer_version=analyzer_version,
            rule_id=rule_id,
            rule_version=rule_version,
            location=location,
            snippet=snippet,
            measurement=measurement,
            graph_ref=graph_ref,
            parent_evidence_ids=parent_ids,
            domain_ref=attrs.get("evidence_id") or None,
            limitations=tuple(limitations),
            source_artifact=attrs.get("source_artifact") or None,
            confidence=attrs.get("confidence") or None,
            evidence_confidence=evidence_confidence,
        )
    except (TraceabilityValidationError, ValueError):
        return None


def evidence_refs_from_rule_match(
    match: RuleMatch,
    *,
    pack_id: str | None = None,
) -> tuple[tuple[EvidenceRef, ...], tuple[str, ...], int]:
    """Map all match evidence; return (refs, limitations, source_count)."""

    rule_id = str(match.rule_id)
    rule_version = str(match.rule_version)
    resolved_pack = pack_id or _pack_id_from_match(match)
    limitations: list[str] = []
    refs: list[EvidenceRef] = []
    source_count = len(match.evidence)

    if not pack_is_traceable(rule_id, match.provenance):
        return (
            (),
            ("evidence_ref_mapping_deferred_for_pack",),
            source_count,
        )

    mode = (
        EvidenceProductionMode.AGGREGATED
        if source_count > 1
        else EvidenceProductionMode.DIRECT
    )
    for item in match.evidence:
        # Multi-evidence dependency conflicts stay direct per-item with parents.
        item_mode = mode
        if item.attributes.get("participating_evidence_ids"):
            item_mode = EvidenceProductionMode.AGGREGATED
        mapped = evidence_ref_from_rule_evidence(
            item,
            rule_id=rule_id,
            rule_version=rule_version,
            pack_id=resolved_pack,
            production_mode=item_mode,
        )
        if mapped is None:
            limitations.append("rule_evidence_unmapped")
            continue
        refs.append(mapped)

    bounded = apply_parent_confidence_bounds(tuple(refs))
    return bounded, tuple(sorted(set(limitations))), source_count


def _pack_id_from_match(match: RuleMatch) -> str | None:
    provenance = (match.provenance or "").strip()
    if provenance.endswith(".core"):
        return provenance[: -len(".core")]
    rule_id = str(match.rule_id)
    for prefix in TRACEABLE_PACK_PREFIXES:
        if rule_id.startswith(prefix):
            return prefix.rstrip(".")
    return None


def _resolve_evidence_id(
    item: RuleEvidence,
    *,
    attrs: dict[str, str],
    rule_id: str,
) -> str:
    existing = (attrs.get("evidence_id") or "").strip()
    if existing:
        return existing
    subject = item.subject_reference.strip()
    if subject.startswith("ev:") or ":" in subject and not subject.startswith("{"):
        # Prefer existing domain-style IDs carried as subject_reference.
        if subject.startswith("ev:") or any(
            subject.startswith(prefix)
            for prefix in (
                "test-file:",
                "cloud-",
                "dep-",
                "sensitive-",
                "complexity.",
            )
        ):
            return subject
    return stable_evidence_id(
        "rule_evidence",
        rule_id,
        item.kind.value,
        subject,
        item.safe_location or "",
        str(item.line_start or ""),
        str(item.line_end or ""),
    )


def _map_location(
    item: RuleEvidence,
) -> tuple[EvidenceLocation | None, list[str]]:
    limits: list[str] = []
    path = item.safe_location
    symbolic = None
    if path:
        try:
            path = normalize_traceability_path(path)
        except TraceabilityValidationError:
            limits.append("unsafe_or_absolute_path_omitted")
            symbolic = item.subject_reference
            path = None
    elif item.subject_reference:
        symbolic = item.subject_reference

    if path is None and symbolic is None:
        return None, limits

    try:
        if path is not None and item.line_start is not None:
            location = EvidenceLocation(
                path=path,
                line_start=item.line_start,
                line_end=item.line_end or item.line_start,
                symbolic_reference=symbolic,
                location_kind=LocationKind.FILE_SPAN,
                precision=LocationPrecision.EXACT,
            )
        elif path is not None:
            location = EvidenceLocation(
                path=path,
                symbolic_reference=symbolic,
                location_kind=LocationKind.FILE,
                precision=LocationPrecision.PATH_ONLY,
            )
        else:
            location = EvidenceLocation(
                symbolic_reference=symbolic,
                location_kind=LocationKind.SYMBOLIC,
                precision=LocationPrecision.SYMBOLIC_ONLY,
            )
        return location, limits
    except (TraceabilityValidationError, ValueError):
        limits.append("location_unmapped")
        return None, limits


def _map_snippet(
    item: RuleEvidence,
    *,
    attrs: dict[str, str],
) -> tuple[RedactedSnippet | None, list[str]]:
    limits: list[str] = []
    preview = (attrs.get("redacted_preview") or "").strip()
    if preview:
        try:
            return (
                RedactedSnippet(
                    text=preview,
                    redaction_level=SnippetRedactionLevel.PARTIALLY_REDACTED,
                    fingerprint=item.excerpt_fingerprint,
                    redaction_reasons=("collector_redacted_preview",),
                    source_kind=SnippetSourceKind.CONFIGURATION_VALUE,
                ),
                limits,
            )
        except (TraceabilityValidationError, ValueError):
            limits.append("redacted_preview_unmapped")
            return None, limits

    # Prefer collector-provided redacted_preview. For diagnostic messages, only
    # attach a snippet when redact_secrets actually masks content — never claim
    # SAFE_NONSENSITIVE for unverified free text (fail closed).
    message = (item.message or "").strip()
    if not message:
        return None, limits
    redacted = redact_secrets(message).strip()
    if not redacted:
        limits.append("snippet_omitted_after_redaction")
        return None, limits
    if redacted == message:
        limits.append("snippet_omitted_unverified_redaction")
        return None, limits
    try:
        return (
            RedactedSnippet(
                text=redacted,
                redaction_level=SnippetRedactionLevel.PARTIALLY_REDACTED,
                fingerprint=item.excerpt_fingerprint,
                redaction_reasons=("secret_pattern_redaction",),
                source_kind=SnippetSourceKind.MESSAGE,
            ),
            limits,
        )
    except (TraceabilityValidationError, ValueError):
        limits.append("snippet_omitted")
        return None, limits


def _map_measurement(attrs: dict[str, str]) -> EvidenceMeasurement | None:
    metric = (attrs.get("metric") or "").strip()
    value_text = (attrs.get("value") or "").strip()
    if not metric or not value_text:
        # Dependency version measurement when structurally present.
        version = (attrs.get("resolved_version_local") or attrs.get("raw_version") or "").strip()
        if not version:
            return None
        try:
            return EvidenceMeasurement.available(
                metric_id="dependency.version",
                metric_name="declared_or_resolved_version",
                measured_value=version,
                value_type=MeasurementValueType.STRING,
                scope=MeasurementScope.ARTIFACT,
                comparison_result=MeasurementComparisonResult.NOT_COMPARED,
                threshold_operator=ThresholdOperator.NONE,
            )
        except (TraceabilityValidationError, ValueError):
            return None

    try:
        number = int(value_text)
    except ValueError:
        try:
            number = float(value_text)
        except ValueError:
            return None

    threshold_text = (attrs.get("threshold") or "").strip()
    threshold: int | float | None
    try:
        threshold = int(threshold_text) if threshold_text else None
    except ValueError:
        try:
            threshold = float(threshold_text) if threshold_text else None
        except ValueError:
            threshold = None

    try:
        scope = MeasurementScope.CALLABLE
        if (attrs.get("type_kind") or "").strip():
            scope = MeasurementScope.TYPE
        elif (attrs.get("callable_kind") or "").strip():
            scope = MeasurementScope.CALLABLE
        if threshold is None:
            return EvidenceMeasurement.available(
                metric_id=f"measurement.{metric}",
                metric_name=metric,
                measured_value=number,
                value_type=MeasurementValueType.INTEGER
                if isinstance(number, int)
                else MeasurementValueType.NUMBER,
                scope=scope,
            )
        return EvidenceMeasurement.available(
            metric_id=f"measurement.{metric}",
            metric_name=metric,
            measured_value=number,
            value_type=MeasurementValueType.INTEGER
            if isinstance(number, int)
            else MeasurementValueType.NUMBER,
            threshold=threshold,
            threshold_operator=ThresholdOperator.GT,
            comparison_result=(
                MeasurementComparisonResult.FAILS
                if number > threshold
                else MeasurementComparisonResult.PASSES
            ),
            scope=scope,
            threshold_source="rule_threshold",
        )
    except (TraceabilityValidationError, ValueError):
        return None


def _map_graph(item: RuleEvidence) -> GraphReference | None:
    ref = item.graph_relationship_reference
    if not ref:
        if item.kind is RuleEvidenceKind.GRAPH_NODE:
            try:
                return GraphReference(
                    graph_id="assessment-graph",
                    graph_kind=GraphKind.ASSESSMENT_GRAPH,
                    reference_kind=GraphReferenceKind.NODE,
                    node_ids=(item.subject_reference,),
                )
            except (TraceabilityValidationError, ValueError):
                return None
        if item.kind is RuleEvidenceKind.GRAPH_EDGE:
            try:
                return GraphReference(
                    graph_id="assessment-graph",
                    graph_kind=GraphKind.ASSESSMENT_GRAPH,
                    reference_kind=GraphReferenceKind.EDGE,
                    edge_ids=(item.subject_reference,),
                )
            except (TraceabilityValidationError, ValueError):
                return None
        return None
    try:
        return GraphReference(
            graph_id="architecture-view",
            graph_kind=GraphKind.ARCHITECTURE_VIEW,
            reference_kind=GraphReferenceKind.RELATIONSHIP,
            relationship_type=ref,
            primary_subject_id=item.subject_reference,
        )
    except (TraceabilityValidationError, ValueError):
        return None


def _parent_ids(attrs: dict[str, str], *, evidence_id: str | None = None) -> tuple[str, ...]:
    raw = (attrs.get("participating_evidence_ids") or attrs.get("parent_evidence_ids") or "").strip()
    if not raw:
        return ()
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if evidence_id:
        parts = [part for part in parts if part != evidence_id]
    return tuple(sorted(set(parts)))
