"""Domain contracts for deterministic repository-to-knowledge bindings.

Bindings are produced by the Knowledge Pipeline service and remain outside both
the Repository Graph and the Engineering Knowledge Graph.
"""

from codestrata.domain.knowledge_binding.enums import (
    KnowledgeBindingType,
    KnowledgeMatchingStrategy,
    KnowledgeObservationKind,
)
from codestrata.domain.knowledge_binding.ids import build_knowledge_binding_id
from codestrata.domain.knowledge_binding.models import (
    KNOWLEDGE_BINDING_RESULT_VERSION,
    KnowledgeBinding,
    KnowledgeBindingResult,
    UnmatchedKnowledgeObservation,
)

__all__ = [
    "KNOWLEDGE_BINDING_RESULT_VERSION",
    "KnowledgeBinding",
    "KnowledgeBindingResult",
    "KnowledgeBindingType",
    "KnowledgeMatchingStrategy",
    "KnowledgeObservationKind",
    "UnmatchedKnowledgeObservation",
    "build_knowledge_binding_id",
]
