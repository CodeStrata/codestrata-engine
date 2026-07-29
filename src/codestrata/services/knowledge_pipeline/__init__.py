"""Knowledge Pipeline services.

Connects Repository Graph observations to Engineering Knowledge concepts via
deterministic exact matching. Output is ``KnowledgeBindingResult`` for future
Assessment Graph consumption.
"""

from __future__ import annotations

from codestrata.services.knowledge_pipeline.exceptions import (
    AmbiguousKnowledgeConceptError,
    KnowledgePipelineError,
)
from codestrata.services.knowledge_pipeline.pipeline import (
    KnowledgePipeline,
    bind_repository_knowledge,
)

__all__ = [
    "AmbiguousKnowledgeConceptError",
    "KnowledgePipeline",
    "KnowledgePipelineError",
    "bind_repository_knowledge",
]
