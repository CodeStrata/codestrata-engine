"""Domain model representing a technology detected in a repository."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from codestrata.models.enums import TechnologyCategory


class Technology(BaseModel):
    """Represents a language, framework, tool, or platform."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    version: str | None = None
    category: TechnologyCategory
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
