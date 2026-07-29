"""Domain model representing a repository analysis finding."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from codestrata.models.enums import FindingCategory, FindingSource, Severity
from codestrata.models.evidence import Evidence


class Finding(BaseModel):
    """Represents an issue, risk, fact, or modernization opportunity."""

    id: UUID = Field(default_factory=uuid4)
    rule_id: str | None = None
    title: str
    description: str
    category: FindingCategory
    severity: Severity
    source: FindingSource
    evidence: list[Evidence] = Field(default_factory=list)
    affected_technologies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
