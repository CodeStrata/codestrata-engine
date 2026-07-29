"""Provenance persistence ports and in-memory store for execution records."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

from codestrata.application.incremental.errors import IncrementalExecutionRecordNotFoundError
from codestrata.application.incremental.execution_record import IncrementalExecutionRecord

logger = logging.getLogger(__name__)


class IncrementalExecutionRecordStore(Protocol):
    """Application port for additive incremental provenance persistence."""

    def save(self, record: IncrementalExecutionRecord) -> None:
        """Persist an execution record. Must not rewrite prior assessment artifacts."""

    def get(self, execution_id: str) -> IncrementalExecutionRecord:
        """Load one execution record by ID."""

    def list_for_repository(
        self,
        repository_id: str,
        *,
        limit: int = 50,
    ) -> tuple[IncrementalExecutionRecord, ...]:
        """List records for a repository (newest first, bounded)."""


class InMemoryIncrementalExecutionRecordStore:
    """Test/dev store that keeps records in process memory."""

    def __init__(self) -> None:
        self._by_id: dict[str, IncrementalExecutionRecord] = {}

    def save(self, record: IncrementalExecutionRecord) -> None:
        self._by_id[record.execution_id] = record
        logger.info(
            "incremental.execution_record_saved",
            extra={
                "execution_id": record.execution_id,
                "plan_id": record.plan_id,
                "repository_id": record.repository_id,
                "run_id": record.run_id,
                "actual_mode": record.actual_mode.value,
                "fallback_used": record.fallback_used,
                "trusted": record.trusted,
            },
        )

    def get(self, execution_id: str) -> IncrementalExecutionRecord:
        compact = execution_id.strip()
        record = self._by_id.get(compact)
        if record is None:
            raise IncrementalExecutionRecordNotFoundError(
                "Incremental execution record not found",
                reason_code="execution_record_not_found",
                execution_id=compact,
            )
        return record

    def list_for_repository(
        self,
        repository_id: str,
        *,
        limit: int = 50,
    ) -> tuple[IncrementalExecutionRecord, ...]:
        rid = repository_id.strip()
        matched = [record for record in self._by_id.values() if (record.repository_id or "") == rid]
        matched.sort(key=lambda item: item.started_at, reverse=True)
        return tuple(matched[: max(1, limit)])


class FileIncrementalExecutionRecordStore:
    """JSON file store under a knowledge directory (no SQLite dependency)."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, execution_id: str) -> Path:
        safe = execution_id.strip().replace("/", "_").replace("..", "_")
        return self._root / f"{safe}.json"

    def save(self, record: IncrementalExecutionRecord) -> None:
        path = self._path_for(record.execution_id)
        payload = record.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        logger.info(
            "incremental.execution_record_saved",
            extra={
                "execution_id": record.execution_id,
                "plan_id": record.plan_id,
                "repository_id": record.repository_id,
                "run_id": record.run_id,
                "actual_mode": record.actual_mode.value,
                "fallback_used": record.fallback_used,
                "trusted": record.trusted,
            },
        )

    def get(self, execution_id: str) -> IncrementalExecutionRecord:
        path = self._path_for(execution_id)
        if not path.is_file():
            raise IncrementalExecutionRecordNotFoundError(
                "Incremental execution record not found",
                reason_code="execution_record_not_found",
                execution_id=execution_id.strip(),
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        return IncrementalExecutionRecord.model_validate(payload)

    def list_for_repository(
        self,
        repository_id: str,
        *,
        limit: int = 50,
    ) -> tuple[IncrementalExecutionRecord, ...]:
        rid = repository_id.strip()
        records: list[IncrementalExecutionRecord] = []
        for path in sorted(self._root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                record = IncrementalExecutionRecord.model_validate(payload)
            except (OSError, ValueError, TypeError):
                continue
            if (record.repository_id or "") == rid:
                records.append(record)
        records.sort(key=lambda item: item.started_at, reverse=True)
        return tuple(records[: max(1, limit)])
