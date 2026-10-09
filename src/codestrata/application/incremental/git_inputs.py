"""E09.1 read-only Git input resolver, M27 change facts, and untrusted PR context."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from html import escape
from pathlib import Path
from typing import Any

from codestrata.application.incremental.errors import IncrementalPlanningError
from codestrata.application.incremental.git_patch import (
    ParsedPatch,
    PatchFileFact,
    parse_unified_patch,
    parsed_patch_canonical,
)
from codestrata.domain.contracts.enums import RevisionAgreement, SuppliedContextProvenance
from codestrata.domain.contracts.invocation import (
    InvocationError,
    SuppliedPrContext,
    parse_pr_context,
)
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.infrastructure.knowledge_store.git_revision import (
    LocalGitState,
    object_exists,
    observe_local_git_state,
)
from codestrata.repository_auth.read_only_git import ReadOnlyGitError, run_readonly_git

GIT_INPUT_SCHEMA = "codestrata.git-input-resolution.v1"
GIT_INPUT_SCHEMA_VERSION = "1.0.0"

_TEST_NAME_MARKERS = ("test_", "_test.", ".test.", ".spec.", "conftest.py")
_CONFIG_TEST_NAMES = frozenset(
    {
        "pytest.ini",
        "tox.ini",
        "phpunit.xml",
        "jest.config.js",
        "jest.config.ts",
        ".coveragerc",
        "vitest.config.ts",
        "vitest.config.js",
    }
)


class GitInputMode(StrEnum):
    WORKING = "working"
    STAGED = "staged"
    RANGE = "range"
    PATCH = "patch"


class ComparisonCompleteness(StrEnum):
    FULL = "full"
    PARTIAL_NO_BASE = "partial_no_base"
    PARTIAL_BINARY = "partial_binary"
    PARTIAL_SHALLOW = "partial_shallow"
    UNAVAILABLE = "unavailable"


class FileChangeStatus(StrEnum):
    ADDED = "added"
    DELETED = "deleted"
    MODIFIED = "modified"
    RENAMED = "renamed"
    SUBMODULE = "submodule"
    UNKNOWN = "unknown"


class FileContentClass(StrEnum):
    TEXT = "text"
    BINARY = "binary"
    GITLINK = "gitlink"
    UNKNOWN = "unknown"


class FileUnitClass(StrEnum):
    SOURCE = "source"
    TEST = "test"
    CONFIG_TEST = "config_test"
    OTHER = "other"


class BoundarySpreadStatus(StrEnum):
    OBSERVED = "observed"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class GitInputError(IncrementalPlanningError):
    """Git input cannot be resolved without mutation or hosted lookup."""


@dataclass(frozen=True, slots=True)
class GitInputRequest:
    repository_root: Path
    mode: GitInputMode
    base: str | None = None
    head: str | None = None
    patch_text: str | None = None
    supplied_context: SuppliedPrContext | Mapping[str, Any] | None = None
    component_map: Mapping[str, str] | None = None
    boundary_membership: Mapping[str, Sequence[str]] | None = None
    boundary_dimension: str | None = None


@dataclass(frozen=True, slots=True)
class ChangedFileFact:
    path: str
    old_path: str | None
    status: FileChangeStatus
    content_class: FileContentClass
    unit_class: FileUnitClass
    added_lines: int | None
    deleted_lines: int | None
    component_id: str | None
    binary: bool
    submodule: bool


@dataclass(frozen=True, slots=True)
class DiffHunkFact:
    path: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    added_lines: int
    deleted_lines: int
    header: str


@dataclass(frozen=True, slots=True)
class ChangeSummary:
    changed_file_ids: tuple[str, ...]
    changed_file_count: int
    changed_text_lines: int | None
    changed_component_ids: tuple[str, ...]
    changed_component_count: int
    unmapped_changed_file_count: int
    mapping_coverage: str | None
    test_touch: bool
    test_touch_paths: tuple[str, ...]
    boundary_dimension: str | None
    boundary_member_ids: tuple[str, ...]
    boundary_spread_count: int | None
    boundary_spread_status: BoundarySpreadStatus
    binary_partial: bool


@dataclass(frozen=True, slots=True)
class BoundSuppliedContext:
    record: SuppliedPrContext
    observed_agreement: RevisionAgreement
    observed_conflict_reason: str | None


@dataclass(frozen=True, slots=True)
class GitInputResolution:
    schema_name: str
    schema_version: str
    mode: GitInputMode
    local_state: LocalGitState
    resolved_base: str | None
    resolved_head: str | None
    patch_digest: str | None
    comparison_completeness: ComparisonCompleteness
    full_comparison: bool
    files: tuple[ChangedFileFact, ...]
    hunks: tuple[DiffHunkFact, ...]
    change_summary: ChangeSummary
    supplied_context: BoundSuppliedContext | None
    canonical_digest: str
    limitations: tuple[str, ...]
    escaped_projection: dict[str, Any]
    anonymous_telemetry: dict[str, Any]


def resolve_git_inputs(request: GitInputRequest) -> GitInputResolution:
    """Pin working, staged, range or patch identity without mutating the checkout."""

    root = request.repository_root.expanduser().resolve()
    state = observe_local_git_state(root)
    limitations = list(state.limitations)
    files: tuple[ChangedFileFact, ...] = ()
    hunks: tuple[DiffHunkFact, ...] = ()
    resolved_base = request.base
    resolved_head = request.head
    patch_digest: str | None = None
    completeness = ComparisonCompleteness.UNAVAILABLE
    full_comparison = False

    if request.mode is GitInputMode.WORKING:
        resolved_base = state.head_sha
        resolved_head = "WORKING_TREE"
        files, hunks, extra = _diff_files(root, ["diff", "HEAD", "--find-renames"], state)
        untracked, untracked_extra = _untracked_file_facts(
            root, {item.path for item in files}, state
        )
        files = tuple((*files, *untracked))
        limitations.extend(extra)
        limitations.extend(untracked_extra)
        completeness = _completeness(files, limitations, base_ok=state.head_sha is not None)
        full_comparison = completeness is ComparisonCompleteness.FULL
    elif request.mode is GitInputMode.STAGED:
        resolved_base = state.head_sha
        resolved_head = "INDEX"
        files, hunks, extra = _diff_files(root, ["diff", "--cached", "--find-renames"], state)
        limitations.extend(extra)
        completeness = _completeness(files, limitations, base_ok=state.head_sha is not None)
        full_comparison = completeness is ComparisonCompleteness.FULL
    elif request.mode is GitInputMode.RANGE:
        files, hunks, extra, resolved_base, resolved_head, completeness, full_comparison = (
            _resolve_range(root, request, state)
        )
        limitations.extend(extra)
    elif request.mode is GitInputMode.PATCH:
        packed = _resolve_patch(root, request, state)
        (
            files,
            hunks,
            extra,
            resolved_base,
            resolved_head,
            patch_digest,
            completeness,
            full_comparison,
        ) = packed
        limitations.extend(extra)
    else:
        raise GitInputError(f"unsupported Git input mode {request.mode}")

    observed_for_context_base = (
        resolved_base if resolved_base not in {None, "WORKING_TREE", "INDEX"} else state.head_sha
    )
    observed_for_context_head = (
        state.head_sha if resolved_head in {"WORKING_TREE", "INDEX", None} else resolved_head
    )
    bound = bind_supplied_context(
        request.supplied_context,
        observed_base=observed_for_context_base,
        observed_head=observed_for_context_head,
    )
    if bound is not None and bound.observed_agreement is RevisionAgreement.CONFLICT:
        limitations.append("supplied_context_revision_conflict")

    summary = summarize_change(
        files,
        component_map=request.component_map,
        boundary_membership=request.boundary_membership,
        boundary_dimension=request.boundary_dimension,
    )
    unique_limitations = tuple(dict.fromkeys(limitations))
    canonical = _canonical_payload(
        mode=request.mode,
        state=state,
        resolved_base=resolved_base,
        resolved_head=resolved_head,
        patch_digest=patch_digest,
        completeness=completeness,
        full_comparison=full_comparison,
        files=files,
        hunks=hunks,
        summary=summary,
        limitations=unique_limitations,
    )
    canonical_digest = digest_canonical(canonical)
    projection = escaped_projection(bound, summary, unique_limitations)
    telemetry = anonymous_telemetry_record(
        mode=request.mode,
        completeness=completeness,
        summary=summary,
        state=state,
        context=bound,
        canonical_digest=canonical_digest,
    )
    return GitInputResolution(
        schema_name=GIT_INPUT_SCHEMA,
        schema_version=GIT_INPUT_SCHEMA_VERSION,
        mode=request.mode,
        local_state=state,
        resolved_base=resolved_base,
        resolved_head=resolved_head,
        patch_digest=patch_digest,
        comparison_completeness=completeness,
        full_comparison=full_comparison,
        files=files,
        hunks=hunks,
        change_summary=summary,
        supplied_context=bound,
        canonical_digest=canonical_digest,
        limitations=unique_limitations,
        escaped_projection=projection,
        anonymous_telemetry=telemetry,
    )


def bind_supplied_context(
    supplied: SuppliedPrContext | Mapping[str, Any] | None,
    *,
    observed_base: str | None,
    observed_head: str | None,
) -> BoundSuppliedContext | None:
    """Accept E01.3 PR metadata only. Never looks up GitHub or tickets."""

    if supplied is None:
        return None
    if isinstance(supplied, SuppliedPrContext):
        record = supplied
    else:
        try:
            record = parse_pr_context(dict(supplied))
        except InvocationError as error:
            raise GitInputError(f"malformed supplied PR context: {error}") from error
    if record.enters_canonical_computation:
        raise GitInputError("supplied PR context cannot enter canonical computation")
    if record.provenance not in {
        SuppliedContextProvenance.LOCAL_CLI,
        SuppliedContextProvenance.LOCAL_FILE,
        SuppliedContextProvenance.LOCAL_FIXTURE,
    }:
        raise GitInputError("supplied PR context provenance must be local")

    reasons: list[str] = []
    if record.base and observed_base and not _sha_prefix_match(record.base, observed_base):
        reasons.append("supplied base disagrees with resolved base")
    if record.head and observed_head and not _sha_prefix_match(record.head, observed_head):
        reasons.append("supplied head disagrees with resolved head")
    if record.revision_agreement is RevisionAgreement.CONFLICT:
        if record.conflict_reason:
            reasons.append(record.conflict_reason)
        else:
            reasons.append("supplied context declared conflict")

    if reasons:
        agreement = RevisionAgreement.CONFLICT
        reason = "; ".join(dict.fromkeys(reasons))
    elif record.base or record.head:
        agreement = RevisionAgreement.AGREES
        reason = None
    else:
        agreement = RevisionAgreement.NOT_APPLICABLE
        reason = None
    return BoundSuppliedContext(
        record=record,
        observed_agreement=agreement,
        observed_conflict_reason=reason,
    )


def classify_unit(path: str) -> FileUnitClass:
    lowered = path.replace("\\", "/").lower()
    name = lowered.rsplit("/", 1)[-1]
    if name in _CONFIG_TEST_NAMES or name.endswith(".coveragerc"):
        return FileUnitClass.CONFIG_TEST
    if any(marker in f"/{lowered}" for marker in ("/tests/", "/test/", "/__tests__/")):
        return FileUnitClass.TEST
    if any(marker in name for marker in _TEST_NAME_MARKERS) or name.startswith("test_"):
        return FileUnitClass.TEST
    source_suffixes = (".py", ".ts", ".js", ".java", ".go", ".rs", ".cs")
    if lowered.endswith(source_suffixes):
        return FileUnitClass.SOURCE
    return FileUnitClass.OTHER


def summarize_change(
    files: Sequence[ChangedFileFact],
    *,
    component_map: Mapping[str, str] | None,
    boundary_membership: Mapping[str, Sequence[str]] | None,
    boundary_dimension: str | None,
) -> ChangeSummary:
    mapping = component_map or {}
    file_ids = tuple(item.path for item in files)
    components: list[str] = []
    unmapped = 0
    for item in files:
        mapped = mapping.get(item.path)
        if mapped is None and item.old_path:
            mapped = mapping.get(item.old_path)
        if mapped:
            components.append(mapped)
        else:
            unmapped += 1
    unique_components = tuple(sorted(set(components)))
    coverage = None if not files else f"{(len(files) - unmapped) / len(files):.6f}"

    text_lines = 0
    binary_partial = False
    text_known = True
    for item in files:
        if item.binary or item.added_lines is None or item.deleted_lines is None:
            binary_partial = binary_partial or item.binary
            if item.binary or item.added_lines is None:
                text_known = False
            continue
        text_lines += item.added_lines + item.deleted_lines

    test_paths = tuple(
        item.path
        for item in files
        if item.unit_class in {FileUnitClass.TEST, FileUnitClass.CONFIG_TEST}
    )

    if boundary_membership is None:
        spread_status = BoundarySpreadStatus.UNKNOWN
        members: tuple[str, ...] = ()
        spread_count: int | None = None
    else:
        found: list[str] = []
        for item in files:
            found.extend(str(member) for member in boundary_membership.get(item.path, ()))
            if item.old_path:
                found.extend(str(member) for member in boundary_membership.get(item.old_path, ()))
        members = tuple(sorted(set(found)))
        spread_status = BoundarySpreadStatus.OBSERVED
        spread_count = len(members)

    return ChangeSummary(
        changed_file_ids=file_ids,
        changed_file_count=len(file_ids),
        changed_text_lines=text_lines if text_known else None,
        changed_component_ids=unique_components,
        changed_component_count=len(unique_components),
        unmapped_changed_file_count=unmapped,
        mapping_coverage=coverage,
        test_touch=bool(test_paths),
        test_touch_paths=test_paths,
        boundary_dimension=boundary_dimension,
        boundary_member_ids=members,
        boundary_spread_count=spread_count,
        boundary_spread_status=spread_status,
        binary_partial=binary_partial,
    )


def escaped_projection(
    bound: BoundSuppliedContext | None,
    summary: ChangeSummary,
    limitations: Sequence[str],
) -> dict[str, Any]:
    """HTML-escaped projection. Raw PR text is never used as markup."""

    context: dict[str, Any] | None = None
    if bound is not None:
        record = bound.record
        context = {
            "title": escape(record.title or "", quote=True),
            "description": escape(record.description or "", quote=True),
            "labels": [escape(item, quote=True) for item in record.labels],
            "linked_references": [escape(item, quote=True) for item in record.linked_references],
            "base": escape(record.base or "", quote=True),
            "head": escape(record.head or "", quote=True),
            "context_digest": record.context_digest,
            "observed_agreement": bound.observed_agreement.value,
            "observed_conflict_reason": escape(bound.observed_conflict_reason or "", quote=True),
            "narrative_only": record.narrative_only,
        }
    return {
        "changed_file_count": summary.changed_file_count,
        "test_touch": summary.test_touch,
        "limitations": [escape(item, quote=True) for item in limitations],
        "supplied_context": context,
    }


def anonymous_telemetry_record(
    *,
    mode: GitInputMode,
    completeness: ComparisonCompleteness,
    summary: ChangeSummary,
    state: LocalGitState,
    context: BoundSuppliedContext | None,
    canonical_digest: str,
) -> dict[str, Any]:
    """Counts and digests only. Raw PR metadata and patch text are excluded."""

    return {
        "schema_name": GIT_INPUT_SCHEMA,
        "mode": mode.value,
        "comparison_completeness": completeness.value,
        "changed_file_count": summary.changed_file_count,
        "changed_text_lines_known": summary.changed_text_lines is not None,
        "changed_component_count": summary.changed_component_count,
        "unmapped_changed_file_count": summary.unmapped_changed_file_count,
        "mapping_coverage": summary.mapping_coverage,
        "test_touch": summary.test_touch,
        "binary_partial": summary.binary_partial,
        "boundary_spread_status": summary.boundary_spread_status.value,
        "boundary_spread_count": summary.boundary_spread_count,
        "shallow": state.shallow,
        "dirty": state.dirty,
        "state_digest": state.state_digest,
        "canonical_digest": canonical_digest,
        "supplied_context_present": context is not None,
        "supplied_context_digest": context.record.context_digest if context else None,
        "observed_agreement": (
            context.observed_agreement.value
            if context
            else RevisionAgreement.NOT_APPLICABLE.value
        ),
    }


def _resolve_range(
    root: Path,
    request: GitInputRequest,
    state: LocalGitState,
) -> tuple[
    tuple[ChangedFileFact, ...],
    tuple[DiffHunkFact, ...],
    list[str],
    str | None,
    str | None,
    ComparisonCompleteness,
    bool,
]:
    extra: list[str] = []
    base = request.base
    head = request.head or state.head_sha
    if not base or not head:
        extra.append("range_requires_base_and_head")
        return ((), (), extra, base, head, ComparisonCompleteness.UNAVAILABLE, False)
    if not object_exists(root, base):
        extra.append("missing_base")
        return ((), (), extra, base, head, ComparisonCompleteness.PARTIAL_NO_BASE, False)
    if not object_exists(root, head):
        extra.append("missing_head")
        extra.append("no_silent_fetch")
        return ((), (), extra, base, head, ComparisonCompleteness.UNAVAILABLE, False)
    files, hunks, diff_extra = _diff_files(root, ["diff", "--find-renames", base, head], state)
    extra.extend(diff_extra)
    completeness = _completeness(files, extra, base_ok=True)
    full = completeness is ComparisonCompleteness.FULL
    return files, hunks, extra, base, head, completeness, full


def _resolve_patch(
    root: Path,
    request: GitInputRequest,
    state: LocalGitState,
) -> tuple[
    tuple[ChangedFileFact, ...],
    tuple[DiffHunkFact, ...],
    list[str],
    str | None,
    str | None,
    str | None,
    ComparisonCompleteness,
    bool,
]:
    extra: list[str] = []
    if request.patch_text is None:
        extra.append("missing_patch")
        return (
            (),
            (),
            extra,
            request.base,
            request.head or state.head_sha,
            None,
            ComparisonCompleteness.UNAVAILABLE,
            False,
        )
    parsed = parse_unified_patch(request.patch_text)
    extra.extend(parsed.limitations)
    if parsed.malformed:
        extra.append("malformed_patch")
    base_ok = True
    unresolved = sum(1 for oid in parsed.claimed_old_oids if not object_exists(root, oid))
    if request.base and not object_exists(root, request.base):
        extra.append("missing_base")
        base_ok = False
    if unresolved:
        extra.append("unresolvable_patch_base")
        base_ok = False
    files = tuple(_file_from_patch(item, state) for item in parsed.files)
    hunks = tuple(
        DiffHunkFact(
            path=hunk.path,
            old_start=hunk.old_start,
            old_count=hunk.old_count,
            new_start=hunk.new_start,
            new_count=hunk.new_count,
            added_lines=hunk.added_lines,
            deleted_lines=hunk.deleted_lines,
            header=hunk.header,
        )
        for item in parsed.files
        for hunk in item.hunks
    )
    if not base_ok:
        completeness = ComparisonCompleteness.PARTIAL_NO_BASE
        full = False
        extra.append("no_fabricated_full_comparison")
    else:
        completeness = _completeness(files, extra, base_ok=True)
        full = completeness is ComparisonCompleteness.FULL
    return (
        files,
        hunks,
        extra,
        request.base,
        request.head or state.head_sha,
        parsed.patch_digest,
        completeness,
        full,
    )


def _file_from_patch(item: PatchFileFact, state: LocalGitState) -> ChangedFileFact:
    submodule = item.path in state.submodule_paths
    status = {
        "added": FileChangeStatus.ADDED,
        "deleted": FileChangeStatus.DELETED,
        "renamed": FileChangeStatus.RENAMED,
        "modified": FileChangeStatus.MODIFIED,
    }.get(item.status, FileChangeStatus.UNKNOWN)
    if submodule:
        status = FileChangeStatus.SUBMODULE
    content = FileContentClass.BINARY if item.binary else FileContentClass.TEXT
    if submodule:
        content = FileContentClass.GITLINK
    return ChangedFileFact(
        path=item.path,
        old_path=item.old_path,
        status=status,
        content_class=content,
        unit_class=classify_unit(item.path),
        added_lines=item.added_lines,
        deleted_lines=item.deleted_lines,
        component_id=None,
        binary=item.binary,
        submodule=submodule,
    )


def _diff_files(
    root: Path,
    diff_args: list[str],
    state: LocalGitState,
) -> tuple[tuple[ChangedFileFact, ...], tuple[DiffHunkFact, ...], list[str]]:
    extra: list[str] = []
    try:
        name_status = run_readonly_git([*diff_args, "--name-status", "-z"], cwd=root)
        numstat = run_readonly_git([*diff_args, "--numstat"], cwd=root)
        unified = run_readonly_git([*diff_args, "-U0", "--no-color"], cwd=root)
    except ReadOnlyGitError as error:
        extra.append("diff_unavailable")
        extra.append(str(error.verb or "diff"))
        return (), (), extra

    statuses = _parse_name_status_z(name_status)
    stats = _parse_numstat(numstat)
    parsed = parse_unified_patch(unified)
    extra.extend(code for code in parsed.limitations if code == "binary_partial_size")
    files: list[ChangedFileFact] = []
    for path, old_path, status_code in statuses:
        added, deleted, binary = stats.get(path, stats.get(old_path or path, (0, 0, False)))
        submodule = path in state.submodule_paths or (
            old_path in state.submodule_paths if old_path else False
        )
        status = _status_from_code(status_code, submodule)
        if submodule:
            content = FileContentClass.GITLINK
        elif binary:
            content = FileContentClass.BINARY
        else:
            content = FileContentClass.TEXT
        files.append(
            ChangedFileFact(
                path=path,
                old_path=old_path,
                status=status,
                content_class=content,
                unit_class=classify_unit(path),
                added_lines=None if binary else added,
                deleted_lines=None if binary else deleted,
                component_id=None,
                binary=binary,
                submodule=submodule,
            )
        )
    hunks = tuple(
        DiffHunkFact(
            path=hunk.path,
            old_start=hunk.old_start,
            old_count=hunk.old_count,
            new_start=hunk.new_start,
            new_count=hunk.new_count,
            added_lines=hunk.added_lines,
            deleted_lines=hunk.deleted_lines,
            header=hunk.header,
        )
        for item in parsed.files
        for hunk in item.hunks
    )
    return tuple(files), hunks, extra


def _untracked_file_facts(
    root: Path,
    already: set[str],
    state: LocalGitState,
) -> tuple[tuple[ChangedFileFact, ...], list[str]]:
    extra: list[str] = []
    try:
        porcelain = run_readonly_git(["status", "--porcelain=v1", "-z"], cwd=root)
    except ReadOnlyGitError:
        extra.append("untracked_unavailable")
        return (), extra
    facts: list[ChangedFileFact] = []
    parts = [item for item in porcelain.split("\0") if item]
    for record in parts:
        if not record.startswith("?? "):
            continue
        relative = record[3:].replace("\\", "/")
        if relative in already:
            continue
        path = root / relative
        binary = False
        added: int | None = 0
        try:
            data = path.read_bytes()
        except OSError:
            extra.append("untracked_unreadable")
            continue
        if b"\0" in data:
            binary = True
            added = None
        else:
            added = len(data.decode("utf-8", errors="replace").splitlines())
        facts.append(
            ChangedFileFact(
                path=relative,
                old_path=None,
                status=FileChangeStatus.ADDED,
                content_class=FileContentClass.BINARY if binary else FileContentClass.TEXT,
                unit_class=classify_unit(relative),
                added_lines=added,
                deleted_lines=0 if not binary else None,
                component_id=None,
                binary=binary,
                submodule=relative in state.submodule_paths,
            )
        )
    return tuple(facts), extra


def _parse_name_status_z(payload: str) -> list[tuple[str, str | None, str]]:
    records: list[tuple[str, str | None, str]] = []
    parts = [item for item in payload.split("\0") if item]
    index = 0
    while index < len(parts):
        code = parts[index]
        status = code[0] if code else "M"
        if status in {"R", "C"} and index + 2 < len(parts):
            records.append((parts[index + 2], parts[index + 1], status))
            index += 3
            continue
        if index + 1 < len(parts):
            records.append((parts[index + 1], None, status))
            index += 2
            continue
        index += 1
    return records


def _parse_numstat(payload: str) -> dict[str, tuple[int | None, int | None, bool]]:
    stats: dict[str, tuple[int | None, int | None, bool]] = {}
    for line in payload.splitlines():
        if not line.strip():
            continue
        pieces = line.split("\t")
        if len(pieces) < 3:
            continue
        added_raw, deleted_raw, path = pieces[0], pieces[1], pieces[-1]
        if " => " in path:
            path = path.split(" => ", 1)[1].strip("{}")
        binary = added_raw == "-" or deleted_raw == "-"
        added = None if binary else int(added_raw)
        deleted = None if binary else int(deleted_raw)
        stats[path] = (added, deleted, binary)
    return stats


def _status_from_code(code: str, submodule: bool) -> FileChangeStatus:
    if submodule:
        return FileChangeStatus.SUBMODULE
    mapping = {
        "A": FileChangeStatus.ADDED,
        "D": FileChangeStatus.DELETED,
        "M": FileChangeStatus.MODIFIED,
        "R": FileChangeStatus.RENAMED,
        "C": FileChangeStatus.RENAMED,
        "T": FileChangeStatus.MODIFIED,
    }
    return mapping.get(code, FileChangeStatus.UNKNOWN)


def _completeness(
    files: Sequence[ChangedFileFact],
    limitations: Sequence[str],
    *,
    base_ok: bool,
) -> ComparisonCompleteness:
    if not base_ok or "missing_base" in limitations or "unresolvable_patch_base" in limitations:
        return ComparisonCompleteness.PARTIAL_NO_BASE
    if any(item.binary for item in files):
        return ComparisonCompleteness.PARTIAL_BINARY
    if "shallow_history" in limitations:
        return ComparisonCompleteness.PARTIAL_SHALLOW
    if "diff_unavailable" in limitations or "not_a_git_repository" in limitations:
        return ComparisonCompleteness.UNAVAILABLE
    return ComparisonCompleteness.FULL


def _canonical_payload(
    *,
    mode: GitInputMode,
    state: LocalGitState,
    resolved_base: str | None,
    resolved_head: str | None,
    patch_digest: str | None,
    completeness: ComparisonCompleteness,
    full_comparison: bool,
    files: Sequence[ChangedFileFact],
    hunks: Sequence[DiffHunkFact],
    summary: ChangeSummary,
    limitations: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_name": GIT_INPUT_SCHEMA,
        "schema_version": GIT_INPUT_SCHEMA_VERSION,
        "mode": mode.value,
        "state_digest": state.state_digest,
        "head_sha": state.head_sha,
        "tree_oid": state.tree_oid,
        "index_digest": state.index_digest,
        "working_tree_digest": state.working_tree_digest,
        "resolved_base": resolved_base,
        "resolved_head": resolved_head,
        "patch_digest": patch_digest,
        "comparison_completeness": completeness.value,
        "full_comparison": full_comparison,
        "files": [
            {
                "path": item.path,
                "old_path": item.old_path,
                "status": item.status.value,
                "content_class": item.content_class.value,
                "unit_class": item.unit_class.value,
                "added_lines": item.added_lines,
                "deleted_lines": item.deleted_lines,
                "binary": item.binary,
                "submodule": item.submodule,
            }
            for item in files
        ],
        "hunks": [
            {
                "path": item.path,
                "old_start": item.old_start,
                "old_count": item.old_count,
                "new_start": item.new_start,
                "new_count": item.new_count,
                "added_lines": item.added_lines,
                "deleted_lines": item.deleted_lines,
                "header": item.header,
            }
            for item in hunks
        ],
        "change_summary": {
            "changed_file_ids": list(summary.changed_file_ids),
            "changed_file_count": summary.changed_file_count,
            "changed_text_lines": summary.changed_text_lines,
            "changed_component_ids": list(summary.changed_component_ids),
            "changed_component_count": summary.changed_component_count,
            "unmapped_changed_file_count": summary.unmapped_changed_file_count,
            "mapping_coverage": summary.mapping_coverage,
            "test_touch": summary.test_touch,
            "boundary_dimension": summary.boundary_dimension,
            "boundary_member_ids": list(summary.boundary_member_ids),
            "boundary_spread_count": summary.boundary_spread_count,
            "boundary_spread_status": summary.boundary_spread_status.value,
        },
        "limitations": list(limitations),
    }


def _sha_prefix_match(left: str, right: str) -> bool:
    first = left.strip().lower()
    second = right.strip().lower()
    if not first or not second:
        return False
    prefix_len = min(len(first), len(second))
    return prefix_len >= 7 and first[:prefix_len] == second[:prefix_len]


def parsed_patch_identity(parsed: ParsedPatch) -> str:
    return parsed_patch_canonical(parsed)
