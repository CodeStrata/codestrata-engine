"""Orchestrate M19/M20/M21 testing evidence. No repository execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from codestrata.application.evidence.testing.association import collect_association_metric
from codestrata.application.evidence.testing.ci_gap import collect_ci_gap_metric
from codestrata.application.evidence.testing.declarations import collect_test_declarations
from codestrata.application.evidence.testing.envelope import (
    TestingEnvelope,
    TestingOperationalMetadata,
    seal_testing_envelope,
)
from codestrata.application.evidence.testing.models import TestingEvidence, TestingThresholds
from codestrata.application.evidence.testing.paths import is_test_like, normalize_relative_path
from codestrata.application.evidence.testing.skipped import collect_skip_metric


class TestingBudgets(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    __test__ = False

    max_file_bytes: int = Field(default=1_048_576, ge=1)
    max_files: int = Field(default=2000, ge=1)


class TestingEvidenceService:
    """Collect static test association, skips and CI gaps from source text."""

    __test__ = False

    def __init__(self, budgets: TestingBudgets | None = None) -> None:
        self._budgets = budgets or TestingBudgets()

    def collect(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str],
        catalog_digest: str = "",
        operational: TestingOperationalMetadata | None = None,
        disabled_low_min: int = 1,
        disabled_medium_min: int = 10,
    ) -> tuple[TestingEvidence, TestingEnvelope]:
        notes: list[str] = []
        limited = relative_paths[: self._budgets.max_files]
        paths = tuple(normalize_relative_path(path) for path in limited)
        texts = {normalize_relative_path(path): text for path, text in file_texts.items()}
        test_paths = [path for path in paths if is_test_like(path)]
        tests = collect_test_declarations(
            relative_paths=test_paths,
            file_texts=texts,
            notes=notes,
            max_file_bytes=self._budgets.max_file_bytes,
        )
        association = collect_association_metric(
            relative_paths=paths,
            file_texts=texts,
            tests=tests,
            notes=notes,
        )
        skipped = collect_skip_metric(
            relative_paths=paths,
            file_texts=texts,
            tests=tests,
            notes=notes,
            max_file_bytes=self._budgets.max_file_bytes,
        )
        ci_gap = collect_ci_gap_metric(
            relative_paths=paths,
            file_texts=texts,
            notes=notes,
        )
        evidence = TestingEvidence(
            repository_id=repository_id,
            tests=tests,
            association=association,
            skipped=skipped,
            ci_gap=ci_gap,
            thresholds=TestingThresholds(
                disabled_low_min=disabled_low_min,
                disabled_medium_min=disabled_medium_min,
            ),
            limitations=tuple(sorted(set(notes))),
        )
        envelope = seal_testing_envelope(
            evidence=evidence,
            catalog_digest=catalog_digest,
            operational=operational,
        )
        return evidence, envelope


__all__ = ["TestingBudgets", "TestingEvidenceService"]
