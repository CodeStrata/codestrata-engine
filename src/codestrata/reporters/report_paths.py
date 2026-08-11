"""Utilities for creating and retaining analysis report run directories.

Slice 17.15: assessment runs stage under
``.codestrata-artifacts/temporary/assessment-runs/<run_id>/`` then promote to
``.codestrata-artifacts/assessments/<repository_id>/current/`` with at most one
``previous/`` slot.
"""

from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from codestrata.artifacts.layout import (
    ARTIFACT_ROOT_NAME,
    ASSESSMENTS_DIRNAME,
    AssessmentRunPaths,
    create_assessment_run_paths,
    format_run_timestamp,
    sanitize_repository_slug,
)
from codestrata.artifacts.lifecycle import (
    MAX_VERSIONS,
    discard_staging,
    promote_assessment_run,
)
from codestrata.artifacts.manifest import ASSESSMENT_HTML_BASENAME, ASSESSMENT_JSON_BASENAME
from codestrata.artifacts.repository_identity import resolve_repository_artifact_id
from codestrata.models import AnalysisResult

logger = logging.getLogger(__name__)

_REPORT_RUN_DIRECTORY_PATTERN = re.compile(r"^\d{8}-\d{6}$")
_ASSESSMENT_RUN_ID_PATTERN = re.compile(r"^[a-z0-9._-]+-\d{8}-\d{6}$")
DEFAULT_RETAINED_RUN_COUNT = MAX_VERSIONS
DEFAULT_ACTIVE_REPORT_RUNS_TO_KEEP = DEFAULT_RETAINED_RUN_COUNT
_DEFAULT_REPORTS_TO_KEEP = DEFAULT_RETAINED_RUN_COUNT

LEGACY_REPORTS_DIRNAME = "reports"
LEGACY_HTML_BASENAME = "report.html"
LEGACY_JSON_BASENAME = "report.json"

DEFAULT_ASSESS_OUTPUT_DIRECTORY = Path(f"{ARTIFACT_ROOT_NAME}/{ASSESSMENTS_DIRNAME}")


