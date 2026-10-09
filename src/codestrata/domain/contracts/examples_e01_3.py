"""Good consumer examples for E01.3 rule, comparison and invocation contracts."""

from __future__ import annotations

from codestrata.domain.contracts.catalog import PACKAGE_REVISION
from codestrata.domain.contracts.comparison import (
    BoundDigests,
    ComparisonEnvelope,
    DriverDelta,
    seal_comparison,
)
from codestrata.domain.contracts.driver_manifest import outcome_driver_manifest_digest
from codestrata.domain.contracts.enums import (
    AdoptionLabel,
    CauseAttribution,
    ChangedInputDimension,
    CompatibilityStatus,
    ExecutionPurpose,
    ExportMode,
    InvocationKind,
    JobProgressState,
    JobTerminalState,
    OutcomeMovement,
    ResultStatus,
    RevisionAgreement,
    SuppliedContextProvenance,
)
from codestrata.domain.contracts.invocation import (
    CandidateValidation,
    ExportTrustConfig,
    FixtureExpectation,
    HeadlessInvocation,
    LocalJobCancellation,
    LocalJobProgress,
    LocalJobState,
    LocalJobTerminal,
    PermittedScope,
    PinnedInputs,
    SuppliedPrContext,
    context_digest_for,
)
from codestrata.domain.contracts.rules import (
    AppliesTo,
    ConditionNode,
    EffectiveRuleSet,
    FindingEmit,
    MessageBinding,
    MetricEmit,
    PackageCompatibility,
    ParameterField,
    ParentRef,
    PayloadDigest,
    ResolvedRule,
    Rule,
    RuleMetadata,
    RuleSet,
    RuleSetEntry,
    RuleSetMetadata,
    SelectClause,
    SelectorDef,
    SignedPackageBody,
    SignedPackageManifest,
    bind_digest,
    seal_package,
)
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.findings.enums import FindingSeverity

SOURCE_REVISION = "abcdef1234567890abcdef1234567890abcdef12"
ENGINE_VERSION = "0.2.1"
DSL = "codestrata.io/rules/v1"


def example_rule() -> Rule:
    return bind_digest(
        Rule,
        {
            "metadata": RuleMetadata(
                id="architecture.dependency-cycle",
                version="1.0.0",
                title="Modules must not form import cycles",
                category="architecture",
                owner="codestrata",
            ),
            "applies_to": AppliesTo(
                languages=("java",),
                facts=("module.declaration", "graph.imports"),
            ),
            "select": SelectClause(
                source="repository_graph",
                nodes={"all": [{"type": "module"}]},
            ),
            "condition": ConditionNode(
                operator="cycle",
                edge_types=("imports",),
                traversal="direct",
                max_depth=1,
            ),
            "finding": FindingEmit(
                default_severity=FindingSeverity.HIGH,
                message_template="{{dependency_path}} participates in an import cycle",
                bindings=(
                    MessageBinding(
                        name="dependency_path",
                        type="string",
                        evidence="dependency_path",
                    ),
                ),
                documentation_url="https://docs.codestrata.ai/rules/architecture/dependency-cycle",
            ),
            "metric": MetricEmit(name="dependency_cycle_count", operation="count"),
            "evidence_include": ("source_location", "dependency_path"),
            "parameter_schema": (
                ParameterField(
                    name="max_cycle_length",
                    value_type="integer",
                    minimum=2,
                    maximum=32,
                    default=8,
                ),
            ),
        },
    )


def example_ruleset(rule: Rule | None = None) -> RuleSet:
    rule = rule or example_rule()
    parent = ParentRef(
        id="codestrata.engineering-health",
        version="1.0.0",
        digest=digest_canonical({"id": "codestrata.engineering-health", "version": "1.0.0"}),
    )
    selector = SelectorDef(
        id="codestrata.production_modules",
        source="repository_graph",
        nodes={"all": [{"type": "module"}, {"generated": False}]},
        digest=digest_canonical({"id": "codestrata.production_modules"}),
    )
    return bind_digest(
        RuleSet,
        {
            "metadata": RuleSetMetadata(
                id="codestrata.engineering-standard",
                version="1.0.0",
                title="Engineering standard",
                owner="codestrata",
            ),
            "extends": (parent,),
            "selectors": (selector,),
            "rules": (
                RuleSetEntry(
                    rule_id=rule.metadata.id,
                    revision=rule.metadata.version,
                    digest=rule.digest,
                    default_enabled=True,
                    adoption=AdoptionLabel.RECOMMENDED,
                ),
            ),
        },
    )


