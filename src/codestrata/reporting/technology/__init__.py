"""Technology Inventory reporting (Epic 3 Slice 3.2)."""

from codestrata.reporting.technology.adapter import (
    build_technology_inventory,
    category_group_id,
)
from codestrata.reporting.technology.models import (
    TECHNOLOGY_INVENTORY_SECTION_ID,
    TECHNOLOGY_INVENTORY_SECTION_VERSION,
    RepositoryCompositionView,
    TechnologyInventoryFact,
    TechnologyInventoryGroup,
    TechnologyInventorySection,
)

__all__ = [
    "TECHNOLOGY_INVENTORY_SECTION_ID",
    "TECHNOLOGY_INVENTORY_SECTION_VERSION",
    "RepositoryCompositionView",
    "TechnologyInventoryFact",
    "TechnologyInventoryGroup",
    "TechnologyInventorySection",
    "build_technology_inventory",
    "category_group_id",
]
