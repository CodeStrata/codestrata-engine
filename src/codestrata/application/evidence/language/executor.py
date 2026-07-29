"""Execute language evidence providers with failure isolation."""

from __future__ import annotations

import time

from pydantic import BaseModel, ConfigDict, Field, field_validator

from codestrata.application.evidence.language.planner import LanguageEvidencePlan
from codestrata.application.evidence.language.registry import LanguageEvidenceProviderRegistry
from codestrata.domain.evidence.language.capabilities import ProviderExecutionStatus
from codestrata.domain.evidence.language.contracts import LanguageEvidenceContext
from codestrata.domain.evidence.language.models import LanguageEvidenceBundle
from codestrata.domain.graph.validation import as_tuple, require_nonblank


class ProviderExecutionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str
    status: ProviderExecutionStatus
    duration_ms: int = Field(default=0, ge=0)
    message: str | None = None
    evidence_count: int = Field(default=0, ge=0)

    @field_validator("provider_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> str:
        return require_nonblank(str(value), label="provider_id").lower()


class LanguageEvidenceExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    plan: LanguageEvidencePlan
    records: tuple[ProviderExecutionRecord, ...] = ()
    bundles: tuple[LanguageEvidenceBundle, ...] = ()
    failed_provider_ids: tuple[str, ...] = ()

    @field_validator("records", "bundles", "failed_provider_ids", mode="before")
    @classmethod
    def normalize_sequences(cls, value: object) -> tuple[object, ...]:
        return as_tuple(value)


class LanguageEvidenceProviderExecutor:
    def __init__(
        self,
        registry: LanguageEvidenceProviderRegistry,
        *,
        fail_fast: bool = False,
    ) -> None:
        self._registry = registry
        self._fail_fast = fail_fast

    def execute(
        self,
        context: LanguageEvidenceContext,
        plan: LanguageEvidencePlan,
    ) -> LanguageEvidenceExecutionResult:
        records: list[ProviderExecutionRecord] = []
        bundles: list[LanguageEvidenceBundle] = []
        failed: list[str] = []

        for provider_id in plan.execution_order:
            provider = self._registry.get(provider_id)
            started = time.perf_counter()
            try:
                result = provider.collect(context)
            except Exception as error:  # noqa: BLE001 — isolate unexpected provider failures
                duration_ms = int((time.perf_counter() - started) * 1000)
                message = f"provider_execution_error:{type(error).__name__}"
                records.append(
                    ProviderExecutionRecord(
                        provider_id=provider_id,
                        status=ProviderExecutionStatus.FAILED,
                        duration_ms=duration_ms,
                        message=message,
                    )
                )
                failed.append(provider_id)
                if self._fail_fast:
                    break
                continue

            duration_ms = result.duration_ms if result.duration_ms is not None else int(
                (time.perf_counter() - started) * 1000
            )
            evidence_count = 0
            if result.bundle is not None:
                evidence_count = (
                    len(result.bundle.source_units)
                    + len(result.bundle.dependencies)
                    + len(result.bundle.framework_usages)
                )
                if result.status in {
                    ProviderExecutionStatus.SUCCEEDED,
                    ProviderExecutionStatus.PARTIALLY_SUCCEEDED,
                }:
                    bundles.append(result.bundle)
            records.append(
                ProviderExecutionRecord(
                    provider_id=provider_id,
                    status=result.status,
                    duration_ms=duration_ms,
                    message=result.message,
                    evidence_count=evidence_count,
                )
            )
            if result.status is ProviderExecutionStatus.FAILED:
                failed.append(provider_id)
                if self._fail_fast:
                    break

        return LanguageEvidenceExecutionResult(
            plan=plan,
            records=tuple(records),
            bundles=tuple(bundles),
            failed_provider_ids=tuple(failed),
        )
