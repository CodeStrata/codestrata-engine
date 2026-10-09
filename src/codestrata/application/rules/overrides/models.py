"""Bounded override, exception and overridden-RuleSet models (E04.2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from codestrata.application.rules.overrides.authority import (
    require_opaque_exception_ref,
    require_opaque_policy_ref,
)
from codestrata.application.rules.overrides.errors import OverrideError
from codestrata.application.rules.overrides.presentation import (
    PresentationFields,
    PresentationOverlay,
)
from codestrata.domain.contracts.rules import (
    CAPABILITY_VERSION,
    CONTRACT_VERSION,
    DSL_VERSION,
    RESOLVER_VERSION,
    ResolvedRule,
)
from codestrata.domain.contracts.serialization import (
    bind_content_digest,
    digest_canonical,
    is_binding_digest,
    omit_key,
    require_content_digest,
    require_pinned_version,
    require_supported_major,
)
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.rules.identifiers import validate_rule_id

OVERRIDE_BUNDLE_SCHEMA = "codestrata.policy-override-bundle.v1"
OVERRIDDEN_SCHEMA = "codestrata.overridden-ruleset.v1"
SCOPE_KINDS = frozenset({"path", "component", "subject"})
OFF_SEVERITY_TOKENS = frozenset({"off", "disabled", "none", "false", "0", "exempt"})
MAX_POLICIES = 64
MAX_OVERRIDES = 1000
MAX_EXCEPTIONS = 1000
MAX_SCOPE_IDENTIFIERS = 256


class SubjectScope(BaseModel):
    """Resolved local subject scope. No organization or workspace authority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["path", "component", "subject"]
    identifiers: tuple[str, ...]

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> str:
        kind = require_nonblank(str(value), label="scope kind").lower()
        if kind not in SCOPE_KINDS:
            raise OverrideError("invalid_scope", f"unsupported subject scope kind {kind!r}")
        return kind

    @field_validator("identifiers", mode="before")
    @classmethod
    def normalize_identifiers(cls, value: object, info: ValidationInfo) -> tuple[str, ...]:
        kind = str((info.data or {}).get("kind") or "subject")
        items = [_normalize_identifier(str(item), kind=kind) for item in as_tuple(value)]
        unique = tuple(sorted(set(items)))
        if not unique:
            raise OverrideError("invalid_scope", "subject scope requires at least one identifier")
        if len(unique) > MAX_SCOPE_IDENTIFIERS:
            raise OverrideError(
                "excessive_size",
                f"subject scope exceeds {MAX_SCOPE_IDENTIFIERS} identifiers",
            )
        return unique


