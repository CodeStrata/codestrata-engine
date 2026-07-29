"""Architecture conclusion policy contracts and registry."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.architecture.conclusions.enums import ConclusionPolicyStatus
from codestrata.domain.architecture.conclusions.identifiers import validate_policy_id
from codestrata.domain.architecture.conclusions.models import ArchitectureConclusion
from codestrata.domain.architecture.conclusions.relationships import FindingCluster
from codestrata.domain.findings import Finding
from codestrata.domain.graph.validation import as_tuple, require_nonblank


class ConclusionPolicyMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str
    policy_version: str = "1.0.0"
    category: str
    title: str
    description: str
    source_rule_ids: tuple[str, ...] = ()
    enterprise_only: bool = False
    enabled_by_default: bool = True
    documentation_reference: str | None = None

    @field_validator("policy_id", mode="before")
    @classmethod
    def normalize_policy(cls, value: object) -> str:
        return validate_policy_id(str(value))

    @field_validator("policy_version", "category", "title", "description", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="policy metadata field")

    @field_validator("source_rule_ids", mode="before")
    @classmethod
    def normalize_rules(cls, value: object) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in as_tuple(value) if str(item).strip()}))


class ConclusionPolicyContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    repository_id: str
    findings: tuple[Finding, ...] = ()
    cluster: FindingCluster | None = None
    extraction_coverage: float | None = None
    classification_coverage: float | None = None
    enterprise_context_present: bool = False
    graph_fingerprint: str = ""

    @field_validator("repository_id", mode="before")
    @classmethod
    def normalize_repo(cls, value: object) -> str:
        return require_nonblank(str(value), label="repository_id")

    @field_validator("findings", mode="before")
    @classmethod
    def normalize_findings(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class ConclusionPolicyResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ConclusionPolicyStatus
    conclusions: tuple[ArchitectureConclusion, ...] = ()
    message: str | None = None

    @classmethod
    def succeeded(cls, *conclusions: ArchitectureConclusion) -> ConclusionPolicyResult:
        return cls(status=ConclusionPolicyStatus.SUCCEEDED, conclusions=tuple(conclusions))

    @classmethod
    def not_applicable(cls, message: str) -> ConclusionPolicyResult:
        return cls(status=ConclusionPolicyStatus.NOT_APPLICABLE, message=message)

    @classmethod
    def failed(cls, message: str) -> ConclusionPolicyResult:
        return cls(status=ConclusionPolicyStatus.FAILED, message=message)

    @classmethod
    def skipped(cls, message: str) -> ConclusionPolicyResult:
        return cls(status=ConclusionPolicyStatus.SKIPPED, message=message)


@runtime_checkable
class ArchitectureConclusionPolicy(Protocol):
    @property
    def metadata(self) -> ConclusionPolicyMetadata: ...

    def evaluate(self, context: ConclusionPolicyContext) -> ConclusionPolicyResult: ...


class ArchitectureConclusionPolicyRegistry:
    def __init__(self) -> None:
        self._policies: dict[str, ArchitectureConclusionPolicy] = {}

    def register(self, policy: ArchitectureConclusionPolicy) -> None:
        meta = policy.metadata
        policy_id = meta.policy_id
        existing = self._policies.get(policy_id)
        if existing is not None:
            if existing.metadata.policy_version != meta.policy_version:
                raise ValueError(
                    f"Conflicting versions for conclusion policy {policy_id}: "
                    f"{existing.metadata.policy_version} vs {meta.policy_version}"
                )
            raise ValueError(f"Duplicate conclusion policy ID: {policy_id}")
        self._policies[policy_id] = policy

    def register_collection(
        self,
        policies: Sequence[ArchitectureConclusionPolicy] | Iterable[ArchitectureConclusionPolicy],
    ) -> None:
        for policy in policies:
            self.register(policy)

    def get(self, policy_id: str) -> ArchitectureConclusionPolicy:
        key = policy_id.strip().lower()
        policy = self._policies.get(key)
        if policy is None:
            raise KeyError(f"Unknown conclusion policy: {policy_id}")
        return policy

    def list_policies(
        self,
        *,
        category: str | None = None,
        enabled_only: bool = False,
    ) -> tuple[ConclusionPolicyMetadata, ...]:
        items: list[ConclusionPolicyMetadata] = []
        for policy_id in sorted(self._policies):
            meta = self._policies[policy_id].metadata
            if enabled_only and not meta.enabled_by_default:
                continue
            if category is not None and meta.category != category.strip().lower():
                continue
            items.append(meta)
        return tuple(items)

    def policies(self) -> tuple[ArchitectureConclusionPolicy, ...]:
        return tuple(self._policies[key] for key in sorted(self._policies))

    @property
    def size(self) -> int:
        return len(self._policies)
