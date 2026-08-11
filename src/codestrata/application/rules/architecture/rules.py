"""Architecture Intelligence SharedRules (Phase 4.2.1 / 4.2.1a)."""

from __future__ import annotations

from collections import Counter
from statistics import median

from codestrata.application.rules.architecture.helpers import (
    architecture_view,
    classification_coverage_ok,
    comparable_coupling_units,
    evidence_graph_edge,
    evidence_unit,
    make_metadata,
    match,
    min_coverage_ok,
)
from codestrata.application.rules.architecture.view_builder import (
    find_directed_cycles,
    incident_edge_shares,
)
from codestrata.domain.rules.applicability import RuleApplicability
from codestrata.domain.rules.architecture.ids import (
    RULE_COMPONENT_CONCENTRATION,
    RULE_DEPENDENCY_CYCLE,
    RULE_ENTERPRISE_STANDARD_MISMATCH,
    RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
    RULE_FRAMEWORK_LEAKAGE,
    RULE_INVALID_DEPENDENCY_DIRECTION,
    RULE_LAYER_BOUNDARY_VIOLATION,
)
from codestrata.domain.rules.context import RuleExecutionContext
from codestrata.domain.rules.enums import (
    MatchEvidenceConfidence,
    RuleEvidenceKind,
    RuleSeverity,
    RuleSkipReason,
)
from codestrata.domain.rules.evidence import RuleEvidence
from codestrata.domain.rules.metadata import RuleMetadata
from codestrata.domain.rules.results import SharedRuleEvaluationResult

_COMPOSITION_EDGE_KINDS = frozenset({"init_aggregation", "registration"})


class DependencyCycleRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_DEPENDENCY_CYCLE,
            title="Architecture dependency cycle",
            description=(
                "Detects directed dependency cycles between primary architectural units "
                "after nested-package collapse and dependency normalization."
            ),
            remediation=(
                "Break the cycle using dependency inversion, a stable abstraction, "
                "responsibility realignment, or a shared neutral module. Regenerate the "
                "package dependency graph to validate removal."
            ),
            severity=RuleSeverity.HIGH,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        view = architecture_view(context)
        if view is None:
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Architecture analysis view unavailable",
            )
        if not min_coverage_ok(view):
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Insufficient architecture extraction coverage",
            )
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        view = architecture_view(context)
        if view is None or not min_coverage_ok(view):
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Insufficient architecture extraction coverage",
            )
        cycles = find_directed_cycles(view.adjacency())
        if not cycles:
            return SharedRuleEvaluationResult.not_matched()
        matches = []
        for cycle in cycles:
            body = cycle[:-1]
            # Skip cycles composed only of composition-root / registration wiring.
            roles = {
                view.unit_map[node].role
                for node in body
                if node in view.unit_map
            }
            if roles.intersection({"composition_root", "registration"}):
                # Bootstrap / registration wiring is not reported as an architectural cycle.
                continue
            size = len(body)
            severity = RuleSeverity.MEDIUM if size <= 2 else RuleSeverity.HIGH
            path_text = " → ".join(cycle)
            edge_evidence = []
            for index in range(len(body)):
                source = body[index]
                target = body[(index + 1) % len(body)]
                edge = next(
                    (
                        item
                        for item in view.included_edges()
                        if item.source_unit_id == source and item.target_unit_id == target
                    ),
                    None,
                )
                edge_evidence.append(
                    evidence_graph_edge(
                        source=source,
                        target=target,
                        path=edge.evidence_paths[0] if edge and edge.evidence_paths else None,
                        message=f"Normalized cycle edge ({size} primary units)",
                        attributes={
                            "normalized_cycle": path_text,
                            "edge_kind": edge.edge_kind if edge else "runtime",
                            "raw_source": (edge.raw_source_package or source) if edge else source,
                            "raw_target": (edge.raw_target_package or target) if edge else target,
                            "unit_selection": view.unit_selection_policy,
                        },
                    )
                )
            confidence = (
                MatchEvidenceConfidence.HIGH
                if view.extraction_coverage >= 0.4
                else MatchEvidenceConfidence.MEDIUM
            )
            matches.append(
                match(
                    rule_id=RULE_DEPENDENCY_CYCLE,
                    title="Dependency cycle detected",
                    summary=(
                        f"A directed dependency cycle was observed among {size} primary "
                        f"architectural units ({path_text}) after nested-package collapse. "
                        "Cycles increase change coordination risk."
                    ),
                    severity=severity,
                    confidence=confidence,
                    evidence=tuple(edge_evidence[:20]),
                    subject_keys=("cycle", *body),
                    remediation=self.metadata.remediation_summary or "",
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(tuple(matches))


class InvalidDependencyDirectionRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_INVALID_DEPENDENCY_DIRECTION,
            title="Invalid dependency direction",
            description=(
                "Detects dependencies that violate the declared or conventional "
                "layer dependency direction for reliably classified primary units."
            ),
            remediation=(
                "Redirect the dependency toward the allowed inward direction, or move "
                "shared types behind an approved boundary interface."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        view = architecture_view(context)
        if view is None or not min_coverage_ok(view):
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Architecture view or extraction coverage insufficient",
            )
        if not classification_coverage_ok(view):
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Insufficient reliable layer classification coverage",
            )
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        view = architecture_view(context)
        if view is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Architecture view unavailable",
            )
        if not classification_coverage_ok(view):
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Insufficient reliable layer classification coverage",
            )
        allowed = set(view.allowed_layer_edges)
        unit_map = view.unit_map
        matches = []
        for edge in view.included_edges():
            if edge.edge_kind in _COMPOSITION_EDGE_KINDS:
                continue
            source = unit_map.get(edge.source_unit_id)
            target = unit_map.get(edge.target_unit_id)
            if source is None or target is None:
                continue
            if source.role == "composition_root":
                continue
            if (
                source.classification_confidence == "low"
                or target.classification_confidence == "low"
            ):
                continue
            if source.layer in {"unknown", "test"} or target.layer in {"unknown", "test"}:
                continue
            key = f"{source.layer}>{target.layer}"
            if key in allowed or source.layer == target.layer:
                continue
            path = edge.evidence_paths[0] if edge.evidence_paths else None
            matches.append(
                match(
                    rule_id=RULE_INVALID_DEPENDENCY_DIRECTION,
                    title="Invalid architectural dependency direction",
                    summary=(
                        f"Primary unit '{source.unit_id}' ({source.layer}) depends on "
                        f"'{target.unit_id}' ({target.layer}), which violates the governing "
                        f"direction rule '{source.layer} must not depend on {target.layer}' "
                        f"under model {view.layer_model}."
                    ),
                    severity=RuleSeverity.MEDIUM,
                    confidence=MatchEvidenceConfidence.MEDIUM,
                    evidence=(
                        evidence_graph_edge(
                            source=source.unit_id,
                            target=target.unit_id,
                            path=path,
                            message=(
                                f"Governing direction: allowed set excludes "
                                f"{source.layer}>{target.layer}"
                            ),
                            attributes={
                                "governing_rule": f"forbid:{source.layer}>{target.layer}",
                                "layer_model": view.layer_model,
                                "source_confidence": source.classification_confidence,
                                "target_confidence": target.classification_confidence,
                                "edge_kind": edge.edge_kind,
                            },
                        ),
                    ),
                    subject_keys=(source.unit_id, target.unit_id, source.layer, target.layer),
                    remediation=self.metadata.remediation_summary or "",
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(tuple(matches))


class LayerBoundaryViolationRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_LAYER_BOUNDARY_VIOLATION,
            title="Layer boundary violation",
            description=(
                "Detects dependencies that skip expected intermediaries "
                "(for example presentation → persistence)."
            ),
            remediation=(
                "Route access through the expected application/domain boundary instead of "
                "reaching persistence or infrastructure directly from presentation/API layers."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        return InvalidDependencyDirectionRule().evaluate_applicability(context)

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        view = architecture_view(context)
        if view is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Architecture view unavailable",
            )
        if not classification_coverage_ok(view):
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Insufficient reliable layer classification coverage",
            )
        skips = {
            ("presentation", "persistence"),
            ("presentation", "infrastructure"),
            ("api", "persistence"),
            ("api", "infrastructure"),
        }
        unit_map = view.unit_map
        matches = []
        for edge in view.included_edges():
            if edge.edge_kind in _COMPOSITION_EDGE_KINDS:
                continue
            source = unit_map.get(edge.source_unit_id)
            target = unit_map.get(edge.target_unit_id)
            if source is None or target is None:
                continue
            if source.role == "composition_root":
                continue
            if (
                source.classification_confidence == "low"
                or target.classification_confidence == "low"
            ):
                continue
            if (source.layer, target.layer) not in skips:
                continue
            path = edge.evidence_paths[0] if edge.evidence_paths else None
            matches.append(
                match(
                    rule_id=RULE_LAYER_BOUNDARY_VIOLATION,
                    title="Architectural layer boundary skipped",
                    summary=(
                        f"'{source.unit_id}' ({source.layer}) depends directly on "
                        f"'{target.unit_id}' ({target.layer}), bypassing expected "
                        "application/domain intermediaries."
                    ),
                    severity=RuleSeverity.HIGH,
                    confidence=MatchEvidenceConfidence.MEDIUM,
                    evidence=(
                        evidence_graph_edge(
                            source=source.unit_id,
                            target=target.unit_id,
                            path=path,
                            message="Boundary skip dependency",
                            attributes={
                                "governing_rule": (
                                    f"forbid_skip:{source.layer}->{target.layer}"
                                ),
                                "expected_path": (
                                    "presentation|api>application>domain>persistence"
                                ),
                            },
                        ),
                    ),
                    subject_keys=(
                        "boundary",
                        source.unit_id,
                        target.unit_id,
                        source.layer,
                        target.layer,
                    ),
                    remediation=self.metadata.remediation_summary or "",
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(tuple(matches))


class ExcessiveCrossModuleCouplingRule:
    def __init__(
        self,
        *,
        outgoing_threshold: int = 8,
        minimum_modules: int = 5,
        relative_multiplier: float = 2.0,
        exclude_composition_roots: bool = True,
    ) -> None:
        self._threshold = outgoing_threshold
        self._minimum = minimum_modules
        self._relative_multiplier = relative_multiplier
        self._exclude_composition_roots = exclude_composition_roots

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
            title="Excessive cross-module coupling",
            description=(
                "Identifies primary architectural modules with an unusually broad outward "
                "dependency surface versus absolute and peer-relative thresholds."
            ),
            remediation=(
                "Reduce outward dependencies by extracting shared abstractions, splitting "
                "responsibilities, or introducing a narrower facade."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        view = architecture_view(context)
        if view is None or not min_coverage_ok(view):
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Architecture view or extraction coverage insufficient",
            )
        peers = comparable_coupling_units(view)
        if len(peers) < self._minimum:
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message=f"Fewer than {self._minimum} comparable architectural modules",
            )
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        view = architecture_view(context)
        if view is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Architecture view unavailable",
            )
        peers = comparable_coupling_units(view)
        if len(peers) < self._minimum:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message=f"Fewer than {self._minimum} comparable architectural modules",
            )
        peer_ids = {unit.unit_id for unit in peers}
        fan_out: Counter[str] = Counter()
        raw_targets: dict[str, set[str]] = {}
        for edge in view.included_edges():
            if edge.source_unit_id not in peer_ids:
                continue
            if edge.edge_kind in _COMPOSITION_EDGE_KINDS:
                continue
            fan_out[edge.source_unit_id] += 1
            raw_targets.setdefault(edge.source_unit_id, set()).add(
                edge.raw_target_package or edge.target_unit_id
            )
        peer_values = [fan_out.get(unit.unit_id, 0) for unit in peers]
        peer_median = float(median(peer_values)) if peer_values else 0.0
        relative_floor = peer_median * self._relative_multiplier
        matches = []
        for unit in peers:
            count = fan_out.get(unit.unit_id, 0)
            if count < self._threshold:
                continue
            if count < relative_floor and peer_median > 0:
                # Absolute threshold alone is not enough when below peer relative floor.
                continue
            severity = (
                RuleSeverity.HIGH if count >= self._threshold * 2 else RuleSeverity.MEDIUM
            )
            targets = sorted(
                edge.target_unit_id
                for edge in view.included_edges()
                if edge.source_unit_id == unit.unit_id
                and edge.edge_kind not in _COMPOSITION_EDGE_KINDS
            )[:10]
            matches.append(
                match(
                    rule_id=RULE_EXCESSIVE_CROSS_MODULE_COUPLING,
                    title="Broad outbound dependency surface",
                    summary=(
                        f"Architectural module '{unit.unit_id}' depends on {count} other "
                        f"primary units (absolute threshold {self._threshold}, peer median "
                        f"{peer_median:.1f}, relative floor {relative_floor:.1f}). A broad "
                        "dependency surface may increase change coordination and weaken "
                        "architectural boundaries."
                    ),
                    severity=severity,
                    confidence=MatchEvidenceConfidence.HIGH
                    if view.extraction_coverage >= 0.4
                    else MatchEvidenceConfidence.MEDIUM,
                    evidence=(
                        evidence_unit(
                            unit_id=unit.unit_id,
                            message=(
                                f"fan_out={count}; "
                                f"unique_targets={','.join(targets)}; "
                                f"raw_packages="
                                f"{','.join(sorted(raw_targets.get(unit.unit_id, set()))[:8])}"
                            ),
                            attributes={
                                "role": unit.role,
                                "absolute_threshold": str(self._threshold),
                                "peer_median": f"{peer_median:.2f}",
                                "relative_multiplier": str(self._relative_multiplier),
                                "peer_population": str(len(peers)),
                                "excluded_roles": "composition_root,registration,test",
                            },
                        ),
                    ),
                    subject_keys=(unit.unit_id, f"out:{count}"),
                    remediation=self.metadata.remediation_summary or "",
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(tuple(matches))


class ComponentConcentrationRule:
    def __init__(
        self,
        *,
        edge_share_threshold: float = 0.30,
        minimum_components: int = 5,
    ) -> None:
        self._threshold = edge_share_threshold
        self._minimum = minimum_components

    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_COMPONENT_CONCENTRATION,
            title="Architectural component concentration",
            description=(
                "Identifies primary architectural units that concentrate a "
                "disproportionate share of dependency edges."
            ),
            remediation=(
                "Redistribute responsibilities or extract collaborators so connectivity "
                "is less concentrated in a single architectural unit."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        view = architecture_view(context)
        if view is None or not min_coverage_ok(view):
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Architecture view or extraction coverage insufficient",
            )
        peers = comparable_coupling_units(view)
        if len(peers) < self._minimum or not view.included_edges():
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Graph population below minimum for concentration analysis",
            )
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        view = architecture_view(context)
        if view is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Architecture view unavailable",
            )
        peers = {unit.unit_id for unit in comparable_coupling_units(view)}
        shares = {
            unit_id: share
            for unit_id, share in incident_edge_shares(view).items()
            if unit_id in peers
        }
        matches = []
        for unit_id, share in sorted(shares.items(), key=lambda item: (-item[1], item[0])):
            if share < self._threshold:
                continue
            unit = view.unit_map.get(unit_id)
            matches.append(
                match(
                    rule_id=RULE_COMPONENT_CONCENTRATION,
                    title="Concentrated architectural connectivity",
                    summary=(
                        f"Architectural module '{unit_id}' accounts for {share:.0%} of "
                        f"incident dependency edges among comparable modules "
                        f"(threshold {self._threshold:.0%}). This may indicate an "
                        "architectural bottleneck."
                    ),
                    severity=RuleSeverity.MEDIUM if share < 0.5 else RuleSeverity.HIGH,
                    confidence=MatchEvidenceConfidence.MEDIUM,
                    evidence=(
                        evidence_unit(
                            unit_id=unit_id,
                            message=f"incident_edge_share={share:.4f}",
                            attributes={
                                "role": unit.role if unit else "architectural_module",
                                "threshold": f"{self._threshold:.2f}",
                                "peer_population": str(len(peers)),
                            },
                        ),
                    ),
                    subject_keys=(unit_id, f"share:{share:.4f}"),
                    remediation=self.metadata.remediation_summary or "",
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(tuple(matches))


class FrameworkLeakageRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_FRAMEWORK_LEAKAGE,
            title="Framework leakage across boundaries",
            description=(
                "Detects framework-specific types or annotations in layers intended "
                "to remain framework-independent (domain)."
            ),
            remediation=(
                "Move framework annotations and SDK types behind adapters; keep domain "
                "contracts free of persistence and web-framework symbols."
            ),
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        view = architecture_view(context)
        if view is None or not min_coverage_ok(view):
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Architecture view or extraction coverage insufficient",
            )
        domain_units = [
            unit
            for unit in view.primary_units()
            if unit.layer == "domain" and unit.classification_confidence != "low"
        ]
        if not domain_units:
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="No reliably classified domain units",
            )
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        view = architecture_view(context)
        if view is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Architecture view unavailable",
            )
        reliable_domain = {
            unit.unit_id
            for unit in view.primary_units()
            if unit.layer == "domain" and unit.classification_confidence != "low"
        }
        hits = [hit for hit in view.framework_hits if hit.unit_id in reliable_domain]
        if not hits:
            return SharedRuleEvaluationResult.not_matched()
        matches = []
        for hit in hits:
            matches.append(
                match(
                    rule_id=RULE_FRAMEWORK_LEAKAGE,
                    title="Framework symbol in domain boundary",
                    summary=(
                        f"Domain unit '{hit.unit_id}' references framework symbol "
                        f"'{hit.symbol}' ({hit.framework}), which may leak infrastructure "
                        "concerns into a framework-independent boundary."
                    ),
                    severity=RuleSeverity.MEDIUM,
                    confidence=MatchEvidenceConfidence.HIGH,
                    evidence=(
                        RuleEvidence(
                            kind=RuleEvidenceKind.SYMBOL,
                            subject_reference=hit.symbol,
                            message=f"{hit.framework} in domain unit",
                            safe_location=hit.path,
                            attributes={"framework": hit.framework, "unit": hit.unit_id},
                            provenance="architecture_analysis_view",
                        ),
                    ),
                    subject_keys=(hit.unit_id, hit.framework, hit.symbol, hit.path),
                    remediation=self.metadata.remediation_summary or "",
                )
            )
        return SharedRuleEvaluationResult.matched(tuple(matches))


