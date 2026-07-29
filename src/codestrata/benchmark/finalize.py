"""Helpers to finalize a per-run benchmark artifact from assessment outputs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from codestrata.benchmark.artifacts import (
    PERFORMANCE_BENCHMARK_FILENAME,
    write_performance_benchmark,
)
from codestrata.benchmark.builder import (
    build_run_record,
    build_suite_document,
    estimate_artifact_object_sizes,
)
from codestrata.benchmark.recorder import BenchmarkRecorder

logger = logging.getLogger(__name__)


def maybe_write_run_benchmark(
    *,
    enabled: bool,
    recorder: BenchmarkRecorder,
    label: str,
    repository_path: Path,
    run_directory: Path,
    report_json_path: Path | None,
    command_result: Any | None,
    ai_requested: bool,
) -> Path | None:
    """Write ``performance-benchmark.json`` into the run directory when enabled."""

    if not enabled:
        return None
    try:
        sizes = estimate_artifact_object_sizes(run_directory)
        for key, value in sizes.items():
            recorder.set_meta(key, value)
        run = build_run_record(
            label=label,
            repository_path=repository_path,
            run_directory=run_directory,
            report_json_path=report_json_path,
            recorder=recorder,
            command_result=command_result,
            ai_requested=ai_requested,
        )
        document = build_suite_document([run])
        path = write_performance_benchmark(document, run_directory)
        assert path.name == PERFORMANCE_BENCHMARK_FILENAME
        return path
    except Exception:  # noqa: BLE001 - benchmark must never fail assessment
        logger.debug("performance benchmark write skipped", exc_info=True)
        return None
