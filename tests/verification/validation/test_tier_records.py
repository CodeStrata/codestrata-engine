"""G50-D003: corpus tier records drive the release gate, not pin identity."""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

import pytest
from verification.validation.checks import check_budget_publication
from verification.validation.loader import load_bundle
from verification.validation.models import CheckStatus, CorpusTier
from verification.validation.release_gate import tier_execute
from verification.validation.release_gate.models import ReleaseGatePolicy, ReviewDecision
from verification.validation.release_gate.policy import load_policy
from verification.validation.release_gate.runner import _decision_from_report
from verification.validation.release_gate.tier_records import (
    RECORD_SCHEMA,
    TierRecord,
    bucket_for_files,
    freshness,
    load_records,
    measured_budgets,
    source_tree_digest,
    write_record,
)
from verification.validation.release_gate.tiers import (
    collect_repository_results,
    tier_failures,
    tiers_fully_executed,
)

REPO = Path(__file__).resolve().parents[4]
ENGINE = REPO / "engine"


def _record(repo_id: str, tier: CorpusTier, pin_sha: str, digest: str, **overrides) -> TierRecord:
    base = TierRecord(
        schema=RECORD_SCHEMA,
        repository_id=repo_id,
        tier=tier.value,
        pin_sha=pin_sha,
        checked_out_sha=pin_sha,
        status=CheckStatus.PASS.value,
        detail="assess exit 0",
        stage="complete",
        exit_code=0,
        wall_seconds=12.5,
        peak_rss_bytes=200_000_000,
        eligible_files=800,
        bucket=bucket_for_files(800),
        depth_class="supported_java",
        source_tree_digest=digest,
        engine_git_sha="abc123abc123",
        engine_tree_dirty=False,
        wheel_sha256="00" * 32,
        canonical_sha256="11" * 32,
        findings_sha256=None,
        host="test",
        python="3.12",
        recorded_at="2026-09-29T00:00:00+00:00",
    )
    return dataclasses.replace(base, **overrides)


def _write_all(results_dir: Path, digest: str, **overrides) -> None:
    bundle = load_bundle()
    for pin in (*bundle.dogfood, *bundle.external_large):
        status = CheckStatus.UNSUPPORTED if pin.depth_class == "partial_unsupported" else None
        record = _record(pin.id, pin.tier, pin.sha, digest, depth_class=pin.depth_class)
        if status is not None:
            record = dataclasses.replace(record, status=status.value)
        write_record(results_dir, dataclasses.replace(record, **overrides))


def _policy() -> ReleaseGatePolicy:
    return load_policy()


def test_bucket_boundaries() -> None:
    assert bucket_for_files(None) == "unknown"
    assert bucket_for_files(10_000) == "le_10k_files"
    assert bucket_for_files(10_001) == "le_100k_files"
    assert bucket_for_files(100_001) == "gt_100k_files"


