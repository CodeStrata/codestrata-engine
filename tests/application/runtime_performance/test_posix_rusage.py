"""Windows hosts must import runtime-performance helpers without POSIX resource."""

from __future__ import annotations

import sys

from codestrata.application.runtime_performance.metrics import peak_rss_mb
from codestrata.application.runtime_performance.posix_rusage import posix_resource_module
from codestrata.benchmark.recorder import BenchmarkRecorder


def test_metrics_and_benchmark_import_without_module_level_resource() -> None:
    assert posix_resource_module() is None if sys.platform == "win32" else True
    if sys.platform == "win32":
        assert peak_rss_mb() is None
        assert BenchmarkRecorder(enabled=True).cpu_time_ms() is None
