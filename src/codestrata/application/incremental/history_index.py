"""E09.2 bounded Git history index: M24 churn/recency, M25 concentration, M26 co-change."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from codestrata.application.incremental.errors import IncrementalPlanningError
from codestrata.domain.contracts.catalog import load_launch_ratification
from codestrata.domain.contracts.enums import FreshnessState, MetricStatus
from codestrata.domain.contracts.formulas import ratio
from codestrata.domain.contracts.models import HistoryProfile, MetricComputation
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.infrastructure.knowledge_store.git_revision import (
    LocalGitState,
    mailmap_present,
    observe_local_git_state,
    read_merge_combined_numstat,
    read_reachable_commit_metadata,
    read_reachable_commit_name_status,
    read_reachable_commit_numstat,
)
from codestrata.repository_auth.read_only_git import ReadOnlyGitError

HISTORY_INDEX_SCHEMA = "codestrata.git-history-index.v1"
HISTORY_INDEX_SCHEMA_VERSION = "1.0.0"
SECONDS_PER_DAY = 86400
COCHANGE_SUPPORT_THRESHOLD = 3
_RENAME_BRACE = re.compile(r"^(.*)\{(.*) => (.*)\}(.*)$")


class HistoryCoverage(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    MISSING = "missing"


class ConcentrationScope(StrEnum):
    REPOSITORY = "repository"
    COMPONENT = "component"
    FILE = "file"


class HistoryIndexError(IncrementalPlanningError):
    """Bounded history index cannot be produced from local Git."""


@dataclass(frozen=True, slots=True)
class FileEdit:
    path: str
    old_path: str | None
    added_lines: int | None
    deleted_lines: int | None
    binary: bool


@dataclass(frozen=True, slots=True)
class RawCommitRecord:
    sha: str
    parents: tuple[str, ...]
    committer_unix: int
    author_name: str
    author_email: str
    mapped_name: str
    mapped_email: str
    subject: str
    body: str
    files: tuple[FileEdit, ...]


@dataclass(frozen=True, slots=True)
class IncludedCommit:
    sha: str
    parents: tuple[str, ...]
    committer_unix: int
    identity: str | None
    raw_author: str
    subject: str
    bugfix_marker: bool
    matched_markers: tuple[str, ...]
    files: tuple[FileEdit, ...]
    text_changed_lines: int | None
    binary_partial: bool
    is_root: bool


@dataclass(frozen=True, slots=True)
class FileChurn:
    path: str
    renamed_from: tuple[str, ...]
    changed_lines: int | None
    binary_unknown: bool
    latest_valid_committer_unix: int | None
    recency_seconds: int | None
    component_id: str | None
    mapping_status: str
    commit_shas: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComponentChurn:
    component_id: str
    changed_lines: int | None
    binary_unknown: bool
    mapping_status: str
    latest_valid_committer_unix: int | None
    recency_seconds: int | None
    file_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContributorShare:
    identity: str
    changed_lines: int
    bot_declared: bool


@dataclass(frozen=True, slots=True)
class ConcentrationRecord:
    scope: ConcentrationScope
    subject_id: str
    status: MetricStatus
    largest_share: MetricComputation
    contributors_to_50pct: int | None
    attributable_lines: int
    unattributed_lines: int
    unknown_contribution_lines: int
    mapping_status: str
    mapping_coverage: str | None
    complete_window: bool
    contributors: tuple[ContributorShare, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CochangeRecord:
    scope: str
    left: str
    right: str
    support: int
    union: int
    jaccard: MetricComputation
    supported_relation: bool
    commit_shas: tuple[str, ...]
    qualified_incomplete_window: bool


@dataclass(frozen=True, slots=True)
class GitCapabilityRecord:
    capability_id: str
    profile_id: str
    requested_window_days: int
    requested_max_commits: int
    observed_commit_count: int
    observed_oldest_committer_unix: int | None
    observed_newest_committer_unix: int | None
    evaluation_time_unix: int
    coverage: HistoryCoverage
    unknown_reasons: tuple[str, ...]
    freshness: FreshnessState
    freshness_reason: str
    complete_window: bool


@dataclass(frozen=True, slots=True)
class BugfixMarkerContext:
    marker_version: str
    patterns: tuple[str, ...]
    matched_commit_shas: tuple[str, ...]
    matched_commit_count: int
    proven_defects: bool
    productivity_claim: bool
    intent_claim: bool


@dataclass(frozen=True, slots=True)
class HistoryWindowBounds:
    profile_id: str
    profile_version: str
    evaluation_time_unix: int
    window_start_unix: int
    requested_window_days: int
    requested_max_commits: int
    merge_policy: str
    rename_policy: str
    mailmap_policy: str
    traversal: str
    order: str
    observed_included_count: int
    observed_oldest_committer_unix: int | None
    observed_newest_committer_unix: int | None
    observed_reachable_non_merge_count: int
    complete_window: bool
    first_parent_combined_with_skip_merges: bool


@dataclass(frozen=True, slots=True)
class HistoryIndex:
    schema_name: str
    schema_version: str
    local_state: LocalGitState
    bounds: HistoryWindowBounds
    included: tuple[IncludedCommit, ...]
    excluded_future_shas: tuple[str, ...]
    merge_shas: tuple[str, ...]
    merge_conflict_only_shas: tuple[str, ...]
    file_churn: tuple[FileChurn, ...]
    component_churn: tuple[ComponentChurn, ...]
    concentrations: tuple[ConcentrationRecord, ...]
    cochange: tuple[CochangeRecord, ...]
    capabilities: tuple[GitCapabilityRecord, ...]
    bugfix_markers: BugfixMarkerContext
    limitations: tuple[str, ...]
    canonical_digest: str
    mailmap_applied: bool


@dataclass(frozen=True, slots=True)
class HistoryIndexRequest:
    repository_root: Path
    evaluation_time: datetime
    head: str | None = None
    component_map: Mapping[str, str] | None = None
    declared_bot_identities: Sequence[str] = ()
    repository_id: str = "repository"


def build_history_index(request: HistoryIndexRequest) -> HistoryIndex:
    """Build the pinned M24/M25/M26 index from local Git. Never fetches or checks out."""

    if request.evaluation_time.tzinfo is None:
        raise HistoryIndexError("evaluation_time must be pinned UTC")
    evaluation = request.evaluation_time.astimezone(UTC)
    evaluation_unix = int(evaluation.timestamp())
    profile = load_launch_ratification().history
    root = request.repository_root.expanduser().resolve()
    state = observe_local_git_state(root)
    limitations: list[str] = list(state.limitations)
    head = request.head or state.head_sha
    mailmap_applied = mailmap_present(root)

    if head is None or "not_a_git_repository" in state.limitations:
        return _unavailable_index(
            state=state,
            profile=profile,
            evaluation_unix=evaluation_unix,
            limitations=(*dict.fromkeys(["git_history_missing", *limitations]),),
            reason="git_history_missing",
            coverage=HistoryCoverage.MISSING,
            mailmap_applied=mailmap_applied,
            repository_id=request.repository_id,
        )

    try:
        raw_meta = read_reachable_commit_metadata(root, head=head)
        raw_numstat = read_reachable_commit_numstat(root, head=head)
        raw_names = read_reachable_commit_name_status(root, head=head)
        raw_merges = read_merge_combined_numstat(root, head=head)
    except ReadOnlyGitError as error:
        limitations.append("history_unavailable")
        limitations.append(str(error.verb or "log"))
        return _unavailable_index(
            state=state,
            profile=profile,
            evaluation_unix=evaluation_unix,
            limitations=tuple(dict.fromkeys(limitations)),
            reason="git_history_missing",
            coverage=HistoryCoverage.UNKNOWN,
            mailmap_applied=mailmap_applied,
            repository_id=request.repository_id,
        )

    records = _attach_files(
        _parse_metadata(raw_meta),
        _merge_file_edits(_parse_numstat_log(raw_numstat), _parse_name_status_log(raw_names)),
    )
    merge_shas, conflict_shas = _parse_merge_log(raw_merges)
    if merge_shas:
        limitations.append("merge_commits_excluded")
    if conflict_shas:
        limitations.append("merge_conflict_resolution_edits_excluded")
    limitations.append("first_parent_not_combined_with_skip_merges")

    window_start = evaluation_unix - profile.window_days * SECONDS_PER_DAY
    future = tuple(
        item.sha for item in records if item.committer_unix > evaluation_unix
    )
    if future:
        limitations.append("future_timestamp_excluded_from_recency")
    included_raw, truncated_cap = select_included_commits(
        records, profile=profile, evaluation_unix=evaluation_unix
    )
    if truncated_cap:
        limitations.append("git_window_partial")

    marker_patterns = tuple(profile.bugfix_markers)
    compiled = tuple(re.compile(item, re.IGNORECASE) for item in marker_patterns)
    included = tuple(
        _to_included(item, compiled, marker_patterns) for item in included_raw
    )
    marker_shas = tuple(item.sha for item in included if item.bugfix_marker)

    complete_window = _complete_window(
        state=state,
        window_start=window_start,
        truncated_cap=truncated_cap,
        reachable=records,
    )
    if state.shallow and not complete_window:
        limitations.append("git_history_shallow")

    canonical_paths, rename_history = _canonical_paths(included)
    file_churn = _file_churn(
        included,
        canonical_paths=canonical_paths,
        rename_history=rename_history,
        component_map=request.component_map or {},
        evaluation_unix=evaluation_unix,
    )
    component_churn = _component_churn(file_churn, evaluation_unix=evaluation_unix)
    bots = frozenset(request.declared_bot_identities)
    concentrations = _concentrations(
        included,
        file_churn=file_churn,
        component_churn=component_churn,
        canonical_paths=canonical_paths,
        bots=bots,
        complete_window=complete_window,
        repository_id=request.repository_id,
    )
    cochange = (
        *_cochange(included, canonical_paths, "file", lambda files: files, complete_window),
        *_component_cochange(
            included,
            canonical_paths,
            request.component_map or {},
            complete_window,
        ),
    )
    bounds = HistoryWindowBounds(
        profile_id=profile.profile_id,
        profile_version=profile.version,
        evaluation_time_unix=evaluation_unix,
        window_start_unix=window_start,
        requested_window_days=profile.window_days,
        requested_max_commits=profile.max_commits,
        merge_policy=profile.merge_policy,
        rename_policy=profile.rename_policy,
        mailmap_policy=profile.mailmap_policy,
        traversal=profile.traversal,
        order=profile.order,
        observed_included_count=len(included),
        observed_oldest_committer_unix=_oldest(included),
        observed_newest_committer_unix=_newest_valid(included, evaluation_unix),
        observed_reachable_non_merge_count=len(records),
        complete_window=complete_window,
        first_parent_combined_with_skip_merges=False,
    )
    coverage, reasons = _coverage_state(
        complete_window=complete_window,
        missing=False,
        shallow=state.shallow,
        truncated_cap=truncated_cap,
        included_count=len(included),
    )
    capabilities = tuple(
        _capability(
            capability_id=item,
            bounds=bounds,
            coverage=coverage,
            reasons=reasons,
        )
        for item in ("M24", "M25", "M26")
    )
    unique_limitations = tuple(dict.fromkeys(limitations))
    payload = _canonical_payload(
        bounds=bounds,
        included=included,
        file_churn=file_churn,
        component_churn=component_churn,
        concentrations=concentrations,
        cochange=cochange,
        capabilities=capabilities,
        limitations=unique_limitations,
        future=future,
        merge_shas=merge_shas,
        conflict_shas=conflict_shas,
        marker_shas=marker_shas,
        mailmap_applied=mailmap_applied,
        state_digest=state.state_digest,
    )
    return HistoryIndex(
        schema_name=HISTORY_INDEX_SCHEMA,
        schema_version=HISTORY_INDEX_SCHEMA_VERSION,
        local_state=state,
        bounds=bounds,
        included=included,
        excluded_future_shas=future,
        merge_shas=merge_shas,
        merge_conflict_only_shas=conflict_shas,
        file_churn=file_churn,
        component_churn=component_churn,
        concentrations=concentrations,
        cochange=cochange,
        capabilities=capabilities,
        bugfix_markers=BugfixMarkerContext(
            marker_version=profile.version,
            patterns=marker_patterns,
            matched_commit_shas=marker_shas,
            matched_commit_count=len(marker_shas),
            proven_defects=False,
            productivity_claim=False,
            intent_claim=False,
        ),
        limitations=unique_limitations,
        canonical_digest=digest_canonical(payload),
        mailmap_applied=mailmap_applied,
    )


def select_included_commits(
    records: Sequence[RawCommitRecord],
    *,
    profile: HistoryProfile,
    evaluation_unix: int,
) -> tuple[tuple[RawCommitRecord, ...], bool]:
    """Apply the ratified 180-day then latest-1000 window. Deterministic ties by SHA."""

    window_start = evaluation_unix - profile.window_days * SECONDS_PER_DAY
    in_window = [
        item
        for item in records
        if window_start <= item.committer_unix <= evaluation_unix
    ]
    ordered = sorted(in_window, key=lambda item: (-item.committer_unix, item.sha))
    truncated = len(ordered) > profile.max_commits
    return tuple(ordered[: profile.max_commits]), truncated


def write_history_index(index: HistoryIndex, output_dir: Path) -> dict[str, Path]:
    """Write a single-pass JSONL/file index. Existing files in the directory are replaced."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    def dump_jsonl(name: str, rows: Sequence[Mapping[str, Any]]) -> None:
        path = output_dir / name
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(
                    json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                )
                handle.write("\n")
        written[name] = path

    dump_jsonl(
        "commits.jsonl",
        [_commit_row(item, index.bounds.evaluation_time_unix) for item in index.included],
    )
    dump_jsonl("file_churn.jsonl", [_file_churn_row(item) for item in index.file_churn])
    dump_jsonl(
        "component_churn.jsonl",
        [_component_churn_row(item) for item in index.component_churn],
    )
    dump_jsonl(
        "concentration.jsonl",
        [_concentration_row(item) for item in index.concentrations],
    )
    dump_jsonl("cochange.jsonl", [_cochange_row(item) for item in index.cochange])
    dump_jsonl("capabilities.jsonl", [_capability_row(item) for item in index.capabilities])
    manifest = output_dir / "index-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_name": index.schema_name,
                "schema_version": index.schema_version,
                "canonical_digest": index.canonical_digest,
                "profile_id": index.bounds.profile_id,
                "evaluation_time_unix": index.bounds.evaluation_time_unix,
                "included_commit_count": index.bounds.observed_included_count,
                "complete_window": index.bounds.complete_window,
                "limitations": list(index.limitations),
                "mailmap_applied": index.mailmap_applied,
                "bugfix_marker_count": index.bugfix_markers.matched_commit_count,
                "bugfix_markers_are_proven_defects": False,
                "first_parent_combined_with_skip_merges": (
                    index.bounds.first_parent_combined_with_skip_merges
                ),
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    written["index-manifest.json"] = manifest
    return written


