"""Tests for PMD provider execution semantics with mocked processes."""

from __future__ import annotations

import subprocess
from pathlib import Path

from codestrata.models import Repository, Technology
from codestrata.models.enums import TechnologyCategory
from codestrata.static_analysis.models import StaticAnalysisContext, StaticAnalysisStatus
from codestrata.static_analysis.providers.pmd_provider import PmdProvider


class _FakeRunner:
    def __init__(self, responses: list[subprocess.CompletedProcess[str]]) -> None:
        self.responses = list(responses)
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        self.calls.append(list(args))
        if not self.responses:
            raise AssertionError("unexpected process call")
        return self.responses.pop(0)


def _write_java(tmp_path: Path, relative: str, body: str = "class Foo {}") -> Path:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _context(
    tmp_path: Path,
    *,
    files: list[str] | None = None,
    technologies: list[Technology] | None = None,
) -> StaticAnalysisContext:
    java_files = files or ["src/main/java/example/Foo.java"]
    for relative in java_files:
        if relative.endswith(".java"):
            _write_java(tmp_path, relative)
    repository = Repository(
        name="sample",
        path=tmp_path,
        files=list(java_files),
    )
    return StaticAnalysisContext(
        repository=repository,
        repository_path=str(tmp_path),
        detected_technologies=technologies
        or [
            Technology(name="Java", category=TechnologyCategory.LANGUAGE, confidence=1.0),
        ],
    )


def _version_ok(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, 0, stdout="PMD 7.26.0", stderr="")


def test_pmd_unavailable() -> None:
    runner = _FakeRunner(
        [
            subprocess.CompletedProcess(
                args=["pmd", "--version"],
                returncode=127,
                stdout="",
                stderr="not found",
            )
        ]
    )
    provider = PmdProvider(process_runner=runner)
    assert provider.is_available() is False


def test_nonzero_exit_with_valid_violations_is_completed(tmp_path: Path) -> None:
    source = tmp_path / "src/main/java/example/Foo.java"
    xml = f"""<?xml version="1.0"?>
    <pmd xmlns="http://pmd.sourceforge.net/report/2.0.0">
      <file name="{source}">
        <violation beginline="1" rule="UnusedPrivateField"
          ruleset="Best Practices" priority="5">unused</violation>
      </file>
    </pmd>
    """

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        report_file = Path(args[args.index("--report-file") + 1])
        report_file.write_text(xml, encoding="utf-8")
        return subprocess.CompletedProcess(args, 4, stdout="", stderr="")

    provider = PmdProvider(process_runner=runner)
    result = provider.analyze(_context(tmp_path))
    assert result.status == StaticAnalysisStatus.COMPLETED
    assert result.eligible_file_count == 1
    assert result.files_analyzed == 1
    assert len(result.findings) == 1
    assert result.findings[0].evidence[0].file_path.startswith("src/")
    assert str(tmp_path) not in result.findings[0].evidence[0].file_path


