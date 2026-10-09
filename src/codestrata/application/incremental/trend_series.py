"""R2-P06 five-snapshot assessment orchestration and P07 durable bundle persist."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codestrata import RULESET_VERSION, __version__
from codestrata.application.assessment import AssessmentCommandError, run_assessment
from codestrata.application.incremental.source_states import (
    SERIES_SLOT_COUNT,
    MaterializedSnapshot,
    SnapshotWorkspace,
    WorktreeFingerprint,
    attach_readonly_gitdir,
    capture_worktree_fingerprint,
    select_first_parent_series,
    snapshot_assessment_root,
)
from codestrata.config import CodestrataSettings
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.reporting import AssessmentMode
from codestrata.reporting.journey_observations import FEED_RELATIVE

TREND_SERIES_SCHEMA = "codestrata.trend-series.v1"
TREND_SERIES_SCHEMA_VERSION = "1.0.0"
DEFAULT_TREND_OUTPUT_DIRECTORY = Path(".codestrata-artifacts")
DIRTY_WORKTREE_NOTICE = (
    "Working tree is dirty and was left untouched. Trend uses committed HEAD "
    "and excludes uncommitted changes."
)


@dataclass(frozen=True, slots=True)
class PinnedEvaluationProfile:
    engine_version: str
    ruleset_version: str
    evaluation_time: datetime
    config_digest: str
    feed_digest: str
    feed_bytes: bytes | None


@dataclass(frozen=True, slots=True)
class TrendSlotRecord:
    slot: int
    sha: str | None
    status: str
    unavailable_reason: str | None
    source_revision: str | None
    git_head: str | None
    dirty: bool | None
    source_digest: str | None
    result_digest: str | None
    config_digest: str
    feed_digest: str | None
    engine_version: str
    evaluation_time: str
    limitations: tuple[str, ...]
    file_paths: tuple[str, ...]
    hotspot_subjects: tuple[str, ...]
    finding_titles: tuple[str, ...]
    graph_node_ids: tuple[str, ...]
    cochange_pairs: tuple[tuple[str, str], ...]
    ownership_profile_ids: tuple[str, ...]
    output_directory: str | None


@dataclass(frozen=True, slots=True)
class TrendSeriesResult:
    repository_root: Path
    git_root: Path | None
    assessment_relpath: str
    head_sha: str | None
    dirty_worktree: bool
    dirty_notice: str | None
    profile: PinnedEvaluationProfile
    before: WorktreeFingerprint
    after: WorktreeFingerprint
    worktree_unchanged: bool
    slots: tuple[TrendSlotRecord, ...]
    series_digest: str
    bundle_directory: Path | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "schema_name": TREND_SERIES_SCHEMA,
            "schema_version": TREND_SERIES_SCHEMA_VERSION,
            "repository_root": str(self.repository_root),
            "git_root": None if self.git_root is None else str(self.git_root),
            "assessment_relpath": self.assessment_relpath,
            "bundle_directory": None
            if self.bundle_directory is None
            else str(self.bundle_directory),
            "head_sha": self.head_sha,
            "dirty_worktree": self.dirty_worktree,
            "dirty_notice": self.dirty_notice,
            "worktree_unchanged": self.worktree_unchanged,
            "profile": {
                "engine_version": self.profile.engine_version,
                "ruleset_version": self.profile.ruleset_version,
                "evaluation_time": _iso(self.profile.evaluation_time),
                "config_digest": self.profile.config_digest,
                "feed_digest": self.profile.feed_digest,
            },
            "slots": [_slot_json(slot) for slot in self.slots],
            "series_digest": self.series_digest,
        }


def freeze_evaluation_profile(
    repository_root: Path,
    *,
    evaluation_time: datetime,
    settings: CodestrataSettings | None,
) -> PinnedEvaluationProfile:
    feed_path = repository_root.expanduser().resolve() / FEED_RELATIVE
    feed_bytes = feed_path.read_bytes() if feed_path.is_file() else None
    feed_digest = hashlib.sha256(feed_bytes).hexdigest() if feed_bytes is not None else ""
    return PinnedEvaluationProfile(
        engine_version=__version__,
        ruleset_version=RULESET_VERSION,
        evaluation_time=evaluation_time.astimezone(UTC),
        config_digest=digest_canonical(semantic_assessment_config(settings)),
        feed_digest=feed_digest,
        feed_bytes=feed_bytes,
    )


def run_trend_series(
    repository_root: Path,
    output_directory: Path,
    *,
    evaluation_time: datetime,
    settings: CodestrataSettings | None = None,
    assess: Callable[..., Any] = run_assessment,
) -> TrendSeriesResult:
    """Assess committed HEAD plus four first-parent predecessors.

    Does not mutate ``repository_root``. Missing and failed slots stay explicit.
    """

    from codestrata.application.incremental.trend_bundle import (
        create_trend_bundle,
        finalize_trend_bundle,
        persist_slot,
        repository_trend_id,
        resolve_series_directory,
    )

    requested = repository_root.expanduser().resolve()
    series_dir = resolve_series_directory(output_directory, requested)
    series_dir.mkdir(parents=True, exist_ok=True)
    bundle = create_trend_bundle(
        series_dir,
        repository_id=repository_trend_id(requested),
        series_id=series_dir.name,
    )
    isolated = _isolate_settings(settings, bundle.staging)
    before = capture_worktree_fingerprint(requested)
    series = select_first_parent_series(requested)
    profile = freeze_evaluation_profile(
        requested,
        evaluation_time=evaluation_time,
        settings=settings,
    )
    records: list[TrendSlotRecord] = []
    with SnapshotWorkspace(series) as workspace:
        for snapshot in workspace.snapshots:
            record = _assess_slot(
                snapshot,
                series_limitations=series.limitations,
                git_root=series.git_root,
                assessment_relpath=series.assessment_relpath,
                profile=profile,
                output_directory=bundle.staging,
                settings=isolated,
                assess=assess,
            )
            staging = None
            if record.output_directory:
                staging = Path(record.output_directory)
            records.append(persist_slot(bundle, record, profile, staging_directory=staging))
    after = capture_worktree_fingerprint(requested)
    slots = tuple(records)
    result = TrendSeriesResult(
        repository_root=requested,
        git_root=series.git_root,
        assessment_relpath=series.assessment_relpath,
        head_sha=series.head_sha,
        dirty_worktree=before.dirty,
        dirty_notice=DIRTY_WORKTREE_NOTICE if before.dirty else None,
        profile=profile,
        before=before,
        after=after,
        worktree_unchanged=_worktree_untouched(
            before, after, series_dir, requested
        ),
        slots=slots,
        series_digest=digest_canonical([_slot_json(slot) for slot in slots]),
        bundle_directory=series_dir,
    )
    finalize_trend_bundle(bundle, result)
    _write_series_index(series_dir, result)
    return result


def _isolate_settings(
    settings: CodestrataSettings | None,
    output_directory: Path,
) -> CodestrataSettings:
    knowledge_dir = output_directory / "knowledge"
    if settings is None:
        return CodestrataSettings.model_validate(
            {
                "repository": {"path": "."},
                "knowledge": {"enabled": False, "directory": str(knowledge_dir)},
                "static_analysis": {"enabled": False},
            }
        )
    knowledge = settings.knowledge.model_copy(update={"directory": knowledge_dir})
    return settings.model_copy(update={"knowledge": knowledge})


def semantic_assessment_config(settings: CodestrataSettings | None) -> dict[str, object]:
    """Return settings that identify assessment semantics, not run storage.

    Operational locations (knowledge/workspace directories and the invocation
    repository path) must not change ``config_digest`` across series/output
    directories. Rules, scan, analysis, and other assessment inputs remain.
    """

    if settings is None:
        return {}
    dump = settings.model_dump(mode="json")
    if not isinstance(dump, dict):
        return {}
    return _strip_operational_config_fields(dump)


def _strip_operational_config_fields(payload: dict[str, object]) -> dict[str, object]:
    cleaned = dict(payload)
    knowledge = cleaned.get("knowledge")
    if isinstance(knowledge, dict):
        knowledge = dict(knowledge)
        knowledge.pop("directory", None)
        cleaned["knowledge"] = knowledge
    workspace = cleaned.get("workspace")
    if isinstance(workspace, dict):
        workspace = dict(workspace)
        workspace.pop("directory", None)
        cleaned["workspace"] = workspace
    repository = cleaned.get("repository")
    if isinstance(repository, dict):
        repository = dict(repository)
        repository.pop("path", None)
        cleaned["repository"] = repository
    return cleaned


def _assess_slot(
    snapshot: MaterializedSnapshot,
    *,
    series_limitations: tuple[str, ...],
    git_root: Path | None,
    assessment_relpath: str,
    profile: PinnedEvaluationProfile,
    output_directory: Path,
    settings: CodestrataSettings,
    assess: Callable[..., Any],
) -> TrendSlotRecord:
    slot = snapshot.slot
    limitations = [*series_limitations, *snapshot.limitations]
    evaluation = _iso(profile.evaluation_time)
    if not slot.available or slot.sha is None or snapshot.root is None:
        return TrendSlotRecord(
            slot=slot.slot,
            sha=slot.sha,
            status="unavailable",
            unavailable_reason=slot.unavailable_reason or "slot_unavailable",
            source_revision=None,
            git_head=None,
            dirty=None,
            source_digest=None,
            result_digest=None,
            config_digest=profile.config_digest,
            feed_digest=profile.feed_digest,
            engine_version=profile.engine_version,
            evaluation_time=evaluation,
            limitations=tuple(dict.fromkeys(limitations)),
            file_paths=(),
            hotspot_subjects=(),
            finding_titles=(),
            graph_node_ids=(),
            cochange_pairs=(),
            ownership_profile_ids=(),
            output_directory=None,
        )

    assess_root = snapshot_assessment_root(snapshot.root, assessment_relpath)
    if not assess_root.is_dir():
        limitations.append("assessment_scope_missing")
        return _failed_record(slot.slot, slot.sha, profile, "", limitations)
    source_digest = _tree_digest(assess_root)
    if git_root is not None:
        attach_readonly_gitdir(snapshot.root, git_root)
    from codestrata.application.incremental.trend_bundle import hash_feed_file

    _overlay_pinned_feed(assess_root, profile, limitations)
    observed_feed_digest = hash_feed_file(assess_root) or profile.feed_digest
    snapshot_files = _tree_paths(assess_root)
    slot_output = output_directory / f"s{slot.slot}"
    try:
        command = assess(
            str(assess_root),
            slot_output,
            mode=AssessmentMode.DETERMINISTIC,
            settings=settings,
            clock=lambda: profile.evaluation_time,
            quiet=True,
            history_head=slot.sha,
            write_reports=True,
        )
    except AssessmentCommandError as error:
        limitations.append(f"assessment_failed:{error}")
        return _failed_record(slot.slot, slot.sha, profile, source_digest, limitations)
    except Exception as error:  # noqa: BLE001 - slot failure must not abort the series
        limitations.append(f"assessment_failed:{error}")
        return _failed_record(slot.slot, slot.sha, profile, source_digest, limitations)

    analysis = _analysis_from_command(command)
    _persist_analysis_result(command, analysis, slot_output)
    metadata = _metadata_from_analysis(analysis)
    files = snapshot_files or _files_from_analysis(analysis)
    return TrendSlotRecord(
        slot=slot.slot,
        sha=slot.sha,
        status="available",
        unavailable_reason=None,
        source_revision=str(metadata.get("source_revision") or slot.sha),
        git_head=str(metadata.get("git_head") or slot.sha),
        dirty=bool(metadata.get("dirty", False)),
        source_digest=source_digest,
        result_digest=digest_canonical(
            {
                "source_revision": metadata.get("source_revision"),
                "findings": _finding_titles(analysis),
                "files": files,
            }
        ),
        config_digest=profile.config_digest,
        feed_digest=observed_feed_digest,
        engine_version=profile.engine_version,
        evaluation_time=str(metadata.get("evaluation_time") or evaluation),
        limitations=tuple(
            dict.fromkeys([*limitations, *list(metadata.get("canonical_limitations") or ())])
        ),
        file_paths=files,
        hotspot_subjects=_hotspot_subjects(metadata),
        finding_titles=_finding_titles(analysis),
        graph_node_ids=_graph_nodes(slot_output),
        cochange_pairs=_cochange_pairs(metadata),
        ownership_profile_ids=_ownership_profiles(metadata),
        output_directory=str(slot_output),
    )


def _failed_record(
    slot: int,
    sha: str,
    profile: PinnedEvaluationProfile,
    source_digest: str,
    limitations: list[str],
) -> TrendSlotRecord:
    return TrendSlotRecord(
        slot=slot,
        sha=sha,
        status="failed",
        unavailable_reason="assessment_failed",
        source_revision=sha,
        git_head=sha,
        dirty=False,
        source_digest=source_digest,
        result_digest=None,
        config_digest=profile.config_digest,
        feed_digest=profile.feed_digest,
        engine_version=profile.engine_version,
        evaluation_time=_iso(profile.evaluation_time),
        limitations=tuple(dict.fromkeys(limitations)),
        file_paths=(),
        hotspot_subjects=(),
        finding_titles=(),
        graph_node_ids=(),
        cochange_pairs=(),
        ownership_profile_ids=(),
        output_directory=None,
    )


def _overlay_pinned_feed(
    snapshot_root: Path,
    profile: PinnedEvaluationProfile,
    limitations: list[str],
) -> None:
    if profile.feed_bytes is None:
        return
    target = snapshot_root / FEED_RELATIVE
    existed = target.is_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not existed or target.read_bytes() != profile.feed_bytes:
        target.write_bytes(profile.feed_bytes)
        limitations.append("pinned_feed_overlay")


def _worktree_untouched(
    before: WorktreeFingerprint,
    after: WorktreeFingerprint,
    output_directory: Path,
    repository_root: Path,
) -> bool:
    if (
        before.head_sha != after.head_sha
        or before.tree_oid != after.tree_oid
        or before.index_digest != after.index_digest
        or before.dirty != after.dirty
    ):
        return False
    try:
        output_directory.resolve().relative_to(repository_root.resolve())
    except ValueError:
        return before == after
    return True


def _tree_paths(root: Path) -> tuple[str, ...]:
    paths: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == ".git" or ".git" in path.parts:
            continue
        paths.append(path.relative_to(root).as_posix())
    return tuple(paths)


def _tree_digest(root: Path) -> str:
    rows = [
        (relative, hashlib.sha256((root / relative).read_bytes()).hexdigest())
        for relative in _tree_paths(root)
    ]
    return digest_canonical(rows)


def _persist_analysis_result(command: Any, analysis: Any, slot_output: Path) -> None:
    """Write the compare-input AnalysisResult next to assessment artifacts."""

    from codestrata.models import AnalysisResult

    if not isinstance(analysis, AnalysisResult):
        return
    from codestrata.application.incremental.trend_bundle import ANALYSIS_RESULT_FILENAME

    json_path = getattr(command, "json_report_path", None)
    destination = (
        Path(json_path).with_name(ANALYSIS_RESULT_FILENAME)
        if json_path
        else slot_output / ANALYSIS_RESULT_FILENAME
    )
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    except (OSError, TypeError, ValueError):
        return


def _analysis_from_command(command: Any) -> Any:
    analysis = getattr(command, "analysis_result", None)
    if analysis is not None:
        return analysis
    path = getattr(command, "json_report_path", None)
    if path is None:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _metadata_from_analysis(analysis: Any) -> dict[str, Any]:
    if analysis is None:
        return {}
    if isinstance(analysis, Mapping):
        raw = analysis.get("metadata") or {}
        return dict(raw) if isinstance(raw, Mapping) else {}
    return dict(getattr(analysis, "metadata", {}) or {})


def _files_from_analysis(analysis: Any) -> tuple[str, ...]:
    if analysis is None:
        return ()
    if isinstance(analysis, Mapping):
        repository = analysis.get("repository") or {}
        files = repository.get("files") if isinstance(repository, Mapping) else ()
    else:
        files = getattr(getattr(analysis, "repository", None), "files", ()) or ()
    return tuple(str(path) for path in files or ())


def _hotspot_subjects(metadata: dict[str, Any]) -> tuple[str, ...]:
    subjects: list[str] = []
    for item in metadata.get("canonical_hotspots") or ():
        if isinstance(item, dict):
            subject = item.get("subject_id") or item.get("path") or item.get("file")
            if subject:
                subjects.append(str(subject))
    return tuple(subjects)


def _finding_titles(analysis: Any) -> tuple[str, ...]:
    if analysis is None:
        return ()
    if isinstance(analysis, Mapping):
        findings = analysis.get("findings") or ()
    else:
        findings = getattr(analysis, "findings", ()) or ()
    titles: list[str] = []
    for finding in findings:
        if isinstance(finding, Mapping):
            title = finding.get("title")
        else:
            title = getattr(finding, "title", None)
        if title:
            titles.append(str(title))
    return tuple(titles)


def _cochange_pairs(metadata: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for item in metadata.get("canonical_cochange") or ():
        if isinstance(item, dict):
            left = str(item.get("left") or "")
            right = str(item.get("right") or "")
            if left and right:
                pairs.append((left, right))
    return tuple(pairs)


def _ownership_profiles(metadata: dict[str, Any]) -> tuple[str, ...]:
    profiles: list[str] = []
    for item in metadata.get("canonical_ownership") or ():
        if isinstance(item, dict):
            profile = item.get("history_profile_id")
            if profile:
                profiles.append(str(profile))
    return tuple(profiles)


def _graph_nodes(slot_output: Path) -> tuple[str, ...]:
    matches = list(slot_output.rglob("graphs/repository-graph.json"))
    if not matches:
        return ()
    try:
        payload = json.loads(matches[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    nodes = payload.get("nodes") or []
    ids: list[str] = []
    for node in nodes:
        if isinstance(node, dict):
            ident = node.get("id") or node.get("path") or node.get("label")
            if ident:
                ids.append(str(ident))
    return tuple(ids)


def _write_series_index(output_directory: Path, result: TrendSeriesResult) -> None:
    path = output_directory / "trend-series.json"
    path.write_text(json.dumps(result.to_json(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _slot_json(slot: TrendSlotRecord) -> dict[str, object]:
    return {
        "slot": slot.slot,
        "sha": slot.sha,
        "status": slot.status,
        "unavailable_reason": slot.unavailable_reason,
        "source_revision": slot.source_revision,
        "git_head": slot.git_head,
        "dirty": slot.dirty,
        "source_digest": slot.source_digest,
        "result_digest": slot.result_digest,
        "config_digest": slot.config_digest,
        "feed_digest": slot.feed_digest,
        "engine_version": slot.engine_version,
        "evaluation_time": slot.evaluation_time,
        "limitations": list(slot.limitations),
        "file_paths": list(slot.file_paths),
        "hotspot_subjects": list(slot.hotspot_subjects),
        "finding_titles": list(slot.finding_titles),
        "graph_node_ids": list(slot.graph_node_ids),
        "cochange_pairs": [list(pair) for pair in slot.cochange_pairs],
        "ownership_profile_ids": list(slot.ownership_profile_ids),
        "output_directory": slot.output_directory,
    }


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def expected_slot_count() -> int:
    return SERIES_SLOT_COUNT
