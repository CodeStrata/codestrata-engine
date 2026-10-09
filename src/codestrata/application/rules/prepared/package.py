"""Map a compiled customer Rule into a reviewed Effective RuleSet.

The compiler plan is not an execution package. Sealing uses the existing
composition and Effective RuleSet contracts. The constant example-rule catalog
is not consulted.
"""

from __future__ import annotations

from datetime import datetime

from codestrata.application.rules.compiler.service import compile_rule_yaml
from codestrata.application.rules.composition.catalog import catalog_from_mapping
from codestrata.application.rules.composition.resolver import resolve_ruleset
from codestrata.application.rules.effective.admission import admit_effective
from codestrata.application.rules.effective.errors import EffectiveSealError
from codestrata.application.rules.effective.models import ExecutionContext
from codestrata.application.rules.effective.seal import seal_effective_ruleset
from codestrata.application.rules.overrides.apply import apply_overrides
from codestrata.application.rules.prepared.errors import PreparedPackageError
from codestrata.application.rules.prepared.models import (
    EXAMPLE_RULE_ID,
    AdmittedPreparedPackage,
    CustomerPackagePreview,
    OwnerReview,
    ReviewDecision,
)
from codestrata.domain.contracts.enums import AdoptionLabel, ExecutionPurpose
from codestrata.domain.contracts.rules import (
    EffectiveRuleSet,
    PackageCompatibility,
    PayloadDigest,
    Rule,
    RuleSet,
    RuleSetEntry,
    RuleSetMetadata,
    SelectorDef,
    SignedPackageBody,
    bind_digest,
    parse_effective_ruleset,
    seal_package,
)
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.rules.compiler_errors import YamlCompileError
from codestrata.domain.rules.compiler_models import CompilationPlan, selector_ast_digest_for
from codestrata.domain.rules.identifiers import validate_rule_id

_COMMUNITY_RULESET_ID = "codestrata.engineering-standard"


def preview_customer_package(
    raw: bytes,
    *,
    purpose: ExecutionPurpose,
    validity_not_after: str | None,
    label: str = "customer-rule.yaml",
) -> CustomerPackagePreview:
    """Compile and seal a review preview. The result is not admitted."""

    plan, rule = _compiled_rule(raw, label=label)
    effective = _seal_rule(plan, rule, purpose=purpose, validity_not_after=validity_not_after)
    return CustomerPackagePreview(
        plan_digest=plan.plan_digest,
        rule_digest=rule.digest,
        package_digest=effective.effective_ruleset_digest,
        source_digest=plan.source_digest,
        rule_id=rule.metadata.id,
        ruleset_id=effective.ruleset_id,
        execution_purpose=purpose,
        effective=effective,
        rule=rule,
    )


def prepare_reviewed_customer_package(
    raw: bytes,
    review: OwnerReview | None,
    *,
    purpose: ExecutionPurpose,
    validity_not_after: str | None,
    observed_at: datetime,
    label: str = "customer-rule.yaml",
) -> AdmittedPreparedPackage:
    """Admit a package only when the owner review matches the sealed digests."""

    if review is None:
        raise PreparedPackageError("review_missing", "owner review is required before admission")
    if review.decision is not ReviewDecision.APPROVED:
        raise PreparedPackageError("review_rejected", "owner review rejected the package")
    preview = preview_customer_package(
        raw,
        purpose=purpose,
        validity_not_after=validity_not_after,
        label=label,
    )
    _require_review(review, preview)
    context = ExecutionContext(now=observed_at, requested_purpose=purpose)
    admission = admit_effective(preview.effective, context)
    if not admission.admitted:
        raise PreparedPackageError(
            admission.reason_code or "not_admitted",
            "Effective RuleSet admission rejected the package",
        )
    manifest = seal_package(
        SignedPackageBody(
            package_id=preview.ruleset_id,
            package_version=preview.effective.ruleset_version,
            effective_ruleset_digest=preview.effective.effective_ruleset_digest,
            payload_digests=(
                PayloadDigest(name="plan", digest=preview.plan_digest),
                PayloadDigest(name="rule", digest=preview.rule_digest),
                PayloadDigest(name="effective", digest=preview.package_digest),
            ),
            execution_purpose=purpose,
            compatibility=PackageCompatibility(),
            validity_not_before=preview.effective.validity_not_before,
            validity_not_after=preview.effective.validity_not_after,
        )
    )
    if manifest.operational.signature is not None:
        raise PreparedPackageError(
            "invalid_trust",
            "ordinary preparation does not attach a detached headless signature",
        )
    return AdmittedPreparedPackage(
        review=review,
        effective=preview.effective,
        rule=preview.rule,
        plan_digest=preview.plan_digest,
        source_digest=preview.source_digest,
        manifest=manifest,
    )


