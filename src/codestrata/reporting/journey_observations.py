"""Observe a repository the Engine already has on disk.

Copies git, feed, ownership, test-association, and impact facts into canonical
records. Does not rank in HTML, invent a trend, or treat a missing input as zero.
"""

from __future__ import annotations

import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.evidence.maintainability.capability import HISTORY_PROFILE_V1
from codestrata.application.evidence.maintainability.derive import collect_hotspots
from codestrata.application.evidence.maintainability.models import (
    ComponentSpec,
    FileChurnRecord,
    HistoryWindow,
)
from codestrata.application.evidence.maintainability.models import (
    CoverageScope as HistoryCoverage,
)
from codestrata.application.evidence.quality.complexity import collect_functions_and_sizes
from codestrata.application.evidence.quality.maps import (
    CLONE_FORMULA_VERSION,
    CLONE_MIN_LINES,
    CLONE_MIN_TOKENS,
    TOKEN_NORMALIZATION_VERSION,
    QualityBudgets,
)
from codestrata.application.evidence.quality.models import (
    CloneMetric,
    MetricStatusName,
    QualityEvidence,
)
from codestrata.application.evidence.quality.models import (
    CoverageScope as QualityCoverage,
)
from codestrata.application.evidence.supply_chain.feed import FeedError, load_osv_snapshot
from codestrata.application.evidence.supply_chain.service import SupplyChainEvidenceService
from codestrata.application.evidence.testing.association import collect_association_metric
from codestrata.application.evidence.testing.declarations import collect_test_declarations
from codestrata.application.evidence.testing.paths import eligible_production, is_test_like
from codestrata.application.incremental.history_index import COCHANGE_SUPPORT_THRESHOLD
from codestrata.domain.contracts.enums import (
    CoverageState,
    FreshnessState,
    MetricStatus,
    OwnershipScope,
    ResultStatus,
)
from codestrata.domain.contracts.envelope import CapabilityCoverage, CapabilityFreshness
from codestrata.domain.contracts.formulas import m22_hotspot_value, m25_ownership, m26_jaccard
from codestrata.domain.contracts.hotspot import (
    ChangeSummary,
    EngineeringHotspot,
    OwnershipConcentration,
    ownership_ratio,
)
from codestrata.scan_boundary import DEFAULT_EXCLUDED_DIRECTORY_NAMES

# Fixture-only pinned clock for E11.3 journey examples. Production assess
# must pass a real evaluation_time into observe_repository().
JOURNEY_EVALUATION_TIME = datetime(2026, 9, 27, tzinfo=UTC)
FEED_RELATIVE = "codestrata/osv-snapshot.json"
IMPACT_NODE_BUDGET = 1
# Most-changed eligible files considered for M26 pairing. Bounds the pair set
# to at most C(200, 2) rows regardless of repository size; the cut is recorded
# as the ``cochange_file_budget`` limitation instead of being silent.
COCHANGE_FILE_BUDGET = 200
_SKIP_DIRS = frozenset(
    DEFAULT_EXCLUDED_DIRECTORY_NAMES
    | {
        ".git",
        ".codestrata",
        ".codestrata-artifacts",
        "node_modules",
        "bin",
        "obj",
        "dist",
        "build",
        ".next",
        "out",
    }
)
_UNKNOWN_AUTHORS = {"unknown", "unmapped", ""}


@dataclass(frozen=True, slots=True)
class JourneyObservation:
    """Facts read from the repository. Ranking values come from M22 only."""

    hotspots: tuple[EngineeringHotspot, ...]
    ownership: tuple[OwnershipConcentration, ...]
    cochange: tuple[dict[str, object], ...]
    change_summary: ChangeSummary | None
    coverage: tuple[CapabilityCoverage, ...]
    freshness: tuple[CapabilityFreshness, ...]
    limitations: tuple[str, ...]
    metrics: dict[str, dict[str, object]]
    coverage_status: str
    feed_digest: str