class TypedOverride(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    revision: str
    enabled: bool | None = None
    severity: FindingSeverity | None = None
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    presentation: PresentationOverlay | None = None

    @field_validator("rule_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return validate_rule_id(str(value))

    @field_validator("revision", mode="before")
    @classmethod
    def normalize_revision(cls, value: object) -> str:
        return require_pinned_version(value, label="override revision")

    @field_validator("severity", mode="before")
    @classmethod
    def reject_off_severity(cls, value: object) -> object:
        return reject_off_severity(value)

    @field_validator("parameters", mode="before")
    @classmethod
    def scalar_parameters(cls, value: object) -> dict[str, str | int | float | bool]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise OverrideError("unknown_parameter", "parameters must be a mapping")
        return {str(key): _require_scalar(item) for key, item in value.items()}


class PolicyFragment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_ref: str
    version: str
    overrides: tuple[TypedOverride, ...] = ()

    @field_validator("policy_ref", mode="before")
    @classmethod
    def opaque_policy(cls, value: object) -> str:
        return require_opaque_policy_ref(value)

    @field_validator("version", mode="before")
    @classmethod
    def pinned_version(cls, value: object) -> str:
        return require_pinned_version(value, label="policy version")

    @field_validator("overrides", mode="before")
    @classmethod
    def bound_overrides(cls, value: object) -> tuple[TypedOverride, ...]:
        items = tuple(
            item if isinstance(item, TypedOverride) else TypedOverride.model_validate(item)
            for item in as_tuple(value)
        )
        if len(items) > MAX_OVERRIDES:
            raise OverrideError("excessive_size", f"policy exceeds {MAX_OVERRIDES} overrides")
        return items


class ScopedException(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    exception_ref: str
    rule_id: str
    revision: str
    scope: SubjectScope
    enabled: bool | None = None
    severity: FindingSeverity | None = None
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    presentation: PresentationOverlay | None = None
    valid_not_after: str | None = None

    @field_validator("exception_ref", mode="before")
    @classmethod
    def opaque_exception(cls, value: object) -> str:
        return require_opaque_exception_ref(value)

    @field_validator("rule_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return validate_rule_id(str(value))

    @field_validator("revision", mode="before")
    @classmethod
    def normalize_revision(cls, value: object) -> str:
        return require_pinned_version(value, label="exception revision")

    @field_validator("severity", mode="before")
    @classmethod
    def reject_off(cls, value: object) -> object:
        return reject_off_severity(value)

    @field_validator("parameters", mode="before")
    @classmethod
    def scalar_parameters(cls, value: object) -> dict[str, str | int | float | bool]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise OverrideError("unknown_parameter", "parameters must be a mapping")
        return {str(key): _require_scalar(item) for key, item in value.items()}

    @field_validator("valid_not_after", mode="before")
    @classmethod
    def optional_timestamp(cls, value: object) -> str | None:
        if value is None:
            return None
        text = require_nonblank(str(value), label="valid_not_after")
        if "T" not in text:
            raise OverrideError("invalid_document", "valid_not_after must be an ISO-8601 timestamp")
        return text


class PolicyOverrideBundle(BaseModel):
    """Platform-resolved overlay admitted by Engine. No approval workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = OVERRIDE_BUNDLE_SCHEMA
    schema_version: str = CONTRACT_VERSION
    policies: tuple[PolicyFragment, ...] = ()
    exceptions: tuple[ScopedException, ...] = ()

    @field_validator("policies", mode="before")
    @classmethod
    def bound_policies(cls, value: object) -> tuple[PolicyFragment, ...]:
        items = tuple(
            item if isinstance(item, PolicyFragment) else PolicyFragment.model_validate(item)
            for item in as_tuple(value)
        )
        if len(items) > MAX_POLICIES:
            raise OverrideError("excessive_size", f"bundle exceeds {MAX_POLICIES} policies")
        return items

    @field_validator("exceptions", mode="before")
    @classmethod
    def bound_exceptions(cls, value: object) -> tuple[ScopedException, ...]:
        items = tuple(
            item if isinstance(item, ScopedException) else ScopedException.model_validate(item)
            for item in as_tuple(value)
        )
        if len(items) > MAX_EXCEPTIONS:
            raise OverrideError("excessive_size", f"bundle exceeds {MAX_EXCEPTIONS} exceptions")
        return items

    @model_validator(mode="after")
    def supported_schema(self) -> PolicyOverrideBundle:
        require_supported_major(self.schema_version)
        if self.schema_name != OVERRIDE_BUNDLE_SCHEMA:
            raise OverrideError("invalid_document", "unexpected policy override bundle schema")
        return self


class ScopedExceptionApplication(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    exception_refs: tuple[str, ...]
    scope: SubjectScope
    enabled: bool | None = None
    severity: FindingSeverity | None = None
    parameters: dict[str, str | int | float | bool] = Field(default_factory=dict)
    presentation: PresentationOverlay | None = None
    valid_not_after: str | None = None


class AppliedRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resolved: ResolvedRule
    presentation: PresentationFields
    scoped_exceptions: tuple[ScopedExceptionApplication, ...] = ()


class OverriddenRuleSet(BaseModel):
    """Policy-applied composition. Package/feed/input sealing remains E04.3."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = OVERRIDDEN_SCHEMA
    schema_version: str = CONTRACT_VERSION
    overlay_digest: str
    composition_digest: str
    ruleset_id: str
    ruleset_version: str
    rules: tuple[AppliedRule, ...]
    resolver_version: str = RESOLVER_VERSION
    dsl_version: str = DSL_VERSION
    capability_version: str = CAPABILITY_VERSION

    @field_validator("overlay_digest", "composition_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="overlay digest")

    @field_validator("ruleset_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="ruleset_id")

    @field_validator("ruleset_version", "resolver_version", "capability_version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return require_pinned_version(value, label="overridden version")

    @model_validator(mode="after")
    def freeze_overlay(self, info: ValidationInfo) -> OverriddenRuleSet:
        require_supported_major(self.schema_version)
        if not self.rules:
            raise OverrideError("invalid_document", "overridden ruleset must materialize rules")
        payload = self.model_dump(mode="json")
        expected = digest_canonical(omit_key(payload, "overlay_digest"))
        if self.overlay_digest != expected and not is_binding_digest(info):
            raise OverrideError(
                "invalid_document",
                "overlay_digest does not match canonical payload",
            )
        return self


def bind_overridden(payload: dict[str, Any]) -> OverriddenRuleSet:
    return bind_content_digest(OverriddenRuleSet, payload, key="overlay_digest")


def reject_off_severity(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, FindingSeverity):
        return value
    token = str(value).strip().lower()
    if token in OFF_SEVERITY_TOKENS:
        raise OverrideError(
            "off_is_not_severity",
            "off is never a severity; use enabled=false to disable evaluation",
        )
    return value


def _require_scalar(value: object) -> str | int | float | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float | str):
        return value
    raise OverrideError(
        "unknown_parameter",
        f"parameter values must be scalars, not {type(value).__name__}",
    )


def _normalize_identifier(value: str, *, kind: str) -> str:
    text = require_nonblank(value, label="subject identifier")
    if ".." in text or "~" in text or "://" in text:
        raise OverrideError(
            "invalid_scope",
            f"subject identifier is not a resolved local scope: {text}",
        )
    if kind == "path":
        normalized = text.replace("\\", "/")
        drive = normalized.split("/", 1)[0]
        if ":" in drive and len(drive) <= 2:
            raise OverrideError(
                "invalid_scope",
                "absolute drive paths are not local subject scopes",
            )
        return normalized
    return text