def _require_review(review: OwnerReview, preview: CustomerPackagePreview) -> None:
    if review.plan_digest != preview.plan_digest:
        raise PreparedPackageError(
            "review_digest_mismatch",
            "reviewed plan digest does not match the compiler plan",
        )
    if review.rule_digest != preview.rule_digest:
        raise PreparedPackageError(
            "review_digest_mismatch",
            "reviewed rule digest does not match the compiled rule",
        )
    if review.package_digest != preview.package_digest:
        raise PreparedPackageError(
            "review_digest_mismatch",
            "reviewed package digest does not match the sealed Effective RuleSet",
        )


def _compiled_rule(raw: bytes, *, label: str) -> tuple[CompilationPlan, Rule]:
    try:
        plan = compile_rule_yaml(raw, label=label)
    except YamlCompileError as error:
        raise PreparedPackageError("invalid_rule", str(error)) from error
    rule = plan.rule
    if rule is None or plan.kind != "Rule":
        raise PreparedPackageError(
            "rule_document_required",
            "preparation accepts one Rule document; a CompilationPlan is not a package",
        )
    if rule.metadata.id == EXAMPLE_RULE_ID or rule.digest == _example_digest():
        raise PreparedPackageError(
            "example_catalog_substituted",
            "the example-rule catalog cannot substitute for a reviewed customer rule",
        )
    validate_rule_id(rule.metadata.id)
    return plan, rule


def _example_digest() -> str:
    from codestrata.domain.contracts.examples_e01_3 import example_rule

    return example_rule().digest


def _seal_rule(
    plan: CompilationPlan,
    rule: Rule,
    *,
    purpose: ExecutionPurpose,
    validity_not_after: str | None,
) -> EffectiveRuleSet:
    ruleset = _ruleset_for(rule)
    if ruleset.metadata.id == _COMMUNITY_RULESET_ID:
        raise PreparedPackageError(
            "example_catalog_substituted",
            "customer preparation cannot seal the community engineering-standard catalog",
        )
    catalog = catalog_from_mapping([ruleset], [rule])
    composed = resolve_ruleset(ruleset, catalog)
    overridden = apply_overrides(composed, catalog, None)
    try:
        effective = seal_effective_ruleset(
            composed=composed,
            overridden=overridden,
            catalog=catalog,
            purpose=purpose,
            input_digest=plan.plan_digest,
            package_digest=digest_canonical(
                {
                    "kind": "reviewed-customer-package",
                    "plan_digest": plan.plan_digest,
                    "rule_digest": rule.digest,
                    "ruleset_digest": ruleset.digest,
                }
            ),
            validity_not_after=validity_not_after,
        )
    except EffectiveSealError as error:
        raise PreparedPackageError(error.code, str(error)) from error
    parsed = parse_effective_ruleset(effective.model_dump(mode="json"))
    if parsed.effective_ruleset_digest != effective.effective_ruleset_digest:
        raise PreparedPackageError("corrupted_package", "sealed package failed re-parse")
    if parsed.input_digest != plan.plan_digest:
        raise PreparedPackageError(
            "corrupted_package",
            "sealed package is not bound to the compiler plan",
        )
    return parsed


def _ruleset_for(rule: Rule) -> RuleSet:
    source = rule.select.source or "repository_graph"
    nodes = dict(rule.select.nodes or {})
    selector = SelectorDef(
        id=f"{rule.metadata.id}.selector",
        source=source,
        nodes=nodes,
        digest=selector_ast_digest_for(source=source, nodes=nodes, selector_ref=None),
    )
    return bind_digest(
        RuleSet,
        {
            "metadata": RuleSetMetadata(
                id=rule.metadata.id,
                version=rule.metadata.version,
                title=rule.metadata.title,
                owner=rule.metadata.owner,
            ),
            "extends": (),
            "selectors": (selector,),
            "rules": (
                RuleSetEntry(
                    rule_id=rule.metadata.id,
                    revision=rule.metadata.version,
                    digest=rule.digest,
                    default_enabled=True,
                    adoption=AdoptionLabel.RECOMMENDED,
                    parameters={},
                    severity_override=None,
                ),
            ),
        },
    )