def test_successful_run_with_no_violations_counts_eligible_files(tmp_path: Path) -> None:
    xml = """<?xml version="1.0"?><pmd xmlns="http://pmd.sourceforge.net/report/2.0.0"></pmd>"""

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        report_file = Path(args[args.index("--report-file") + 1])
        report_file.write_text(xml, encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    provider = PmdProvider(process_runner=runner)
    result = provider.analyze(_context(tmp_path))
    assert result.status == StaticAnalysisStatus.COMPLETED
    assert result.files_analyzed > 0
    assert result.eligible_file_count == result.files_analyzed
    assert result.findings == []
    assert "category/java/bestpractices.xml" in result.command_metadata["rulesets"]


def test_main_and_test_java_sources_are_included(tmp_path: Path) -> None:
    files = [
        "src/main/java/example/Foo.java",
        "src/test/java/example/FooTest.java",
    ]
    seen_dirs: list[str] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        indexes = [index for index, value in enumerate(args) if value == "--dir"]
        for index in indexes:
            seen_dirs.append(args[index + 1])
        report_file = Path(args[args.index("--report-file") + 1])
        report_file.write_text(
            '<?xml version="1.0"?><pmd xmlns="http://pmd.sourceforge.net/report/2.0.0"></pmd>',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    provider = PmdProvider(process_runner=runner)
    result = provider.analyze(_context(tmp_path, files=files))
    assert result.status == StaticAnalysisStatus.COMPLETED
    assert result.eligible_file_count == 2
    assert result.files_analyzed == 2
    assert any(path.endswith("src/main/java") for path in seen_dirs)
    assert any(path.endswith("src/test/java") for path in seen_dirs)
    assert result.command_metadata["source_roots"] == [
        "src/main/java",
        "src/test/java",
    ]


def test_gradle_java_layout_is_detected(tmp_path: Path) -> None:
    files = [
        "src/main/java/com/example/App.java",
        "src/test/java/com/example/AppTest.java",
    ]

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        report_file = Path(args[args.index("--report-file") + 1])
        report_file.write_text(
            '<?xml version="1.0"?><pmd xmlns="http://pmd.sourceforge.net/report/2.0.0"></pmd>',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    provider = PmdProvider(process_runner=runner)
    result = provider.analyze(_context(tmp_path, files=files))
    assert result.status == StaticAnalysisStatus.COMPLETED
    assert result.eligible_file_count == 2


def test_nonstandard_java_sources_are_supported(tmp_path: Path) -> None:
    files = ["java/src/App.java"]

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        report_file = Path(args[args.index("--report-file") + 1])
        report_file.write_text(
            '<?xml version="1.0"?><pmd xmlns="http://pmd.sourceforge.net/report/2.0.0"></pmd>',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    provider = PmdProvider(process_runner=runner)
    result = provider.analyze(_context(tmp_path, files=files))
    assert result.status == StaticAnalysisStatus.COMPLETED
    assert result.eligible_file_count == 1
    assert result.command_metadata["source_roots"] == ["java/src"]


def test_no_java_files_results_in_skipped(tmp_path: Path) -> None:
    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        raise AssertionError("analyze should not run when no Java files exist")

    provider = PmdProvider(process_runner=runner)
    context = StaticAnalysisContext(
        repository=Repository(name="empty", path=tmp_path, files=["README.md"]),
        repository_path=str(tmp_path),
        detected_technologies=[
            Technology(name="Java", category=TechnologyCategory.LANGUAGE, confidence=1.0)
        ],
    )
    result = provider.analyze(context)
    assert result.status == StaticAnalysisStatus.SKIPPED
    assert result.files_analyzed == 0
    assert "No Java source files" in (result.warnings[0] if result.warnings else "")


def test_invalid_invocation_results_in_failed(tmp_path: Path) -> None:
    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        return subprocess.CompletedProcess(args, 2, stdout="", stderr="Unknown option")

    provider = PmdProvider(process_runner=runner)
    result = provider.analyze(_context(tmp_path))
    assert result.status == StaticAnalysisStatus.FAILED
    assert result.files_analyzed == 0


def test_timeout_results_in_failed(tmp_path: Path) -> None:
    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        raise subprocess.TimeoutExpired(cmd=args, timeout=1)

    provider = PmdProvider(process_runner=runner)
    result = provider.analyze(_context(tmp_path))
    assert result.status == StaticAnalysisStatus.FAILED
    assert "timed out" in (result.error_message or "").lower()


def test_malformed_output_results_in_failed(tmp_path: Path) -> None:
    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        report_file = Path(args[args.index("--report-file") + 1])
        report_file.write_text("<pmd><file>", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    provider = PmdProvider(process_runner=runner)
    result = provider.analyze(_context(tmp_path))
    assert result.status == StaticAnalysisStatus.FAILED
    assert "Malformed" in (result.error_message or "")


def test_eligible_java_never_reports_completed_with_zero_files(tmp_path: Path) -> None:
    xml = """<?xml version="1.0"?><pmd xmlns="http://pmd.sourceforge.net/report/2.0.0"></pmd>"""

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        report_file = Path(args[args.index("--report-file") + 1])
        report_file.write_text(xml, encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    provider = PmdProvider(process_runner=runner)
    result = provider.analyze(_context(tmp_path))
    assert result.status == StaticAnalysisStatus.COMPLETED
    assert result.eligible_file_count > 0
    assert result.files_analyzed > 0


def test_source_roots_resolve_against_repository_root(tmp_path: Path) -> None:
    foreign = tmp_path / "elsewhere" / "src/main/java"
    foreign.mkdir(parents=True)
    (foreign / "Ignored.java").write_text("class Ignored {}", encoding="utf-8")
    repo = tmp_path / "repo"
    _write_java(repo, "src/main/java/example/Foo.java")

    captured: list[str] = []

    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        if "--version" in args:
            return _version_ok(args)
        for index, value in enumerate(args):
            if value == "--dir":
                captured.append(args[index + 1])
        report_file = Path(args[args.index("--report-file") + 1])
        report_file.write_text(
            '<?xml version="1.0"?><pmd xmlns="http://pmd.sourceforge.net/report/2.0.0"></pmd>',
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    provider = PmdProvider(process_runner=runner)
    context = StaticAnalysisContext(
        repository=Repository(
            name="repo",
            path=repo,
            files=["src/main/java/example/Foo.java"],
        ),
        repository_path=str(repo),
        detected_technologies=[
            Technology(name="Java", category=TechnologyCategory.LANGUAGE, confidence=1.0)
        ],
    )
    result = provider.analyze(context)
    assert result.status == StaticAnalysisStatus.COMPLETED
    assert all(str(repo.resolve()) in path for path in captured)
    assert all("elsewhere" not in path for path in captured)


def test_applicability_requires_java(tmp_path: Path) -> None:
    provider = PmdProvider(
        process_runner=lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["pmd"], returncode=0, stdout="7.0.0", stderr=""
        )
    )
    context = StaticAnalysisContext(
        repository=Repository(name="js", path=tmp_path, files=["index.js"]),
        repository_path=str(tmp_path),
        detected_technologies=[],
    )
    assert provider.is_applicable(context) is False


def test_unavailable_analyze_status(tmp_path: Path) -> None:
    def runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(args, 127, stdout="", stderr="missing")

    provider = PmdProvider(process_runner=runner, executable="pmd-missing")
    result = provider.analyze(_context(tmp_path))
    assert result.status == StaticAnalysisStatus.UNAVAILABLE