def observe_repository(
    root: Path,
    *,
    evaluation_time: datetime | None = None,
    head: str | None = None,
) -> JourneyObservation:
    """Read one local repository. No network and no dependency install.

    Production callers must pass ``evaluation_time``. The default is the
    current UTC time, not the fixture-only ``JOURNEY_EVALUATION_TIME``.
    """

    if evaluation_time is not None and evaluation_time.tzinfo is None:
        raise ValueError("evaluation_time must be timezone-aware")
    pinned = datetime.now(UTC) if evaluation_time is None else evaluation_time.astimezone(UTC)
    repository = root.resolve()
    texts = _read_texts(repository)
    paths = tuple(sorted(texts))
    git_state, resolved_head, history, authors, unknown_lines, commits = _read_git(
        repository,
        evaluation_time=pinned,
        head=head,
    )
    feed = _read_feed(repository, paths, texts, evaluation_time=pinned)
    hotspots = _hotspots(repository.name, texts, paths, history)
    ownership = _ownership(repository.name, git_state, authors, unknown_lines, resolved_head)
    cochange, cochange_truncated = _cochange(git_state, commits)
    tests = _tests(paths, texts)
    change = _change_summary(git_state, history, tests)
    limitations = _limitations(git_state, feed, tests, change, cochange_truncated)
    coverage, freshness = _capability_rows(
        git_state,
        resolved_head,
        history,
        hotspots,
        feed,
        evaluation_time=pinned,
    )
    metrics = _metrics(hotspots)
    status = "pass" if git_state == "complete" and feed.family_error is None else "unknown"
    return JourneyObservation(
        hotspots=hotspots,
        ownership=ownership,
        cochange=cochange,
        change_summary=change,
        coverage=coverage,
        freshness=freshness,
        limitations=limitations,
        metrics=metrics,
        coverage_status=status,
        feed_digest=feed.digest,
    )


@dataclass(frozen=True, slots=True)
class _FeedView:
    reason: str
    state: str
    provider: str | None
    digest: str
    published_at: str | None
    family_error: str | None
    match_count: int | None
    matching_reason: str
    cannot_prove_clean: bool


@dataclass(frozen=True, slots=True)
class _TestView:
    missing: bool
    count: int | None
    test_ids: tuple[str, ...]


