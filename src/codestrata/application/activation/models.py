"""Phase 7.1.1 smart default assessment activation models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssessmentActivationMode(StrEnum):
    """How Community Edition chooses which intelligence packs to run."""

    DEFAULT = "default"
    MINIMAL = "minimal"
    FULL = "full"
    CUSTOM = "custom"


class PackActivationDecision(StrEnum):
    """Outcome for one intelligence pack."""

    ENABLED = "enabled"
    SKIPPED = "skipped"
    FORCED_ON = "forced_on"
    FORCED_OFF = "forced_off"


class PackId(StrEnum):
    """Activatable Community Edition intelligence packs."""

    SECURITY = "security"
    DEPENDENCY = "dependency"
    ARCHITECTURE = "architecture"
    TECHNICAL_DEBT = "technical_debt"
    TESTING = "testing"
    CLOUD = "cloud"
    AI_READINESS = "ai_readiness"
    PERFORMANCE = "performance"
    ROADMAP = "roadmap"


PACK_ORDER: tuple[PackId, ...] = (
    PackId.SECURITY,
    PackId.DEPENDENCY,
    PackId.ARCHITECTURE,
    PackId.TECHNICAL_DEBT,
    PackId.TESTING,
    PackId.CLOUD,
    PackId.AI_READINESS,
    PackId.PERFORMANCE,
    PackId.ROADMAP,
)


class PackActivationRecord(BaseModel):
    """One pack decision with explainable evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pack_id: PackId
    enabled: bool
    decision: PackActivationDecision
    reason: str
    evidence: tuple[str, ...] = ()


class ActivationPlan(BaseModel):
    """Deterministic activation plan for one assessment run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: AssessmentActivationMode
    packs: tuple[PackActivationRecord, ...] = ()

    def record_for(self, pack_id: PackId) -> PackActivationRecord | None:
        for item in self.packs:
            if item.pack_id == pack_id:
                return item
        return None

    def enabled_pack_ids(self) -> tuple[PackId, ...]:
        return tuple(item.pack_id for item in self.packs if item.enabled)

    def to_coverage_payload(self) -> dict[str, Any]:
        """Machine-readable Assessment Coverage for report.json."""

        return {
            "mode": self.mode.value,
            "packs": [
                {
                    "pack_id": item.pack_id.value,
                    "enabled": item.enabled,
                    "decision": item.decision.value,
                    "reason": item.reason,
                    "evidence": list(item.evidence),
                }
                for item in self.packs
            ],
        }


class ExplicitPackOverride(BaseModel):
    """User-forced enablement for a pack (any triad member set in TOML/CLI)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pack_id: PackId
    enabled: bool
    source_paths: tuple[str, ...] = ()


class ExplicitActivationOverrides(BaseModel):
    """Explicit configuration that must win over smart defaults."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: AssessmentActivationMode | None = None
    mode_source: str | None = None
    packs: tuple[ExplicitPackOverride, ...] = Field(default_factory=tuple)
    rules_master_enabled: bool | None = None
    rules_master_source: str | None = None

    def pack_override(self, pack_id: PackId) -> ExplicitPackOverride | None:
        for item in self.packs:
            if item.pack_id == pack_id:
                return item
        return None


__all__ = [
    "PACK_ORDER",
    "ActivationPlan",
    "AssessmentActivationMode",
    "ExplicitActivationOverrides",
    "ExplicitPackOverride",
    "PackActivationDecision",
    "PackActivationRecord",
    "PackId",
]