def example_effective(
    rule: Rule | None = None,
    ruleset: RuleSet | None = None,
) -> EffectiveRuleSet:
    rule = rule or example_rule()
    ruleset = ruleset or example_ruleset(rule)
    selector_digest = ruleset.selectors[0].digest
    local_config = digest_canonical({"local_exclusions": []})
    signed_base = ruleset.digest
    input_digest = digest_canonical({"source_revision": SOURCE_REVISION})
    config_digest = digest_canonical({"unsigned": local_config, "base": signed_base})
    feed_digest = digest_canonical({"feed": "osv", "version": "1.0.0"})
    package_digest = digest_canonical(
        {"package": "codestrata.engineering-standard", "ver": "1.0.0"}
    )
    return bind_digest(
        EffectiveRuleSet,
        {
            "ruleset_id": ruleset.metadata.id,
            "ruleset_version": ruleset.metadata.version,
            "ordered_composition": ruleset.extends,
            "rules": (
                ResolvedRule(
                    rule_id=rule.metadata.id,
                    revision=rule.metadata.version,
                    rule_digest=rule.digest,
                    enabled=True,
                    default_enabled=True,
                    adoption=AdoptionLabel.RECOMMENDED,
                    default_severity=rule.finding.default_severity,
                    effective_severity=rule.finding.default_severity,
                    selector_digest=selector_digest,
                    policy_refs=("policy:opaque:acme.engineering-policy@3",),
                    exception_refs=(),
                ),
            ),
            "signed_base_digest": signed_base,
            "local_unsigned_config_digest": local_config,
            "package_digest": package_digest,
            "feed_digest": feed_digest,
            "input_digest": input_digest,
            "config_digest": config_digest,
            "execution_purpose": ExecutionPurpose.PRODUCTION,
            "validity_not_after": "2027-09-15T00:00:00Z",
        },
        key="effective_ruleset_digest",
    )


def example_package(
    effective: EffectiveRuleSet | None = None,
    purpose: ExecutionPurpose = ExecutionPurpose.PRODUCTION,
) -> SignedPackageManifest:
    effective = effective or example_effective()
    body = SignedPackageBody(
        package_id="codestrata.engineering-standard.pkg",
        package_version="1.0.0",
        effective_ruleset_digest=effective.effective_ruleset_digest,
        payload_digests=(
            PayloadDigest(name="effective_ruleset", digest=effective.effective_ruleset_digest),
            PayloadDigest(name="ruleset", digest=effective.signed_base_digest),
        ),
        execution_purpose=purpose,
        compatibility=PackageCompatibility(),
        validity_not_after="2027-09-15T00:00:00Z",
    )
    return seal_package(body)


def example_pinned(effective: EffectiveRuleSet | None = None) -> PinnedInputs:
    effective = effective or example_effective()
    return PinnedInputs(
        source_revision=SOURCE_REVISION,
        working_state_digest=digest_canonical({"working": SOURCE_REVISION}),
        ruleset_digest=effective.effective_ruleset_digest,
        package_digest=effective.package_digest or effective.signed_base_digest,
        config_digest=effective.config_digest,
        input_digest=effective.input_digest,
        feed_digest=effective.feed_digest,
        engine_version=ENGINE_VERSION,
        dsl_version=DSL,
    )


