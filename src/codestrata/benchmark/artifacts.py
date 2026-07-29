"""Persist performance-benchmark.json without touching report.json schema."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.benchmark.models import PerformanceBenchmarkDocument

PERFORMANCE_BENCHMARK_FILENAME = "performance-benchmark.json"


def write_performance_benchmark(
    document: PerformanceBenchmarkDocument,
    destination: Path,
) -> Path:
    """Write the benchmark document to ``destination`` (file or directory)."""

    if destination.suffix.lower() == ".json":
        path = destination
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        destination.mkdir(parents=True, exist_ok=True)
        path = destination / PERFORMANCE_BENCHMARK_FILENAME
    payload = document.model_dump(mode="json")
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
