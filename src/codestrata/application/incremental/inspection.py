"""Transport-neutral inspection of persisted incremental executions."""

from __future__ import annotations

import logging

from codestrata.application.incremental.errors import (
    IncrementalExecutionRecordNotFoundError,
    IncrementalInspectionError,
)
from codestrata.application.incremental.execution_record import IncrementalExecutionRecord
from codestrata.application.incremental.explainability import (
    ExplanationFilters,
    IncrementalExplainabilityService,
    IncrementalExplanation,
)
from codestrata.application.incremental.metrics import IncrementalExecutionMetrics
from codestrata.application.incremental.provenance import IncrementalExecutionRecordStore
from codestrata.application.incremental.validation_models import IncrementalValidationResult

logger = logging.getLogger(__name__)


class IncrementalInspectionService:
    """Query persisted IncrementalExecutionRecord data without reading source/reports."""

    def __init__(
        self,
        store: IncrementalExecutionRecordStore,
        *,
        explainability: IncrementalExplainabilityService | None = None,
        max_list: int = 100,
    ) -> None:
        self._store = store
        self._explainability = explainability or IncrementalExplainabilityService()
        self._max_list = max(1, max_list)

    def get_execution(self, execution_id: str) -> IncrementalExecutionRecord:
        compact = (execution_id or "").strip()
        if not compact:
            raise IncrementalInspectionError(
                "execution_id is required",
                reason_code="missing_execution_id",
            )
        return self._store.get(compact)

    def list_executions(
        self,
        repository_id: str,
        *,
        limit: int = 50,
    ) -> tuple[IncrementalExecutionRecord, ...]:
        rid = (repository_id or "").strip()
        if not rid:
            raise IncrementalInspectionError(
                "repository_id is required",
                reason_code="missing_repository_id",
            )
        bound = min(max(1, limit), self._max_list)
        records = self._store.list_for_repository(rid, limit=bound)
        logger.info(
            "incremental.list_executions",
            extra={"repository_id": rid, "count": len(records)},
        )
        return records

    def explain_execution(
        self,
        execution_id: str,
        *,
        filters: ExplanationFilters | None = None,
    ) -> tuple[IncrementalExplanation, ...]:
        record = self.get_execution(execution_id)
        selected = record.explanations
        if filters is not None:
            selected = self._explainability.filter_explanations(selected, filters)
        return selected

    def get_validation(self, execution_id: str) -> IncrementalValidationResult:
        record = self.get_execution(execution_id)
        if record.validation is None:
            raise IncrementalInspectionError(
                "Validation result is not available for this execution",
                reason_code="validation_missing",
                execution_id=execution_id.strip(),
            )
        return record.validation

    def get_metrics(self, execution_id: str) -> IncrementalExecutionMetrics:
        record = self.get_execution(execution_id)
        if record.metrics is None:
            raise IncrementalInspectionError(
                "Metrics are not available for this execution",
                reason_code="metrics_missing",
                execution_id=execution_id.strip(),
            )
        return record.metrics


# Re-export for callers that only need the not-found type from this module.
__all__ = [
    "IncrementalExecutionRecordNotFoundError",
    "IncrementalInspectionService",
]
