"""Engineering Knowledge Catalog loading services.

Curated catalog documents are versioned seed data. They become an
``EngineeringKnowledgeGraph`` only after safe parse, typed property validation,
duplicate checks, and domain schema validation. Loading is deterministic and
does not evaluate rule expressions or technology lifecycle dates.
"""

from __future__ import annotations

from codestrata.services.engineering_knowledge.builtin import (
    BUILTIN_CATALOG_ID,
    BUILTIN_CATALOG_VERSION,
    builtin_engineering_knowledge_catalog_path,
    load_builtin_engineering_knowledge_catalog,
)
from codestrata.services.engineering_knowledge.catalog_models import (
    EngineeringKnowledgeCatalogDocument,
    EngineeringKnowledgeCatalogNode,
    EngineeringKnowledgeCatalogReference,
    EngineeringKnowledgeCatalogRelationship,
)
from codestrata.services.engineering_knowledge.exceptions import (
    EngineeringKnowledgeCatalogError,
    EngineeringKnowledgeCatalogParseError,
    EngineeringKnowledgeCatalogValidationError,
)
from codestrata.services.engineering_knowledge.loader import EngineeringKnowledgeCatalogLoader

__all__ = [
    "BUILTIN_CATALOG_ID",
    "BUILTIN_CATALOG_VERSION",
    "EngineeringKnowledgeCatalogDocument",
    "EngineeringKnowledgeCatalogError",
    "EngineeringKnowledgeCatalogLoader",
    "EngineeringKnowledgeCatalogNode",
    "EngineeringKnowledgeCatalogParseError",
    "EngineeringKnowledgeCatalogReference",
    "EngineeringKnowledgeCatalogRelationship",
    "EngineeringKnowledgeCatalogValidationError",
    "builtin_engineering_knowledge_catalog_path",
    "load_builtin_engineering_knowledge_catalog",
]
