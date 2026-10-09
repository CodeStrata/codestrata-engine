"""Orchestrate M16/M17/M18 structural quality evidence. No repository execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from codestrata.application.evidence.quality.clones import collect_clone_metric
from codestrata.application.evidence.quality.complexity import collect_functions_and_sizes
from codestrata.application.evidence.quality.envelope import (
    QualityEnvelope,
    QualityOperationalMetadata,
    seal_quality_envelope,
)
from codestrata.application.evidence.quality.maps import (
    DEFAULT_CLONE_RATIO_THRESHOLD,
    DEFAULT_COMPLEXITY_THRESHOLD,
    DEFAULT_FUNCTION_SIZE_THRESHOLD,
    DEFAULT_NESTING_THRESHOLD,
    QualityBudgets,
)
from codestrata.application.evidence.quality.models import QualityEvidence, QualityThresholds


class QualityEvidenceService:
    """Collect size, complexity, nesting and clone indicators from source text."""

    def __init__(self, budgets: QualityBudgets | None = None) -> None:
        self._budgets = budgets or QualityBudgets()

    def collect(
        self,
        *,
        repository_id: str,
        relative_paths: Sequence[str],
        file_texts: Mapping[str, str],
        catalog_digest: str = "",
        operational: QualityOperationalMetadata | None = None,
        complexity_threshold: int = DEFAULT_COMPLEXITY_THRESHOLD,
        function_lines_threshold: int = DEFAULT_FUNCTION_SIZE_THRESHOLD,
        nesting_threshold: int = DEFAULT_NESTING_THRESHOLD,
        clone_ratio_threshold: float = DEFAULT_CLONE_RATIO_THRESHOLD,
    ) -> tuple[QualityEvidence, QualityEnvelope]:
        functions, files, distribution, complexity_notes, _cutoff = collect_functions_and_sizes(
            relative_paths=relative_paths,
            file_texts=file_texts,
            budgets=self._budgets,
        )
        clone, clone_notes = collect_clone_metric(
            relative_paths=relative_paths,
            file_texts=file_texts,
            budgets=self._budgets,
        )
        limitations = tuple(sorted(set(complexity_notes + clone_notes)))
        evidence = QualityEvidence(
            repository_id=repository_id,
            functions=functions,
            files=files,
            distribution=distribution,
            clone=clone,
            thresholds=QualityThresholds(
                complexity=complexity_threshold,
                function_lines=function_lines_threshold,
                nesting=nesting_threshold,
                clone_ratio=f"{clone_ratio_threshold:.6f}",
            ),
            limitations=limitations,
        )
        envelope = seal_quality_envelope(
            evidence=evidence,
            catalog_digest=catalog_digest,
            operational=operational,
        )
        return evidence, envelope


__all__ = ["QualityEvidenceService"]
