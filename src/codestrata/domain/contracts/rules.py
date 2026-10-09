"""Rule, RuleSet, Effective RuleSet and signed-package contracts (E01.3)."""

from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from codestrata.domain.contracts.enums import AdoptionLabel, ExecutionPurpose
from codestrata.domain.contracts.serialization import (
    bind_content_digest,
    digest_canonical,
    is_binding_digest,
    omit_key,
    require_content_digest,
    require_pinned_version,
    require_supported_major,
    walk_forbidden_credentials,
    walk_forbidden_identity,
)
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.rules.identifiers import validate_rule_id

RULE_SCHEMA = "codestrata.rule.v1"
RULESET_SCHEMA = "codestrata.ruleset.v1"
EFFECTIVE_SCHEMA = "codestrata.effective-ruleset.v1"
PACKAGE_SCHEMA = "codestrata.signed-package-manifest.v1"
CONTRACT_VERSION = "1.0.0"
DSL_VERSION = "codestrata.io/rules/v1"
RULESET_API = "codestrata.io/ruleset/v1"
RESOLVER_VERSION = "1.0.0"
CAPABILITY_VERSION = "1.0.0"

BOUNDED_OPERATORS = frozenset(
    {
        "all",
        "any",
        "not",
        "equals",
        "in",
        "matches",
        "exists",
        "count",
        "sum",
        "min",
        "max",
        "ratio",
        "distinct",
        "percentile",
        "neighbors",
        "degree",
        "exists_path",
        "reachable",
        "cycle",
        "crosses_boundary",
        "changed",
        "introduced",
        "removed",
        "increased_by",
        "decreased_by",
        "compare",
        "threshold",
        "and",
        "or",
        "metric_ref",
    }
)
DISALLOWED_OPERATORS = frozenset(
    {"loop", "eval", "exec", "import", "call", "lambda", "network", "read_file"}
)


class ContractError(ValueError):
    """Unsupported, unknown-field or corrupt rule/package contract."""


class RuleMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    version: str
    title: str
    category: str
    owner: str

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return validate_rule_id(str(value))

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return require_pinned_version(value, label="rule version")

    @field_validator("title", "category", "owner", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="rule metadata")


class AppliesTo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    languages: tuple[str, ...]
    facts: tuple[str, ...]

    @field_validator("languages", "facts", mode="before")
    @classmethod
    def normalize_seq(cls, value: object) -> tuple[str, ...]:
        items = [require_nonblank(str(item), label="applies_to") for item in as_tuple(value)]
        if not items:
            raise ValueError("applies_to lists must be non-empty")
        return tuple(items)