def test_source_digest_ignores_docs_and_changes_with_source(tmp_path: Path) -> None:
    root = tmp_path / "engine"
    (root / "src" / "codestrata").mkdir(parents=True)
    (root / "src" / "codestrata" / "__init__.py").write_text("x = 1\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='c'\n", encoding="utf-8")
    (root / "docs").mkdir()
    first = source_tree_digest(root)
    (root / "docs" / "note.md").write_text("docs only\n", encoding="utf-8")
    assert source_tree_digest(root) == first
    (root / "src" / "codestrata" / "__pycache__").mkdir()
    (root / "src" / "codestrata" / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    assert source_tree_digest(root) == first
    (root / "src" / "codestrata" / "__init__.py").write_text("x = 2\n", encoding="utf-8")
    assert source_tree_digest(root) != first


def test_record_round_trip_and_freshness(tmp_path: Path) -> None:
    record = _record("doris", CorpusTier.EXTERNAL_LARGE, "a" * 40, "d" * 64)
    path = write_record(tmp_path, record)
    assert path.name == "doris.json"
    loaded = load_records(tmp_path)
    assert loaded["doris"] == record
    assert freshness(record, current_digest="d" * 64, pin_sha="a" * 40).fresh
    assert not freshness(record, current_digest="e" * 64, pin_sha="a" * 40).fresh
    assert not freshness(record, current_digest="d" * 64, pin_sha="b" * 40).fresh


def test_malformed_and_foreign_json_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "junk.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "other.json").write_text('{"schema": "something.else"}', encoding="utf-8")
    (tmp_path / "summary.json").write_text('{"schema": "codestrata.m33.tier-summary.v1"}')
    assert load_records(tmp_path) == {}


def test_without_records_every_pin_is_not_yet_due(tmp_path: Path) -> None:
    results = collect_repository_results(
        engine_root=ENGINE,
        policy=_policy(),
        remote_enabled=True,
        results_dir=tmp_path / "empty",
        current_digest="d" * 64,
    )
    pins = [r for r in results if not r.repository_id.startswith("tier:")]
    external = [r for r in pins if r.tier is CorpusTier.EXTERNAL_LARGE]
    assert len(external) == 50
    assert all(r.status is CheckStatus.NOT_YET_DUE for r in external)
    assert tiers_fully_executed(results, remote_enabled=True) is False
    assert tiers_fully_executed(results, remote_enabled=False) is False


def test_fresh_records_for_all_pins_count_as_executed(tmp_path: Path) -> None:
    digest = "d" * 64
    _write_all(tmp_path, digest)
    results = collect_repository_results(
        engine_root=ENGINE,
        policy=_policy(),
        remote_enabled=False,
        results_dir=tmp_path,
        current_digest=digest,
    )
    assert tiers_fully_executed(results, remote_enabled=False) is True
    assert tier_failures(results) == ()
    statuses = {r.status for r in results if r.tier is CorpusTier.EXTERNAL_LARGE}
    assert CheckStatus.UNSUPPORTED in statuses  # partial_unsupported is explicit, not PASS


def test_stale_records_are_not_executed(tmp_path: Path) -> None:
    _write_all(tmp_path, "old" * 21 + "x")
    results = collect_repository_results(
        engine_root=ENGINE,
        policy=_policy(),
        remote_enabled=True,
        results_dir=tmp_path,
        current_digest="new" * 21 + "x",
    )
    pins = [
        r
        for r in results
        if r.tier in {CorpusTier.DOGFOOD, CorpusTier.EXTERNAL_LARGE}
        and not r.repository_id.startswith("tier:")
    ]
    assert len(pins) == 51
    assert all(r.status is CheckStatus.NOT_YET_DUE for r in pins)
    assert all("stale record" in r.detail for r in pins)
    assert tiers_fully_executed(results, remote_enabled=True) is False


def test_one_missing_record_blocks_execution(tmp_path: Path) -> None:
    digest = "d" * 64
    _write_all(tmp_path, digest)
    (tmp_path / "kafka.json").unlink()
    results = collect_repository_results(
        engine_root=ENGINE,
        policy=_policy(),
        remote_enabled=True,
        results_dir=tmp_path,
        current_digest=digest,
    )
    assert tiers_fully_executed(results, remote_enabled=True) is False


def _decide(results, *, executed: bool, budgets: bool = True) -> ReviewDecision:
    return _decision_from_report(
        corpus_ok=True,
        regression_ok=True,
        gates=(),
        stories=(),
        m15_blocked=False,
        tiers_executed=executed,
        remote_enabled=False,
        exceptions=(),
        repository_results=results,
        budgets_published=budgets,
    )


def test_decision_passes_only_with_fresh_records_and_published_budgets(tmp_path: Path) -> None:
    digest = "d" * 64
    _write_all(tmp_path, digest)
    results = collect_repository_results(
        engine_root=ENGINE,
        policy=_policy(),
        remote_enabled=False,
        results_dir=tmp_path,
        current_digest=digest,
    )
    executed = tiers_fully_executed(results, remote_enabled=False)
    assert _decide(results, executed=executed) is ReviewDecision.PASS
    assert _decide(results, executed=executed, budgets=False) is ReviewDecision.BLOCKED
    assert _decide((), executed=False) is ReviewDecision.BLOCKED


def test_decision_fails_when_a_repository_failed(tmp_path: Path) -> None:
    digest = "d" * 64
    _write_all(tmp_path, digest)
    bundle = load_bundle()
    kafka = next(p for p in bundle.external_large if p.id == "kafka")
    write_record(
        tmp_path,
        _record(
            "kafka",
            CorpusTier.EXTERNAL_LARGE,
            kafka.sha,
            digest,
            status=CheckStatus.FAIL.value,
            detail="budget_exceeded",
        ),
    )
    results = collect_repository_results(
        engine_root=ENGINE,
        policy=_policy(),
        remote_enabled=False,
        results_dir=tmp_path,
        current_digest=digest,
    )
    assert [r.repository_id for r in tier_failures(results)] == ["kafka"]
    assert _decide(results, executed=True) is ReviewDecision.FAIL
    # A failure is still a FAIL when other pins are missing; it is never hidden as BLOCKED.
    (tmp_path / "doris.json").unlink()
    results = collect_repository_results(
        engine_root=ENGINE,
        policy=_policy(),
        remote_enabled=False,
        results_dir=tmp_path,
        current_digest=digest,
    )
    assert _decide(results, executed=False) is ReviewDecision.FAIL


def test_blocked_clone_keeps_gate_blocked(tmp_path: Path) -> None:
    digest = "d" * 64
    _write_all(tmp_path, digest)
    bundle = load_bundle()
    pin = bundle.external_large[0]
    write_record(
        tmp_path,
        _record(
            pin.id,
            CorpusTier.EXTERNAL_LARGE,
            pin.sha,
            digest,
            status=CheckStatus.BLOCKED.value,
            detail="clone: clone timed out",
            stage="clone",
        ),
    )
    results = collect_repository_results(
        engine_root=ENGINE,
        policy=_policy(),
        remote_enabled=False,
        results_dir=tmp_path,
        current_digest=digest,
    )
    assert _decide(results, executed=True) is ReviewDecision.BLOCKED


def test_measured_budgets_take_max_per_bucket(tmp_path: Path) -> None:
    records = {
        "a": _record("a", CorpusTier.EXTERNAL_LARGE, "1" * 40, "d" * 64, wall_seconds=10.0),
        "b": _record(
            "b",
            CorpusTier.EXTERNAL_LARGE,
            "2" * 40,
            "d" * 64,
            wall_seconds=40.0,
            peak_rss_bytes=900,
        ),
        "c": _record(
            "c",
            CorpusTier.EXTERNAL_LARGE,
            "3" * 40,
            "d" * 64,
            status=CheckStatus.BLOCKED.value,
            wall_seconds=999.0,
        ),
    }
    budgets = measured_budgets(records)
    bucket = budgets["le_10k_files"]
    assert bucket["count"] == 2
    assert bucket["max_wall_seconds"] == 40.0
    assert bucket["slowest"] == "b"
    assert bucket["max_peak_rss_bytes"] == 200_000_000


def test_budget_publication_requires_measurements_and_evidence(tmp_path: Path) -> None:
    bundle = load_bundle()
    unpublished = check_budget_publication(bundle, ENGINE)
    assert unpublished.status is CheckStatus.PASS
    window = dataclasses.replace(
        bundle.window,
        budgets_published=True,
        measured_budget_le_10k="",
        measured_budget_le_100k="",
        budget_evidence="",
    )
    bare = dataclasses.replace(bundle, window=window)
    assert check_budget_publication(bare, ENGINE).status is CheckStatus.FAIL
    evidence = tmp_path / "results" / "summary.json"
    evidence.parent.mkdir()
    evidence.write_text("{}", encoding="utf-8")
    measured = dataclasses.replace(
        window,
        measured_budget_le_10k="max 120s / 400MiB over 30 repos",
        measured_budget_le_100k="max 900s / 2GiB over 20 repos",
        budget_evidence="results/summary.json",
    )
    good = dataclasses.replace(bundle, window=measured)
    assert check_budget_publication(good, tmp_path).status is CheckStatus.PASS


def test_executor_refuses_without_maintainer_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODESTRATA_RUN_REMOTE_VALIDATION", raising=False)
    with pytest.raises(tier_execute.RemoteValidationDisabled):
        tier_execute.require_remote_opt_in("CODESTRATA_RUN_REMOTE_VALIDATION")
    assert tier_execute.main(["--all"]) == 2
    monkeypatch.setenv("CODESTRATA_RUN_REMOTE_VALIDATION", "1")
    tier_execute.require_remote_opt_in("CODESTRATA_RUN_REMOTE_VALIDATION")


def test_unapproved_mutations_flag_source_edits(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
        "PATH": __import__("os").environ["PATH"],
    }
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=env)
    (repo / "src.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True, env=env)
    (repo / "codestrata.toml").write_text("[repository]\n", encoding="utf-8")
    (repo / "reports").mkdir()
    (repo / "reports" / "x.json").write_text("{}", encoding="utf-8")
    assert tier_execute.unapproved_mutations(repo) == []
    (repo / "src.txt").write_text("changed\n", encoding="utf-8")
    assert tier_execute.unapproved_mutations(repo) == ["src.txt"]


def test_run_measured_reports_timeout_and_memory(tmp_path: Path) -> None:
    import sys

    quick = tier_execute.run_measured(
        [sys.executable, "-c", "print('ok')"],
        cwd=tmp_path,
        env=dict(__import__("os").environ),
        timeout_s=60,
    )
    assert quick.exit_code == 0
    assert quick.timed_out is False
    assert quick.peak_rss_bytes is None or quick.peak_rss_bytes > 0
    allocated = tier_execute.run_measured(
        [sys.executable, "-c", "block = bytearray(80 * 1024 * 1024); import time; time.sleep(1.5)"],
        cwd=tmp_path,
        env=dict(__import__("os").environ),
        timeout_s=30,
    )
    assert allocated.exit_code == 0
    assert allocated.peak_rss_bytes is not None
    assert allocated.peak_rss_bytes > 50 * 1024 * 1024
    slow = tier_execute.run_measured(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        cwd=tmp_path,
        env=dict(__import__("os").environ),
        timeout_s=1,
    )
    assert slow.timed_out is True
    assert slow.exit_code == 124
