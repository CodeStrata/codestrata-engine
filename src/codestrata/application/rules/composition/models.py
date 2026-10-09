"""Composed RuleSet artifact produced by E04.1 (not yet an Effective RuleSet)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from codestrata.domain.contracts.rules import (
    CAPABILITY_VERSION,
    CONTRACT_VERSION,
    DSL_VERSION,
    RESOLVER_VERSION,
    ParentRef,
    RuleSetEntry,
    SelectorDef,
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
from codestrata.domain.graph.validation import require_nonblank

COMPOSED_SCHEMA = "codestrata.composed-ruleset.v1"


class ComposedRuleSet(BaseModel):
    """Flattened, pinned composition. Policy overrides remain E04.2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = COMPOSED_SCHEMA
    schema_version: str = CONTRACT_VERSION
    composition_digest: str
    ruleset_id: str
    ruleset_version: str
    root_digest: str
    ordered_composition: tuple[ParentRef, ...]
    selectors: tuple[SelectorDef, ...]
    rules: tuple[RuleSetEntry, ...]
    resolver_version: str = RESOLVER_VERSION
    dsl_version: str = DSL_VERSION
    capability_version: str = CAPABILITY_VERSION

    @field_validator("composition_digest", "root_digest", mode="before")
    @classmethod
    def normalize_digest(cls, value: object) -> str:
        return require_content_digest(value, label="composition digest")

    @field_validator("ruleset_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="ruleset_id")

    @field_validator("ruleset_version", "resolver_version", "capability_version", mode="before")
    @classmethod
    def normalize_version(cls, value: object) -> str:
        return require_pinned_version(value, label="composed version")

    @model_validator(mode="after")
    def freeze_composed(self, info: ValidationInfo) -> ComposedRuleSet:
        require_supported_major(self.schema_version)
        if not self.rules:
            raise ValueError("composed ruleset must materialize at least one rule")
        payload = self.model_dump(mode="json")
        expected = digest_canonical(omit_key(payload, "composition_digest"))
        if self.composition_digest != expected and not is_binding_digest(info):
            raise ValueError("composition_digest does not match canonical payload")
        return self


def bind_composed(payload: dict[str, Any]) -> ComposedRuleSet:
    return bind_content_digest(ComposedRuleSet, payload, key="composition_digest")


def selector_ast_digest(selector: SelectorDef) -> str:
    return digest_canonical({"source": selector.source, "nodes": selector.nodes})