class SelectClause(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str | None = None
    nodes: dict[str, Any] | None = None
    selector_ref: str | None = None
    selector_digest: str | None = None

    @field_validator("selector_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str | None:
        if value is None:
            return None
        return require_content_digest(value, label="selector_digest")

    @model_validator(mode="after")
    def pin_or_inline(self) -> SelectClause:
        if self.selector_ref:
            require_nonblank(self.selector_ref, label="selector_ref")
            if self.selector_digest is None:
                raise ValueError("selector_ref requires a pinned selector_digest")
            return self
        if not self.source:
            raise ValueError("select needs source or selector_ref")
        return self


class ConditionNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operator: str
    edge_types: tuple[str, ...] = ()
    traversal: str | None = None
    max_depth: int | None = Field(default=None, ge=1)
    dependency_view: str | None = None
    fact: str | None = None
    value: str | int | float | bool | None = None
    operands: tuple[ConditionNode, ...] = ()

    @field_validator("operator", mode="before")
    @classmethod
    def normalize_operator(cls, value: object) -> str:
        token = require_nonblank(str(value), label="operator").lower()
        if token in DISALLOWED_OPERATORS:
            raise ValueError(f"disallowed operator {token}")
        if token not in BOUNDED_OPERATORS:
            raise ValueError(f"unknown operator {token}")
        return token

    @model_validator(mode="after")
    def bound_traversal(self) -> ConditionNode:
        if self.traversal == "direct" and self.max_depth not in (None, 1):
            raise ValueError("direct traversal has max_depth 1")
        if self.traversal == "transitive" and (self.max_depth is None or self.max_depth < 1):
            raise ValueError("transitive traversal requires a positive bounded max_depth")
        return self


class MessageBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    type: str
    evidence: str

    @field_validator("name", "type", "evidence", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="message binding")


class FindingEmit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    default_severity: FindingSeverity
    message_template: str
    bindings: tuple[MessageBinding, ...] = ()
    documentation_url: str | None = None

    @field_validator("message_template", mode="before")
    @classmethod
    def safe_template(cls, value: object) -> str:
        text = require_nonblank(str(value), label="message_template")
        if "(" in text or "|" in text or "lambda" in text.lower():
            raise ValueError("message templates cannot contain expressions, filters or calls")
        return text


class MetricEmit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    operation: str

    @field_validator("name", "operation", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="metric emit")


class ParameterField(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    value_type: str
    minimum: float | None = None
    maximum: float | None = None
    default: str | int | float | bool | None = None

    @field_validator("name", "value_type", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="parameter field")


class Rule(BaseModel):
    """Immutable evaluation logic. Preview/production purpose lives on the package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = RULE_SCHEMA
    schema_version: str = CONTRACT_VERSION
    api_version: str = DSL_VERSION
    kind: str = "Rule"
    metadata: RuleMetadata
    digest: str
    applies_to: AppliesTo
    select: SelectClause
    condition: ConditionNode
    finding: FindingEmit
    metric: MetricEmit | None = None
    evidence_include: tuple[str, ...] = ()
    parameter_schema: tuple[ParameterField, ...] = ()

    @field_validator("digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="rule digest")

    @field_validator("kind")
    @classmethod
    def require_kind(cls, value: str) -> str:
        if value != "Rule":
            raise ValueError("kind must be Rule")
        return value

    @field_validator("evidence_include", mode="before")
    @classmethod
    def normalize_evidence(cls, value: object) -> tuple[str, ...]:
        return tuple(require_nonblank(str(item), label="evidence") for item in as_tuple(value))

    @model_validator(mode="after")
    def freeze_contract(self, info: ValidationInfo) -> Rule:
        require_supported_major(self.schema_version)
        payload = self.model_dump(mode="json")
        walk_forbidden_identity(payload)
        walk_forbidden_credentials(payload)
        expected = digest_canonical(omit_key(payload, "digest"))
        if self.digest != expected and not is_binding_digest(info):
            raise ValueError("rule digest does not match canonical logic payload")
        return self


class ParentRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    version: str
    digest: str

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="parent id")

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return require_pinned_version(value, label="parent version")

    @field_validator("digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="parent digest")


class SelectorDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    source: str
    nodes: dict[str, Any]
    digest: str

    @field_validator("id", "source", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="selector")

    @field_validator("digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="selector digest")


class RuleSetEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    revision: str
    digest: str
    default_enabled: bool
    adoption: AdoptionLabel
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    severity_override: FindingSeverity | None = None

    @field_validator("rule_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return validate_rule_id(str(value))

    @field_validator("revision", mode="before")
    @classmethod
    def normalize_revision(cls, value: object) -> str:
        return require_pinned_version(value, label="rule revision")

    @field_validator("digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="rule digest")


class RuleSetMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    version: str
    title: str
    owner: str

    @field_validator("id", "title", "owner", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return require_nonblank(str(value), label="ruleset metadata")

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return require_pinned_version(value, label="ruleset version")


class RuleSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = RULESET_SCHEMA
    schema_version: str = CONTRACT_VERSION
    api_version: str = RULESET_API
    kind: str = "RuleSet"
    metadata: RuleSetMetadata
    digest: str
    extends: tuple[ParentRef, ...] = ()
    selectors: tuple[SelectorDef, ...] = ()
    rules: tuple[RuleSetEntry, ...]

    @field_validator("digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="ruleset digest")

    @field_validator("kind")
    @classmethod
    def require_kind(cls, value: str) -> str:
        if value != "RuleSet":
            raise ValueError("kind must be RuleSet")
        return value

    @model_validator(mode="after")
    def freeze_contract(self, info: ValidationInfo) -> RuleSet:
        require_supported_major(self.schema_version)
        if not self.rules:
            raise ValueError("ruleset must include at least one rule entry")
        payload = self.model_dump(mode="json")
        walk_forbidden_identity(payload)
        walk_forbidden_credentials(payload)
        expected = digest_canonical(omit_key(payload, "digest"))
        if self.digest != expected and not is_binding_digest(info):
            raise ValueError("ruleset digest does not match canonical payload")
        return self


class ResolvedRule(BaseModel):
    """Fully materialized rule settings. No unresolved inheritance remains."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    revision: str
    rule_digest: str
    enabled: bool
    default_enabled: bool
    adoption: AdoptionLabel
    default_severity: FindingSeverity
    effective_severity: FindingSeverity
    override_source: str | None = None
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    selector_digest: str
    exception_refs: tuple[str, ...] = ()
    policy_refs: tuple[str, ...] = ()

    @field_validator("rule_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return validate_rule_id(str(value))

    @field_validator("revision", mode="before")
    @classmethod
    def normalize_revision(cls, value: object) -> str:
        return require_pinned_version(value, label="resolved revision")

    @field_validator("rule_digest", "selector_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="resolved digest")

    @field_validator("exception_refs", "policy_refs", mode="before")
    @classmethod
    def opaque_refs(cls, value: object) -> tuple[str, ...]:
        refs = tuple(require_nonblank(str(item), label="opaque ref") for item in as_tuple(value))
        for item in refs:
            lowered = item.lower()
            if "approver" in lowered or "approval" in lowered or "mailto:" in lowered:
                raise ValueError("approval identities cannot enter canonical computation")
        return refs


class EffectiveRuleSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = EFFECTIVE_SCHEMA
    schema_version: str = CONTRACT_VERSION
    effective_ruleset_digest: str
    ruleset_id: str
    ruleset_version: str
    ordered_composition: tuple[ParentRef, ...]
    rules: tuple[ResolvedRule, ...]
    resolver_version: str = RESOLVER_VERSION
    dsl_version: str = DSL_VERSION
    capability_version: str = CAPABILITY_VERSION
    signed_base_digest: str
    local_unsigned_config_digest: str
    package_digest: str | None = None
    feed_digest: str | None = None
    input_digest: str
    config_digest: str
    execution_purpose: ExecutionPurpose
    validity_not_before: str | None = None
    validity_not_after: str | None = None
    preview_cannot_authorize_production: bool = True

    @field_validator(
        "effective_ruleset_digest",
        "signed_base_digest",
        "local_unsigned_config_digest",
        "input_digest",
        "config_digest",
        mode="before",
    )
    @classmethod
    def normalize_required_digest(cls, value: object) -> str:
        return require_content_digest(value, label="effective digest")

    @field_validator("package_digest", "feed_digest", mode="before")
    @classmethod
    def normalize_optional_digest(cls, value: object) -> str | None:
        if value is None:
            return None
        return require_content_digest(value, label="optional digest")

    @field_validator("ruleset_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="ruleset_id")

    @field_validator("ruleset_version", "resolver_version", "capability_version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return require_pinned_version(value, label="effective version")

    @model_validator(mode="after")
    def freeze_resolved(self, info: ValidationInfo) -> EffectiveRuleSet:
        require_supported_major(self.schema_version)
        if not self.rules:
            raise ValueError("effective ruleset must materialize at least one rule")
        if self.preview_cannot_authorize_production is not True:
            raise ValueError("preview signer/purpose cannot authorize production")
        if self.execution_purpose is ExecutionPurpose.PRODUCTION:
            if self.validity_not_after is None:
                raise ValueError("production effective ruleset needs validity_not_after")
        payload = self.model_dump(mode="json")
        walk_forbidden_identity(payload)
        walk_forbidden_credentials(payload)
        expected = digest_canonical(omit_key(payload, "effective_ruleset_digest"))
        if self.effective_ruleset_digest != expected and not is_binding_digest(info):
            raise ValueError("effective_ruleset_digest does not match canonical payload")
        return self


class PackageCompatibility(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    engine_schema_major: int = 1
    dsl_version: str = DSL_VERSION
    capability_version: str = CAPABILITY_VERSION
    serialization_profile: str = "codestrata.canonical-json.v1"

    @field_validator("capability_version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return require_pinned_version(value, label="capability_version")


class PayloadDigest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    digest: str

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> str:
        return require_nonblank(str(value), label="payload name")

    @field_validator("digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="payload digest")


class SignedPackageBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = PACKAGE_SCHEMA
    schema_version: str = CONTRACT_VERSION
    package_id: str
    package_version: str
    effective_ruleset_digest: str
    payload_digests: tuple[PayloadDigest, ...]
    execution_purpose: ExecutionPurpose
    compatibility: PackageCompatibility
    validity_not_before: str | None = None
    validity_not_after: str | None = None
    preview_cannot_authorize_production: bool = True

    @field_validator("package_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="package_id")

    @field_validator("package_version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return require_pinned_version(value, label="package_version")

    @field_validator("effective_ruleset_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="effective_ruleset_digest")

    @model_validator(mode="after")
    def distinct_purpose(self) -> SignedPackageBody:
        require_supported_major(self.schema_version)
        if not self.payload_digests:
            raise ValueError("signed package must bind payload digests")
        if self.preview_cannot_authorize_production is not True:
            raise ValueError("preview signer cannot authorize production")
        if self.execution_purpose is ExecutionPurpose.CANDIDATE_VALIDATION:
            raise ValueError(
                "candidate_validation is not a signed production/preview package purpose"
            )
        payload = self.model_dump(mode="json")
        walk_forbidden_identity(payload)
        walk_forbidden_credentials(payload)
        return self


class SignedPackageOperational(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    signature: str | None = None
    signed_at: str | None = None


class SignedPackageManifest(BaseModel):
    """Distribution container. Signature timestamps stay outside body_digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = PACKAGE_SCHEMA
    schema_version: str = CONTRACT_VERSION
    body: SignedPackageBody
    body_digest: str
    operational: SignedPackageOperational = Field(default_factory=SignedPackageOperational)

    @model_validator(mode="after")
    def digest_matches(self) -> SignedPackageManifest:
        require_supported_major(self.schema_version)
        expected = digest_canonical(self.body.model_dump(mode="json"))
        if self.body_digest != expected:
            raise ValueError("package body_digest does not match canonical body")
        return self


def bind_digest[T: BaseModel](
    model_cls: type[T],
    payload: dict[str, Any],
    key: str = "digest",
) -> T:
    return bind_content_digest(model_cls, payload, key)


def seal_package(
    body: SignedPackageBody,
    operational: SignedPackageOperational | None = None,
) -> SignedPackageManifest:
    return SignedPackageManifest(
        body=body,
        body_digest=digest_canonical(body.model_dump(mode="json")),
        operational=operational or SignedPackageOperational(),
    )


def admit_package(manifest: SignedPackageManifest, requested: ExecutionPurpose) -> None:
    purpose = manifest.body.execution_purpose
    if requested is ExecutionPurpose.PRODUCTION and purpose is not ExecutionPurpose.PRODUCTION:
        raise ContractError("preview-only package cannot admit production")
    if requested is ExecutionPurpose.PRODUCTION and purpose is ExecutionPurpose.PREVIEW:
        raise ContractError("preview purpose is distinct and cannot silently become production")


def parse_rule(payload: object) -> Rule:
    return _parse(Rule, payload)


def parse_ruleset(payload: object) -> RuleSet:
    return _parse(RuleSet, payload)


def parse_effective_ruleset(payload: object) -> EffectiveRuleSet:
    return _parse(EffectiveRuleSet, payload)


def parse_signed_package(payload: object) -> SignedPackageManifest:
    return _parse(SignedPackageManifest, payload)


def _parse[T: BaseModel](model: type[T], payload: object) -> T:
    if not isinstance(payload, dict):
        raise ContractError("contract must be an object")
    try:
        require_supported_major(str(payload.get("schema_version", "")))
        return model.model_validate(payload)
    except (ValidationError, ValueError) as error:
        raise ContractError(str(error)) from error


def unsigned_rule_payload(rule: Rule) -> dict[str, Any]:
    return omit_key(rule.model_dump(mode="json"), "digest")