def _read_texts(root: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    if not root.is_dir():
        return texts
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.stat().st_size > 1_048_576:
            continue
        relative = path.relative_to(root).as_posix()
        try:
            texts[relative] = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
    return texts


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _read_git(
    root: Path,
    *,
    evaluation_time: datetime,
    head: str | None = None,
) -> tuple[
    str,
    str | None,
    HistoryWindow | None,
    dict[str, int],
    bool,
    list[set[str]],
]:
    probe = _git(root, "rev-parse", "--is-inside-work-tree")
    if probe is None or probe.returncode != 0 or probe.stdout.strip() != "true":
        reason = "git_command_unavailable" if probe is None else "missing_git_history"
        return reason if probe is None else "missing", None, None, {}, False, []
    # ``root`` may be a directory nested inside a larger checkout. Git reports
    # history for the whole work tree unless the log is restricted to ``root``
    # and numstat paths are relative to the top level, so record the prefix
    # and scope every history read to the observed directory.
    prefix_probe = _git(root, "rev-parse", "--show-prefix")
    prefix = "" if prefix_probe is None else prefix_probe.stdout.strip().replace("\\", "/")
    toplevel_probe = _git(root, "rev-parse", "--show-toplevel")
    toplevel = (
        root
        if toplevel_probe is None or toplevel_probe.returncode != 0
        else Path(toplevel_probe.stdout.strip())
    )
    shallow_marker = toplevel / ".git" / "shallow"
    shallow_probe = _git(root, "rev-parse", "--is-shallow-repository")
    shallow = (shallow_marker.is_file() and shallow_marker.stat().st_size > 0) or (
        shallow_probe is not None and shallow_probe.stdout.strip() == "true"
    )
    head_probe = _git(root, "rev-parse", "HEAD")
    observed_head = (
        None if head_probe is None or head_probe.returncode != 0 else head_probe.stdout.strip()
    )
    resolved_head = head or observed_head
    log_args = ["log"]
    if resolved_head:
        log_args.append(resolved_head)
    log_args.extend(
        [
            "--numstat",
            "--pretty=format:COMMIT%x09%H%x09%aN%x09%aE",
            "--",
            ".",
        ]
    )
    log = _git(root, *log_args)
    if log is None or log.returncode != 0 or resolved_head is None:
        return "missing", resolved_head, None, {}, False, []
    churn, authors, unknown_lines, commits = _parse_log(log.stdout, prefix=prefix)
    state = "shallow" if shallow else "complete"
    coverage = HistoryCoverage.PARTIAL if shallow else HistoryCoverage.COMPLETE
    reason = "shallow_git_history" if shallow else "pinned_git_history"
    history = HistoryWindow(
        profile_id=HISTORY_PROFILE_V1,
        window="all_observed_local_commits",
        head_sha=resolved_head,
        coverage=coverage,
        coverage_reason=reason,
        evaluation_time_unix=int(evaluation_time.timestamp()),
        included_commit_count=len(commits),
        file_churn=tuple(
            FileChurnRecord(path=path, changed_lines=lines, coverage_reason=reason)
            for path, lines in sorted(churn.items())
        ),
    )
    return state, resolved_head, history, authors, unknown_lines, commits


def _parse_log(
    text: str,
    *,
    prefix: str = "",
) -> tuple[dict[str, int | None], dict[str, int], bool, list[set[str]]]:
    """Parse ``git log --numstat`` output.

    ``prefix`` is the observed directory relative to the work-tree top level
    (``git rev-parse --show-prefix``). Numstat paths are reported relative to
    the top level, so the prefix is stripped to match ``_read_texts`` keys and
    paths outside the observed directory are ignored.
    """

    churn: dict[str, int | None] = {}
    authors: dict[str, int] = defaultdict(int)
    unknown_lines = False
    commits: list[set[str]] = []
    current_files: set[str] = set()
    author = ""
    for raw in text.splitlines():
        if raw.startswith("COMMIT\t"):
            if current_files:
                commits.append(current_files)
            current_files = set()
            parts = raw.split("\t")
            name = parts[2].strip() if len(parts) > 2 else ""
            email = parts[3].strip() if len(parts) > 3 else ""
            author = f"{name} <{email}>"
            if name.casefold() in _UNKNOWN_AUTHORS or email.casefold().startswith("unknown"):
                author = ""
            continue
        columns = raw.split("\t")
        if len(columns) != 3:
            continue
        added, deleted, path = columns
        path = path.replace("\\", "/")
        if prefix:
            if not path.startswith(prefix):
                continue
            path = path[len(prefix) :]
        current_files.add(path)
        if added == "-" or deleted == "-":
            churn[path] = None
            unknown_lines = True
            continue
        try:
            lines = int(added) + int(deleted)
        except ValueError:
            churn[path] = None
            unknown_lines = True
            continue
        previous = churn.get(path)
        if previous is None and path in churn:
            continue
        churn[path] = (0 if previous is None else previous) + lines
        if author:
            authors[author] += lines
        else:
            unknown_lines = True
    if current_files:
        commits.append(current_files)
    return churn, dict(authors), unknown_lines, commits


def _read_feed(
    root: Path,
    paths: tuple[str, ...],
    texts: dict[str, str],
    *,
    evaluation_time: datetime,
) -> _FeedView:
    snapshot_path = root / FEED_RELATIVE
    try:
        evidence, _envelope = SupplyChainEvidenceService().collect(
            repository_id=root.name,
            relative_paths=paths,
            file_texts=texts,
            evaluation_time=evaluation_time,
            snapshot_path=snapshot_path,
        )
    except FeedError as error:
        return _FeedView(
            reason="feed_unreadable",
            state="error",
            provider=None,
            digest="",
            published_at=None,
            family_error=str(error),
            match_count=None,
            matching_reason="feed_unreadable",
            cannot_prove_clean=True,
        )
    freshness = evidence.freshness
    matching = evidence.matching
    loaded = load_osv_snapshot(snapshot_path if snapshot_path.is_file() else None)
    return _FeedView(
        reason=freshness.reason,
        state=freshness.status.value,
        provider=freshness.provider_id,
        digest=freshness.snapshot_digest or ("" if loaded is None else loaded.digest),
        published_at=freshness.published_at,
        family_error=None,
        match_count=matching.match_count,
        matching_reason=matching.reason,
        cannot_prove_clean=matching.cannot_prove_clean or freshness.cannot_prove_clean,
    )


def _hotspots(
    name: str,
    texts: dict[str, str],
    paths: tuple[str, ...],
    history: HistoryWindow | None,
) -> tuple[EngineeringHotspot, ...]:
    budgets = QualityBudgets()
    functions, files, distribution, limitations, _cutoff = collect_functions_and_sizes(
        relative_paths=paths,
        file_texts=texts,
        budgets=budgets,
    )
    quality = QualityEvidence(
        repository_id=name,
        functions=functions,
        files=files,
        distribution=distribution,
        clone=CloneMetric(
            status=MetricStatusName.UNKNOWN,
            numerator=None,
            denominator=None,
            serialized=None,
            full_scope_status=QualityCoverage.UNKNOWN,
            reason="clone_scan_not_part_of_journey_rank",
            normalization_version=TOKEN_NORMALIZATION_VERSION,
            formula_version=CLONE_FORMULA_VERSION,
            min_tokens=CLONE_MIN_TOKENS,
            min_lines=CLONE_MIN_LINES,
        ),
        executed_repository_code=False,
        live_lookup=False,
        limitations=tuple(limitations),
    )
    components = tuple(
        ComponentSpec(component_id=path, file_paths=(path,))
        for path in paths
        if eligible_production(path)
    )
    complete, partial, _digest, _rejected, _ids = collect_hotspots(
        quality=quality,
        history=history,
        components=components,
    )
    return complete + partial


def _ownership(
    name: str,
    git_state: str,
    authors: dict[str, int],
    unknown_lines: bool,
    head: str | None,
) -> tuple[OwnershipConcentration, ...]:
    profile = head or "missing"
    if git_state != "complete" or unknown_lines or not authors:
        reason = {
            "missing": "Ownership mapping was not attached to this analysis result.",
            "shallow": "shallow_git_history",
            "git_command_unavailable": "git_command_unavailable",
        }.get(git_state, "unknown_ownership_mapping")
        if git_state == "complete" and (unknown_lines or not authors):
            reason = "unknown_ownership_mapping"
        return (
            OwnershipConcentration(
                record_id=f"m25:{name}:repository",
                scope=OwnershipScope.REPOSITORY,
                subject_id=name,
                numerator=None,
                denominator=None,
                serialized_ratio=None,
                history_profile_id=profile,
                evidence_ids=("m25.repository",),
                status=ResultStatus.UNKNOWN,
                notes=reason,
            ),
        )
    share = m25_ownership(authors)
    if share.status is MetricStatus.NOT_APPLICABLE:
        return (
            OwnershipConcentration(
                record_id=f"m25:{name}:repository",
                scope=OwnershipScope.REPOSITORY,
                subject_id=name,
                numerator=None,
                denominator=0,
                serialized_ratio=None,
                history_profile_id=profile,
                evidence_ids=("m25.repository",),
                status=ResultStatus.NOT_APPLICABLE,
                notes=share.reason or "zero_attributable_churn",
            ),
        )
    numerator = int(share.numerator or 0)
    denominator = int(share.denominator or 0)
    return (
        OwnershipConcentration(
            record_id=f"m25:{name}:repository",
            scope=OwnershipScope.REPOSITORY,
            subject_id=name,
            numerator=numerator,
            denominator=denominator,
            serialized_ratio=share.serialized or ownership_ratio(numerator, denominator),
            history_profile_id=profile,
            evidence_ids=("m25.repository",),
            status=ResultStatus.PASS,
            notes="largest_contributor_share",
        ),
    )


def _cochange(
    git_state: str,
    commits: list[set[str]],
) -> tuple[tuple[dict[str, object], ...], bool]:
    """Return co-change rows and whether the file budget cut the pair set."""

    if git_state != "complete":
        reason = {
            "shallow": "shallow_git_history",
            "git_command_unavailable": "git_command_unavailable",
        }.get(git_state, "missing_git_history")
        return (
            (
                {
                    "scope": "repository",
                    "left": "unavailable",
                    "right": "unavailable",
                    "support": None,
                    "union": None,
                    "jaccard": None,
                    "supported_relation": None,
                    "qualified_incomplete_window": True,
                    "unavailable_reason": reason,
                },
            ),
            False,
        )
    # Incidence (file -> commit indexes) is built in one pass. Pairs are then
    # generated per commit, so work is bounded by the commits that actually
    # co-change files instead of every file pair times every commit.
    incidence: dict[str, set[int]] = defaultdict(set)
    for index, commit in enumerate(commits):
        for path in commit:
            if eligible_production(path) and not path.startswith("codestrata/"):
                incidence[path].add(index)
    files = sorted(incidence)
    if len(files) < 2:
        return (
            (
                {
                    "scope": "repository",
                    "left": files[0] if files else "unavailable",
                    "right": "unavailable",
                    "support": None,
                    "union": None,
                    "jaccard": None,
                    "supported_relation": None,
                    "qualified_incomplete_window": False,
                    "unavailable_reason": "single_file_window",
                },
            ),
            False,
        )
    truncated = len(files) > COCHANGE_FILE_BUDGET
    # Most-changed files first; ties by path so the budget cut is deterministic.
    budgeted = set(
        sorted(files, key=lambda path: (-len(incidence[path]), path))[:COCHANGE_FILE_BUDGET]
    )
    support_by_pair: dict[tuple[str, str], int] = defaultdict(int)
    for commit in commits:
        members = sorted(path for path in commit if path in budgeted)
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                support_by_pair[(left, right)] += 1
    rows: list[dict[str, object]] = []
    for left, right in sorted(support_by_pair):
        support = support_by_pair[(left, right)]
        union = len(incidence[left] | incidence[right])
        jaccard = None
        computed = m26_jaccard(support, union)
        if computed.status is MetricStatus.VALUE:
            jaccard = computed.serialized
        rows.append(
            {
                "scope": "repository",
                "left": left,
                "right": right,
                "support": support,
                "union": union,
                "jaccard": jaccard,
                "supported_relation": support >= COCHANGE_SUPPORT_THRESHOLD,
                "qualified_incomplete_window": False,
                "unavailable_reason": None,
            }
        )
    if not rows:
        return (
            (
                {
                    "scope": "repository",
                    "left": "unavailable",
                    "right": "unavailable",
                    "support": 0,
                    "union": None,
                    "jaccard": None,
                    "supported_relation": False,
                    "qualified_incomplete_window": False,
                    "unavailable_reason": "no_cochanged_pair",
                },
            ),
            truncated,
        )
    return tuple(rows), truncated


def _tests(paths: tuple[str, ...], texts: dict[str, str]) -> _TestView:
    test_paths = [path for path in paths if is_test_like(path)]
    if not test_paths:
        return _TestView(missing=True, count=None, test_ids=())
    notes: list[str] = []
    declarations = collect_test_declarations(
        relative_paths=paths,
        file_texts=texts,
        notes=notes,
        max_file_bytes=1_048_576,
    )
    metric = collect_association_metric(
        relative_paths=paths,
        file_texts=texts,
        tests=declarations,
        notes=notes,
    )
    if metric.status.value != "value" or metric.full_scope_status.value != "complete":
        return _TestView(missing=True, count=None, test_ids=())
    ids = tuple(sorted({item.test_id or item.test_path for item in metric.associations}))
    return _TestView(missing=False, count=metric.associated, test_ids=ids)


def _change_summary(
    git_state: str,
    history: HistoryWindow | None,
    tests: _TestView,
) -> ChangeSummary | None:
    if history is None or git_state == "missing":
        return None
    files = tuple(
        sorted(
            item.path
            for item in history.file_churn
            if eligible_production(item.path) and not item.path.startswith("codestrata/")
        )
    )
    components = files
    cutoff = len(files) > IMPACT_NODE_BUDGET or git_state == "shallow"
    reason = None
    if len(files) > IMPACT_NODE_BUDGET:
        reason = "impact_node_budget"
    elif git_state == "shallow":
        reason = "shallow_git_history"
    visited = IMPACT_NODE_BUDGET if len(files) > IMPACT_NODE_BUDGET else len(files)
    return ChangeSummary(
        changed_file_ids=files,
        changed_component_ids=components,
        changed_file_count=len(files),
        changed_component_count=len(components),
        unmapped_changed_file_count=0,
        mapping_coverage="observed_paths" if files else None,
        mapping_coverage_status=ResultStatus.PASS if files else ResultStatus.UNKNOWN,
        boundary_dimension=None,
        boundary_spread_member_ids=(),
        boundary_spread_count=None,
        boundary_spread_status=ResultStatus.UNKNOWN,
        crossed_boundary_count=None,
        crossed_boundary_pairs=(),
        crossed_boundary_status=ResultStatus.UNKNOWN,
        affected_component_ids=() if cutoff else components,
        affected_component_count=None if cutoff else len(components),
        affected_test_ids=() if tests.missing else tests.test_ids,
        affected_test_count=None if tests.missing else tests.count,
        visited_nodes=visited,
        visited_edges=None,
        cutoff_reason=reason,
        graph_side="candidate",
        lower_bound=cutoff,
    )


def _limitations(
    git_state: str,
    feed: _FeedView,
    tests: _TestView,
    change: ChangeSummary | None,
    cochange_truncated: bool = False,
) -> tuple[str, ...]:
    rows = [feed.reason]
    if cochange_truncated:
        rows.append("cochange_file_budget")
    if git_state == "missing":
        rows.append("missing_git_history")
        rows.append("git_history_not_attached")
        rows.append("m22_records_not_attached")
    elif git_state == "shallow":
        rows.append("shallow_git_history")
    elif git_state == "git_command_unavailable":
        rows.append("git_command_unavailable")
    if tests.missing:
        rows.append("missing_test_association")
    if feed.family_error:
        rows.append("failed_family_vulnerability")
    if change is not None and change.cutoff_reason:
        rows.append(change.cutoff_reason)
    if feed.cannot_prove_clean:
        rows.append("cannot_prove_clean")
    return tuple(dict.fromkeys(rows))


def _capability_rows(
    git_state: str,
    head: str | None,
    history: HistoryWindow | None,
    hotspots: tuple[EngineeringHotspot, ...],
    feed: _FeedView,
    *,
    evaluation_time: datetime,
) -> tuple[tuple[CapabilityCoverage, ...], tuple[CapabilityFreshness, ...]]:
    partial = any(item.ranking_value is None for item in hotspots) or not hotspots
    if git_state == "complete" and hotspots and not partial:
        hotspot_coverage = CapabilityCoverage(
            capability_id="quality.m22.hotspots",
            capability_version="1.0.0",
            scope="repository",
            applicability="applicable",
            execution_state=CoverageState.COMPLETE,
            evaluated_count=len(hotspots),
            eligible_count=len(hotspots),
            coverage_ratio=None,
            coverage_reason="hotspot_records_attached",
        )
        git_fresh = CapabilityFreshness(
            capability_id="quality.m22.hotspots",
            state=FreshnessState.NOT_APPLICABLE,
            reason_code="git_history_pinned",
            explanation=(
                "Pinned local history is present. An old commit does not prove the "
                "checkout is current."
            ),
            evaluation_time=_stamp(evaluation_time),
            git_head=head,
            git_window=None if history is None else history.window,
        )
    else:
        reason = {
            "missing": "missing_git_history",
            "shallow": "shallow_git_history",
            "git_command_unavailable": "git_command_unavailable",
        }.get(git_state, "partial_hotspot_list")
        hotspot_coverage = CapabilityCoverage(
            capability_id="quality.m22.hotspots",
            capability_version="1.0.0",
            scope="repository",
            applicability="applicable",
            execution_state=CoverageState.UNKNOWN,
            evaluated_count=None,
            eligible_count=None,
            coverage_ratio=None,
            coverage_reason=reason,
            limitations=(reason,),
        )
        git_fresh = CapabilityFreshness(
            capability_id="quality.m22.hotspots",
            state=FreshnessState.UNKNOWN,
            reason_code=reason,
            explanation=f"Git history coverage is {reason}.",
            evaluation_time=_stamp(evaluation_time),
            git_head=head,
            git_window=None if history is None else history.window,
        )
    feed_state = CoverageState.ERROR if feed.family_error else _feed_execution(feed)
    feed_coverage = CapabilityCoverage(
        capability_id="security.m13.vulnerabilities",
        capability_version="1.0.0",
        scope="repository",
        applicability="applicable",
        execution_state=feed_state,
        evaluated_count=None if feed.cannot_prove_clean else feed.match_count,
        eligible_count=None if feed.cannot_prove_clean else feed.match_count,
        coverage_ratio=None,
        coverage_reason=feed.reason if feed.family_error else feed.matching_reason,
        limitations=(feed.reason,),
        error_count=1 if feed.family_error else 0,
    )
    fresh_state = {
        "fresh": FreshnessState.FRESH,
        "stale": FreshnessState.STALE,
        "error": FreshnessState.UNKNOWN,
    }.get(feed.state, FreshnessState.UNKNOWN)
    feed_fresh = CapabilityFreshness(
        capability_id="security.m13.vulnerabilities",
        state=fresh_state,
        reason_code=feed.reason,
        explanation=(
            feed.family_error
            or (
                f"Vulnerability feed {feed.reason}. "
                "A stale or missing feed cannot prove a clean result."
            )
        ),
        evaluation_time=_stamp(evaluation_time),
        source_digest=feed.digest or None,
        source_publication_time=feed.published_at,
        max_age_days=7,
        feed_provider=feed.provider,
        feed_digest=feed.digest or None,
    )
    return (hotspot_coverage, feed_coverage), (git_fresh, feed_fresh)


def _feed_execution(feed: _FeedView) -> CoverageState:
    if feed.state == "fresh" and not feed.cannot_prove_clean:
        return CoverageState.COMPLETE
    if feed.state == "not_applicable":
        return CoverageState.NOT_APPLICABLE
    return CoverageState.UNKNOWN


def _metrics(hotspots: tuple[EngineeringHotspot, ...]) -> dict[str, dict[str, object]]:
    complete = [item for item in hotspots if item.ranking_value is not None]
    if len(complete) != 1:
        return {}
    item = complete[0]
    expected = m22_hotspot_value(
        int(_contributor(item, "complexity") or 0),
        int(_contributor(item, "churn") or 0),
    )
    if str(expected) != item.ranking_value:
        return {}
    return {
        "m22.hotspot": {
            "value": item.ranking_value,
            "unit": "complexity_times_changed_lines",
            "scope": item.subject_id,
            "direction": "lower_is_better",
            "coverage_status": "pass",
            "formula_version": "hotspot.complexity_churn.v1",
            "evidence_ids": list(item.evidence_ids),
        }
    }


def _contributor(item: EngineeringHotspot, name: str) -> str | None:
    for part in item.contributors:
        if part.name == name and part.value is not None and part.value != "UNKNOWN":
            return part.value
    return None


def _stamp(evaluation_time: datetime) -> str:
    return evaluation_time.astimezone(UTC).isoformat().replace("+00:00", "Z")