def _git_origin_url(path: Path | str | None) -> str | None:
    """Best-effort read of ``remote.origin.url`` for GitHub identity resolution."""

    if path is None:
        return None
    root = Path(path)
    git_config = root / ".git" / "config"
    # Detached worktrees / plain .git files are uncommon here; handle directories only.
    if not git_config.is_file():
        # Some clones use .git as a file pointing elsewhere — fall back to git CLI.
        try:
            import subprocess

            proc = subprocess.run(
                ["git", "-C", str(root), "config", "--get", "remote.origin.url"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
                env={
                    "PATH": __import__("os").environ.get("PATH", ""),
                    "GIT_TERMINAL_PROMPT": "0",
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_CONFIG_SYSTEM": "/dev/null",
                },
            )
            url = (proc.stdout or "").strip()
            return url or None
        except Exception:  # noqa: BLE001
            return None
    try:
        text = git_config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    # Minimal parse: [remote "origin"] ... url = ...
    in_origin = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_origin = stripped.lower() == '[remote "origin"]'
            continue
        if in_origin and stripped.lower().startswith("url"):
            _, _, value = stripped.partition("=")
            url = value.strip()
            return url or None
    return None

class ReportRetentionError(RuntimeError):
    """Raised when an older report run cannot be pruned safely."""


@dataclass(frozen=True)
class ReportPaths:
    """Paths for all reports generated during one analysis run."""

    directory: Path
    text_report: Path
    json_report: Path
    html_report: Path
    timestamp: str
    repository_name: str
    run_id: str = ""
    heads_directory: Path | None = None
    repository_id: str = ""
    staging: bool = False
    artifact_root: Path | None = None

    @property
    def run_directory(self) -> Path:
        return self.directory

    @property
    def run_timestamp(self) -> str:
        return self.timestamp

    @property
    def html_report_path(self) -> Path:
        return self.html_report

    @property
    def json_report_path(self) -> Path:
        return self.json_report

    @property
    def text_report_path(self) -> Path:
        return self.text_report


def sanitize_repository_directory_name(repository_name: str) -> str:
    """Return a filesystem-safe repository directory name."""

    return sanitize_repository_slug(repository_name)


def format_report_run_timestamp(moment: datetime | None = None) -> str:
    """Return a UTC run timestamp formatted as ``YYYYMMDD-HHMMSS``."""

    return format_run_timestamp(moment)


def _resolve_output_root(base_directory: Path) -> Path:
    """Map legacy ``reports`` default to the authoritative assessments root."""

    if base_directory == Path(LEGACY_REPORTS_DIRNAME) or base_directory.as_posix() == LEGACY_REPORTS_DIRNAME:
        return DEFAULT_ASSESS_OUTPUT_DIRECTORY
    return base_directory


def create_report_paths(
    result: AnalysisResult,
    base_directory: Path,
    *,
    timestamp: str | None = None,
    clock: Callable[[], datetime] | None = None,
    create_directory: bool = True,
) -> ReportPaths:
    """Create report paths for one analysis or assessment run.

    Slice 17.15 default layout stages under temporary then promotes to::

        <artifact-root>/assessments/<repository_id>/current/
    """

    if timestamp is not None:
        run_timestamp = timestamp
        if not _REPORT_RUN_DIRECTORY_PATTERN.match(run_timestamp):
            raise ValueError(f"timestamp must match YYYYMMDD-HHMMSS, got {run_timestamp!r}")
    else:
        now = clock() if clock is not None else datetime.now(UTC)
        run_timestamp = format_report_run_timestamp(now)

    output_root = _resolve_output_root(Path(base_directory))
    repository = result.repository
    repo_path = getattr(repository, "path", None)
    repository_id = resolve_repository_artifact_id(
        repository_name=repository.name,
        source_url=getattr(repository, "source_url", None),
        remote=_git_origin_url(repo_path),
        path=repo_path,
    )

    workspace: Path | None = None
    if output_root == DEFAULT_ASSESS_OUTPUT_DIRECTORY or output_root.as_posix().endswith(
        f"{ARTIFACT_ROOT_NAME}/{ASSESSMENTS_DIRNAME}"
    ):
        if output_root.is_absolute():
            workspace = output_root.parent.parent
        else:
            workspace = Path.cwd()
        run = create_assessment_run_paths(
            repository_name=repository.name,
            base=workspace,
            timestamp=run_timestamp,
            create_directory=create_directory,
            stage=True,
        )
        return _from_assessment_run(run, repository_id=repository_id, staging=True)

    # Custom --output: stage under <output>/.staging/<run-id>/ then promote.
    repo = sanitize_repository_directory_name(repository.name)
    run_id = f"{repo}-{run_timestamp}"
    run_directory = output_root / ".staging" / run_id
    heads = run_directory / "heads"
    if create_directory:
        heads.mkdir(parents=True, exist_ok=True)
    return ReportPaths(
        directory=run_directory,
        text_report=run_directory / "report.txt",
        json_report=run_directory / ASSESSMENT_JSON_BASENAME,
        html_report=run_directory / ASSESSMENT_HTML_BASENAME,
        timestamp=run_timestamp,
        repository_name=repo,
        run_id=run_id,
        heads_directory=heads,
        repository_id=repository_id,
        staging=True,
        artifact_root=output_root,
    )


def _from_assessment_run(
    run: AssessmentRunPaths,
    *,
    repository_id: str,
    staging: bool,
) -> ReportPaths:
    return ReportPaths(
        directory=run.directory,
        text_report=run.text_report,
        json_report=run.assessment_json,
        html_report=run.assessment_html,
        timestamp=run.timestamp,
        repository_name=run.repository_name,
        run_id=run.run_id,
        heads_directory=run.heads_directory,
        repository_id=repository_id,
        staging=staging,
        artifact_root=run.root,
    )


def promote_staged_report(report_paths: ReportPaths) -> Path:
    """Promote a completed staged assessment into current/previous slots."""

    if not report_paths.staging:
        return report_paths.directory
    repository_id = report_paths.repository_id or resolve_repository_artifact_id(
        repository_name=report_paths.repository_name
    )
    base = report_paths.artifact_root
    # Default tree: artifact_root is ``.codestrata-artifacts``.
    if base is not None and base.name == ARTIFACT_ROOT_NAME:
        return promote_assessment_run(
            repository_id=repository_id,
            staging_directory=report_paths.directory,
            base=base.parent,
        )
    return _promote_custom_output(report_paths, repository_id=repository_id)


def _promote_custom_output(report_paths: ReportPaths, *, repository_id: str) -> Path:
    """Promote into ``<output>/<repository_id>/current`` for explicit --output."""

    from codestrata.artifacts.lifecycle import (
        SLOT_CURRENT,
        SLOT_PREVIOUS,
        _annotate_assessment_manifest,
        _replace_dir,
        _rmtree_safe,
        acquire_lifecycle_lock,
        validate_assessment_bundle,
    )

    validate_assessment_bundle(report_paths.directory)
    root = report_paths.artifact_root
    assert root is not None
    logical = root / repository_id
    lock = acquire_lifecycle_lock(logical)
    try:
        current = logical / SLOT_CURRENT
        previous = logical / SLOT_PREVIOUS
        _annotate_assessment_manifest(
            report_paths.directory,
            repository_id=repository_id,
            artifact_slot=SLOT_CURRENT,
            previous_assessment_run_id=None,
        )
        if previous.exists():
            _rmtree_safe(previous)
        if current.exists():
            _annotate_assessment_manifest(
                current,
                repository_id=repository_id,
                artifact_slot=SLOT_PREVIOUS,
                previous_assessment_run_id=None,
            )
            _replace_dir(current, previous)
        _replace_dir(report_paths.directory, current)
        return current
    finally:
        lock.release()


def discard_staged_report(report_paths: ReportPaths) -> None:
    if report_paths.staging and report_paths.directory.exists():
        # Custom output staging uses .staging/ not temporary/
        try:
            discard_staging(report_paths.directory)
        except Exception:
            shutil.rmtree(report_paths.directory, ignore_errors=True)


def is_completed_report_run(run_directory: Path) -> bool:
    """Return True when a run directory contains required report artifacts."""

    if run_directory.is_symlink() or not run_directory.is_dir():
        return False
    modern = (run_directory / ASSESSMENT_HTML_BASENAME).is_file() and (
        run_directory / ASSESSMENT_JSON_BASENAME
    ).is_file()
    legacy = (run_directory / LEGACY_HTML_BASENAME).is_file() and (
        run_directory / LEGACY_JSON_BASENAME
    ).is_file()
    return modern or legacy


def list_active_report_run_directories(repository_directory: Path) -> list[Path]:
    """Return run/slot directories under a parent, newest first."""

    if not repository_directory.exists():
        return []

    candidates: list[Path] = []
    for path in repository_directory.iterdir():
        if path.is_symlink() or not path.is_dir():
            continue
        if path.name in {"current", "previous"}:
            candidates.append(path)
        elif _REPORT_RUN_DIRECTORY_PATTERN.match(path.name):
            candidates.append(path)
        elif _ASSESSMENT_RUN_ID_PATTERN.match(path.name):
            candidates.append(path)
        elif (path / "current").is_dir():
            candidates.append(path / "current")
    return sorted(candidates, key=lambda path: path.name, reverse=True)


def list_completed_report_run_directories(repository_directory: Path) -> list[Path]:
    """Return completed run directories, newest first."""

    return [
        path
        for path in list_active_report_run_directories(repository_directory)
        if is_completed_report_run(path)
    ]


def list_completed_assessment_runs(
    assessments_root: Path,
    *,
    repository_slug: str | None = None,
) -> list[Path]:
    """List completed assessment runs under the assessments root."""

    if repository_slug is not None:
        rid = resolve_repository_artifact_id(repository_name=repository_slug)
        logical = assessments_root / rid
        slots: list[Path] = []
        for slot in ("current", "previous"):
            candidate = logical / slot
            if is_completed_report_run(candidate):
                slots.append(candidate)
        if slots:
            return slots
        runs = list_completed_report_run_directories(assessments_root)
        slug = sanitize_repository_slug(repository_slug)
        prefix = f"{slug}-"
        return [path for path in runs if path.name.startswith(prefix)]

    return list_completed_report_run_directories(assessments_root)


def _is_safe_run_directory(repository_directory: Path, run_directory: Path) -> bool:
    try:
        repository_root = repository_directory.resolve(strict=False)
        candidate = run_directory.resolve(strict=False)
    except OSError:
        return False
    if candidate == repository_root:
        return False
    if candidate.parent != repository_root and candidate.parent.parent != repository_root:
        return False
    if run_directory.is_symlink():
        return False
    return bool(
        run_directory.name in {"current", "previous"}
        or _REPORT_RUN_DIRECTORY_PATTERN.match(run_directory.name)
        or _ASSESSMENT_RUN_ID_PATTERN.match(run_directory.name)
    )


def retain_recent_reports(
    repository_directory: Path,
    keep: int = DEFAULT_RETAINED_RUN_COUNT,
    *,
    repository_slug: str | None = None,
) -> list[Path]:
    """Legacy prune helper — prefer :func:`promote_staged_report` for 17.15."""

    if keep < 1:
        raise ValueError("keep must be at least 1")

    if not repository_directory.exists():
        return []

    if repository_slug is not None:
        rid = resolve_repository_artifact_id(repository_name=repository_slug)
        logical = repository_directory / rid
        if (logical / "current").is_dir():
            return []
        completed = list_completed_assessment_runs(
            repository_directory, repository_slug=repository_slug
        )
    else:
        completed = list_completed_report_run_directories(repository_directory)

    to_delete = completed[keep:]
    deleted: list[Path] = []
    for outdated_directory in to_delete:
        if not _is_safe_run_directory(repository_directory, outdated_directory):
            logger.warning(
                "Skipping unsafe report run path during retention: %s",
                outdated_directory,
            )
            continue
        try:
            shutil.rmtree(outdated_directory)
        except OSError as error:
            raise ReportRetentionError(
                f"Failed to delete aged report run {outdated_directory.name!r}: {error}"
            ) from error
        logger.info("Removed aged report run %s", outdated_directory.name)
        deleted.append(outdated_directory)
    return deleted


def prune_excess_report_runs(
    repository_directory: Path,
    *,
    keep: int = DEFAULT_RETAINED_RUN_COUNT,
    repository_slug: str | None = None,
) -> list[Path]:
    """Alias for :func:`retain_recent_reports` used by assessment cleanup."""

    return retain_recent_reports(
        repository_directory, keep=keep, repository_slug=repository_slug
    )
