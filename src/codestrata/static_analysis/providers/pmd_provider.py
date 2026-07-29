"""PMD static-analysis provider."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from time import perf_counter

from codestrata.models.repository import Repository
from codestrata.models.technology import Technology
from codestrata.scan_boundary import DEFAULT_EXCLUDED_DIRECTORY_NAMES
from codestrata.static_analysis.grouping import (
    group_observations,
    observations_from_pmd_findings,
    visibility_counts,
)
from codestrata.static_analysis.models import (
    StaticAnalysisContext,
    StaticAnalysisResult,
    StaticAnalysisStatus,
)
from codestrata.static_analysis.providers.pmd_command import PmdCommandBuilder
from codestrata.static_analysis.providers.pmd_discovery import (
    probe_pmd_version,
    resolve_pmd_executable,
    sanitize_pmd_user_message,
)
from codestrata.static_analysis.providers.pmd_parser import PmdParser
from codestrata.static_analysis.providers.pmd_profiles import (
    DEFAULT_PMD_PROFILE,
    PmdProfile,
    parse_pmd_profile,
    resolve_pmd_profile_definition,
)

_JAVA_SOURCE_ROOTS = (
    "src/main/java",
    "src/test/java",
)

_EXCLUDED_DIRECTORY_NAMES = DEFAULT_EXCLUDED_DIRECTORY_NAMES


class PmdProvider:
    """Run PMD against Java repositories and normalize findings."""

    def __init__(
        self,
        *,
        executable: str = "pmd",
        rulesets: Sequence[str] | None = None,
        minimum_priority: int | None = None,
        timeout_seconds: int = 120,
        enabled: bool = True,
        profile: str | PmdProfile | None = None,
        command_builder: PmdCommandBuilder | None = None,
        parser: PmdParser | None = None,
        process_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self._configured_executable = executable
        self._profile = parse_pmd_profile(profile or DEFAULT_PMD_PROFILE)
        definition = resolve_pmd_profile_definition(
            self._profile,
            configured_rulesets=list(rulesets) if rulesets is not None else None,
        )
        self._rulesets = list(definition.rulesets)
        self._minimum_priority = (
            minimum_priority if minimum_priority is not None else definition.minimum_priority
        )
        self._timeout_seconds = timeout_seconds
        self._enabled = enabled
        self._parser = parser or PmdParser()
        self._process_runner = process_runner or subprocess.run
        self._cached_version: str | None | bool = False
        self._resolved_executable: str | None = None
        self._discovery_source: str | None = None
        self._discovery_message: str | None = None
        # Command builder is refreshed once discovery resolves an executable.
        self._command_builder = command_builder or PmdCommandBuilder(executable)
        self._injected_command_builder = command_builder is not None

    @property
    def provider_id(self) -> str:
        return "pmd"

    @property
    def display_name(self) -> str:
        return "PMD"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"Java"})

    def is_available(self) -> bool:
        if self._cached_version is False:
            self._cached_version = self._resolve_version()
        return self._cached_version is not None

    def is_applicable(self, context: StaticAnalysisContext) -> bool:
        if not self._enabled:
            return False
        return self._repository_has_java(
            repository=context.repository,
            technologies=context.detected_technologies,
        )

    def analyze(self, context: StaticAnalysisContext) -> StaticAnalysisResult:
        started = perf_counter()
        version = self._resolve_version()
        if version is None:
            message = (
                self._discovery_message
                or "PMD executable was not found or could not report a version."
            )
            sanitized = sanitize_pmd_user_message(message)
            return StaticAnalysisResult(
                provider_id=self.provider_id,
                provider_name=self.display_name,
                status=StaticAnalysisStatus.UNAVAILABLE,
                error_message=sanitized,
                warnings=[sanitized],
            )

        repository_path = Path(context.repository_path).resolve()
        source_roots = self._resolve_source_roots(
            repository=context.repository,
            repository_path=repository_path,
        )
        eligible_files = self._collect_java_files(source_roots)
        eligible_count = len(eligible_files)
        metadata_base: dict[str, object] = {
            "profile": self._profile.value,
            "rulesets": list(self._rulesets),
            "source_roots": [self._relative_root(root, repository_path) for root in source_roots],
            "eligible_file_count": eligible_count,
            "minimum_priority": self._minimum_priority,
        }

        if not source_roots or eligible_count == 0:
            return StaticAnalysisResult(
                provider_id=self.provider_id,
                provider_name=self.display_name,
                provider_version=version,
                status=StaticAnalysisStatus.SKIPPED,
                eligible_file_count=0,
                files_analyzed=0,
                warnings=["No Java source files were found for PMD analysis."],
                duration_ms=round((perf_counter() - started) * 1000, 2),
                command_metadata=metadata_base,
            )

        with tempfile.TemporaryDirectory(prefix="codestrata-pmd-") as temp_directory:
            report_file = Path(temp_directory) / "pmd-report.xml"
            command = self._command_builder.analyze_command(
                source_roots=source_roots,
                rulesets=self._rulesets,
                report_file=report_file,
                minimum_priority=self._minimum_priority,
            )

            try:
                completed = self._run_process(command.args)
            except subprocess.TimeoutExpired:
                return StaticAnalysisResult(
                    provider_id=self.provider_id,
                    provider_name=self.display_name,
                    provider_version=version,
                    status=StaticAnalysisStatus.FAILED,
                    eligible_file_count=eligible_count,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    command_metadata=self._merge_metadata(command.metadata, metadata_base),
                    error_message="PMD analysis timed out.",
                    warnings=["PMD analysis timed out."],
                )

            if completed.returncode not in {0, 4} and not report_file.exists():
                # Retry once with legacy CLI if the modern command is unrecognized.
                legacy = self._command_builder.legacy_analyze_command(
                    source_roots=source_roots,
                    rulesets=self._rulesets,
                    report_file=report_file,
                    minimum_priority=self._minimum_priority,
                )
                try:
                    completed = self._run_process(legacy.args)
                except subprocess.TimeoutExpired:
                    return StaticAnalysisResult(
                        provider_id=self.provider_id,
                        provider_name=self.display_name,
                        provider_version=version,
                        status=StaticAnalysisStatus.FAILED,
                        eligible_file_count=eligible_count,
                        duration_ms=round((perf_counter() - started) * 1000, 2),
                        command_metadata=self._merge_metadata(legacy.metadata, metadata_base),
                        error_message="PMD analysis timed out.",
                        warnings=["PMD analysis timed out."],
                    )
                command = legacy

            if completed.returncode not in {0, 4} and not report_file.exists():
                return StaticAnalysisResult(
                    provider_id=self.provider_id,
                    provider_name=self.display_name,
                    provider_version=version,
                    status=StaticAnalysisStatus.FAILED,
                    eligible_file_count=eligible_count,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    command_metadata=self._merge_metadata(command.metadata, metadata_base),
                    error_message=self._sanitize_error(
                        completed.stderr or completed.stdout or "PMD failed"
                    ),
                    warnings=["PMD analysis failed."],
                )

            report_xml = ""
            if report_file.exists():
                report_xml = report_file.read_text(encoding="utf-8", errors="replace")
            elif completed.stdout:
                report_xml = completed.stdout

            if not report_xml.strip():
                return StaticAnalysisResult(
                    provider_id=self.provider_id,
                    provider_name=self.display_name,
                    provider_version=version,
                    status=StaticAnalysisStatus.FAILED,
                    eligible_file_count=eligible_count,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    command_metadata=self._merge_metadata(command.metadata, metadata_base),
                    error_message="PMD produced no report output.",
                    warnings=["PMD produced no report output."],
                )

            try:
                findings = self._parser.parse(
                    report_xml,
                    repository_path=repository_path,
                    provider_version=version,
                )
            except ValueError as exc:
                return StaticAnalysisResult(
                    provider_id=self.provider_id,
                    provider_name=self.display_name,
                    provider_version=version,
                    status=StaticAnalysisStatus.FAILED,
                    eligible_file_count=eligible_count,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    command_metadata=self._merge_metadata(command.metadata, metadata_base),
                    error_message=str(exc),
                    warnings=[str(exc)],
                )

            # Successful processing of a non-empty eligible set.
            files_analyzed = eligible_count
            status = StaticAnalysisStatus.COMPLETED
            warnings: list[str] = []
            error_message = None
            if files_analyzed <= 0:
                status = StaticAnalysisStatus.FAILED
                error_message = (
                    "PMD unexpectedly processed zero files despite eligible Java sources."
                )
                warnings = [error_message]
                return StaticAnalysisResult(
                    provider_id=self.provider_id,
                    provider_name=self.display_name,
                    provider_version=version,
                    status=status,
                    findings=[],
                    files_analyzed=0,
                    eligible_file_count=eligible_count,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    command_metadata=self._merge_metadata(command.metadata, metadata_base),
                    warnings=warnings,
                    error_message=error_message,
                    profile=self._profile.value,
                )

            observations = observations_from_pmd_findings(findings)
            groups, customer_findings = group_observations(observations)
            counts = visibility_counts(observations, groups)

            return StaticAnalysisResult(
                provider_id=self.provider_id,
                provider_name=self.display_name,
                provider_version=version,
                status=status,
                findings=customer_findings,
                files_analyzed=files_analyzed,
                eligible_file_count=eligible_count,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                command_metadata=self._merge_metadata(command.metadata, metadata_base),
                warnings=warnings,
                error_message=error_message,
                profile=self._profile.value,
                observations=observations,
                groups=groups,
                raw_observation_count=counts["raw_observation_count"],
                grouped_finding_count=counts["grouped_finding_count"],
                primary_count=counts["primary_count"],
                supporting_count=counts["supporting_count"],
                informational_count=counts["informational_count"],
                suppressed_from_html_count=counts["suppressed_from_html_count"],
            )

    def _resolve_version(self) -> str | None:
        discovery = resolve_pmd_executable(configured=self._configured_executable)
        self._discovery_source = discovery.source
        self._discovery_message = discovery.message
        if discovery.executable is None:
            return None

        self._resolved_executable = discovery.executable
        if not self._injected_command_builder:
            self._command_builder = PmdCommandBuilder(discovery.executable)

        version = probe_pmd_version(
            discovery.executable,
            process_runner=self._process_runner,
            timeout_seconds=min(30, self._timeout_seconds),
        )
        if version is None:
            self._discovery_message = (
                discovery.message or "PMD executable was not found or could not report a version."
            )
            return None
        return version

    def _run_process(
        self,
        args: list[str],
        *,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        completed = self._process_runner(
            args,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=timeout or self._timeout_seconds,
        )
        if not isinstance(completed, subprocess.CompletedProcess):
            raise TypeError("process runner must return CompletedProcess")
        return completed

    def _resolve_source_roots(
        self,
        *,
        repository: Repository,
        repository_path: Path,
    ) -> list[Path]:
        roots: list[Path] = []
        for relative in _JAVA_SOURCE_ROOTS:
            candidate = (repository_path / relative).resolve()
            if candidate.is_dir():
                roots.append(candidate)

        if roots:
            return roots

        java_files = [
            Path(path)
            for path in repository.files
            if path.replace("\\", "/").endswith(".java") and not self._is_excluded(path)
        ]
        if not java_files:
            # Last resort: walk repository for .java files outside excluded dirs.
            discovered = self._discover_java_files_on_disk(repository_path)
            if not discovered:
                return []
            parents = sorted({path.parent for path in discovered})
            return parents[:20]

        parents = sorted({(repository_path / path).resolve().parent for path in java_files})
        return parents[:20]

    def _collect_java_files(self, source_roots: list[Path]) -> list[Path]:
        files: list[Path] = []
        for root in source_roots:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.java")):
                if not path.is_file():
                    continue
                try:
                    relative = path.relative_to(root)
                except ValueError:
                    relative = path
                if self._is_excluded(relative.as_posix()):
                    continue
                files.append(path.resolve())
        # Unique while preserving order
        seen: set[Path] = set()
        unique: list[Path] = []
        for path in files:
            if path in seen:
                continue
            seen.add(path)
            unique.append(path)
        return unique

    def _discover_java_files_on_disk(self, repository_path: Path) -> list[Path]:
        discovered: list[Path] = []
        for path in repository_path.rglob("*.java"):
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(repository_path).as_posix()
            except ValueError:
                continue
            if self._is_excluded(relative):
                continue
            discovered.append(path.resolve())
        return discovered

    def _repository_has_java(
        self,
        *,
        repository: Repository,
        technologies: Sequence[Technology],
    ) -> bool:
        if any(technology.name == "Java" for technology in technologies):
            return True
        return any(path.replace("\\", "/").endswith(".java") for path in repository.files)

    @staticmethod
    def _relative_root(root: Path, repository_path: Path) -> str:
        try:
            return root.resolve().relative_to(repository_path.resolve()).as_posix()
        except ValueError:
            return root.name

    @staticmethod
    def _is_excluded(relative_path: str) -> bool:
        parts = set(Path(relative_path.replace("\\", "/")).parts)
        return bool(parts & _EXCLUDED_DIRECTORY_NAMES)

    def _merge_metadata(
        self,
        command_metadata: dict[str, object],
        extra: dict[str, object],
    ) -> dict[str, object]:
        sanitized = self._sanitize_command_metadata(command_metadata)
        sanitized.update(extra)
        return sanitized

    @staticmethod
    def _sanitize_command_metadata(metadata: dict[str, object]) -> dict[str, object]:
        sanitized = dict(metadata)
        sanitized.pop("args", None)
        sanitized.pop("command", None)
        sanitized.pop("executable_path", None)
        return sanitized

    @staticmethod
    def _sanitize_error(message: str) -> str:
        compact = " ".join(message.split())
        if len(compact) > 300:
            return compact[:297] + "..."
        return compact
