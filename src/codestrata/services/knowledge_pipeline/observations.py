"""Extract deterministic match candidates from a Repository Graph.

Does not mutate the graph. Candidates are derived only from existing node
properties (dependency names, file languages, module build systems).
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.domain.engineering_knowledge.ids import normalize_canonical_key
from codestrata.domain.graph.models import GraphNode
from codestrata.domain.graph.validation import require_nonblank
from codestrata.domain.knowledge_binding.enums import KnowledgeObservationKind
from codestrata.domain.repository_graph.enums import RepositoryNodeType
from codestrata.domain.repository_graph.models import RepositoryGraph


class RepositoryKnowledgeObservation(BaseModel):
    """One normalized candidate key observed on a Repository Graph node."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_node: GraphNode
    observation_kind: KnowledgeObservationKind
    candidate_key: str

    @field_validator("candidate_key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> str:
        return normalize_canonical_key(str(value))


def _observation_key(raw: str) -> str:
    """Normalize an observed name into a knowledge candidate key.

    Composer (``vendor/package``) and npm scoped packages (``@scope/name``) are
    rewritten so they remain valid canonical keys without inventing aliases.
    Display labels such as ``C#`` are normalized by stripping ``#``.
    """

    compact = (
        raw.strip()
        .replace("@", "")
        .replace("#", "")
        .replace("/", "-")
        .replace("\\", "-")
    )
    return normalize_canonical_key(compact)


def extract_repository_observations(
    repository_graph: RepositoryGraph,
) -> tuple[RepositoryKnowledgeObservation, ...]:
    """Collect exact-match candidate keys from repository graph nodes."""

    observations: list[RepositoryKnowledgeObservation] = []
    for node in repository_graph.nodes:
        observations.extend(_observations_for_node(node))
    return tuple(
        sorted(
            observations,
            key=lambda item: (
                item.repository_node.id.root,
                item.observation_kind.value,
                item.candidate_key,
            ),
        )
    )


def _observations_for_node(node: GraphNode) -> Sequence[RepositoryKnowledgeObservation]:
    node_type = node.node_type
    properties = node.properties

    if node_type == RepositoryNodeType.DEPENDENCY.value:
        name = properties.get("name")
        if isinstance(name, str) and name.strip():
            try:
                key = _observation_key(name)
            except ValueError:
                return ()
            return (
                RepositoryKnowledgeObservation(
                    repository_node=node,
                    observation_kind=KnowledgeObservationKind.DEPENDENCY_NAME,
                    candidate_key=key,
                ),
            )
        return ()

    if node_type == RepositoryNodeType.FILE.value:
        language = properties.get("language")
        if isinstance(language, str) and language.strip():
            try:
                key = _observation_key(language)
            except ValueError:
                return ()
            return (
                RepositoryKnowledgeObservation(
                    repository_node=node,
                    observation_kind=KnowledgeObservationKind.FILE_LANGUAGE,
                    candidate_key=key,
                ),
            )
        return ()

    if node_type == RepositoryNodeType.MODULE.value:
        build_system = properties.get("build_system")
        if isinstance(build_system, str) and build_system.strip():
            return (
                RepositoryKnowledgeObservation(
                    repository_node=node,
                    observation_kind=KnowledgeObservationKind.MODULE_BUILD_SYSTEM,
                    candidate_key=build_system,
                ),
            )
        return ()

    # Unknown / non-matchable node types are ignored for this milestone.
    _ = require_nonblank(node_type, label="node_type")
    return ()