def example_pr_context(*, conflict: bool = False) -> SuppliedPrContext:
    head = SOURCE_REVISION if not conflict else "ffffffffffffffffffffffffffffffffffffffff"
    agreement = RevisionAgreement.CONFLICT if conflict else RevisionAgreement.AGREES
    conflict_reason = "supplied head does not match pinned source_revision" if conflict else None
    fields = {
        "title": "Tighten module imports",
        "description": "Local PR narrative. Not proof of behavior.",
        "base": "1111111111111111111111111111111111111111",
        "head": head,
        "labels": ("architecture",),
        "linked_references": ("LOCAL-123",),
        "provenance": SuppliedContextProvenance.LOCAL_FILE.value,
        "supplied_path": "./pr-context.json",
        "revision_agreement": agreement.value,
        "conflict_reason": conflict_reason,
        "narrative_only": True,
    }
    return SuppliedPrContext(
        title="Tighten module imports",
        description="Local PR narrative. Not proof of behavior.",
        base="1111111111111111111111111111111111111111",
        head=head,
        labels=("architecture",),
        linked_references=("LOCAL-123",),
        provenance=SuppliedContextProvenance.LOCAL_FILE,
        supplied_path="./pr-context.json",
        context_digest=context_digest_for(**fields),
        revision_agreement=agreement,
        conflict_reason=conflict_reason,
        narrative_only=True,
        enters_canonical_computation=False,
    )


def example_invocation(
    *,
    kind: InvocationKind = InvocationKind.ASSESS,
    purpose: ExecutionPurpose = ExecutionPurpose.PRODUCTION,
    with_context: bool = True,
) -> HeadlessInvocation:
    effective = example_effective()
    return HeadlessInvocation(
        kind=kind,
        requested_package_purpose=purpose,
        source_path="./repos/example",
        output_path="./out/example",
        baseline_path="./baselines/example" if kind is InvocationKind.COMPARE else None,
        pinned_inputs=example_pinned(effective),
        export_trust=ExportTrustConfig(
            export_mode=ExportMode.RESTRICTED,
            trust_policy_path="./trust-policy.yaml",
            withheld_categories=("source_text",),
        ),
        permitted_scope=PermittedScope(
            languages=("java",),
            local_paths=("./repos/example",),
            max_files=10_000,
        ),
        expiry="2026-10-01T00:00:00Z",
        supplied_context=example_pr_context() if with_context else None,
    )


def example_candidate() -> CandidateValidation:
    digest = digest_canonical({"candidate": "architecture.dependency-cycle@draft"})
    return CandidateValidation(
        permitted_scope=PermittedScope(languages=("java",), local_paths=("./fixture",)),
        expiry="2026-09-20T00:00:00Z",
        candidate_digest=digest,
        selector_digest=digest_canonical({"selector": "production_modules"}),
        effective_setting_digest=digest_canonical({"enabled": True}),
        input_digest=digest_canonical({"fixture": "violating"}),
        engine_digest=digest_canonical({"engine": ENGINE_VERSION}),
        dsl_digest=digest_canonical({"dsl": DSL}),
        fixtures=(
            FixtureExpectation(name="compliant", expected_status="pass"),
            FixtureExpectation(name="violating", expected_status="fail"),
            FixtureExpectation(name="unknown-edge", expected_status="unknown"),
        ),
    )


def example_job(*, terminal: JobTerminalState = JobTerminalState.COMPLETED) -> LocalJobState:
    digest = digest_canonical({"body": "complete"})
    cancellation = None
    if terminal in {JobTerminalState.CANCELLED, JobTerminalState.KILLED}:
        cancellation = LocalJobCancellation(
            local_job_id="local-job-1",
            requested=True,
            grace_seconds=2,
        )
    return LocalJobState(
        progress=LocalJobProgress(
            local_job_id="local-job-1",
            state=JobProgressState.TERMINAL,
            phase="execute",
            units_done=1,
            units_total=1,
        ),
        cancellation=cancellation,
        terminal=LocalJobTerminal(
            local_job_id="local-job-1",
            terminal_state=terminal,
            successful=terminal is JobTerminalState.COMPLETED,
            assessment_body_digest=digest if terminal is JobTerminalState.COMPLETED else None,
            failure_code=None if terminal is JobTerminalState.COMPLETED else "cancelled",
        ),
    )


