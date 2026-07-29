"""Application logging configuration."""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format application log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in (
            "repository_name",
            "repository_path",
            "analysis_id",
            "stage",
            "duration_ms",
            "file_count",
            "technology_count",
            "finding_count",
        ):
            value = getattr(record, field, None)

            if value is not None:
                log_entry[field] = value

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def configure_logging(
    *,
    level: str | None = None,
    json_logs: bool | None = None,
) -> None:
    """Configure root application logging."""

    resolved_level = (level or os.getenv("CODESTRATA_LOG_LEVEL") or "WARNING").upper()

    resolved_json_logs = (
        json_logs
        if json_logs is not None
        else os.getenv("CODESTRATA_LOG_FORMAT", "text").lower() == "json"
    )

    handler = logging.StreamHandler()

    if resolved_json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    logging.basicConfig(
        level=resolved_level,
        handlers=[handler],
        force=True,
    )
