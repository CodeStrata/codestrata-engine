"""Deliberate mapping from existing Engine identities onto the E01.2 contract."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.contracts.catalog import PACKAGE_REVISION
from codestrata.domain.contracts.enums import SubjectKind
from codestrata.domain.findings.ids import build_finding_id
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.repository.identities import normalize_repository_key
from codestrata.domain.repository.paths import normalize_repository_relative_path
from codestrata.domain.repository_graph.ids import RepositoryNodeIdFactory
from codestrata.domain.rules.identifiers import validate_rule_id


class IdentityMapping(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: SubjectKind
    existing_form: str
    canonical_form: str
    compatibility: str
    notes: str


IDENTITY_MAP: tuple[IdentityMapping, ...] = (
    IdentityMapping(
        kind=SubjectKind.REPOSITORY,
        existing_form="repo:{repository_key}",
        canonical_form="repo:{repository_key}",
        compatibility="unchanged",
        notes=(
            "Repository root identity is an explicit local key via "
            "RepositoryNodeIdFactory. It is not an inferred organization URL."
        ),
    ),
    IdentityMapping(
        kind=SubjectKind.FILE,
        existing_form="repo:{repository_key}:file:{posix_relative_path}",
        canonical_form="repo:{repository_key}:file:{posix_relative_path}",
        compatibility="unchanged",
        notes=(
            "File identity is the normalized relative path under the repository. "
            "Absolute paths and '..' are rejected. Comparisons may apply verified "
            "Git rename mapping later without rewriting this form."
        ),
    ),
    IdentityMapping(
        kind=SubjectKind.COMPONENT,
        existing_form="repo:{repository_key}:module:{module_path}",
        canonical_form="repo:{repository_key}:module:{module_path}",
        compatibility="unchanged",
        notes="Module/component identity uses the full repository-relative path.",
    ),
    IdentityMapping(
        kind=SubjectKind.SYMBOL,
        existing_form="repo:{key}:callable:{owner}:{name}:{signature}",
        canonical_form="repo:{key}:callable:{owner}:{name}:{signature}",
        compatibility="unchanged",
        notes="Symbols add qualified kind/name and disambiguating source identity.",
    ),
    IdentityMapping(
        kind=SubjectKind.FINDING,
        existing_form="finding:{rule_id}:{sha256(subject_keys)[:16]}",
        canonical_form="finding:{rule_id}:{sha256(subject_keys)[:16]}",
        compatibility="unchanged",
        notes=(
            "Finding matching uses stable rule identity plus subject and occurrence "
            "semantics. Source-line movement or message formatting alone cannot "
            "create a new finding. Ambiguous rename/occurrence mappings remain unknown."
        ),
    ),
    IdentityMapping(
        kind=SubjectKind.EVIDENCE,
        existing_form="evidence:{kind}:{working_state_digest}:{locator_digest}",
        canonical_form="evidence:{kind}:{working_state_digest}:{locator_digest}",
        compatibility="new_canonical",
        notes=(
            "Paths alone are not durable evidence identity. Evidence binds input "
            "revision or working-state digest, relative path/span or graph/feed/"
            "commit record, extractor version and limitation."
        ),
    ),
    IdentityMapping(
        kind=SubjectKind.DEPENDENCY,
        existing_form="repo:{key}:dep:{ecosystem}:{namespace}:{name}",
        canonical_form="repo:{key}:dep:{ecosystem}:{namespace}:{name}",
        compatibility="unchanged",
        notes="Dependency identity omits version so upgrades preserve logical identity.",
    ),
)


def repository_subject_id(repository_key: str) -> str:
    return str(RepositoryNodeIdFactory(repository_key).repository())


def file_subject_id(repository_key: str, relative_path: str) -> str:
    return str(RepositoryNodeIdFactory(repository_key).file(relative_path))


def component_subject_id(repository_key: str, module_key: str) -> str:
    return str(RepositoryNodeIdFactory(repository_key).module(module_key))


def evidence_id(
    *,
    kind: str,
    working_state_digest: str,
    locator: str,
) -> str:
    kind_n = require_nonblank(kind, label="evidence kind")
    digest = require_nonblank(working_state_digest, label="working_state_digest")
    loc = require_nonblank(locator, label="evidence locator")
    material = f"{kind_n}\n{digest}\n{loc}".encode()
    return f"evidence:{kind_n}:{digest}:{hashlib.sha256(material).hexdigest()[:16]}"


def canonical_finding_id(
    rule_id: str,
    subject_keys: Sequence[str],
    *,
    occurrence_key: str | None = None,
) -> str:
    """Stable finding ID. Line numbers and messages are not identity material."""

    rule = validate_rule_id(rule_id)
    keys = [require_nonblank(str(item), label="subject_key") for item in as_tuple(subject_keys)]
    if occurrence_key is not None:
        keys.append(require_nonblank(occurrence_key, label="occurrence_key"))
        if occurrence_key.isdigit():
            raise ValueError("occurrence_key must not be a source line number")
    return build_finding_id(rule_id=rule, subject_keys=keys)


def require_relative_path(path: str) -> str:
    return normalize_repository_relative_path(path)


def require_repository_key(key: str) -> str:
    return normalize_repository_key(key)


class IdentityMapDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    package_revision: str
    mappings: tuple[IdentityMapping, ...]

    @field_validator("package_revision", mode="before")
    @classmethod
    def normalize_revision(cls, value: object) -> str:
        return require_nonblank(str(value), label="package_revision")


def published_identity_map() -> IdentityMapDocument:
    return IdentityMapDocument(package_revision=PACKAGE_REVISION, mappings=IDENTITY_MAP)
