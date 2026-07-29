"""Stable schema for performance-benchmark.json (Phase 14.1).

Future releases compare runs using COMPARISON_KEYS without changing
field names or types in this document.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

BENCHMARK_SCHEMA_VERSION = "1.0.0"
BENCHMARK_ID = "codestrata.performance_and_scale_baseline"

# Stable paths for release-over-release comparison tooling.
COMPARISON_KEYS: tuple[str, ...] = (
    "timings.total_ms",
    "timings.cpu_time_ms",
    "memory.peak_rss_mb",
    "memory.average_rss_mb",
    "repository.files_assessed",
    "repository.production_files",
    "repository.test_files",
    "graphs.repository.nodes",
    "graphs.repository.edges",
    "graphs.engineering_knowledge.nodes",
    "graphs.engineering_knowledge.edges",
    "graphs.assessment.nodes",
    "graphs.assessment.edges",
    "report.findings_count",
    "report.recommendations_count",
    "report.html_bytes",
    "report.json_bytes",
    "artifacts.total_output_bytes",
    "ai.overall_enrichment_ms",
)


class PerformanceBenchmarkDocument(BaseModel):
    """Top-level machine-readable benchmark suite document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = BENCHMARK_SCHEMA_VERSION
    benchmark_id: str = BENCHMARK_ID
    generated_at: str
    environment: dict[str, Any] = Field(default_factory=dict)
    comparison_keys: list[str] = Field(
        default_factory=lambda: list(COMPARISON_KEYS)
    )
    measurement_limitations: list[str] = Field(default_factory=list)
    runs: list[PerformanceBenchmarkRun] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class PerformanceBenchmarkRun(BaseModel):
    """One repository assessment measurement."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    label: str
    status: str = "completed"
    repository: dict[str, Any] = Field(default_factory=dict)
    timings: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    graphs: dict[str, Any] = Field(default_factory=dict)
    report: dict[str, Any] = Field(default_factory=dict)
    ai: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    failure: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)
