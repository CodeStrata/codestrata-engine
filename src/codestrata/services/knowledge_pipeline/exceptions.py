"""Focused errors for Knowledge Pipeline matching."""

from __future__ import annotations


class KnowledgePipelineError(ValueError):
    """Base error for Knowledge Pipeline failures."""


class AmbiguousKnowledgeConceptError(KnowledgePipelineError):
    """Raised when a normalized alias maps to more than one knowledge concept."""

    def __init__(
        self,
        *,
        alias: str,
        knowledge_node_ids: tuple[str, ...],
        catalog_hint: str | None = None,
    ) -> None:
        ids = ", ".join(knowledge_node_ids)
        hint = f" Catalog/provenance: {catalog_hint}." if catalog_hint else ""
        super().__init__(
            "Ambiguous engineering knowledge alias "
            f"'{alias}' maps to multiple concepts: {ids}.{hint} "
            "Resolve the catalog ambiguity before binding."
        )
        self.alias = alias
        self.knowledge_node_ids = knowledge_node_ids
        self.catalog_hint = catalog_hint
