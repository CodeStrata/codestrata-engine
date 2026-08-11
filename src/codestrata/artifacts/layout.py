"""Filesystem layout for ``.codestrata-artifacts/`` (Slice 17.12)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ARTIFACT_ROOT_NAME = ".codestrata-artifacts"
ASSESSMENTS_DIRNAME = "assessments"
INTELLIGENCE_DIRNAME = "intelligence"
VALIDATION_DIRNAME = "validation"
VALIDATION_REPOSITORIES_DIRNAME = "repositories"
VALIDATION_SUITES_DIRNAME = "suites"
VALIDATION_LOGS_DIRNAME = "logs"
MANIFESTS_DIRNAME = "manifests"
TEMPORARY_DIRNAME = "temporary"

_UNSAFE_CHARS = re.compile(r"[^a-z0-9._-]+")
_RUN_ID_PATTERN = re.compile(r"^[a-z0-9._-]+-\d{8}-\d{6}$")


@dataclass(frozen=True, slots=True)
class AssessmentRunPaths:
    """Paths for one assessment run under ``.codestrata-artifacts/assessments/``."""

    root: Path
    run_id: str
    directory: Path
    assessment_json: Path
    assessment_html: Path
    heads_directory: Path
    repository_name: str
    timestamp: str

    @property
    def run_directory(self) -> Path:
        return self.directory

    @property
    def html_report(self) -> Path:
        """Compatibility alias used by existing reporters/CLI."""

        return self.assessment_html

    @property
    def html_report_path(self) -> Path:
        return self.assessment_html

    @property
    def json_report(self) -> Path:
        """Compatibility alias — points at the lightweight assessment manifest."""

        return self.assessment_json

    @property
    def json_report_path(self) -> Path:
        return self.assessment_json

    @property
    def text_report(self) -> Path:
        """Legacy scan text report path (still under the run directory)."""

        return self.directory / "report.txt"

    @property
    def text_report_path(self) -> Path:
        return self.text_report

    @property
    def run_timestamp(self) -> str:
        return self.timestamp


def artifact_root(base: Path | None = None) -> Path:
    """Return the authoritative artifact root (created on demand by callers)."""

    root = (base or Path.cwd()) / ARTIFACT_ROOT_NAME
    return root


def ensure_artifact_tree(base: Path | None = None) -> Path:
    """Create the standard artifact directory tree and return the root."""

    root = artifact_root(base)
    for relative in (
        ASSESSMENTS_DIRNAME,
        INTELLIGENCE_DIRNAME,
        f"{VALIDATION_DIRNAME}/{VALIDATION_REPOSITORIES_DIRNAME}",
        f"{VALIDATION_DIRNAME}/{VALIDATION_SUITES_DIRNAME}",
        f"{VALIDATION_DIRNAME}/{VALIDATION_LOGS_DIRNAME}",
        MANIFESTS_DIRNAME,
        TEMPORARY_DIRNAME,
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    return root


def sanitize_repository_slug(repository_name: str) -> str:
    compact = repository_name.strip().lower()
    slug = _UNSAFE_CHARS.sub("-", compact).strip(".-")
    return slug or "repository"


def format_run_timestamp(moment: datetime | None = None) -> str:
    value = moment if moment is not None else datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.strftime("%Y%m%d-%H%M%S")


def build_assessment_run_id(repository_name: str, timestamp: str | None = None) -> str:
    stamp = timestamp or format_run_timestamp()
    return f"{sanitize_repository_slug(repository_name)}-{stamp}"


def assessments_directory(base: Path | None = None) -> Path:
    return artifact_root(base) / ASSESSMENTS_DIRNAME


def create_assessment_run_paths(
    *,
    repository_name: str,
    base: Path | None = None,
    timestamp: str | None = None,
    run_id: str | None = None,
    create_directory: bool = True,
    stage: bool = True,
) -> AssessmentRunPaths:
    """Create paths for one assessment run.

    Slice 17.15: successful runs are promoted to::

        .codestrata-artifacts/assessments/<repository_id>/current/

    Generation writes under temporary staging first (``stage=True``)::

        .codestrata-artifacts/temporary/assessment-runs/<run_id>/
    """

    from codestrata.artifacts.manifest import (
        ASSESSMENT_HTML_BASENAME,
        ASSESSMENT_JSON_BASENAME,
    )

    root = ensure_artifact_tree(base) if create_directory else artifact_root(base)
    stamp = timestamp or format_run_timestamp()
    rid = run_id or build_assessment_run_id(repository_name, stamp)
    if timestamp is not None and not re.fullmatch(r"\d{8}-\d{6}", stamp):
        raise ValueError(f"timestamp must match YYYYMMDD-HHMMSS, got {stamp!r}")
    if stage:
        directory = root / TEMPORARY_DIRNAME / "assessment-runs" / rid
    else:
        directory = root / ASSESSMENTS_DIRNAME / rid
    heads = directory / "heads"
    if create_directory:
        heads.mkdir(parents=True, exist_ok=True)
    return AssessmentRunPaths(
        root=root,
        run_id=rid,
        directory=directory,
        assessment_json=directory / ASSESSMENT_JSON_BASENAME,
        assessment_html=directory / ASSESSMENT_HTML_BASENAME,
        heads_directory=heads,
        repository_name=sanitize_repository_slug(repository_name),
        timestamp=stamp,
    )


def intelligence_run_directory(
    portfolio_run_id: str,
    *,
    base: Path | None = None,
    create_directory: bool = True,
    stage: bool = True,
    portfolio_id: str | None = None,
) -> Path:
    """Return intelligence output directory.

    Slice 17.15: prefer temporary staging for new runs; promote to
    ``intelligence/<portfolio_id>/current/`` after validation.
    Legacy callers that pass a timestamped ``portfolio_run_id`` still get a
    staging directory keyed by that run id when ``stage=True``.
    """

    root = ensure_artifact_tree(base) if create_directory else artifact_root(base)
    if stage:
        path = root / TEMPORARY_DIRNAME / "intelligence-runs" / portfolio_run_id
    elif portfolio_id:
        path = root / INTELLIGENCE_DIRNAME / portfolio_id / "current"
    else:
        path = root / INTELLIGENCE_DIRNAME / portfolio_run_id
    if create_directory:
        path.mkdir(parents=True, exist_ok=True)
    return path


def validation_suite_directory(
    suite_id: str,
    *,
    base: Path | None = None,
    create_directory: bool = True,
) -> Path:
    root = ensure_artifact_tree(base) if create_directory else artifact_root(base)
    path = root / VALIDATION_DIRNAME / VALIDATION_SUITES_DIRNAME / suite_id
    if create_directory:
        path.mkdir(parents=True, exist_ok=True)
    return path


def validation_repositories_directory(*, base: Path | None = None) -> Path:
    return artifact_root(base) / VALIDATION_DIRNAME / VALIDATION_REPOSITORIES_DIRNAME


def validation_logs_directory(*, base: Path | None = None) -> Path:
    return artifact_root(base) / VALIDATION_DIRNAME / VALIDATION_LOGS_DIRNAME


def manifests_directory(*, base: Path | None = None) -> Path:
    return artifact_root(base) / MANIFESTS_DIRNAME


def temporary_directory(*, base: Path | None = None) -> Path:
    return artifact_root(base) / TEMPORARY_DIRNAME


def is_assessment_run_id(value: str) -> bool:
    return bool(_RUN_ID_PATTERN.match(value))