class EnterpriseStandardMismatchRule:
    @property
    def metadata(self) -> RuleMetadata:
        return make_metadata(
            rule_id=RULE_ENTERPRISE_STANDARD_MISMATCH,
            title="Enterprise architecture standard mismatch",
            description=(
                "Compares observed architecture signals with declared enterprise "
                "architecture/technology standards when Enterprise context is present."
            ),
            remediation=(
                "Align the repository with the cited enterprise standard, or update the "
                "declared standard through governance if the exception is intentional."
            ),
            requires_enterprise=True,
        )

    def evaluate_applicability(self, context: RuleExecutionContext) -> RuleApplicability:
        if not context.has_enterprise_context:
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.MISSING_ENTERPRISE_CONTEXT,
                message="Enterprise context required",
            )
        view = architecture_view(context)
        if view is None or not min_coverage_ok(view, minimum=0.05):
            return RuleApplicability.not_applicable(
                reason_code=RuleSkipReason.OTHER,
                message="Architecture view insufficient",
            )
        return RuleApplicability.applicable()

    def evaluate(self, context: RuleExecutionContext) -> SharedRuleEvaluationResult:
        if not context.has_enterprise_context:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.MISSING_ENTERPRISE_CONTEXT,
                message="Enterprise context required",
            )
        enterprise = context.enterprise_context
        standards = getattr(enterprise, "standards", ()) or ()
        if not standards:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="No enterprise standards declared for this repository context",
            )
        view = architecture_view(context)
        if view is None:
            return SharedRuleEvaluationResult.not_applicable(
                reason=RuleSkipReason.OTHER,
                message="Architecture view unavailable",
            )
        observed_frameworks = sorted({hit.framework for hit in view.framework_hits})
        matches = []
        for standard in standards:
            labels = getattr(standard, "labels", {}) or {}
            prohibited = {
                item.strip().lower()
                for item in str(labels.get("prohibited_frameworks", "")).split(",")
                if item.strip()
            }
            if not prohibited:
                continue
            offenders = sorted(set(observed_frameworks).intersection(prohibited))
            if not offenders:
                continue
            standard_id = getattr(standard, "entity_id", None) or getattr(
                standard, "name", "standard"
            )
            matches.append(
                match(
                    rule_id=RULE_ENTERPRISE_STANDARD_MISMATCH,
                    title="Observed framework prohibited by enterprise standard",
                    summary=(
                        f"Repository architecture evidence includes framework(s) "
                        f"{', '.join(offenders)} prohibited by enterprise standard "
                        f"'{standard_id}' (declared)."
                    ),
                    severity=RuleSeverity.HIGH,
                    confidence=MatchEvidenceConfidence.MEDIUM,
                    evidence=(
                        RuleEvidence(
                            kind=RuleEvidenceKind.ENTERPRISE_RELATIONSHIP,
                            subject_reference=str(standard_id),
                            message="Enterprise-declared prohibited frameworks",
                            attributes={
                                "prohibited": ",".join(sorted(prohibited)),
                                "observed": ",".join(offenders),
                            },
                            provenance="enterprise-declared",
                        ),
                    ),
                    subject_keys=(str(standard_id), *offenders),
                    remediation=self.metadata.remediation_summary or "",
                )
            )
        if not matches:
            return SharedRuleEvaluationResult.not_matched()
        return SharedRuleEvaluationResult.matched(tuple(matches))