def example_comparison(*, kind: str = "compatible") -> ComparisonEnvelope:
    effective = example_effective()
    candidate = BoundDigests(
        artifact_digest=digest_canonical({"artifact": "candidate"}),
        ruleset_digest=effective.effective_ruleset_digest,
        package_digest=effective.package_digest or effective.signed_base_digest,
        config_digest=effective.config_digest,
        feed_digest=effective.feed_digest,
        input_digest=effective.input_digest,
        engine_version=ENGINE_VERSION,
        dsl_version=DSL,
        outcome_driver_manifest_digest=outcome_driver_manifest_digest(),
    )
    if kind == "no-baseline":
        return seal_comparison(
            {
                "has_baseline": False,
                "compatibility": CompatibilityStatus.NO_BASELINE,
                "compatibility_reasons": ("no_baseline",),
                "movement": OutcomeMovement.INSUFFICIENT,
                "cause_attribution": CauseAttribution.UNDETERMINED,
                "candidate": candidate,
                "coverage_status": ResultStatus.UNKNOWN,
                "notes": (f"package_revision={PACKAGE_REVISION}",),
            }
        )
    baseline = candidate.model_copy(
        update={"artifact_digest": digest_canonical({"artifact": "baseline"})}
    )
    if kind == "incompatible":
        return seal_comparison(
            {
                "has_baseline": True,
                "compatibility": CompatibilityStatus.INCOMPATIBLE,
                "compatibility_reasons": ("ruleset_digest_mismatch",),
                "movement": OutcomeMovement.INSUFFICIENT,
                "cause_attribution": CauseAttribution.CONFIGURATION_ONLY,
                "changed_input_dimensions": (ChangedInputDimension.RULESET,),
                "baseline": baseline,
                "candidate": candidate,
                "coverage_status": ResultStatus.UNKNOWN,
            }
        )
    if kind == "mixed-cause":
        return seal_comparison(
            {
                "has_baseline": True,
                "compatibility": CompatibilityStatus.COMPATIBLE,
                "compatibility_reasons": ("schema_formula_identity_match",),
                "movement": OutcomeMovement.MIXED,
                "cause_attribution": CauseAttribution.MIXED,
                "changed_input_dimensions": (
                    ChangedInputDimension.SOURCE,
                    ChangedInputDimension.FEED,
                ),
                "controlled_equivalent_inputs": False,
                "baseline": baseline,
                "candidate": candidate,
                "driver_deltas": (
                    DriverDelta(
                        driver_id="M06",
                        comparison_unit="count",
                        base_value="1",
                        candidate_value="2",
                        delta="1",
                        compatible=True,
                        compatibility_reason="same formula and identity",
                        cause=CauseAttribution.MIXED,
                        outcome_role="architecture",
                    ),
                ),
                "retained_known_violation_ids": ("finding:architecture.dependency-cycle:abcd",),
                "coverage_status": ResultStatus.PASS,
            }
        )
    return seal_comparison(
        {
            "has_baseline": True,
            "compatibility": CompatibilityStatus.COMPATIBLE,
            "compatibility_reasons": ("schema_formula_identity_match",),
            "movement": OutcomeMovement.STABLE,
            "cause_attribution": CauseAttribution.SOURCE_ONLY,
            "changed_input_dimensions": (ChangedInputDimension.SOURCE,),
            "baseline": baseline,
            "candidate": candidate,
            "driver_deltas": (
                DriverDelta(
                    driver_id="architecture.dependency-cycle",
                    comparison_unit="count",
                    base_value="1",
                    candidate_value="1",
                    delta="0",
                    compatible=True,
                    compatibility_reason="same rule digest and coverage",
                    cause=CauseAttribution.SOURCE_ONLY,
                    outcome_role="architecture",
                    finding_lifecycle="unchanged",
                ),
            ),
            "retained_known_violation_ids": ("finding:architecture.dependency-cycle:abcd",),
            "coverage_status": ResultStatus.PASS,
        }
    )