def local_identity(name: str, email: str) -> str | None:
    """Repository-local identity. No organization attribution."""

    cleaned_name = name.strip()
    cleaned_email = email.strip().lower()
    if not cleaned_email:
        return None
    if not cleaned_name:
        return f"<{cleaned_email}>"
    return f"{cleaned_name} <{cleaned_email}>"


def _parse_metadata(payload: str) -> list[RawCommitRecord]:
    records: list[RawCommitRecord] = []
    for chunk in payload.split("\x1e"):
        if not chunk.strip("\0\n"):
            continue
        parts = chunk.split("\0", 8)
        if len(parts) < 9:
            continue
        sha, parent_text, ct_raw, an, ae, mapped_n, mapped_e, subject, body = parts
        try:
            committer_unix = int(ct_raw)
        except ValueError:
            continue
        parents = tuple(item for item in parent_text.split() if item)
        records.append(
            RawCommitRecord(
                sha=sha.strip(),
                parents=parents,
                committer_unix=committer_unix,
                author_name=an,
                author_email=ae,
                mapped_name=mapped_n,
                mapped_email=mapped_e,
                subject=subject,
                body=body.rstrip("\n"),
                files=(),
            )
        )
    return records


def _parse_numstat_log(payload: str) -> dict[str, tuple[FileEdit, ...]]:
    by_sha: dict[str, tuple[FileEdit, ...]] = {}
    for chunk in payload.split("\x1e"):
        text = chunk.strip("\n")
        if not text:
            continue
        lines = text.splitlines()
        sha = lines[0].strip()
        parsed: list[FileEdit] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            item = _parse_numstat_line(line)
            if item is not None:
                parsed.append(item)
        by_sha[sha] = tuple(parsed)
    return by_sha


