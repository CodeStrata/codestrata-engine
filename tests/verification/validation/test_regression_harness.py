"""E15.2 harness: three-repeat semantics, adversarial kinds, quality floor."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from verification.validation.regression.adversarial import (
    classify_cancellation,
    classify_corruption,
    classify_report_escaping,
    classify_resource_exhaustion,
    classify_unknown_coverage,
)
from verification.validation.regression.models import HarnessStatus
from verification.validation.regression.policy import load_policy
from verification.validation.regression.runner import run_harness, undeclared_field_breaks_repeats
from verification.validation.regression.semantic import full_incremental_parity, semantic_digest
from verification.validation.regression.skips import evaluate_skip_inflation

from codestrata.reporters.html_rendering import escape_html

REPO = Path(__file__).resolve().parents[4]
ENGINE = REPO / "engine"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "e15.2"
EXPECTED = FIXTURES / "expected-passing-ids.json"


def _fixture_json(*parts: str) -> dict[str, Any]:
    payload: Any = json.loads((FIXTURES.joinpath(*parts)).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("fixture is not a JSON object")
    return payload


def test_adversarial_kinds_use_live_engine_not_authored_json(tmp_path: Path) -> None:
    from verification.validation.regression.execute import (
        live_corruption,
        live_disk_full,
        live_output_collision,
        live_retention,
        live_tamper,
        live_unknown_coverage,
    )
    from verification.validation.regression.runner import evaluate_adversarial

    empty = tmp_path / "no-authored-json"
    empty.mkdir()
    policy = load_policy()
    outcomes = evaluate_adversarial(policy, empty)
    ids = {item.id for item in outcomes}
    assert "adversarial:corruption" in ids
    assert "adversarial:disk-full" in ids
    assert "contract:tamper" in ids
    assert all(item.status is HarnessStatus.PASS for item in outcomes)
    assert live_corruption()["corrupt"] is True
    assert live_disk_full()["disk_full"] is True
    _before, _after, collision = live_output_collision()
    assert collision["status"] == "ERROR"
    _present, retention = live_retention()
    assert retention["retained"] is True
    tamper, expected = live_tamper()
    assert tamper["status"] == "TAMPERED"
    assert tamper["body_digest"] != expected
    unknown = live_unknown_coverage()
    assert unknown["coverage_status"] == "UNKNOWN"


def test_harness_passes_on_planted_fixtures() -> None:
    report = run_harness(engine_root=ENGINE, fixture_dir=FIXTURES, platform="win32")
    failed = [item for item in report.outcomes if item.status is not HarnessStatus.PASS]
    assert report.ok, failed
    assert report.status is HarnessStatus.PASS
    ids = [item.id for item in report.outcomes]
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert ids == expected["ids"]


def test_three_repeats_ignore_only_declared_operational_fields() -> None:
    from verification.validation.regression.execute import live_repeat_payload

    policy = load_policy()
    runs = [live_repeat_payload("planted-local", index) for index in (1, 2, 3)]
    fields = policy.operational_fields
    digest = semantic_digest(runs[0], fields)
    assert semantic_digest(runs[1], fields) == digest
    assert semantic_digest(runs[2], fields) == digest
    assert len({item["run_id"] for item in runs}) == 3
    assert runs[0]["functions"]
    assert runs[0]["maintainability_index"] is None


def test_undeclared_field_change_fails_repeats() -> None:
    policy = load_policy()
    good = _fixture_json("planted-local", "run-1.json")
    bad = _fixture_json("negative", "undeclared-variation.json")
    assert undeclared_field_breaks_repeats([good, good, bad], policy.operational_fields)


def test_budget_and_honesty_negatives() -> None:
    budget = _fixture_json("negative", "budget-as-pass.json")
    assert classify_resource_exhaustion(budget).status is HarnessStatus.FAIL
    empty = _fixture_json("negative", "healthy-empty-corruption.json")
    assert classify_corruption(empty).status is HarnessStatus.FAIL
    cancelled = _fixture_json("negative", "cancel-as-pass.json")
    assert classify_cancellation(cancelled).status is HarnessStatus.FAIL
    unknown = _fixture_json("negative", "unknown-as-complete.json")
    assert classify_unknown_coverage(unknown).status is HarnessStatus.FAIL


def test_skip_inflation_is_fail() -> None:
    policy = load_policy()
    payload = _fixture_json("negative", "skip-inflation.json")
    reasons = payload["reasons"]
    assert isinstance(reasons, list)
    outcome = evaluate_skip_inflation(
        [str(item) for item in reasons],
        policy.disclosed_skips,
        platform="win32",
    )
    assert outcome.status is HarnessStatus.FAIL


def test_full_incremental_divergence_fails() -> None:
    policy = load_policy()
    full = _fixture_json("parity", "full.json")
    divergent = _fixture_json("negative", "incremental-divergent.json")
    assert full_incremental_parity(full, divergent, policy.operational_fields) is False


def test_unescaped_html_fails() -> None:
    marker = '<script>alert("xss")</script>'
    assert classify_report_escaping(marker, marker).status is HarnessStatus.FAIL
    assert classify_report_escaping(escape_html(marker), marker).status is HarnessStatus.PASS


def test_coverage_floor_is_combined_not_branch_threshold() -> None:
    policy = load_policy()
    assert policy.coverage.fail_under == 80
    assert policy.coverage.branch is True
    assert policy.coverage.separate_branch_threshold is False
    assert policy.repeats == 3
    assert policy.scan.may_run_assessed_builds_or_tests is False
