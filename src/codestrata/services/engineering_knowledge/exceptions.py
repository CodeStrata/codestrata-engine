"""Focused errors for Engineering Knowledge Catalog loading."""

from __future__ import annotations


class EngineeringKnowledgeCatalogError(ValueError):
    """Base error for curated catalog load failures."""


class EngineeringKnowledgeCatalogParseError(EngineeringKnowledgeCatalogError):
    """Raised when catalog text cannot be safely parsed into a document."""


class EngineeringKnowledgeCatalogValidationError(EngineeringKnowledgeCatalogError):
    """Raised when a parsed catalog fails document or graph construction rules."""
