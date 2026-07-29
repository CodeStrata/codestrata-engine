"""Rule contracts for the deterministic Assessment Graph Rule Engine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.domain.assessment_graph import AssessmentGraph, AssessmentNodeType
from codestrata.domain.engineering_knowledge import EngineeringKnowledgeGraph
from codestrata.domain.findings import Finding
from codestrata.domain.graph.ids import NodeId
from codestrata.domain.graph.models import GraphNode
from codestrata.domain.graph.validation import as_tuple, require_nonblank
from codestrata.domain.knowledge_binding import KnowledgeBinding, KnowledgeBindingResult
from codestrata.domain.repository import RepositoryFileKind, RepositoryManifest
from codestrata.domain.repository_graph import RepositoryGraph, RepositoryNodeType
from codestrata.domain.repository_graph.dependencies import DependencyVersion


class RuleContext(BaseModel):
    """Read-only evaluation context for Assessment Graph rules.

    Provides Assessment Graph bindings plus supporting inventory/graph views.
    Rules must not mutate any nested graph or result object.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    assessment_graph: AssessmentGraph
    repository_graph: RepositoryGraph
    knowledge_graph: EngineeringKnowledgeGraph
    binding_result: KnowledgeBindingResult
    manifest: RepositoryManifest

    def bound_keys(self) -> frozenset[str]:
        return frozenset(binding.matched_key for binding in self.binding_result.bindings)

    def bindings_for_key(self, canonical_key: str) -> tuple[KnowledgeBinding, ...]:
        key = canonical_key.strip().lower()
        return tuple(
            binding for binding in self.binding_result.bindings if binding.matched_key == key
        )

    def assessment_nodes_for_binding(
        self,
        binding: KnowledgeBinding,
    ) -> tuple[NodeId, ...]:
        """Return Assessment Graph node IDs related to a binding when present."""

        related: list[NodeId] = []
        for node in self.assessment_graph.nodes:
            props = node.properties
            if node.node_type == AssessmentNodeType.REPOSITORY_ENTITY_REFERENCE.value:
                if props.get("source_repository_node_id") == binding.repository_node_id.root:
                    related.append(node.id)
            elif node.node_type == AssessmentNodeType.KNOWLEDGE_CONCEPT_REFERENCE.value:
                if props.get("source_knowledge_node_id") == binding.knowledge_node_id.root:
                    related.append(node.id)
        return tuple(sorted(related, key=lambda item: item.root))

    def relative_paths(self) -> frozenset[str]:
        return frozenset(entry.path.root for entry in self.manifest.files)

    def basenames(self) -> frozenset[str]:
        names: set[str] = set()
        for path in self.relative_paths():
            names.add(path.rsplit("/", 1)[-1].lower())
        return frozenset(names)

    def has_basename(self, *candidates: str) -> bool:
        names = self.basenames()
        return any(candidate.lower() in names for candidate in candidates)

    def path_contains(self, fragment: str) -> bool:
        needle = fragment.lower()
        return any(needle in path.lower() for path in self.relative_paths())

    def file_count(self) -> int:
        return len(self.manifest.files)

    def source_file_count(self) -> int:
        return sum(
            1 for entry in self.manifest.files if entry.file_kind is RepositoryFileKind.SOURCE
        )

    def test_file_count(self) -> int:
        count = 0
        for entry in self.manifest.files:
            path = entry.path.root.lower()
            if entry.file_kind is RepositoryFileKind.TEST:
                count += 1
                continue
            if "/test/" in f"/{path}/" or "/tests/" in f"/{path}/":
                count += 1
                continue
            if path.startswith("test/") or path.startswith("tests/"):
                count += 1
        return count

    def repository_nodes_by_type(
        self,
        node_type: RepositoryNodeType | str,
    ) -> tuple[GraphNode, ...]:
        expected = node_type.value if isinstance(node_type, RepositoryNodeType) else node_type
        return tuple(node for node in self.repository_graph.nodes if node.node_type == expected)

    def dependency_nodes(self) -> tuple[GraphNode, ...]:
        return self.repository_nodes_by_type(RepositoryNodeType.DEPENDENCY)

    def find_dependency_nodes(
        self,
        *,
        name: str | None = None,
        ecosystem: str | None = None,
        namespace: str | None = None,
    ) -> tuple[GraphNode, ...]:
        matches: list[GraphNode] = []
        for node in self.dependency_nodes():
            props = node.properties
            if name is not None and str(props.get("name") or "").lower() != name.lower():
                continue
            if (
                ecosystem is not None
                and str(props.get("ecosystem") or "").lower() != ecosystem.lower()
            ):
                continue
            if namespace is not None:
                node_ns = props.get("namespace")
                if node_ns is None and namespace != "":
                    continue
                if node_ns is not None and str(node_ns).lower() != namespace.lower():
                    continue
            matches.append(node)
        return tuple(matches)

    def dependency_version(
        self,
        *,
        name: str,
        ecosystem: str | None = None,
        namespace: str | None = None,
    ) -> DependencyVersion | None:
        for node in self.find_dependency_nodes(
            name=name,
            ecosystem=ecosystem,
            namespace=namespace,
        ):
            raw = node.properties.get("version")
            if isinstance(raw, str) and raw.strip():
                return DependencyVersion(raw=raw.strip())
        return None

    def java_version(self) -> DependencyVersion | None:
        return self.dependency_version(name="java", ecosystem="jvm")

    def spring_boot_version(self) -> DependencyVersion | None:
        version = self.dependency_version(
            name="spring-boot",
            ecosystem="maven",
            namespace="org.springframework.boot",
        )
        if version is not None:
            return version
        return self.dependency_version(name="spring-boot", ecosystem="maven")

    def node_engine_version(self) -> DependencyVersion | None:
        return self.dependency_version(name="nodejs", ecosystem="nodejs")

    def has_maven_project(self) -> bool:
        return self.has_basename("pom.xml") or "maven" in self.bound_keys()

    def has_npm_project(self) -> bool:
        return self.has_basename("package.json")


class RuleResult(BaseModel):
    """Result of evaluating one rule against a context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    findings: tuple[Finding, ...] = ()
    skipped: bool = False
    skip_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("rule_id", mode="before")
    @classmethod
    def normalize_rule_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="rule_id")

    @field_validator("findings", mode="before")
    @classmethod
    def normalize_findings(cls, value: object) -> tuple[Any, ...]:
        return as_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("metadata must be a mapping")
        return dict(value)


@runtime_checkable
class Rule(Protocol):
    """Deterministic Assessment Graph rule contract."""

    def id(self) -> str:
        """Stable rule identity."""

    def name(self) -> str:
        """Human-readable rule name."""

    def description(self) -> str:
        """Explain what the rule detects."""

    def supported_languages(self) -> frozenset[str]:
        """Languages this rule applies to; empty means language-agnostic."""

    def evaluate(self, context: RuleContext) -> RuleResult:
        """Evaluate the rule without mutating graphs or calling AI."""
