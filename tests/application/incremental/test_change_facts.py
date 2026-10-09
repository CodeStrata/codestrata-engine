"""E09.3 reusable change facts, E05.2 identity join, cache keys and reuse."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from codestrata.application.incremental.change_facts import (
    CHANGE_FACTS_SCHEMA,
    ChangeFactsRequest,
    LineageStatus,
    MappingJoinStatus,
    PreviousFinding,
    build_change_cache_key,
    evaluate_reuse_against_full,
    identities_for_paths,
    match_findings_across_lineage,
    normalize_change_events,
    operator_set_binding,
    publish_change_facts,
)
from codestrata.application.incremental.equivalence import artifacts_from_semantic_payloads
from codestrata.application.incremental.git_inputs import (
    ChangedFileFact,
    FileChangeStatus,
    FileContentClass,
    FileUnitClass,
    GitInputMode,
    GitInputRequest,
    resolve_git_inputs,
)
from codestrata.application.incremental.history_index import (
    ConcentrationScope,
    HistoryIndexRequest,
    build_history_index,
)
from codestrata.application.incremental.models import ReuseDecision
from codestrata.domain.contracts.enums import RevisionAgreement, SuppliedContextProvenance
from codestrata.domain.contracts.invocation import context_digest_for
from codestrata.domain.contracts.serialization import digest_canonical
from tests.application.incremental.git_repo_helpers import (
    _git,
    commit_all,
    commit_dated,
    init_repo,
    write,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e09.3"
EVAL = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
EVAL_UNIX = int(EVAL.timestamp())
DAY = 86400
RULE = digest_canonical({"ruleset": "launch", "version": "1.0.0"})


def _lines(text: str, count: int) -> str:
    return "".join(f"{text}{index}\n" for index in range(count))


def _context_payload(**overrides: object) -> dict[str, object]:
    fields = {
        "title": "local title",
        "description": "Local PR narrative. Not proof of behavior.",
        "base": None,
        "head": None,
        "labels": (),
        "linked_references": (),
        "provenance": SuppliedContextProvenance.LOCAL_FILE.value,
        "supplied_path": "./pr-context.json",
        "revision_agreement": RevisionAgreement.NOT_APPLICABLE.value,
        "conflict_reason": None,
        "narrative_only": True,
    }
    fields.update(overrides)
    return {
        "schema_name": "codestrata.supplied-pr-context.v1",
        "schema_version": "1.0.0",
        "title": fields["title"],
        "description": fields["description"],
        "base": fields["base"],
        "head": fields["head"],
        "labels": list(fields["labels"] or ()),
        "linked_references": list(fields["linked_references"] or ()),
        "provenance": fields["provenance"],
        "supplied_path": fields["supplied_path"],
        "context_digest": context_digest_for(**fields),
        "revision_agreement": fields["revision_agreement"],
        "conflict_reason": fields["conflict_reason"],
        "narrative_only": fields["narrative_only"],
        "enters_canonical_computation": False,
    }


def _range_resolution(repo: Path) -> tuple[object, str, str]:
    base = _git(repo, ["rev-parse", "HEAD~1"]).strip()
    head = _git(repo, ["rev-parse", "HEAD"]).strip()
    resolved = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.RANGE,
            base=base,
            head=head,
        )
    )
    return resolved, base, head


def test_cache_key_binds_source_config_rule_operator_feed() -> None:
    expected = json.loads((FIXTURE_DIR / "expected-cache-key.json").read_text(encoding="utf-8"))
    version, digest = operator_set_binding()
    assert version == expected["operator_version"]
    assert digest == expected["operator_digest"]
    left = build_change_cache_key(
        source_digest="aa" * 32,
        config_digest=expected["empty_config_digest"],
        rule_digest=RULE,
        feed_digest=None,
    )
    right = build_change_cache_key(
        source_digest="bb" * 32,
        config_digest=expected["empty_config_digest"],
        rule_digest=RULE,
        feed_digest=None,
    )
    assert left.digest != right.digest
    assert left.operator_digest == right.operator_digest
    assert left.feed_binding == expected["feed_absent"]
    config_changed = build_change_cache_key(
        source_digest=left.source_digest,
        config_digest=digest_canonical({"parameters_by_rule": {"r": {"n": 1}}}),
        rule_digest=RULE,
        feed_digest=None,
    )
    rule_changed = build_change_cache_key(
        source_digest=left.source_digest,
        config_digest=left.config_digest,
        rule_digest=digest_canonical({"ruleset": "other"}),
        feed_digest=None,
    )
    feed_changed = build_change_cache_key(
        source_digest=left.source_digest,
        config_digest=left.config_digest,
        rule_digest=RULE,
        feed_digest="cc" * 32,
    )
    assert len({left.digest, config_changed.digest, rule_changed.digest, feed_changed.digest}) == 4


def test_rename_joins_e05_2_identities_without_finding_churn(tmp_path: Path) -> None:
    expected = json.loads(
        (FIXTURE_DIR / "expected-rename-lineage.json").read_text(encoding="utf-8")
    )
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    commit_all(repo, "base")
    _git(repo, ["mv", "src/app.py", "src/service.py"])
    commit_all(repo, "rename")
    resolved, _, _ = _range_resolution(repo)
    published = publish_change_facts(
        ChangeFactsRequest(
            repository_key="demo",
            git_inputs=resolved,
            rule_digest=RULE,
            previous_findings=(
                PreviousFinding(
                    finding_key="secret.hardcoded:src/app.py",
                    rule_id="secret.hardcoded",
                    path="src/app.py",
                ),
            ),
        )
    )
    event = next(item for item in published.events if item.status is FileChangeStatus.RENAMED)
    assert event.lineage_status is LineageStatus.UNIQUE
    assert event.file_id == expected["file_id"]
    assert event.previous_file_id == expected["previous_file_id"]
    assert event.component_id == expected["component_id"]
    match = published.finding_matches[0]
    assert match.match_kind.value == expected["match_kind"]
    assert match.location_moved is expected["location_moved"]
    assert match.finding_churn is expected["finding_churn"]
    assert match.current_path == "src/service.py"
    identities = {item.path: item.file_id for item in published.graph_identities}
    assert identities["src/app.py"] == expected["previous_file_id"]
    assert identities["src/service.py"] == expected["file_id"]
    repeats = [
        publish_change_facts(
            ChangeFactsRequest(
                repository_key="demo",
                git_inputs=resolved,
                rule_digest=RULE,
            )
        ).analysis_digest
        for _ in range(3)
    ]
    assert repeats[0] == repeats[1] == repeats[2]


def test_ambiguous_lineage_is_unknown_and_falls_back() -> None:
    expected = json.loads(
        (FIXTURE_DIR / "expected-ambiguous-lineage.json").read_text(encoding="utf-8")
    )
    by_path = identities_for_paths(
        ("src/a.py", "src/b.py", "src/c.py"),
        repository_key="demo",
        manifest_directories=("src",),
    )
    renamed = ChangedFileFact(
        path="src/c.py",
        old_path="src/a.py",
        status=FileChangeStatus.RENAMED,
        content_class=FileContentClass.TEXT,
        unit_class=FileUnitClass.SOURCE,
        added_lines=0,
        deleted_lines=0,
        component_id=None,
        binary=False,
        submodule=False,
    )
    events = normalize_change_events(
        (renamed,),
        by_path=by_path,
        history_aliases={"src/c.py": ("src/a.py", "src/b.py")},
    )
    assert events[0].lineage_status.value == expected["lineage_status"]
    matches = match_findings_across_lineage(
        (
            PreviousFinding(
                finding_key="rule:src/a.py",
                rule_id="rule",
                path="src/a.py",
            ),
        ),
        events,
        by_path=by_path,
    )
    assert matches[0].match_kind.value == expected["match_kind"]
    assert matches[0].finding_churn is expected["finding_churn"]
    assert matches[0].location_moved is expected["location_moved"]


def test_unsupported_mapping_stays_explicit() -> None:
    by_path = identities_for_paths(("src/app.py",), repository_key="demo")
    unknown = ChangedFileFact(
        path="../outside.py",
        old_path=None,
        status=FileChangeStatus.MODIFIED,
        content_class=FileContentClass.TEXT,
        unit_class=FileUnitClass.OTHER,
        added_lines=1,
        deleted_lines=0,
        component_id=None,
        binary=False,
        submodule=False,
    )
    events = normalize_change_events((unknown,), by_path=by_path)
    assert events[0].mapping_status is MappingJoinStatus.UNSUPPORTED
    assert events[0].file_id is None


def test_narrative_only_does_not_change_analysis_digest(tmp_path: Path) -> None:
    expected = json.loads(
        (FIXTURE_DIR / "expected-narrative-isolation.json").read_text(encoding="utf-8")
    )
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    commit_all(repo, "base")
    write(repo, "src/app.py", "print(2)\n")
    commit_all(repo, "edit")
    resolved_one, _, _ = _range_resolution(repo)
    first = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.RANGE,
            base=resolved_one.resolved_base,
            head=resolved_one.resolved_head,
            supplied_context=_context_payload(title="one"),
        )
    )
    second = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.RANGE,
            base=resolved_one.resolved_base,
            head=resolved_one.resolved_head,
            supplied_context=_context_payload(title="two"),
        )
    )
    pub_one = publish_change_facts(
        ChangeFactsRequest(repository_key="demo", git_inputs=first, rule_digest=RULE)
    )
    pub_two = publish_change_facts(
        ChangeFactsRequest(repository_key="demo", git_inputs=second, rule_digest=RULE)
    )
    assert pub_one.analysis_digest == pub_two.analysis_digest
    assert pub_one.supplied_context_digest != pub_two.supplied_context_digest
    assert pub_one.history_message_provenance == expected["history_message_provenance"]


def test_bugfix_markers_are_separate_provenance(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    commit_dated(repo, "fixed login timeout", unix=EVAL_UNIX - 2 * DAY)
    write(repo, "src/app.py", "print(2)\n")
    commit_dated(repo, "add logging", unix=EVAL_UNIX - DAY)
    resolved, _, _ = _range_resolution(repo)
    history = build_history_index(
        HistoryIndexRequest(repository_root=repo, evaluation_time=EVAL)
    )
    published = publish_change_facts(
        ChangeFactsRequest(
            repository_key="demo",
            git_inputs=resolved,
            history=history,
            rule_digest=RULE,
        )
    )
    assert published.bugfix_marker_digest is not None
    without_history = publish_change_facts(
        ChangeFactsRequest(repository_key="demo", git_inputs=resolved, rule_digest=RULE)
    )
    assert published.bugfix_marker_digest != published.analysis_digest
    assert published.bugfix_marker_digest != without_history.analysis_digest
    marked = [item.sha for item in history.included if item.bugfix_marker]
    assert marked
    assert history.bugfix_markers.proven_defects is False
    assert published.productivity_claim is False
    provenance = "contextual_bugfix_markers_separate_from_analysis"
    assert published.history_message_provenance == provenance


def test_m25_join_uses_e05_2_ids_and_subject_denominators(tmp_path: Path) -> None:
    expected = json.loads((FIXTURE_DIR / "expected-m25-joined.json").read_text(encoding="utf-8"))
    repo = init_repo(tmp_path / "repo")
    write(repo, ".mailmap", "Alice Example <alice@ex.test> Ali Alias <ali@ex.test>\n")
    write(repo, "alpha.txt", _lines("a", 4))
    commit_dated(
        repo,
        "alice alpha",
        unix=EVAL_UNIX - 4 * DAY,
        author_name="Ali Alias",
        author_email="ali@ex.test",
    )
    write(repo, "beta.txt", _lines("b", 2))
    commit_dated(
        repo,
        "alice beta",
        unix=EVAL_UNIX - 3 * DAY,
        author_name="Ali Alias",
        author_email="ali@ex.test",
    )
    write(repo, "beta.txt", _lines("b", 4))
    commit_dated(
        repo,
        "bob beta",
        unix=EVAL_UNIX - 2 * DAY,
        author_name="Bob",
        author_email="bob@ex.test",
    )
    root = _git(repo, ["rev-list", "--max-parents=0", "HEAD"]).strip().splitlines()[-1]
    head = _git(repo, ["rev-parse", "HEAD"]).strip()
    resolved = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.RANGE,
            base=root,
            head=head,
        )
    )
    history = build_history_index(
        HistoryIndexRequest(
            repository_root=repo,
            evaluation_time=EVAL,
            component_map={"alpha.txt": "comp-a", "beta.txt": "comp-b"},
        )
    )
    published = publish_change_facts(
        ChangeFactsRequest(
            repository_key="demo",
            git_inputs=resolved,
            history=history,
            rule_digest=RULE,
        )
    )
    repo_c = next(
        item for item in published.concentrations if item.scope is ConcentrationScope.REPOSITORY
    )
    assert repo_c.largest_share_serialized == expected["repository_largest_share_serialized"]
    assert repo_c.contributors_to_50pct == expected["repository_contributors_to_50pct"]
    assert repo_c.attributable_lines == expected["repository_attributable_lines"]
    assert published.organizational_bus_factor is expected["organizational_bus_factor"]
    assert published.productivity_claim is expected["productivity_claim"]
    for note in expected["notes_required"]:
        assert note in repo_c.notes
    subjects = {
        item.subject_id
        for item in published.concentrations
        if item.scope is ConcentrationScope.FILE
    }
    assert expected["m25_file_alpha_id"] in subjects
    assert expected["m25_file_beta_id"] in subjects
    if published.cochange:
        joined = published.cochange[0]
        source = next(
            item
            for item in history.cochange
            if item.left == joined.left and item.right == joined.right
        )
        assert joined.support == source.support
        assert joined.union == source.union


def test_capabilities_expose_bounds_and_unknown_reasons(tmp_path: Path) -> None:
    source = init_repo(tmp_path / "source")
    write(source, "a.txt", "one\n")
    commit_dated(source, "old", unix=EVAL_UNIX - 40 * DAY)
    write(source, "a.txt", "one\ntwo\n")
    commit_dated(source, "new", unix=EVAL_UNIX - DAY)
    clone = tmp_path / "shallow"
    _git(tmp_path, ["clone", "--no-local", "--depth", "1", str(source), str(clone)])
    write(clone, "a.txt", "one\ntwo\nthree\n")
    _git(clone, ["add", "-A"])
    commit_dated(clone, "shallow edit", unix=EVAL_UNIX - 1)
    resolved, _, _ = _range_resolution(clone)
    history = build_history_index(
        HistoryIndexRequest(repository_root=clone, evaluation_time=EVAL)
    )
    published = publish_change_facts(
        ChangeFactsRequest(
            repository_key="demo",
            git_inputs=resolved,
            history=history,
            rule_digest=RULE,
        )
    )
    m24 = next(item for item in published.capabilities if item.capability_id == "M24")
    assert m24.requested_window_days == 180
    assert m24.requested_max_commits == 1000
    assert m24.observed_commit_count >= 1
    assert m24.complete_window is False
    assert m24.unknown_reasons


def test_selective_full_match_allows_recompute_mismatch_falls_back(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    commit_all(repo, "base")
    write(repo, "src/app.py", "print(2)\n")
    commit_all(repo, "edit")
    resolved, _, _ = _range_resolution(repo)
    artifacts = artifacts_from_semantic_payloads(
        inventory_paths=("src/app.py",),
        finding_keys=("secret.hardcoded:src/app.py",),
    )
    other = artifacts_from_semantic_payloads(
        inventory_paths=("src/app.py",),
        finding_keys=("other.rule:src/app.py",),
    )
    published = publish_change_facts(
        ChangeFactsRequest(
            repository_key="demo",
            git_inputs=resolved,
            rule_digest=RULE,
            reference_cache_key=build_change_cache_key(
                source_digest="dd" * 32,
                config_digest=None,
                rule_digest=RULE,
                feed_digest=None,
            ),
            incremental_artifacts=artifacts,
            full_reference_artifacts=artifacts,
            selective_scan_complete=True,
        )
    )
    assert published.schema_name == CHANGE_FACTS_SCHEMA
    assert published.reuse.decision is ReuseDecision.RECOMPUTE
    assert published.reuse.fallback_to_full is False
    assert published.reuse.semantic_equivalent is True
    mismatch = publish_change_facts(
        ChangeFactsRequest(
            repository_key="demo",
            git_inputs=resolved,
            rule_digest=RULE,
            reference_cache_key=published.cache_key,
            incremental_artifacts=artifacts,
            full_reference_artifacts=other,
            selective_scan_complete=True,
        )
    )
    assert mismatch.reuse.fallback_to_full is True
    assert mismatch.reuse.decision is ReuseDecision.FULL_REBUILD
    assert "selective_full_not_equivalent" in mismatch.reuse.reasons
    feed_mismatch = evaluate_reuse_against_full(
        published.cache_key,
        build_change_cache_key(
            source_digest=published.cache_key.source_digest,
            config_digest=published.cache_key.config_digest,
            rule_digest=RULE,
            feed_digest="ee" * 32,
        ),
        events=published.events,
        git_inputs=resolved,
    )
    assert feed_mismatch.fallback_to_full is True
    assert "incompatible_reference_bindings" in feed_mismatch.reasons
    assert "feed" in feed_mismatch.mismatched_bindings


def test_insufficient_git_comparison_falls_back(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write(repo, "src/app.py", "print(1)\n")
    commit_all(repo, "base")
    write(repo, "assets/logo.bin", b"\x00\xff")
    commit_all(repo, "binary")
    resolved, _, _ = _range_resolution(repo)
    published = publish_change_facts(
        ChangeFactsRequest(
            repository_key="demo",
            git_inputs=resolved,
            rule_digest=RULE,
            reference_cache_key=build_change_cache_key(
                source_digest="ff" * 32,
                config_digest=None,
                rule_digest=RULE,
                feed_digest=None,
            ),
        )
    )
    assert resolved.full_comparison is False
    assert published.reuse.fallback_to_full is True
    assert "insufficient_git_comparison" in published.reuse.reasons


def test_series_pair_change_facts_bind_range_identity(tmp_path: Path) -> None:
    from tests.application.incremental.test_r2_p06_trend_series import (
        LATER_PATH,
        _five_commit_adversarial,
    )

    repo, shas = _five_commit_adversarial(tmp_path / "repo")
    adjacent = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.RANGE,
            base=shas[0],
            head=shas[1],
        )
    )
    span = resolve_git_inputs(
        GitInputRequest(
            repository_root=repo,
            mode=GitInputMode.RANGE,
            base=shas[0],
            head=shas[4],
        )
    )
    assert adjacent.resolved_base == shas[0]
    assert adjacent.resolved_head == shas[1]
    assert {item.path for item in adjacent.files} == {"src/app.js"}
    assert LATER_PATH not in {item.path for item in adjacent.files}
    assert span.resolved_head == shas[4]
    assert LATER_PATH in {item.path for item in span.files}
    published = publish_change_facts(
        ChangeFactsRequest(
            repository_key="trend-s1-s2",
            git_inputs=adjacent,
            rule_digest=RULE,
            reference_cache_key=build_change_cache_key(
                source_digest="aa" * 32,
                config_digest=None,
                rule_digest=RULE,
                feed_digest=None,
            ),
        )
    )
    assert {item.path for item in published.events} == {"src/app.js"}
    assert LATER_PATH not in {item.path for item in published.events}
    assert adjacent.resolved_base == shas[0]
    assert adjacent.resolved_head == shas[1]
