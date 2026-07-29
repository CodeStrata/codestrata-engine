"""Domain model representing a modernization recommendation."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from codestrata.models.enums import Effort, Priority, RecommendationCategory, Risk
from codestrata.models.evidence import Evidence


class Recommendation(BaseModel):
    """Represents an action recommended in response to facts and findings."""

    id: UUID = Field(default_factory=uuid4)
    rule_id: str
    title: str
    description: str
    rationale: str
    priority: Priority
    category: RecommendationCategory
    effort: Effort = Effort.UNKNOWN
    risk: Risk
    evidence: list[Evidence] = Field(default_factory=list)
    related_finding_ids: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