def _parse_numstat_line(line: str) -> FileEdit | None:
    pieces = line.split("\t")
    if len(pieces) < 3:
        return None
    added_raw, deleted_raw = pieces[0], pieces[1]
    path_raw = "\t".join(pieces[2:])
    path, old_path = _split_rename_path(path_raw)
    binary = added_raw == "-" or deleted_raw == "-"
    added = None if binary else int(added_raw)
    deleted = None if binary else int(deleted_raw)
    return FileEdit(
        path=path,
        old_path=old_path,
        added_lines=added,
        deleted_lines=deleted,
        binary=binary,
    )


def _split_rename_path(raw: str) -> tuple[str, str | None]:
    path = raw.strip()
    match = _RENAME_BRACE.match(path)
    if match:
        prefix, old, new, suffix = match.groups()
        return f"{prefix}{new}{suffix}", f"{prefix}{old}{suffix}"
    if " => " in path:
        old, new = path.split(" => ", 1)
        return new, old
    return path, None


def _parse_name_status_log(payload: str) -> dict[str, list[tuple[str, str, str | None]]]:
    by_sha: dict[str, list[tuple[str, str, str | None]]] = {}
    for chunk in payload.split("\x1e"):
        text = chunk.strip("\n")
        if not text:
            continue
        lines = text.splitlines()
        sha = lines[0].strip()
        rows: list[tuple[str, str, str | None]] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            pieces = line.split("\t")
            code = pieces[0][:1] if pieces else "M"
            if code in {"R", "C"} and len(pieces) >= 3:
                rows.append((code, pieces[2], pieces[1]))
            elif len(pieces) >= 2:
                rows.append((code, pieces[1], None))
        by_sha[sha] = rows
    return by_sha


