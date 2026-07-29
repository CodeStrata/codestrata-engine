"""Deterministic language evidence provider planner."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, field_validator

from codestrata.application.evidence.language.raw_facts import (
    PROVIDER_PRECEDENCE,
    detect_languages_from_paths,
)
from codestrata.application.evidence.language.registry import LanguageEvidenceProviderRegistry
from codestrata.domain.evidence.language.contracts import LanguageEvidenceContext
from codestrata.domain.graph.validation import as_tuple, require_nonblank


class PlannedProvider(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str
    status: str
    reason: str = ""
    languages: tuple[str, ...] = ()

    @field_validator("provider_id", "status", mode="before")
    @classmethod
    def normalize_required(cls, value: object) -> str:
        return require_nonblank(str(value), label="planned provider field").lower()


class LanguageEvidencePlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detected_languages: tuple[str, ...] = ()
    candidate_provider_ids: tuple[str, ...] = ()
    applicable_provider_ids: tuple[str, ...] = ()
    skipped: tuple[PlannedProvider, ...] = ()
    execution_order: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @field_validator(
        "detected_languages",
        "candidate_provider_ids",
        "applicable_provider_ids",
        "skipped",
        "execution_order",
        "conflicts",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class LanguageEvidenceProviderPlanner:
    def __init__(
        self,
        registry: LanguageEvidenceProviderRegistry,
        *,
        enabled_provider_ids: frozenset[str] | None = None,
        auto_detect: bool = True,
        precedence: Sequence[str] | None = None,
    ) -> None:
        self._registry = registry
        self._enabled = enabled_provider_ids
        self._auto_detect = auto_detect
        self._precedence = tuple(precedence or PROVIDER_PRECEDENCE)

    def plan(self, context: LanguageEvidenceContext) -> LanguageEvidencePlan:
        detected = context.detected_languages or detect_languages_from_paths(
            context.relative_paths
        )
        skipped: list[PlannedProvider] = []
        candidates: list[str] = []
        applicable: list[str] = []
        conflicts: list[str] = []

        for meta in self._registry.list_providers():
            provider_id = str(meta.provider_id)
            if self._enabled is not None and provider_id not in self._enabled:
                skipped.append(
                    PlannedProvider(
                        provider_id=provider_id,
                        status="skipped",
                        reason="disabled_by_configuration",
                        languages=meta.supported_languages,
                    )
                )
                continue
            if self._auto_detect and detected:
                if not set(meta.supported_languages).intersection(detected):
                    skipped.append(
                        PlannedProvider(
                            provider_id=provider_id,
                            status="not_applicable",
                            reason="no_matching_detected_language",
                            languages=meta.supported_languages,
                        )
                    )
                    continue
            candidates.append(provider_id)
            provider = self._registry.get(provider_id)
            applicability = provider.evaluate_applicability(context)
            if not applicability.is_applicable:
                skipped.append(
                    PlannedProvider(
                        provider_id=provider_id,
                        status=str(applicability.status),
                        reason=applicability.message or str(applicability.status),
                        languages=meta.supported_languages,
                    )
                )
                continue
            applicable.append(provider_id)

        capability_owners: dict[str, list[str]] = {}
        for provider_id in applicable:
            meta = self._registry.get(provider_id).metadata
            for cap in sorted(meta.capabilities.supported_ids()):
                capability_owners.setdefault(cap, []).append(provider_id)
        for capability, owners in sorted(capability_owners.items()):
            if len(owners) > 1:
                conflicts.append(
                    f"capability:{capability}:providers={','.join(sorted(owners))}"
                )

        order = _order_providers(applicable, precedence=self._precedence)
        notes = [
            "selection=auto_detect" if self._auto_detect else "selection=explicit",
            f"precedence={','.join(self._precedence)}",
        ]
        if conflicts:
            notes.append("conflicts_reported_not_silently_resolved")
        return LanguageEvidencePlan(
            detected_languages=tuple(sorted(detected)),
            candidate_provider_ids=tuple(sorted(candidates)),
            applicable_provider_ids=tuple(order),
            skipped=tuple(
                sorted(skipped, key=lambda item: (item.provider_id, item.status))
            ),
            execution_order=tuple(order),
            conflicts=tuple(sorted(conflicts)),
            notes=tuple(notes),
        )


def _order_providers(provider_ids: Sequence[str], *, precedence: Sequence[str]) -> list[str]:
    rank = {provider_id: index for index, provider_id in enumerate(precedence)}
    return sorted(
        provider_ids,
        key=lambda item: (rank.get(item, len(rank)), item),
    )
