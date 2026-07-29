"""Built-in CodeStrata Engineering Knowledge Catalog access.

The seed catalog is deliberately small: enough to prove catalog contracts and
support upcoming Knowledge Pipeline work without attempting to model the entire
engineering industry. It is not loaded at import time.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from codestrata.domain.engineering_knowledge import EngineeringKnowledgeGraph
from codestrata.services.engineering_knowledge.loader import EngineeringKnowledgeCatalogLoader

BUILTIN_CATALOG_ID = "codestrata-core"
BUILTIN_CATALOG_VERSION = "1.0.0"
_BUILTIN_RESOURCE = "codestrata-core-v1.yaml"


def builtin_engineering_knowledge_catalog_path() -> Path:
    """Return the filesystem path of the packaged CodeStrata core catalog."""

    resource = files("codestrata.resources.engineering_knowledge").joinpath(_BUILTIN_RESOURCE)
    return Path(str(resource))


def load_builtin_engineering_knowledge_catalog() -> EngineeringKnowledgeGraph:
    """Load and validate the packaged CodeStrata core Engineering Knowledge Catalog."""

    return EngineeringKnowledgeCatalogLoader().load_path(
        builtin_engineering_knowledge_catalog_path()
    )
