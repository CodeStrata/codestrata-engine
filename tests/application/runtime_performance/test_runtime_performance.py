"""Phase 5.19 runtime performance regression tests (non-flaky)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codestrata.application.runtime_performance.file_text_cache import (
    load_shared_source_texts,
    select_source_paths,
)
from codestrata.models import AnalysisResult, Repository, RepositoryFacts
from codestrata.reporters.report_paths import create_report_paths
from codestrata.reporting.modernization_models import (
    AssessmentMode,
    AssessmentTiming,
    ModernizationReportInput,
)
from codestrata.reporting.modernization_serialization import (
    write_modernization_assessment_reports,
)


def test_select_source_paths_is_deterministic_and_bounded() -> None:
    paths = (
        "z/B.java",
        "a/A.java",
        "a/A.java",
        "readme.md",
        "src/App.cs",
    )
    selected, skipped = select_source_paths(paths, max_files=2)
    assert selected == ("a/A.java", "src/App.cs")
    assert skipped == 1


def test_shared_source_text_cache_hits(tmp_path: Path) -> None:
    (tmp_path / "A.java").write_text("class A {}", encoding="utf-8")
    (tmp_path / "B.java").write_text("class B {}", encoding="utf-8")
    first, stats1 = load_shared_source_texts(
        relative_paths=["A.java", "B.java"],
        repository_root=tmp_path,
        max_read_workers=1,
    )
    assert stats1.cache_misses == 2
    assert stats1.cache_hits == 0
    second, stats2 = load_shared_source_texts(
        relative_paths=["A.java", "B.java"],
        repository_root=tmp_path,
        prior_texts=first,
        max_read_workers=2,
    )
    assert second == first
    assert stats2.cache_hits == 2
    assert stats2.cache_misses == 0


def test_parallel_read_matches_serial(tmp_path: Path) -> None:
    for index in range(8):
        (tmp_path / f"F{index}.java").write_text(f"class F{index} {{}}", encoding="utf-8")
    paths = [f"F{index}.java" for index in range(8)]
    serial, _ = load_shared_source_texts(
        relative_paths=paths,
        repository_root=tmp_path,
        max_read_workers=1,
    )
    parallel, _ = load_shared_source_texts(
        relative_paths=paths,
        repository_root=tmp_path,
        max_read_workers=4,
    )
    assert parallel == serial
    assert list(parallel.keys()) == sorted(paths)


def test_shared_cache_avoids_second_disk_read(tmp_path: Path) -> None:
    """Regression: prior_texts must eliminate repeated reader.read calls."""

    from codestrata.services.inventory import LocalFilesystemContentReader

    for index in range(4):
        (tmp_path / f"S{index}.java").write_text(f"class S{index} {{}}", encoding="utf-8")
    paths = [f"S{index}.java" for index in range(4)]
    reader = LocalFilesystemContentReader(tmp_path)
    reads: list[str] = []
    original_read = reader.read

    def counting_read(path: str):  # type: ignore[no-untyped-def]
        reads.append(path)
        return original_read(path)

    reader.read = counting_read  # type: ignore[method-assign]
    first, _ = load_shared_source_texts(
        relative_paths=paths,
        content_reader=reader,
        max_read_workers=1,
    )
    assert len(reads) == 4
    _, stats = load_shared_source_texts(
        relative_paths=paths,
        content_reader=reader,
        prior_texts=first,
        max_read_workers=2,
    )
    assert len(reads) == 4
    assert stats.cache_hits == 4
    assert stats.cache_misses == 0


def test_assessment_timing_accepts_phase_5_19_fields() -> None:
    timing = AssessmentTiming(
        total_ms=100.0,
        scan_ms=10.0,
        analysis_ms=20.0,
        graph_ms=15.0,
        rules_ms=30.0,
        report_ms=5.0,
        files_loaded=12,
        files_skipped=1,
        cache_hits=0,
        cache_misses=12,
        peak_rss_mb=64.0,
    )
    assert timing.graph_ms == 15.0
    assert timing.files_loaded == 12


def test_report_write_single_html_render(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: with timing present, HTML must not be rendered twice."""

    from codestrata.reporting import modernization_serialization as ser

    render_calls = {"html": 0}

    class _FakeRenderer:
        def render(self, report_input: object) -> str:
            render_calls["html"] += 1
            return "<html>ok</html>"

    monkeypatch.setattr(ser, "ModernizationHTMLReportRenderer", _FakeRenderer)

    repository = Repository(name="demo", path=tmp_path, files=[])
    analysis = AnalysisResult(
        repository=repository,
        technologies=[],
        findings=[],
        facts=RepositoryFacts(),
        recommendations=[],
    )
    report_input = ModernizationReportInput(
        analysis_result=analysis,
        assessment_mode=AssessmentMode.DETERMINISTIC,
        generated_at_utc=datetime.now(UTC),
        timing=AssessmentTiming(total_ms=10.0, scan_ms=1.0),
    )
    paths = create_report_paths(
        analysis,
        tmp_path / "out",
        timestamp="20260726-120000",
        create_directory=False,
    )
    write_modernization_assessment_reports(report_input, paths)
    assert render_calls["html"] == 1
    assert paths.json_report_path.is_file()
    payload = json.loads(paths.json_report_path.read_text(encoding="utf-8"))
    assert str(payload["schema"]).startswith("codestrata-assessment-manifest")
    assert paths.html_report_path.is_file()
