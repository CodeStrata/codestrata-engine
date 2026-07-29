"""Performance & scale baseline measurement (Phase 14.1).

Observational only — must not change assessment findings, recommendations,
graph semantics, or ``report.json`` schema.
"""

from __future__ import annotations

from codestrata.benchmark.artifacts import (
    PERFORMANCE_BENCHMARK_FILENAME,
    write_performance_benchmark,
)
from codestrata.benchmark.builder import build_run_record, build_suite_document
from codestrata.benchmark.environment import capture_environment
from codestrata.benchmark.models import (
    BENCHMARK_SCHEMA_VERSION,
    COMPARISON_KEYS,
    PerformanceBenchmarkDocument,
    PerformanceBenchmarkRun,
)
from codestrata.benchmark.recorder import BenchmarkRecorder, get_active_recorder
from codestrata.benchmark.redaction import redact_ai_metrics

__all__ = [
    "BENCHMARK_SCHEMA_VERSION",
    "COMPARISON_KEYS",
    "PERFORMANCE_BENCHMARK_FILENAME",
    "BenchmarkRecorder",
    "PerformanceBenchmarkDocument",
    "PerformanceBenchmarkRun",
    "build_run_record",
    "build_suite_document",
    "capture_environment",
    "get_active_recorder",
    "redact_ai_metrics",
    "write_performance_benchmark",
]
