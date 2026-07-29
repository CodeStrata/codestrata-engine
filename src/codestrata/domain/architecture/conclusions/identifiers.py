"""Architecture conclusion identifiers and deterministic ID builders."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from pydantic import RootModel, field_validator

from codestrata.domain.graph.validation import require_nonblank

_POLICY_ID_PATTERN = re.compile(
    r"^architecture\.conclusion\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
)
_CATEGORY_ID_PATTERN = re.compile(
    r"^architecture\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
)


def validate_policy_id(value: str) -> str:
    compact = value.strip().lower()
    if not _POLICY_ID_PATTERN.fullmatch(compact):
        raise ValueError(
            "policy_id must look like architecture.conclusion.<name> "
            "(example: architecture.conclusion.boundary-integrity)"
        )
    return compact


def validate_category_id(value: str) -> str:
    compact = value.strip().lower()
    if not _CATEGORY_ID_PATTERN.fullmatch(compact):
        raise ValueError(
            "category must look like architecture.<name> "
            "(example: architecture.boundary-integrity)"
        )
    return compact


def build_conclusion_id(
    *,
    policy_id: str,
    policy_version: str,
    repository_id: str,
    affected_scope: Sequence[str],
    source_finding_ids: Sequence[str],
) -> str:
    """Deterministic conclusion identity (no timestamps/UUIDs)."""

    policy = validate_policy_id(policy_id)
    version = require_nonblank(policy_version, label="policy_version")
    repo = require_nonblank(repository_id, label="repository_id").lower()
    scope = tuple(sorted({item.strip().lower() for item in affected_scope if item.strip()}))
    findings = tuple(sorted({item.strip() for item in source_finding_ids if item.strip()}))
    payload = "\n".join(
        [
            f"policy:{policy}",
            f"version:{version}",
            f"repo:{repo}",
            f"scope:{','.join(scope)}",
            f"findings:{','.join(findings)}",
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"conclusion:{policy}:{digest}"


def build_cluster_id(
    *,
    category: str,
    scope_keys: Sequence[str],
    finding_ids: Sequence[str],
) -> str:
    cat = validate_category_id(category)
    scope = tuple(sorted({item.strip().lower() for item in scope_keys if item.strip()}))
    findings = tuple(sorted({item.strip() for item in finding_ids if item.strip()}))
    payload = "\n".join([f"cat:{cat}", f"scope:{','.join(scope)}", f"f:{','.join(findings)}"])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"cluster:{cat}:{digest}"


def build_recommendation_group_id(
    *,
    conclusion_id: str,
    primary_action_key: str,
) -> str:
    conclusion = require_nonblank(conclusion_id, label="conclusion_id")
    action = require_nonblank(primary_action_key, label="primary_action_key").lower()
    digest = hashlib.sha256(f"{conclusion}\n{action}".encode()).hexdigest()[:16]
    return f"recgroup:{digest}"


class ArchitectureConclusionPolicyId(RootModel[str]):
    root: str

    @field_validator("root", mode="before")
    @classmethod
    def validate_root(cls, value: object) -> str:
        return validate_policy_id(str(value))

    def __str__(self) -> str:
        return self.root


class ArchitectureConclusionCategoryId(RootModel[str]):
    root: str

    @field_validator("root", mode="before")
    @classmethod
    def validate_root(cls, value: object) -> str:
        return validate_category_id(str(value))

    def __str__(self) -> str:
        return self.root


# Stable policy IDs.
POLICY_BOUNDARY_INTEGRITY = "architecture.conclusion.boundary-integrity"
POLICY_CYCLIC_DEPENDENCY = "architecture.conclusion.cyclic-dependency-structure"
POLICY_BROAD_DEPENDENCY = "architecture.conclusion.broad-dependency-surface"
POLICY_FRAMEWORK_EROSION = "architecture.conclusion.framework-boundary-erosion"
POLICY_ENTERPRISE_NONCONFORMANCE = "architecture.conclusion.enterprise-nonconformance"
POLICY_POSITIVE_BOUNDARY = "architecture.conclusion.positive-boundary-conformance"
POLICY_INSUFFICIENT_EVIDENCE = "architecture.conclusion.insufficient-evidence"

# Categories.
CAT_BOUNDARY_INTEGRITY = "architecture.boundary-integrity"
CAT_DEPENDENCY_STRUCTURE = "architecture.dependency-structure"
CAT_MODULARITY = "architecture.modularity"
CAT_COUPLING = "architecture.coupling"
CAT_FRAMEWORK_INDEPENDENCE = "architecture.framework-independence"
CAT_ENTERPRISE_CONFORMANCE = "architecture.enterprise-conformance"
CAT_ARCHITECTURAL_STRENGTH = "architecture.architectural-strength"
CAT_INSUFFICIENT_EVIDENCE = "architecture.insufficient-evidence"
