"""Typed review, package and operator-fact contracts for prepared customer rules.

Additive application API ``codestrata.prepared-customer-package.v1``.
Engine distribution version stays 0.2.1 until a release cut. Keyword-only
assessment arguments default to absent, so an assessment with no customer
package keeps the previous behavior. This module is not a CLI, MCP tool,
HTTP route or hosted authoring surface.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from codestrata.application.evidence.language.python_imports import (
    ImportCoverageLimitation,
    PythonImportRecord,
)
from codestrata.application.rules.prepared.errors import PreparedPackageError
from codestrata.domain.contracts.enums import ExecutionPurpose, ResultStatus
from codestrata.domain.contracts.rules import EffectiveRuleSet, Rule, SignedPackageManifest
from codestrata.domain.contracts.serialization import require_content_digest
from codestrata.domain.graph.validation import require_nonblank
from codestrata.domain.rules.operators.models import OperatorContext

PREPARED_CUSTOMER_PACKAGE_API = "codestrata.prepared-customer-package.v1"
STANDARD_RULES_IDENTITY = "python-shared-rules"
EXAMPLE_RULE_ID = "architecture.dependency-cycle"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class OperatorFactKind(StrEnum):
    """How caller-supplied operator facts relate to a resolved import view.

    ``contains_only`` is the repository file graph. It is not an import view
    and must not be interpreted as import independence.
    """

    MISSING = "missing"
    CONTAINS_ONLY = "contains_only"
    RESOLVED_IMPORTS = "resolved_imports"


class OwnerReview(BaseModel):
    """Immutable owner decision bound to compiler and sealed-package digests."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reviewer: str
    decision: ReviewDecision
    plan_digest: str
    rule_digest: str
    package_digest: str

    @field_validator("reviewer", mode="before")
    @classmethod
    def normalize_reviewer(cls, value: object) -> str:
        return require_nonblank(str(value), label="reviewer")

    @field_validator("plan_digest", "rule_digest", "package_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="review digest")


class PreparedOperatorFacts(BaseModel):
    """Caller-supplied structural facts. Production does not invent edges."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: OperatorFactKind
    context: OperatorContext | None = None
    import_records: tuple[PythonImportRecord, ...] = ()
    source_roots: tuple[str, ...] = ()
    root_discovery: str = ""
    discovery_rule: str = ""
    coverage_scope: str = ""
    limitations: tuple[ImportCoverageLimitation, ...] = ()
    external_import_names: tuple[str, ...] = ()

    @model_validator(mode="after")
    def context_matches_kind(self) -> PreparedOperatorFacts:
        if self.kind is OperatorFactKind.MISSING and self.context is not None:
            raise PreparedPackageError(
                "unsupported_fact_view",
                "a missing import view cannot carry an operator context",
            )
        if self.kind is not OperatorFactKind.MISSING and self.context is None:
            raise PreparedPackageError(
                "unsupported_fact_view",
                "a supplied fact kind requires an operator context",
            )
        return self


class CustomerPackagePreview(BaseModel):
    """Sealed but not admitted. Digests are what an owner reviews."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_digest: str
    rule_digest: str
    package_digest: str
    source_digest: str
    rule_id: str
    ruleset_id: str
    execution_purpose: ExecutionPurpose
    effective: EffectiveRuleSet
    rule: Rule

    @field_validator("source_digest", mode="before")
    @classmethod
    def normalize_source_digest(cls, value: object) -> str:
        return require_content_digest(value, label="source digest")


class AdmittedPreparedPackage(BaseModel):
    """Approved package. CompilationPlan alone cannot construct this object."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    api: str = PREPARED_CUSTOMER_PACKAGE_API
    review: OwnerReview
    effective: EffectiveRuleSet
    rule: Rule
    plan_digest: str
    source_digest: str
    manifest: SignedPackageManifest
    standard_rules_identity: str = STANDARD_RULES_IDENTITY
    example_catalog_substituted: bool = False

    @field_validator("plan_digest", "source_digest", mode="before")
    @classmethod
    def normalize_plan_digest(cls, value: object) -> str:
        return require_content_digest(value, label="plan digest")

    @model_validator(mode="after")
    def review_matches_sealed_package(self) -> AdmittedPreparedPackage:
        if self.review.decision is not ReviewDecision.APPROVED:
            raise PreparedPackageError("review_rejected", "owner review is not approved")
        if self.review.plan_digest != self.plan_digest:
            raise PreparedPackageError(
                "review_digest_mismatch",
                "reviewed plan digest does not match the compiled plan",
            )
        if self.review.rule_digest != self.rule.digest:
            raise PreparedPackageError(
                "review_digest_mismatch",
                "reviewed rule digest does not match the compiled rule",
            )
        if self.review.package_digest != self.effective.effective_ruleset_digest:
            raise PreparedPackageError(
                "review_digest_mismatch",
                "reviewed package digest does not match the sealed Effective RuleSet",
            )
        if self.example_catalog_substituted or self.rule.metadata.id == EXAMPLE_RULE_ID:
            raise PreparedPackageError(
                "example_catalog_substituted",
                "the example-rule catalog cannot substitute for a reviewed customer rule",
            )
        if self.manifest.body.effective_ruleset_digest != self.effective.effective_ruleset_digest:
            raise PreparedPackageError(
                "corrupted_package",
                "signed package manifest does not bind the sealed Effective RuleSet",
            )
        if self.manifest.body.execution_purpose is not self.effective.execution_purpose:
            raise PreparedPackageError(
                "invalid_purpose",
                "signed package purpose does not match the Effective RuleSet",
            )
        _require_sealed_bindings(self)
        return self


def _require_sealed_bindings(package: AdmittedPreparedPackage) -> None:
    """Construction check. Invocation repeats this against a recomputed plan."""

    if package.effective.input_digest != package.plan_digest:
        raise PreparedPackageError(
            "package_binding_mismatch",
            "Effective RuleSet input digest does not match the reviewed plan",
        )
    if len(package.effective.rules) != 1:
        raise PreparedPackageError(
            "package_binding_mismatch",
            "prepared package must resolve exactly the reviewed rule",
        )
    resolved = package.effective.rules[0]
    if (
        resolved.rule_id != package.rule.metadata.id
        or resolved.revision != package.rule.metadata.version
        or resolved.rule_digest != package.rule.digest
        or resolved.rule_digest != package.review.rule_digest
    ):
        raise PreparedPackageError(
            "package_binding_mismatch",
            "resolved rule does not match the reviewed rule",
        )
    payloads = {item.name: item.digest for item in package.manifest.body.payload_digests}
    if (
        payloads.get("plan") != package.plan_digest
        or payloads.get("rule") != package.rule.digest
        or payloads.get("effective") != package.effective.effective_ruleset_digest
    ):
        raise PreparedPackageError(
            "package_binding_mismatch",
            "manifest payload bindings do not match the reviewed package",
        )


class PreparedRuleExecution(BaseModel):
    """One customer rule evaluated beside, not instead of, standard assessment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    rule_digest: str
    plan_digest: str
    package_digest: str
    ruleset_id: str
    status: ResultStatus
    reason: str | None = None
    fact_kind: OperatorFactKind
    members: tuple[str, ...] = ()
    example_catalog_substituted: bool = False
    standard_rules_identity: str = STANDARD_RULES_IDENTITY
    reviewer: str
    provenance: dict[str, str | bool | None] = Field(default_factory=dict)