def _merge_file_edits(
    numstat: Mapping[str, tuple[FileEdit, ...]],
    names: Mapping[str, list[tuple[str, str, str | None]]],
) -> dict[str, tuple[FileEdit, ...]]:
    merged: dict[str, tuple[FileEdit, ...]] = {}
    shas = set(numstat) | set(names)
    for sha in shas:
        stats = {item.path: item for item in numstat.get(sha, ())}
        rows = names.get(sha, [])
        files: list[FileEdit] = []
        seen: set[str] = set()
        for code, path, old_path in rows:
            stat = stats.get(path)
            if stat is None and old_path:
                stat = stats.get(old_path)
            if stat is None:
                files.append(
                    FileEdit(
                        path=path,
                        old_path=old_path,
                        added_lines=0 if code != "D" else None,
                        deleted_lines=0,
                        binary=False,
                    )
                )
            else:
                files.append(
                    FileEdit(
                        path=path,
                        old_path=old_path or stat.old_path,
                        added_lines=stat.added_lines,
                        deleted_lines=stat.deleted_lines,
                        binary=stat.binary,
                    )
                )
            seen.add(path)
            if old_path:
                seen.add(old_path)
        for path, stat in stats.items():
            if path in seen or (stat.old_path and stat.old_path in seen):
                continue
            files.append(stat)
        merged[sha] = tuple(files)
    return merged


def _attach_files(
    records: Sequence[RawCommitRecord],
    files_by_sha: Mapping[str, tuple[FileEdit, ...]],
) -> tuple[RawCommitRecord, ...]:
    attached: list[RawCommitRecord] = []
    for item in records:
        attached.append(
            RawCommitRecord(
                sha=item.sha,
                parents=item.parents,
                committer_unix=item.committer_unix,
                author_name=item.author_name,
                author_email=item.author_email,
                mapped_name=item.mapped_name,
                mapped_email=item.mapped_email,
                subject=item.subject,
                body=item.body,
                files=files_by_sha.get(item.sha, ()),
            )
        )
    return tuple(attached)


