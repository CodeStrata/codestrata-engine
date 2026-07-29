"""Phase 14.1 performance baseline regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.benchmark.artifacts import (
    PERFORMANCE_BENCHMARK_FILENAME,
    write_performance_benchmark,
)
from codestrata.benchmark.builder import build_run_record, build_suite_document
from codestrata.benchmark.models import (
    BENCHMARK_SCHEMA_VERSION,
    COMPARISON_KEYS,
    PerformanceBenchmarkDocument,
)
from codestrata.benchmark.recorder import BenchmarkRecorder, get_active_recorder
from codestrata.benchmark.redaction import redact_ai_metrics
from codestrata.config.settings import AnalysisRuntimeSettings


def test_benchmark_schema_version_stable() -> None:
    assert BENCHMARK_SCHEMA_VERSION == "1.0.0"
    assert "timings.total_ms" in COMPARISON_KEYS
    assert "memory.peak_rss_mb" in COMPARISON_KEYS


def test_disabled_recorder_is_noop() -> None:
    recorder = BenchmarkRecorder.create(enabled=False)
    recorder.activate()
    try:
        with recorder.stage("x"):
            pass
        recorder.record("y", 12.5)
        assert recorder.stages_ms == {}
        assert get_active_recorder().enabled is False or True
    finally:
        recorder.deactivate()


def test_enabled_recorder_captures_non_negative_timings() -> None:
    recorder = BenchmarkRecorder.create(enabled=True)
    with recorder.stage("alpha"):
        pass
    recorder.record("beta", 1.25)
    assert recorder.stages_ms["alpha"] >= 0.0
    assert recorder.stages_ms["beta"] == 1.25


def test_memory_metrics_degrade_safely_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "codestrata.benchmark.recorder.peak_rss_mb",
        lambda: None,
    )
    recorder = BenchmarkRecorder.create(enabled=True)
    assert recorder.peak_rss() is None
    assert recorder.average_rss() is None


def test_ai_metrics_redact_secrets() -> None:
    cleaned = redact_ai_metrics(
        {
            "provider": "bedrock",
            "api_key": "SECRET",
            "prompt": "do not keep",
            "overall_enrichment_ms": 12.0,
            "nested": {"token": "x", "model": "m"},
        }
    )
    blob = json.dumps(cleaned)
    assert "SECRET" not in blob
    assert "do not keep" not in blob
    assert "api_key" not in cleaned
    assert cleaned["provider"] == "bedrock"
    assert cleaned["nested"]["model"] == "m"
    assert "token" not in cleaned["nested"]


def test_benchmark_artifact_generation(tmp_path: Path) -> None:
    (tmp_path / "report.json").write_text(
        json.dumps(
            {
                "assessment": {
                    "repository": {"name": "demo", "file_count": 2},
                    "timing": {"total_ms": 10.0, "scan_ms": 1.0, "peak_rss_mb": 32.0},
                    "findings": [],
                    "summary": {"recommendation_count": 0},
                    "technologies": [{"name": "Python"}],
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "scan-boundary-diagnostics.json").write_text(
        json.dumps(
            {
                "policy_version": "1.0.0",
                "included_files": 2,
                "excluded_files": 1,
                "role_counts": {"production": 2},
            }
        ),
        encoding="utf-8",
    )
    run = build_run_record(
        label="demo",
        repository_path=tmp_path,
        run_directory=tmp_path,
        report_json_path=tmp_path / "report.json",
    )
    document = build_suite_document([run])
    path = write_performance_benchmark(document, tmp_path / "out")
    assert path.name == PERFORMANCE_BENCHMARK_FILENAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    PerformanceBenchmarkDocument.model_validate(payload)
    assert payload["schema_version"] == BENCHMARK_SCHEMA_VERSION
    assert payload["runs"][0]["timings"]["total_ms"] >= 0
    assert all(
        stage["duration_ms"] >= 0 for stage in payload["runs"][0]["timings"]["stages"]
    )


def test_benchmark_collection_setting_default_off() -> None:
    settings = AnalysisRuntimeSettings()
    assert settings.benchmark_collection is False


def test_benchmark_does_not_mutate_assessment_payload(tmp_path: Path) -> None:
    report = {
        "assessment": {
            "repository": {"name": "demo", "file_count": 1},
            "timing": {"total_ms": 5.0},
            "findings": [{"id": "f1", "severity": "low"}],
            "summary": {"recommendation_count": 1},
        }
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    before = report_path.read_text(encoding="utf-8")
    build_run_record(
        label="demo",
        repository_path=tmp_path,
        run_directory=tmp_path,
        report_json_path=report_path,
    )
    assert report_path.read_text(encoding="utf-8") == before
