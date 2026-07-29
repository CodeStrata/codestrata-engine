"""Domain model representing a source-code repository."""

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from codestrata.models.technology import Technology


class Repository(BaseModel):
    """Represents the application repository being analyzed."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    path: Path
    source_url: str | None = None
    default_branch: str | None = None
    description: str | None = None
    languages: list[str] = Field(default_factory=list)
    technologies: list[Technology] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    total_files: int | None = Field(default=None, ge=0)
    total_lines: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # True when path is a temporary GitHub clone owned by CodeStrata (Phase 6.2).
    # Local user checkouts must remain False so assess never deletes them.
    ephemeral: bool = False