def _parse_merge_log(payload: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    merges: list[str] = []
    conflicts: list[str] = []
    for chunk in payload.split("\x1e"):
        text = chunk.strip("\n")
        if not text:
            continue
        header, _, rest = text.partition("\n")
        sha = header.split("\0", 1)[0].strip()
        if not sha:
            continue
        merges.append(sha)
        if any(line.strip() for line in rest.splitlines()):
            conflicts.append(sha)
    return tuple(dict.fromkeys(merges)), tuple(dict.fromkeys(conflicts))


def _to_included(
    item: RawCommitRecord,
    compiled: Sequence[re.Pattern[str]],
    patterns: Sequence[str],
) -> IncludedCommit:
    message = f"{item.subject}\n{item.body}"
    matched = tuple(
        pattern
        for pattern, regex in zip(patterns, compiled, strict=True)
        if regex.search(message)
    )
    identity = local_identity(item.mapped_name, item.mapped_email)
    text_known = True
    text_lines = 0
    binary_partial = False
    for file_edit in item.files:
        if file_edit.binary or file_edit.added_lines is None or file_edit.deleted_lines is None:
            binary_partial = binary_partial or file_edit.binary
            text_known = False
            continue
        text_lines += file_edit.added_lines + file_edit.deleted_lines
    return IncludedCommit(
        sha=item.sha,
        parents=item.parents,
        committer_unix=item.committer_unix,
        identity=identity,
        raw_author=f"{item.author_name} <{item.author_email}>",
        subject=item.subject,
        bugfix_marker=bool(matched),
        matched_markers=matched,
        files=item.files,
        text_changed_lines=text_lines if text_known else None,
        binary_partial=binary_partial,
        is_root=len(item.parents) == 0,
    )


def _complete_window(
    *,
    state: LocalGitState,
    window_start: int,
    truncated_cap: bool,
    reachable: Sequence[RawCommitRecord],
) -> bool:
    if truncated_cap:
        return False
    if not reachable:
        return not state.shallow
    oldest = min(item.committer_unix for item in reachable)
    if state.shallow:
        return oldest <= window_start
    return True


def _canonical_paths(
    included: Sequence[IncludedCommit],
) -> tuple[dict[str, str], dict[str, set[str]]]:
    parent: dict[str, str] = {}

    def root_of(path: str) -> str:
        seen: set[str] = set()
        current = path
        while current in parent and current not in seen:
            seen.add(current)
            current = parent[current]
        return current

    chronological = sorted(included, key=lambda item: (item.committer_unix, item.sha))
    aliases: dict[str, set[str]] = defaultdict(set)
    for commit in chronological:
        for file_edit in commit.files:
            if file_edit.old_path:
                parent[root_of(file_edit.old_path)] = file_edit.path
            aliases[file_edit.path].add(file_edit.path)
            if file_edit.old_path:
                aliases[file_edit.path].add(file_edit.old_path)
                aliases[file_edit.old_path].add(file_edit.path)
    canonical = {path: root_of(path) for path in aliases}
    for path, names in list(aliases.items()):
        dest = canonical.get(path, path)
        aliases[dest].update(names)
        aliases[dest].add(dest)
    return canonical, {key: set(value) for key, value in aliases.items()}


def _file_churn(
    included: Sequence[IncludedCommit],
    *,
    canonical_paths: Mapping[str, str],
    rename_history: Mapping[str, set[str]],
    component_map: Mapping[str, str],
    evaluation_unix: int,
) -> tuple[FileChurn, ...]:
    lines: dict[str, int | None] = {}
    binary_flag: dict[str, bool] = defaultdict(bool)
    latest: dict[str, int] = {}
    shas: dict[str, list[str]] = defaultdict(list)
    renamed_from: dict[str, set[str]] = defaultdict(set)
    for commit in included:
        valid_recency = commit.committer_unix <= evaluation_unix
        for file_edit in commit.files:
            dest = canonical_paths.get(file_edit.path, file_edit.path)
            if file_edit.old_path:
                renamed_from[dest].add(file_edit.old_path)
            shas[dest].append(commit.sha)
            if valid_recency:
                latest[dest] = max(latest.get(dest, 0), commit.committer_unix)
            if file_edit.binary or file_edit.added_lines is None or file_edit.deleted_lines is None:
                binary_flag[dest] = True
                lines[dest] = None
                continue
            if binary_flag[dest]:
                lines[dest] = None
                continue
            lines[dest] = (lines.get(dest) or 0) + file_edit.added_lines + file_edit.deleted_lines
    records: list[FileChurn] = []
    for path in sorted(lines):
        aliases = rename_history.get(path, {path}) | renamed_from.get(path, set()) | {path}
        component_id, mapping_status = _map_component(aliases, component_map)
        changed = None if binary_flag[path] else lines[path]
        latest_unix = latest.get(path)
        recency = None if latest_unix is None else evaluation_unix - latest_unix
        records.append(
            FileChurn(
                path=path,
                renamed_from=tuple(sorted(renamed_from.get(path, ()))),
                changed_lines=changed,
                binary_unknown=binary_flag[path],
                latest_valid_committer_unix=latest_unix,
                recency_seconds=recency,
                component_id=component_id,
                mapping_status=mapping_status,
                commit_shas=tuple(dict.fromkeys(shas[path])),
            )
        )
    return tuple(records)


def _map_component(
    aliases: set[str],
    component_map: Mapping[str, str],
) -> tuple[str | None, str]:
    if not component_map:
        return None, "unmapped"
    ids = {component_map[path] for path in aliases if path in component_map}
    if len(ids) > 1:
        return None, "unknown_ambiguous"
    if len(ids) == 1:
        return next(iter(ids)), "mapped"
    return None, "unmapped"


def _component_churn(
    files: Sequence[FileChurn],
    *,
    evaluation_unix: int,
) -> tuple[ComponentChurn, ...]:
    grouped: dict[str, list[FileChurn]] = defaultdict(list)
    for item in files:
        if item.component_id and item.mapping_status == "mapped":
            grouped[item.component_id].append(item)
    records: list[ComponentChurn] = []
    for component_id in sorted(grouped):
        members = grouped[component_id]
        binary = any(item.binary_unknown for item in members)
        known = [item.changed_lines for item in members if item.changed_lines is not None]
        changed = None if binary and not known else sum(known)
        latest_unix = max(
            (item.latest_valid_committer_unix or 0 for item in members),
            default=0,
        ) or None
        recency = None if latest_unix is None else evaluation_unix - latest_unix
        records.append(
            ComponentChurn(
                component_id=component_id,
                changed_lines=changed,
                binary_unknown=binary,
                mapping_status="mapped",
                latest_valid_committer_unix=latest_unix,
                recency_seconds=recency,
                file_paths=tuple(sorted(item.path for item in members)),
            )
        )
    return tuple(records)


def _concentrations(
    included: Sequence[IncludedCommit],
    *,
    file_churn: Sequence[FileChurn],
    component_churn: Sequence[ComponentChurn],
    canonical_paths: Mapping[str, str],
    bots: frozenset[str],
    complete_window: bool,
    repository_id: str,
) -> tuple[ConcentrationRecord, ...]:
    records: list[ConcentrationRecord] = []
    records.append(
        _concentration_for_subject(
            included,
            scope=ConcentrationScope.REPOSITORY,
            subject_id=repository_id,
            file_filter=lambda path: True,
            mapping_status="observed",
            mapping_coverage="1.000000" if included else None,
            bots=bots,
            complete_window=complete_window,
            canonical_paths=canonical_paths,
        )
    )
    files_by_path = {row.path: row for row in file_churn}
    for file_row in file_churn:
        dest = file_row.path

        def _matches_file(path: str, target: str = dest) -> bool:
            return canonical_paths.get(path, path) == target

        records.append(
            _concentration_for_subject(
                included,
                scope=ConcentrationScope.FILE,
                subject_id=file_row.path,
                file_filter=_matches_file,
                mapping_status=file_row.mapping_status,
                mapping_coverage=(
                    "1.000000" if file_row.mapping_status == "mapped" else "0.000000"
                ),
                bots=bots,
                complete_window=complete_window,
                canonical_paths=canonical_paths,
            )
        )
    for component_row in component_churn:
        member_paths = set(component_row.file_paths)

        def _matches_component(path: str, members: set[str] = member_paths) -> bool:
            return canonical_paths.get(path, path) in members

        records.append(
            _concentration_for_subject(
                included,
                scope=ConcentrationScope.COMPONENT,
                subject_id=component_row.component_id,
                file_filter=_matches_component,
                mapping_status=component_row.mapping_status,
                mapping_coverage=_component_mapping_coverage(files_by_path, member_paths),
                bots=bots,
                complete_window=complete_window,
                canonical_paths=canonical_paths,
            )
        )
    ambiguous = [item for item in file_churn if item.mapping_status == "unknown_ambiguous"]
    for item in ambiguous:
        records.append(
            ConcentrationRecord(
                scope=ConcentrationScope.COMPONENT,
                subject_id=f"ambiguous:{item.path}",
                status=MetricStatus.UNKNOWN,
                largest_share=_unknown_share(),
                contributors_to_50pct=None,
                attributable_lines=0,
                unattributed_lines=0,
                unknown_contribution_lines=0,
                mapping_status="unknown_ambiguous",
                mapping_coverage=None,
                complete_window=complete_window,
                contributors=(),
                notes=(
                    "ambiguous_mapping_unknown_at_component_scope",
                    "preserve_repository_and_file_observations",
                ),
            )
        )
    return tuple(records)


def _component_mapping_coverage(
    files: Mapping[str, FileChurn],
    member_paths: set[str],
) -> str:
    if not member_paths:
        return "0.000000"
    mapped = sum(
        1
        for path in member_paths
        if files.get(path) and files[path].mapping_status == "mapped"
    )
    return f"{mapped / len(member_paths):.6f}"


def _concentration_for_subject(
    included: Sequence[IncludedCommit],
    *,
    scope: ConcentrationScope,
    subject_id: str,
    file_filter: Callable[[str], bool],
    mapping_status: str,
    mapping_coverage: str | None,
    bots: frozenset[str],
    complete_window: bool,
    canonical_paths: Mapping[str, str],
) -> ConcentrationRecord:
    by_identity: dict[str, int] = defaultdict(int)
    unattributed = 0
    unknown_contrib = 0
    for commit in included:
        added = 0
        binary = False
        matched = False
        for file_edit in commit.files:
            path = canonical_paths.get(file_edit.path, file_edit.path)
            if not file_filter(file_edit.path) and not file_filter(path):
                continue
            matched = True
            if file_edit.binary or file_edit.added_lines is None or file_edit.deleted_lines is None:
                binary = True
                continue
            added += file_edit.added_lines + file_edit.deleted_lines
        if not matched:
            continue
        if binary:
            unknown_contrib += added
            continue
        if commit.identity is None:
            unattributed += added
            continue
        by_identity[commit.identity] += added
    attributable = sum(by_identity.values())
    notes = [
        "change_concentration_not_ownership_authority",
        "not_organizational_bus_factor",
        "not_productivity_or_blame",
    ]
    if attributable == 0:
        if unattributed:
            notes.append("missing_identity_visible")
        if not complete_window:
            notes.append("partial_window_cannot_claim_complete_ownership")
        return ConcentrationRecord(
            scope=scope,
            subject_id=subject_id,
            status=MetricStatus.NOT_APPLICABLE,
            largest_share=ratio(0, 0, empty_status=MetricStatus.NOT_APPLICABLE),
            contributors_to_50pct=None,
            attributable_lines=0,
            unattributed_lines=unattributed,
            unknown_contribution_lines=unknown_contrib,
            mapping_status=mapping_status,
            mapping_coverage=mapping_coverage,
            complete_window=complete_window,
            contributors=(),
            notes=tuple(notes),
        )
    ordered = sorted(by_identity.items(), key=lambda item: (-item[1], item[0]))
    largest = ordered[0][1]
    share = ratio(largest, attributable)
    cumulative = 0
    contributors_to_50 = 0
    for _identity, amount in ordered:
        contributors_to_50 += 1
        cumulative += amount
        if cumulative * 2 >= attributable:
            break
    contributors = tuple(
        ContributorShare(
            identity=identity,
            changed_lines=amount,
            bot_declared=identity in bots,
        )
        for identity, amount in ordered
    )
    if not complete_window:
        notes.append("partial_window_cannot_claim_complete_ownership")
    if unattributed:
        notes.append("missing_identity_visible")
    return ConcentrationRecord(
        scope=scope,
        subject_id=subject_id,
        status=MetricStatus.VALUE,
        largest_share=share,
        contributors_to_50pct=contributors_to_50,
        attributable_lines=attributable,
        unattributed_lines=unattributed,
        unknown_contribution_lines=unknown_contrib,
        mapping_status=mapping_status,
        mapping_coverage=mapping_coverage,
        complete_window=complete_window,
        contributors=contributors,
        notes=tuple(notes),
    )


def _unknown_share() -> MetricComputation:
    return MetricComputation(
        status=MetricStatus.UNKNOWN,
        numerator=None,
        denominator=None,
        value=None,
        serialized=None,
        reason="unknown_ambiguous_mapping",
    )


def _cochange(
    included: Sequence[IncludedCommit],
    canonical_paths: Mapping[str, str],
    scope: str,
    members_of: Callable[[set[str]], set[str]],
    complete_window: bool,
) -> tuple[CochangeRecord, ...]:
    incidence: dict[str, set[str]] = defaultdict(set)
    for commit in included:
        members = {
            canonical_paths.get(file_edit.path, file_edit.path) for file_edit in commit.files
        }
        for member in members_of(members):
            incidence[member].add(commit.sha)
    records: list[CochangeRecord] = []
    names = sorted(incidence)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            left_set = incidence[left]
            right_set = incidence[right]
            support_set = left_set & right_set
            union_set = left_set | right_set
            support = len(support_set)
            if support == 0:
                continue
            union = len(union_set)
            records.append(
                CochangeRecord(
                    scope=scope,
                    left=left,
                    right=right,
                    support=support,
                    union=union,
                    jaccard=ratio(support, union),
                    supported_relation=support >= COCHANGE_SUPPORT_THRESHOLD,
                    commit_shas=tuple(sorted(support_set)),
                    qualified_incomplete_window=not complete_window,
                )
            )
    return tuple(records)


def _component_cochange(
    included: Sequence[IncludedCommit],
    canonical_paths: Mapping[str, str],
    component_map: Mapping[str, str],
    complete_window: bool,
) -> tuple[CochangeRecord, ...]:
    if not component_map:
        return ()

    def members_of(files: set[str]) -> set[str]:
        ids: set[str] = set()
        for path in files:
            aliases = {path, canonical_paths.get(path, path)}
            mapped = {component_map[item] for item in aliases if item in component_map}
            if len(mapped) == 1:
                ids.add(next(iter(mapped)))
        return ids

    return _cochange(included, canonical_paths, "component", members_of, complete_window)


def _capability(
    *,
    capability_id: str,
    bounds: HistoryWindowBounds,
    coverage: HistoryCoverage,
    reasons: tuple[str, ...],
) -> GitCapabilityRecord:
    freshness = FreshnessState.NOT_APPLICABLE
    freshness_reason = "not_time_sensitive"
    if coverage in {HistoryCoverage.MISSING, HistoryCoverage.UNKNOWN}:
        freshness = FreshnessState.UNKNOWN
        freshness_reason = reasons[0] if reasons else "git_history_missing"
    return GitCapabilityRecord(
        capability_id=capability_id,
        profile_id=bounds.profile_id,
        requested_window_days=bounds.requested_window_days,
        requested_max_commits=bounds.requested_max_commits,
        observed_commit_count=bounds.observed_included_count,
        observed_oldest_committer_unix=bounds.observed_oldest_committer_unix,
        observed_newest_committer_unix=bounds.observed_newest_committer_unix,
        evaluation_time_unix=bounds.evaluation_time_unix,
        coverage=coverage,
        unknown_reasons=reasons,
        freshness=freshness,
        freshness_reason=freshness_reason,
        complete_window=bounds.complete_window,
    )


def _coverage_state(
    *,
    complete_window: bool,
    missing: bool,
    shallow: bool,
    truncated_cap: bool,
    included_count: int,
) -> tuple[HistoryCoverage, tuple[str, ...]]:
    if missing:
        return HistoryCoverage.MISSING, ("git_history_missing",)
    reasons: list[str] = []
    if shallow and not complete_window:
        reasons.append("git_history_shallow")
    if truncated_cap:
        reasons.append("git_window_partial")
    if complete_window:
        return HistoryCoverage.COMPLETE, ()
    if included_count == 0:
        return HistoryCoverage.UNKNOWN, tuple(reasons or ("git_history_missing",))
    return HistoryCoverage.PARTIAL, tuple(reasons)


def _unavailable_index(
    *,
    state: LocalGitState,
    profile: HistoryProfile,
    evaluation_unix: int,
    limitations: tuple[str, ...],
    reason: str,
    coverage: HistoryCoverage,
    mailmap_applied: bool,
    repository_id: str,
) -> HistoryIndex:
    window_start = evaluation_unix - profile.window_days * SECONDS_PER_DAY
    bounds = HistoryWindowBounds(
        profile_id=profile.profile_id,
        profile_version=profile.version,
        evaluation_time_unix=evaluation_unix,
        window_start_unix=window_start,
        requested_window_days=profile.window_days,
        requested_max_commits=profile.max_commits,
        merge_policy=profile.merge_policy,
        rename_policy=profile.rename_policy,
        mailmap_policy=profile.mailmap_policy,
        traversal=profile.traversal,
        order=profile.order,
        observed_included_count=0,
        observed_oldest_committer_unix=None,
        observed_newest_committer_unix=None,
        observed_reachable_non_merge_count=0,
        complete_window=False,
        first_parent_combined_with_skip_merges=False,
    )
    capabilities = tuple(
        _capability(capability_id=item, bounds=bounds, coverage=coverage, reasons=(reason,))
        for item in ("M24", "M25", "M26")
    )
    empty_concentration = ConcentrationRecord(
        scope=ConcentrationScope.REPOSITORY,
        subject_id=repository_id,
        status=MetricStatus.NOT_APPLICABLE,
        largest_share=ratio(0, 0, empty_status=MetricStatus.NOT_APPLICABLE),
        contributors_to_50pct=None,
        attributable_lines=0,
        unattributed_lines=0,
        unknown_contribution_lines=0,
        mapping_status="unavailable",
        mapping_coverage=None,
        complete_window=False,
        contributors=(),
        notes=("git_history_missing", "not_organizational_bus_factor"),
    )
    payload = _canonical_payload(
        bounds=bounds,
        included=(),
        file_churn=(),
        component_churn=(),
        concentrations=(empty_concentration,),
        cochange=(),
        capabilities=capabilities,
        limitations=limitations,
        future=(),
        merge_shas=(),
        conflict_shas=(),
        marker_shas=(),
        mailmap_applied=mailmap_applied,
        state_digest=state.state_digest,
    )
    return HistoryIndex(
        schema_name=HISTORY_INDEX_SCHEMA,
        schema_version=HISTORY_INDEX_SCHEMA_VERSION,
        local_state=state,
        bounds=bounds,
        included=(),
        excluded_future_shas=(),
        merge_shas=(),
        merge_conflict_only_shas=(),
        file_churn=(),
        component_churn=(),
        concentrations=(empty_concentration,),
        cochange=(),
        capabilities=capabilities,
        bugfix_markers=BugfixMarkerContext(
            marker_version=profile.version,
            patterns=tuple(profile.bugfix_markers),
            matched_commit_shas=(),
            matched_commit_count=0,
            proven_defects=False,
            productivity_claim=False,
            intent_claim=False,
        ),
        limitations=limitations,
        canonical_digest=digest_canonical(payload),
        mailmap_applied=mailmap_applied,
    )


def _oldest(included: Sequence[IncludedCommit]) -> int | None:
    if not included:
        return None
    return min(item.committer_unix for item in included)


def _newest_valid(included: Sequence[IncludedCommit], evaluation_unix: int) -> int | None:
    valid = [item.committer_unix for item in included if item.committer_unix <= evaluation_unix]
    if not valid:
        return None
    return max(valid)


def _commit_row(item: IncludedCommit, evaluation_unix: int) -> dict[str, Any]:
    return {
        "sha": item.sha,
        "parents": list(item.parents),
        "committer_unix": item.committer_unix,
        "identity": item.identity,
        "raw_author": item.raw_author,
        "subject": item.subject,
        "bugfix_marker": item.bugfix_marker,
        "matched_markers": list(item.matched_markers),
        "text_changed_lines": item.text_changed_lines,
        "binary_partial": item.binary_partial,
        "is_root": item.is_root,
        "future_timestamp": item.committer_unix > evaluation_unix,
        "files": [
            {
                "path": file_edit.path,
                "old_path": file_edit.old_path,
                "added_lines": file_edit.added_lines,
                "deleted_lines": file_edit.deleted_lines,
                "binary": file_edit.binary,
            }
            for file_edit in item.files
        ],
    }


def _file_churn_row(item: FileChurn) -> dict[str, Any]:
    return {
        "path": item.path,
        "renamed_from": list(item.renamed_from),
        "changed_lines": item.changed_lines,
        "binary_unknown": item.binary_unknown,
        "latest_valid_committer_unix": item.latest_valid_committer_unix,
        "recency_seconds": item.recency_seconds,
        "component_id": item.component_id,
        "mapping_status": item.mapping_status,
        "commit_shas": list(item.commit_shas),
    }


def _component_churn_row(item: ComponentChurn) -> dict[str, Any]:
    return {
        "component_id": item.component_id,
        "changed_lines": item.changed_lines,
        "binary_unknown": item.binary_unknown,
        "mapping_status": item.mapping_status,
        "latest_valid_committer_unix": item.latest_valid_committer_unix,
        "recency_seconds": item.recency_seconds,
        "file_paths": list(item.file_paths),
    }


def _share_payload(share: MetricComputation) -> dict[str, Any]:
    value: str | None
    if share.value is None:
        value = None
    else:
        value = format(share.value, "f")
    return {
        "status": share.status.value,
        "numerator": share.numerator,
        "denominator": share.denominator,
        "serialized": share.serialized,
        "reason": share.reason,
        "value": value,
    }


def _concentration_row(item: ConcentrationRecord) -> dict[str, Any]:
    return {
        "scope": item.scope.value,
        "subject_id": item.subject_id,
        "status": item.status.value,
        "largest_share": _share_payload(item.largest_share),
        "contributors_to_50pct": item.contributors_to_50pct,
        "attributable_lines": item.attributable_lines,
        "unattributed_lines": item.unattributed_lines,
        "unknown_contribution_lines": item.unknown_contribution_lines,
        "mapping_status": item.mapping_status,
        "mapping_coverage": item.mapping_coverage,
        "complete_window": item.complete_window,
        "contributors": [
            {
                "identity": contrib.identity,
                "changed_lines": contrib.changed_lines,
                "bot_declared": contrib.bot_declared,
            }
            for contrib in item.contributors
        ],
        "notes": list(item.notes),
        "organizational_bus_factor": False,
        "productivity_claim": False,
    }


def _cochange_row(item: CochangeRecord) -> dict[str, Any]:
    return {
        "scope": item.scope,
        "left": item.left,
        "right": item.right,
        "support": item.support,
        "union": item.union,
        "jaccard": _share_payload(item.jaccard),
        "supported_relation": item.supported_relation,
        "commit_shas": list(item.commit_shas),
        "qualified_incomplete_window": item.qualified_incomplete_window,
        "architectural_dependency_claim": False,
    }


def _capability_row(item: GitCapabilityRecord) -> dict[str, Any]:
    return {
        "capability_id": item.capability_id,
        "profile_id": item.profile_id,
        "requested_window_days": item.requested_window_days,
        "requested_max_commits": item.requested_max_commits,
        "observed_commit_count": item.observed_commit_count,
        "observed_oldest_committer_unix": item.observed_oldest_committer_unix,
        "observed_newest_committer_unix": item.observed_newest_committer_unix,
        "evaluation_time_unix": item.evaluation_time_unix,
        "coverage": item.coverage.value,
        "unknown_reasons": list(item.unknown_reasons),
        "freshness": item.freshness.value,
        "freshness_reason": item.freshness_reason,
        "complete_window": item.complete_window,
    }


def _canonical_payload(
    *,
    bounds: HistoryWindowBounds,
    included: Sequence[IncludedCommit],
    file_churn: Sequence[FileChurn],
    component_churn: Sequence[ComponentChurn],
    concentrations: Sequence[ConcentrationRecord],
    cochange: Sequence[CochangeRecord],
    capabilities: Sequence[GitCapabilityRecord],
    limitations: Sequence[str],
    future: Sequence[str],
    merge_shas: Sequence[str],
    conflict_shas: Sequence[str],
    marker_shas: Sequence[str],
    mailmap_applied: bool,
    state_digest: str,
) -> dict[str, Any]:
    return {
        "schema_name": HISTORY_INDEX_SCHEMA,
        "schema_version": HISTORY_INDEX_SCHEMA_VERSION,
        "state_digest": state_digest,
        "bounds": {
            "profile_id": bounds.profile_id,
            "profile_version": bounds.profile_version,
            "evaluation_time_unix": bounds.evaluation_time_unix,
            "window_start_unix": bounds.window_start_unix,
            "requested_window_days": bounds.requested_window_days,
            "requested_max_commits": bounds.requested_max_commits,
            "observed_included_count": bounds.observed_included_count,
            "observed_oldest_committer_unix": bounds.observed_oldest_committer_unix,
            "observed_newest_committer_unix": bounds.observed_newest_committer_unix,
            "complete_window": bounds.complete_window,
            "first_parent_combined_with_skip_merges": (
                bounds.first_parent_combined_with_skip_merges
            ),
        },
        "included_shas": [item.sha for item in included],
        "file_churn": [_file_churn_row(item) for item in file_churn],
        "component_churn": [_component_churn_row(item) for item in component_churn],
        "concentrations": [_concentration_row(item) for item in concentrations],
        "cochange": [_cochange_row(item) for item in cochange],
        "capabilities": [_capability_row(item) for item in capabilities],
        "limitations": list(limitations),
        "future_shas": list(future),
        "merge_shas": list(merge_shas),
        "merge_conflict_only_shas": list(conflict_shas),
        "bugfix_marker_shas": list(marker_shas),
        "mailmap_applied": mailmap_applied,
        "proven_defects": False,
    }
