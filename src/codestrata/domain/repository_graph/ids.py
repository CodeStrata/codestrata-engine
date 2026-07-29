"""Deterministic Repository Graph node identity construction.

Identity rules (language-neutral, storage-independent):

- ``repository_key`` is an explicitly supplied stable key (not a raw URL with
  credentials, and not a display name alone).
- File identities use repository-relative POSIX paths; absolute paths and
  ``..`` traversal segments are rejected.
- Qualified names and signatures are normalized (strip) but not language-parsed.
- Callable identities include owner plus signature so overloads stay distinct.
- Dependency identities include ecosystem and coordinates but omit version so
  version upgrades preserve logical identity.

Path and repository-key normalization live in ``codestrata.domain.repository`` so
inventory and graph identities share one implementation.
"""

from __future__ import annotations

from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.validation import require_nonblank
from codestrata.domain.repository.identities import normalize_repository_key
from codestrata.domain.repository.paths import normalize_repository_relative_path

__all__ = [
    "RepositoryNodeIdFactory",
    "normalize_dependency_namespace",
    "normalize_qualified_name",
    "normalize_repository_key",
    "normalize_repository_relative_path",
]


def normalize_qualified_name(value: str, *, label: str) -> str:
    """Strip a qualified name without applying language-specific parsing."""

    return require_nonblank(value, label=label)


def normalize_dependency_namespace(value: str | None) -> str:
    """Normalize an optional dependency namespace; ``_`` marks absence."""

    if value is None:
        return "_"
    compact = require_nonblank(value, label="dependency namespace")
    if compact == "_":
        return "_"
    return compact


class RepositoryNodeIdFactory:
    """Build deterministic ``NodeId`` values for Repository Graph nodes."""

    def __init__(self, repository_key: str) -> None:
        self._repository_key = normalize_repository_key(repository_key)

    @property
    def repository_key(self) -> str:
        return self._repository_key

    def repository(self) -> NodeId:
        return NodeId(f"repo:{self._repository_key}")

    def module(self, module_key: str) -> NodeId:
        """Build a module ID from a normalized repository-relative module path.

        Module identity uses the full module root path (for example
        ``services/orders``), not only the final directory segment, so sibling
        directories with the same basename remain distinct.
        """

        path = normalize_repository_relative_path(module_key)
        return NodeId(f"repo:{self._repository_key}:module:{path}")

    def file(self, relative_path: str) -> NodeId:
        path = normalize_repository_relative_path(relative_path)
        return NodeId(f"repo:{self._repository_key}:file:{path}")

    def namespace(self, qualified_name: str) -> NodeId:
        name = normalize_qualified_name(qualified_name, label="qualified_name")
        return NodeId(f"repo:{self._repository_key}:namespace:{name}")

    def type(self, qualified_name: str) -> NodeId:
        name = normalize_qualified_name(qualified_name, label="qualified_name")
        return NodeId(f"repo:{self._repository_key}:type:{name}")

    def callable(self, *, qualified_owner: str, signature: str) -> NodeId:
        owner = normalize_qualified_name(qualified_owner, label="qualified_owner")
        sig = require_nonblank(signature, label="signature")
        return NodeId(f"repo:{self._repository_key}:callable:{owner}#{sig}")

    def dependency(
        self,
        *,
        ecosystem: str,
        name: str,
        namespace: str | None = None,
    ) -> NodeId:
        eco = require_nonblank(ecosystem, label="ecosystem")
        dep_name = require_nonblank(name, label="dependency name")
        group = normalize_dependency_namespace(namespace)
        return NodeId(f"repo:{self._repository_key}:dependency:{eco}:{group}:{dep_name}")
