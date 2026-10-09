"""E09.3 reusable change facts: E05.2 identity join, cache keys, reuse eligibility."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from codestrata import __version__ as RUNTIME_ENGINE_VERSION
from codestrata.application.incremental.equivalence import (
    AssessmentEquivalenceResult,
    AssessmentSemanticComparator,
    CompleteAssessmentArtifacts,
)
from codestrata.application.incremental.errors import IncrementalPlanningError
from codestrata.application.incremental.git_inputs import (
    ChangedFileFact,
    FileChangeStatus,
    GitInputResolution,
)
from codestrata.application.incremental.history_index import (
    ConcentrationRecord,
    ConcentrationScope,
    GitCapabilityRecord,
    HistoryIndex,
)
from codestrata.application.incremental.models import ReuseDecision
from codestrata.domain.contracts.rules import BOUNDED_OPERATORS, CAPABILITY_VERSION
from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.domain.repository.paths import normalize_repository_relative_path
from codestrata.domain.repository_graph.mapping import (
    FileComponentMapping,
    map_files_to_components,
)

CHANGE_FACTS_SCHEMA = "codestrata.reusable-change-facts.v1"
CHANGE_FACTS_SCHEMA_VERSION = "1.0.0"
OPERATOR_SET_ID = "codestrata.bounded-operators.v1"
FEED_ABSENT = "absent"
RULE_MISSING = "missing"
CONFIG_EMPTY_DIGEST = digest_canonical({"parameters_by_rule": {}})


class MappingJoinStatus(StrEnum):
    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    UNKNOWN_AMBIGUOUS = "unknown_ambiguous"
    UNSUPPORTED = "unsupported"


class LineageStatus(StrEnum):
    UNIQUE = "unique"
    UNKNOWN_AMBIGUOUS = "unknown_ambiguous"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"


class FindingMatchKind(StrEnum):
    UNCHANGED_LOCATION = "unchanged_location"
    RENAME_LOCATION = "rename_location"
    UNKNOWN_LINEAGE = "unknown_lineage"
    UNSUPPORTED = "unsupported"


class ChangeFactsError(IncrementalPlanningError):
    """Reusable change facts cannot be published honestly."""


@dataclass(frozen=True, slots=True)
class ChangeCacheKey:
    """Reuse key. Binds source, config, rule, operator and feed versions."""

    source_digest: str
    config_digest: str
    rule_digest: str
    operator_version: str
    operator_digest: str
    feed_binding: str
    engine_version: str
    digest: str


@dataclass(frozen=True, slots=True)
class NormalizedChangeEvent:
    status: FileChangeStatus
    path: str
    old_path: str | None
    file_id: str | None
    previous_file_id: str | None
    component_id: str | None
    mapping_status: MappingJoinStatus
    lineage_status: LineageStatus
    aliases: tuple[str, ...]
    added_lines: int | None
    deleted_lines: int | None
    binary: bool


@dataclass(frozen=True, slots=True)
class GraphIdentityFixture:
    path: str
    file_id: str
    component_key: str
    component_id: str


@dataclass(frozen=True, slots=True)
class JoinedConcentration:
    scope: ConcentrationScope
    subject_id: str
    git_subject_id: str
    status: str
    largest_share_serialized: str | None
    contributors_to_50pct: int | None
    attributable_lines: int
    unattributed_lines: int
    mapping_status: MappingJoinStatus
    mapping_coverage: str | None
    complete_window: bool
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JoinedCochange:
    scope: str
    left: str
    right: str
    left_id: str | None
    right_id: str | None
    support: int
    union: int
    jaccard_serialized: str | None
    supported_relation: bool
    commit_shas: tuple[str, ...]
    qualified_incomplete_window: bool
    mapping_status: MappingJoinStatus


@dataclass(frozen=True, slots=True)
class FindingLocationMatch:
    finding_key: str
    rule_id: str
    previous_path: str
    current_path: str | None
    previous_file_id: str | None
    current_file_id: str | None
    match_kind: FindingMatchKind
    location_moved: bool
    finding_churn: bool


@dataclass(frozen=True, slots=True)
class PreviousFinding:
    finding_key: str
    rule_id: str
    path: str


@dataclass(frozen=True, slots=True)
class ReuseAgainstFull:
    decision: ReuseDecision
    cache_keys_match: bool
    proof_sufficient: bool
    semantic_equivalent: bool | None
    fallback_to_full: bool
    reasons: tuple[str, ...]
    mismatched_bindings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChangeFactsPublication:
    schema_name: str
    schema_version: str
    cache_key: ChangeCacheKey
    events: tuple[NormalizedChangeEvent, ...]
    graph_identities: tuple[GraphIdentityFixture, ...]
    concentrations: tuple[JoinedConcentration, ...]
    cochange: tuple[JoinedCochange, ...]
    capabilities: tuple[GitCapabilityRecord, ...]
    finding_matches: tuple[FindingLocationMatch, ...]
    reuse: ReuseAgainstFull
    analysis_digest: str
    supplied_context_digest: str | None
    bugfix_marker_digest: str | None
    history_message_provenance: str
    organizational_bus_factor: bool
    productivity_claim: bool
    limitations: tuple[str, ...]
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ChangeFactsRequest:
    repository_key: str
    git_inputs: GitInputResolution
    history: HistoryIndex | None = None
    manifest_directories: tuple[str, ...] = ()
    config_digest: str | None = None
    rule_digest: str | None = None
    feed_digest: str | None = None
    previous_findings: tuple[PreviousFinding, ...] = ()
    reference_cache_key: ChangeCacheKey | None = None
    incremental_artifacts: CompleteAssessmentArtifacts | None = None
    full_reference_artifacts: CompleteAssessmentArtifacts | None = None
    selective_scan_complete: bool | None = None


def operator_set_binding() -> tuple[str, str]:
    """Pinned E03.2 bounded-operator identity used by reuse cache keys."""

    payload = {
        "id": OPERATOR_SET_ID,
        "capability_version": CAPABILITY_VERSION,
        "operators": sorted(BOUNDED_OPERATORS),
    }
    return CAPABILITY_VERSION, digest_canonical(payload)


def build_change_cache_key(
    *,
    source_digest: str,
    config_digest: str | None,
    rule_digest: str | None,
    feed_digest: str | None,
    engine_version: str = RUNTIME_ENGINE_VERSION,
) -> ChangeCacheKey:
    operator_version, operator_digest = operator_set_binding()
    config = config_digest or CONFIG_EMPTY_DIGEST
    rule = rule_digest or RULE_MISSING
    feed = feed_digest or FEED_ABSENT
    body = {
        "source_digest": source_digest,
        "config_digest": config,
        "rule_digest": rule,
        "operator_version": operator_version,
        "operator_digest": operator_digest,
        "feed_binding": feed,
        "engine_version": engine_version,
    }
    return ChangeCacheKey(
        source_digest=source_digest,
        config_digest=config,
        rule_digest=rule,
        operator_version=operator_version,
        operator_digest=operator_digest,
        feed_binding=feed,
        engine_version=engine_version,
        digest=digest_canonical(body),
    )


def identities_for_paths(
    paths: Sequence[str],
    *,
    repository_key: str,
    manifest_directories: Sequence[str] = (),
) -> dict[str, FileComponentMapping]:
    mappings = map_files_to_components(
        tuple(dict.fromkeys(path for path in paths if path)),
        repository_key=repository_key,
        manifest_directories=manifest_directories,
    )
    return {item.relative_path: item for item in mappings}


def mapping_status_for(
    path: str,
    mapping: FileComponentMapping | None,
    *,
    aliases: Sequence[str] = (),
    by_path: Mapping[str, FileComponentMapping] | None = None,
) -> MappingJoinStatus:
    if mapping is None:
        if _unsupported_path(path):
            return MappingJoinStatus.UNSUPPORTED
        return MappingJoinStatus.UNMAPPED
    if not by_path or not aliases:
        return MappingJoinStatus.MAPPED
    component_ids = {
        by_path[alias].component_id for alias in aliases if alias in by_path
    }
    if len(component_ids) > 1:
        return MappingJoinStatus.UNKNOWN_AMBIGUOUS
    return MappingJoinStatus.MAPPED


def normalize_change_events(
    files: Sequence[ChangedFileFact],
    *,
    by_path: Mapping[str, FileComponentMapping],
    history_aliases: Mapping[str, Sequence[str]] | None = None,
) -> tuple[NormalizedChangeEvent, ...]:
    extra = history_aliases or {}
    events: list[NormalizedChangeEvent] = []
    for item in files:
        history_names = extra.get(item.path, ()) if item.status is FileChangeStatus.RENAMED else ()
        aliases = tuple(
            dict.fromkeys(path for path in (item.path, item.old_path, *history_names) if path)
        )
        current = by_path.get(item.path)
        previous = by_path.get(item.old_path) if item.old_path else None
        status = mapping_status_for(
            item.path, current, aliases=aliases, by_path=by_path
        )
        lineage = _lineage_status(item, current, previous, status, aliases=aliases)
        events.append(
            NormalizedChangeEvent(
                status=item.status,
                path=item.path,
                old_path=item.old_path,
                file_id=None if current is None else current.file_id,
                previous_file_id=None if previous is None else previous.file_id,
                component_id=None
                if status is not MappingJoinStatus.MAPPED or current is None
                else current.component_id,
                mapping_status=status,
                lineage_status=lineage,
                aliases=aliases,
                added_lines=item.added_lines,
                deleted_lines=item.deleted_lines,
                binary=item.binary,
            )
        )
    return tuple(events)


def match_findings_across_lineage(
    previous: Sequence[PreviousFinding],
    events: Sequence[NormalizedChangeEvent],
    *,
    by_path: Mapping[str, FileComponentMapping],
) -> tuple[FindingLocationMatch, ...]:
    """Move finding location on unique rename; do not invent churn or resolution."""

    dest_by_old = {
        event.old_path: event
        for event in events
        if event.status is FileChangeStatus.RENAMED and event.old_path
    }
    matches: list[FindingLocationMatch] = []
    for finding in previous:
        event = dest_by_old.get(finding.path)
        previous_id = (
            by_path[finding.path].file_id if finding.path in by_path else None
        )
        if event is None:
            current_id = (
                by_path[finding.path].file_id if finding.path in by_path else None
            )
            matches.append(
                FindingLocationMatch(
                    finding_key=finding.finding_key,
                    rule_id=finding.rule_id,
                    previous_path=finding.path,
                    current_path=finding.path,
                    previous_file_id=previous_id,
                    current_file_id=current_id,
                    match_kind=FindingMatchKind.UNCHANGED_LOCATION,
                    location_moved=False,
                    finding_churn=False,
                )
            )
            continue
        if event.lineage_status is LineageStatus.UNIQUE:
            matches.append(
                FindingLocationMatch(
                    finding_key=finding.finding_key,
                    rule_id=finding.rule_id,
                    previous_path=finding.path,
                    current_path=event.path,
                    previous_file_id=event.previous_file_id or previous_id,
                    current_file_id=event.file_id,
                    match_kind=FindingMatchKind.RENAME_LOCATION,
                    location_moved=True,
                    finding_churn=False,
                )
            )
            continue
        kind = (
            FindingMatchKind.UNSUPPORTED
            if event.lineage_status is LineageStatus.UNSUPPORTED
            else FindingMatchKind.UNKNOWN_LINEAGE
        )
        matches.append(
            FindingLocationMatch(
                finding_key=finding.finding_key,
                rule_id=finding.rule_id,
                previous_path=finding.path,
                current_path=None,
                previous_file_id=event.previous_file_id or previous_id,
                current_file_id=None,
                match_kind=kind,
                location_moved=False,
                finding_churn=False,
            )
        )
    return tuple(matches)


def evaluate_reuse_against_full(
    current: ChangeCacheKey,
    reference: ChangeCacheKey | None,
    *,
    events: Sequence[NormalizedChangeEvent],
    git_inputs: GitInputResolution,
    selective_scan_complete: bool | None = None,
    incremental_artifacts: CompleteAssessmentArtifacts | None = None,
    full_reference_artifacts: CompleteAssessmentArtifacts | None = None,
) -> ReuseAgainstFull:
    reasons: list[str] = []
    mismatched: list[str] = []
    if reference is None:
        reasons.append("missing_reference_assessment")
    else:
        if current.source_digest != reference.source_digest:
            mismatched.append("source")
        if current.config_digest != reference.config_digest:
            mismatched.append("config")
        if current.rule_digest != reference.rule_digest:
            mismatched.append("rule")
        if current.operator_digest != reference.operator_digest:
            mismatched.append("operator")
        if current.feed_binding != reference.feed_binding:
            mismatched.append("feed")
        incompatible = tuple(item for item in mismatched if item != "source")
        if incompatible:
            reasons.append("incompatible_reference_bindings")

    if current.rule_digest == RULE_MISSING:
        reasons.append("missing_rule_digest")
    if not git_inputs.full_comparison:
        reasons.append("insufficient_git_comparison")
        reasons.append(git_inputs.comparison_completeness.value)
    if any(item.lineage_status is LineageStatus.UNKNOWN_AMBIGUOUS for item in events):
        reasons.append("ambiguous_lineage")
    if any(item.mapping_status is MappingJoinStatus.UNSUPPORTED for item in events):
        reasons.append("unsupported_mapping")
    if selective_scan_complete is False:
        reasons.append("selective_scan_incomplete")

    semantic: bool | None = None
    equivalence: AssessmentEquivalenceResult | None = None
    if incremental_artifacts is not None and full_reference_artifacts is not None:
        equivalence = AssessmentSemanticComparator().compare(
            incremental_artifacts, full_reference_artifacts
        )
        semantic = equivalence.equivalent
        if not equivalence.equivalent:
            reasons.append("selective_full_not_equivalent")
    elif incremental_artifacts is not None or full_reference_artifacts is not None:
        reasons.append("incomplete_equivalence_pair")

    bindings_compatible = reference is not None and not any(
        item != "source" for item in mismatched
    )
    unique_reasons = tuple(dict.fromkeys(reasons))
    proof = not unique_reasons
    fallback = not proof
    if fallback:
        decision = ReuseDecision.FULL_REBUILD
    elif "source" not in mismatched:
        decision = ReuseDecision.REUSABLE
    else:
        decision = ReuseDecision.RECOMPUTE
    return ReuseAgainstFull(
        decision=decision,
        cache_keys_match=bindings_compatible and "source" not in mismatched,
        proof_sufficient=proof,
        semantic_equivalent=semantic,
        fallback_to_full=fallback,
        reasons=unique_reasons,
        mismatched_bindings=tuple(mismatched),
    )


def publish_change_facts(request: ChangeFactsRequest) -> ChangeFactsPublication:
    """Join Git observations to E05.2 identities and decide incremental reuse."""

    git_inputs = request.git_inputs
    paths = _collect_paths(git_inputs, request.history)
    by_path = identities_for_paths(
        paths,
        repository_key=request.repository_key,
        manifest_directories=request.manifest_directories,
    )
    events = normalize_change_events(
        git_inputs.files,
        by_path=by_path,
        history_aliases=_history_aliases(request.history),
    )
    graph_identities = tuple(
        GraphIdentityFixture(
            path=item.relative_path,
            file_id=item.file_id,
            component_key=item.component_key,
            component_id=item.component_id,
        )
        for item in sorted(by_path.values(), key=lambda row: row.relative_path)
    )
    concentrations = join_concentrations(request.history, by_path)
    cochange = join_cochange(request.history, by_path)
    capabilities = () if request.history is None else request.history.capabilities
    finding_matches = match_findings_across_lineage(
        request.previous_findings, events, by_path=by_path
    )
    cache_key = build_change_cache_key(
        source_digest=git_inputs.canonical_digest,
        config_digest=request.config_digest,
        rule_digest=request.rule_digest,
        feed_digest=request.feed_digest,
    )
    reuse = evaluate_reuse_against_full(
        cache_key,
        request.reference_cache_key,
        events=events,
        git_inputs=git_inputs,
        selective_scan_complete=request.selective_scan_complete,
        incremental_artifacts=request.incremental_artifacts,
        full_reference_artifacts=request.full_reference_artifacts,
    )
    limitations = list(git_inputs.limitations)
    if request.history is not None:
        limitations.extend(request.history.limitations)
    if any(item.mapping_status is MappingJoinStatus.UNMAPPED for item in events):
        limitations.append("unmapped_changed_files")
    if any(item.mapping_status is MappingJoinStatus.UNKNOWN_AMBIGUOUS for item in events):
        limitations.append("ambiguous_file_component_mapping")
    unique_limitations = tuple(dict.fromkeys(limitations))

    supplied = None
    if git_inputs.supplied_context is not None:
        supplied = git_inputs.supplied_context.record.context_digest
    bugfix_digest = None
    if request.history is not None:
        bugfix_digest = digest_canonical(
            {
                "marker_version": request.history.bugfix_markers.marker_version,
                "matched_commit_shas": list(request.history.bugfix_markers.matched_commit_shas),
                "proven_defects": False,
                "productivity_claim": False,
                "intent_claim": False,
            }
        )

    analysis_digest = digest_canonical(
        _analysis_payload(
            cache_key=cache_key,
            events=events,
            graph_identities=graph_identities,
            concentrations=concentrations,
            cochange=cochange,
            capabilities=capabilities,
            finding_matches=finding_matches,
            reuse=reuse,
            limitations=unique_limitations,
        )
    )
    canonical = digest_canonical(
        {
            "schema_name": CHANGE_FACTS_SCHEMA,
            "schema_version": CHANGE_FACTS_SCHEMA_VERSION,
            "analysis_digest": analysis_digest,
            "supplied_context_digest": supplied,
            "bugfix_marker_digest": bugfix_digest,
        }
    )
    return ChangeFactsPublication(
        schema_name=CHANGE_FACTS_SCHEMA,
        schema_version=CHANGE_FACTS_SCHEMA_VERSION,
        cache_key=cache_key,
        events=events,
        graph_identities=graph_identities,
        concentrations=concentrations,
        cochange=cochange,
        capabilities=capabilities,
        finding_matches=finding_matches,
        reuse=reuse,
        analysis_digest=analysis_digest,
        supplied_context_digest=supplied,
        bugfix_marker_digest=bugfix_digest,
        history_message_provenance="contextual_bugfix_markers_separate_from_analysis",
        organizational_bus_factor=False,
        productivity_claim=False,
        limitations=unique_limitations,
        canonical_digest=canonical,
    )


def join_concentrations(
    history: HistoryIndex | None,
    by_path: Mapping[str, FileComponentMapping],
) -> tuple[JoinedConcentration, ...]:
    if history is None:
        return ()
    joined: list[JoinedConcentration] = []
    for record in history.concentrations:
        subject, status = _join_concentration_subject(record, by_path)
        notes = tuple(
            dict.fromkeys(
                (
                    *record.notes,
                    "not_organizational_bus_factor",
                    "not_productivity_or_blame",
                    "change_concentration_observation_only",
                )
            )
        )
        joined.append(
            JoinedConcentration(
                scope=record.scope,
                subject_id=subject,
                git_subject_id=record.subject_id,
                status=record.status.value,
                largest_share_serialized=record.largest_share.serialized,
                contributors_to_50pct=record.contributors_to_50pct,
                attributable_lines=record.attributable_lines,
                unattributed_lines=record.unattributed_lines,
                mapping_status=status,
                mapping_coverage=record.mapping_coverage,
                complete_window=record.complete_window,
                notes=notes,
            )
        )
    return tuple(joined)


def join_cochange(
    history: HistoryIndex | None,
    by_path: Mapping[str, FileComponentMapping],
) -> tuple[JoinedCochange, ...]:
    if history is None:
        return ()
    rows: list[JoinedCochange] = []
    for item in history.cochange:
        left_id, right_id, status = _join_pair(item.scope, item.left, item.right, by_path)
        rows.append(
            JoinedCochange(
                scope=item.scope,
                left=item.left,
                right=item.right,
                left_id=left_id,
                right_id=right_id,
                support=item.support,
                union=item.union,
                jaccard_serialized=item.jaccard.serialized,
                supported_relation=item.supported_relation,
                commit_shas=item.commit_shas,
                qualified_incomplete_window=item.qualified_incomplete_window,
                mapping_status=status,
            )
        )
    return tuple(rows)


def publication_row(publication: ChangeFactsPublication) -> dict[str, Any]:
    return {
        "schema_name": publication.schema_name,
        "schema_version": publication.schema_version,
        "cache_key": {
            "digest": publication.cache_key.digest,
            "source_digest": publication.cache_key.source_digest,
            "config_digest": publication.cache_key.config_digest,
            "rule_digest": publication.cache_key.rule_digest,
            "operator_version": publication.cache_key.operator_version,
            "operator_digest": publication.cache_key.operator_digest,
            "feed_binding": publication.cache_key.feed_binding,
        },
        "events": [
            {
                "status": item.status.value,
                "path": item.path,
                "old_path": item.old_path,
                "file_id": item.file_id,
                "previous_file_id": item.previous_file_id,
                "component_id": item.component_id,
                "mapping_status": item.mapping_status.value,
                "lineage_status": item.lineage_status.value,
            }
            for item in publication.events
        ],
        "reuse": {
            "decision": publication.reuse.decision.value,
            "fallback_to_full": publication.reuse.fallback_to_full,
            "proof_sufficient": publication.reuse.proof_sufficient,
            "reasons": list(publication.reuse.reasons),
        },
        "organizational_bus_factor": publication.organizational_bus_factor,
        "productivity_claim": publication.productivity_claim,
        "history_message_provenance": publication.history_message_provenance,
        "analysis_digest": publication.analysis_digest,
    }


def _unsupported_path(path: str) -> bool:
    if not path.strip() or path.endswith("/"):
        return True
    try:
        normalize_repository_relative_path(path)
    except ValueError:
        return True
    return False


def _history_aliases(history: HistoryIndex | None) -> dict[str, tuple[str, ...]]:
    if history is None:
        return {}
    return {item.path: item.renamed_from for item in history.file_churn if item.renamed_from}


def _lineage_status(
    item: ChangedFileFact,
    current: FileComponentMapping | None,
    previous: FileComponentMapping | None,
    mapping_status: MappingJoinStatus,
    *,
    aliases: Sequence[str],
) -> LineageStatus:
    if mapping_status is MappingJoinStatus.UNSUPPORTED:
        return LineageStatus.UNSUPPORTED
    if mapping_status is MappingJoinStatus.UNKNOWN_AMBIGUOUS:
        return LineageStatus.UNKNOWN_AMBIGUOUS
    predecessors = tuple(path for path in aliases if path != item.path)
    if item.status is FileChangeStatus.RENAMED or len(predecessors) > 1:
        if item.status is FileChangeStatus.RENAMED and item.old_path is None:
            return LineageStatus.UNKNOWN_AMBIGUOUS
        if len(predecessors) > 1:
            return LineageStatus.UNKNOWN_AMBIGUOUS
        if current is None or previous is None:
            return LineageStatus.UNSUPPORTED
        if current.file_id == previous.file_id:
            return LineageStatus.UNKNOWN_AMBIGUOUS
        return LineageStatus.UNIQUE
    if mapping_status is MappingJoinStatus.UNMAPPED:
        return LineageStatus.UNSUPPORTED
    return LineageStatus.NOT_APPLICABLE


def _collect_paths(
    git_inputs: GitInputResolution,
    history: HistoryIndex | None,
) -> tuple[str, ...]:
    paths: list[str] = []
    for item in git_inputs.files:
        paths.append(item.path)
        if item.old_path:
            paths.append(item.old_path)
    if history is not None:
        for churn in history.file_churn:
            paths.append(churn.path)
            paths.extend(churn.renamed_from)
    return tuple(dict.fromkeys(paths))


def _join_concentration_subject(
    record: ConcentrationRecord,
    by_path: Mapping[str, FileComponentMapping],
) -> tuple[str, MappingJoinStatus]:
    if record.mapping_status == "unknown_ambiguous":
        return record.subject_id, MappingJoinStatus.UNKNOWN_AMBIGUOUS
    if record.scope is ConcentrationScope.REPOSITORY:
        return record.subject_id, MappingJoinStatus.MAPPED
    if record.scope is ConcentrationScope.FILE:
        mapped = by_path.get(record.subject_id)
        if mapped is None:
            return record.subject_id, MappingJoinStatus.UNMAPPED
        return mapped.file_id, MappingJoinStatus.MAPPED
    members = [
        item for path, item in by_path.items() if item.component_id == record.subject_id
    ]
    if members:
        return members[0].component_id, MappingJoinStatus.MAPPED
    keyed = [
        item for item in by_path.values() if item.component_key == record.subject_id
    ]
    if len({item.component_id for item in keyed}) == 1:
        return keyed[0].component_id, MappingJoinStatus.MAPPED
    if keyed:
        return record.subject_id, MappingJoinStatus.UNKNOWN_AMBIGUOUS
    return record.subject_id, MappingJoinStatus.UNMAPPED


def _join_pair(
    scope: str,
    left: str,
    right: str,
    by_path: Mapping[str, FileComponentMapping],
) -> tuple[str | None, str | None, MappingJoinStatus]:
    if scope == "file":
        left_map = by_path.get(left)
        right_map = by_path.get(right)
        if left_map is None or right_map is None:
            return (
                None if left_map is None else left_map.file_id,
                None if right_map is None else right_map.file_id,
                MappingJoinStatus.UNMAPPED,
            )
        return left_map.file_id, right_map.file_id, MappingJoinStatus.MAPPED
    left_ids = {item.component_id for item in by_path.values() if item.component_key == left}
    right_ids = {
        item.component_id for item in by_path.values() if item.component_key == right
    }
    if not left_ids:
        left_ids = {left} if any(item.component_id == left for item in by_path.values()) else set()
    if not right_ids:
        right_ids = (
            {right} if any(item.component_id == right for item in by_path.values()) else set()
        )
    if len(left_ids) > 1 or len(right_ids) > 1:
        return None, None, MappingJoinStatus.UNKNOWN_AMBIGUOUS
    if not left_ids or not right_ids:
        return None, None, MappingJoinStatus.UNMAPPED
    return next(iter(left_ids)), next(iter(right_ids)), MappingJoinStatus.MAPPED


def _analysis_payload(
    *,
    cache_key: ChangeCacheKey,
    events: Sequence[NormalizedChangeEvent],
    graph_identities: Sequence[GraphIdentityFixture],
    concentrations: Sequence[JoinedConcentration],
    cochange: Sequence[JoinedCochange],
    capabilities: Sequence[GitCapabilityRecord],
    finding_matches: Sequence[FindingLocationMatch],
    reuse: ReuseAgainstFull,
    limitations: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_name": CHANGE_FACTS_SCHEMA,
        "schema_version": CHANGE_FACTS_SCHEMA_VERSION,
        "cache_key_digest": cache_key.digest,
        "source_digest": cache_key.source_digest,
        "config_digest": cache_key.config_digest,
        "rule_digest": cache_key.rule_digest,
        "operator_digest": cache_key.operator_digest,
        "feed_binding": cache_key.feed_binding,
        "events": [
            {
                "status": item.status.value,
                "path": item.path,
                "old_path": item.old_path,
                "file_id": item.file_id,
                "previous_file_id": item.previous_file_id,
                "component_id": item.component_id,
                "mapping_status": item.mapping_status.value,
                "lineage_status": item.lineage_status.value,
                "aliases": list(item.aliases),
                "added_lines": item.added_lines,
                "deleted_lines": item.deleted_lines,
                "binary": item.binary,
            }
            for item in events
        ],
        "graph_identities": [
            {
                "path": item.path,
                "file_id": item.file_id,
                "component_key": item.component_key,
                "component_id": item.component_id,
            }
            for item in graph_identities
        ],
        "concentrations": [
            {
                "scope": item.scope.value,
                "subject_id": item.subject_id,
                "git_subject_id": item.git_subject_id,
                "status": item.status,
                "largest_share_serialized": item.largest_share_serialized,
                "contributors_to_50pct": item.contributors_to_50pct,
                "attributable_lines": item.attributable_lines,
                "mapping_status": item.mapping_status.value,
                "complete_window": item.complete_window,
            }
            for item in concentrations
        ],
        "cochange": [
            {
                "scope": item.scope,
                "left": item.left,
                "right": item.right,
                "left_id": item.left_id,
                "right_id": item.right_id,
                "support": item.support,
                "union": item.union,
                "jaccard_serialized": item.jaccard_serialized,
                "supported_relation": item.supported_relation,
                "mapping_status": item.mapping_status.value,
            }
            for item in cochange
        ],
        "capabilities": [
            {
                "capability_id": item.capability_id,
                "requested_window_days": item.requested_window_days,
                "requested_max_commits": item.requested_max_commits,
                "observed_commit_count": item.observed_commit_count,
                "coverage": item.coverage.value,
                "unknown_reasons": list(item.unknown_reasons),
                "freshness": item.freshness.value,
                "freshness_reason": item.freshness_reason,
                "complete_window": item.complete_window,
            }
            for item in capabilities
        ],
        "finding_matches": [
            {
                "finding_key": item.finding_key,
                "rule_id": item.rule_id,
                "previous_path": item.previous_path,
                "current_path": item.current_path,
                "match_kind": item.match_kind.value,
                "location_moved": item.location_moved,
                "finding_churn": item.finding_churn,
            }
            for item in finding_matches
        ],
        "reuse": {
            "decision": reuse.decision.value,
            "fallback_to_full": reuse.fallback_to_full,
            "proof_sufficient": reuse.proof_sufficient,
            "reasons": list(reuse.reasons),
        },
        "organizational_bus_factor": False,
        "productivity_claim": False,
        "limitations": list(limitations),
    }
