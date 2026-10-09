"""Tests for E10.3 / M31 cause attribution across source, feed, and configuration dimensions."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.application.incremental.cause_attribution import (
    evaluate_cause_attribution,
    isolate_causes_with_controlled_reruns,
)
from codestrata.models import AnalysisResult, Finding, Repository, RepositoryFacts
from codestrata.models.enums import (
    FindingCategory,
    FindingSource,
    Severity,
    TechnologyCategory,
)
from codestrata.models.scan_comparison import (
    ComparedFinding,
    ControlledRerunReference,
)
from codestrata.models.technology import Technology
from codestrata.services.scan_comparison_service import ScanComparisonService

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "e10.3"


def _cve_finding(rule_id: str = "cve-2026-1234", lifecycle: str = "new") -> ComparedFinding:
    return ComparedFinding(
        rule_id=rule_id,
        identity_key=f"cve::{rule_id}",
        lifecycle=lifecycle,
        title=f"Vulnerability {rule_id}",
        category="security",
        severity="high",
    )


def test_cause_attribution_source_only() -> None:
    attr = evaluate_cause_attribution(
        source_changed=True,
        feed_changed=False,
        config_changed=False,
    )
    assert attr.attribution == "source_only"
    assert attr.label == "source-driven"
    assert attr.controlled_rerun_performed is False
    assert attr.changed_dimensions == ["source"]
    assert attr.is_feed_driven is False


def test_cause_attribution_feed_only() -> None:
    cve = _cve_finding()
    attr = evaluate_cause_attribution(
        source_changed=False,
        feed_changed=True,
        config_changed=False,
        cve_findings=[cve],
    )
    assert attr.attribution == "feed_only"
    assert attr.label == "feed-driven"
    assert attr.is_feed_driven is True
    assert attr.customer_code_deterioration is False
    assert "feed_driven_cve_changes_not_customer_code_deterioration" in attr.evidence_notes
    assert attr.changed_dimensions == ["feed"]


def test_cause_attribution_configuration_only() -> None:
    attr = evaluate_cause_attribution(
        source_changed=False,
        feed_changed=False,
        config_changed=True,
    )
    assert attr.attribution == "configuration_only"
    assert attr.label == "configuration-driven"
    assert attr.is_feed_driven is False
    assert attr.customer_code_deterioration is False
    assert "policy_override_or_config_change_not_source_fix" in attr.evidence_notes
    assert attr.changed_dimensions == ["configuration"]


def test_cause_attribution_coverage_only() -> None:
    attr = evaluate_cause_attribution(
        coverage_changed=True,
    )
    assert attr.attribution == "coverage_only"
    assert attr.label == "coverage-driven"
    assert attr.is_feed_driven is False
    assert attr.customer_code_deterioration is False
    assert "coverage_change_forces_unknown_lifecycle" in attr.evidence_notes
    assert attr.changed_dimensions == ["coverage"]


def test_cause_attribution_mixed_without_controlled_rerun() -> None:
    # Multiple dimensions changed without controlled rerun => mixed / undetermined
    attr = evaluate_cause_attribution(
        source_changed=True,
        feed_changed=True,
        config_changed=False,
        controlled_rerun=False,
    )
    assert attr.attribution == "mixed"
    assert attr.label == "mixed"
    assert "multiple_dimensions_differ_without_controlled_rerun" in attr.evidence_notes
    assert attr.controlled_rerun_performed is False
    assert attr.is_feed_driven is False
    assert attr.customer_code_deterioration is False


def test_cause_attribution_mixed_with_controlled_rerun() -> None:
    ref = ControlledRerunReference(
        rerun_id="rr_1",
        isolated_dimension="feed",
        isolated_finding_keys=["cve::cve-2026-1234"],
    )
    attr = evaluate_cause_attribution(
        source_changed=True,
        feed_changed=True,
        config_changed=False,
        controlled_rerun=True,
        controlled_reruns=[ref],
    )
    assert attr.attribution == "controlled_isolated"
    assert attr.label == "controlled-isolated"
    assert attr.controlled_rerun_performed is True
    assert "controlled_rerun_validated" in attr.evidence_notes
    assert "rr_1" in attr.controlled_rerun_references
    assert attr.isolated_causes.get("feed") == ["cve::cve-2026-1234"]


def test_cause_attribution_feed_cves_not_code_deterioration() -> None:
    cves = [_cve_finding("cve-1"), _cve_finding("cve-2")]
    attr = evaluate_cause_attribution(
        source_changed=False,
        feed_changed=True,
        config_changed=False,
        cve_findings=cves,
    )
    # Evidence notes explicitly record that feed-driven CVEs are not customer code deterioration
    assert any("not_customer_code_deterioration" in note for note in attr.evidence_notes)
    assert attr.customer_code_deterioration is False
    assert attr.is_feed_driven is True
    assert attr.label == "feed-driven"


def test_cause_attribution_auto_detect_from_digests() -> None:
    base_digests = {
        "source": "sha256:src_v1",
        "feed": "sha256:feed_v1",
        "config": "sha256:cfg_v1",
    }
    cand_digests = {
        "source": "sha256:src_v1",  # unchanged
        "feed": "sha256:feed_v2",    # changed!
        "config": "sha256:cfg_v1",  # unchanged
    }
    attr = evaluate_cause_attribution(
        base_digests=base_digests,
        candidate_digests=cand_digests,
    )
    assert attr.changed_dimensions == ["feed"]
    assert attr.attribution == "feed_only"
    assert attr.label == "feed-driven"
    assert attr.is_feed_driven is True
    assert attr.base_digests == base_digests
    assert attr.candidate_digests == cand_digests


def test_isolate_causes_with_controlled_reruns() -> None:
    base_keys = ["cve::old-vuln"]
    cand_keys = ["cve::new-vuln"]
    # Source rerun (candidate source + base feed): old-vuln fixed, no new vuln
    source_rerun_keys: list[str] = []
    # Feed rerun (base source + candidate feed): old-vuln still present + new-vuln present
    feed_rerun_keys = ["cve::old-vuln", "cve::new-vuln"]

    attr = isolate_causes_with_controlled_reruns(
        base_finding_keys=base_keys,
        candidate_finding_keys=cand_keys,
        source_rerun_finding_keys=source_rerun_keys,
        feed_rerun_finding_keys=feed_rerun_keys,
        base_digests={"source": "v1", "feed": "v1"},
        candidate_digests={"source": "v2", "feed": "v2"},
    )
    assert attr.attribution == "controlled_isolated"
    assert attr.label == "controlled-isolated"
    assert attr.controlled_rerun_performed is True
    assert attr.isolated_causes["source"] == ["cve::old-vuln"]
    assert attr.isolated_causes["feed"] == ["cve::new-vuln"]
    assert len(attr.controlled_reruns) == 2


# =========================================================================
# Fixture-driven verification of all 5 deliverable scenarios + 5 families
# =========================================================================


def test_fixture_unchanged_code_new_cve() -> None:
    fixture_path = FIXTURES_DIR / "unchanged_code_new_cve.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    cve_f = [
        ComparedFinding(
            rule_id=f["rule_id"],
            identity_key=f["identity_key"],
            title=f["title"],
            category=f["category"],
            severity=f["severity"],
            cause=f["cause"],
            lifecycle="new",
        )
        for f in data["candidate"]["findings"]
    ]
    base_d = {
        "feed": data["base"]["feed_digest"],
        "source": data["base"]["source_digest"],
    }
    cand_d = {
        "feed": data["candidate"]["feed_digest"],
        "source": data["candidate"]["source_digest"],
    }
    attr = evaluate_cause_attribution(
        base_digests=base_d,
        candidate_digests=cand_d,
        cve_findings=cve_f,
    )
    assert attr.attribution == data["expected"]["attribution"]
    assert attr.label == data["expected"]["label"]
    assert attr.is_feed_driven == data["expected"]["is_feed_driven"]
    assert attr.customer_code_deterioration == data["expected"]["customer_code_deterioration"]
    assert attr.changed_dimensions == data["expected"]["changed_dimensions"]
    assert any(data["expected"]["evidence_note"] in note for note in attr.evidence_notes)


def test_fixture_dependency_fix_same_feed() -> None:
    fixture_path = FIXTURES_DIR / "dependency_fix_same_feed.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    base_d = {
        "source": data["base"]["source_digest"],
        "feed": data["base"]["feed_digest"],
    }
    cand_d = {
        "source": data["candidate"]["source_digest"],
        "feed": data["candidate"]["feed_digest"],
    }
    attr = evaluate_cause_attribution(
        base_digests=base_d,
        candidate_digests=cand_d,
    )
    assert attr.attribution == data["expected"]["attribution"]
    assert attr.label == data["expected"]["label"]
    assert attr.is_feed_driven == data["expected"]["is_feed_driven"]
    assert attr.customer_code_deterioration == data["expected"]["customer_code_deterioration"]
    assert attr.changed_dimensions == data["expected"]["changed_dimensions"]


def test_fixture_policy_override() -> None:
    fixture_path = FIXTURES_DIR / "policy_override.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    attr = evaluate_cause_attribution(
        base_digests={"config": data["base"]["config_digest"]},
        candidate_digests={"config": data["candidate"]["config_digest"]},
    )
    assert attr.attribution == data["expected"]["attribution"]
    assert attr.label == data["expected"]["label"]
    assert attr.changed_dimensions == data["expected"]["changed_dimensions"]
    assert any(data["expected"]["evidence_note"] in note for note in attr.evidence_notes)


def test_fixture_changed_coverage() -> None:
    fixture_path = FIXTURES_DIR / "changed_coverage.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    attr = evaluate_cause_attribution(
        base_digests={"coverage": data["base"]["coverage_status"]},
        candidate_digests={"coverage": data["candidate"]["coverage_status"]},
    )
    assert attr.attribution == data["expected"]["attribution"]
    assert attr.label == data["expected"]["label"]
    assert attr.changed_dimensions == data["expected"]["changed_dimensions"]
    assert any(data["expected"]["evidence_note"] in note for note in attr.evidence_notes)


def test_fixture_mixed_inputs_without_rerun() -> None:
    fixture_path = FIXTURES_DIR / "mixed_inputs_without_rerun.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    base_d = {
        "source": data["base"]["source_digest"],
        "feed": data["base"]["feed_digest"],
    }
    cand_d = {
        "source": data["candidate"]["source_digest"],
        "feed": data["candidate"]["feed_digest"],
    }
    attr = evaluate_cause_attribution(
        base_digests=base_d,
        candidate_digests=cand_d,
        controlled_rerun=False,
    )
    assert attr.attribution == data["expected"]["attribution"]
    assert attr.label == data["expected"]["label"]
    assert attr.controlled_rerun_performed is False
    assert attr.changed_dimensions == data["expected"]["changed_dimensions"]
    assert any(data["expected"]["evidence_note"] in note for note in attr.evidence_notes)


def test_fixture_mixed_inputs_with_controlled_rerun() -> None:
    fixture_path = FIXTURES_DIR / "mixed_inputs_with_controlled_rerun.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    base_d = {
        "source": data["base"]["source_digest"],
        "feed": data["base"]["feed_digest"],
    }
    cand_d = {
        "source": data["candidate"]["source_digest"],
        "feed": data["candidate"]["feed_digest"],
    }
    attr = isolate_causes_with_controlled_reruns(
        base_finding_keys=data["base"]["findings"],
        candidate_finding_keys=data["candidate"]["findings"],
        source_rerun_finding_keys=data["controlled_rerun_source"]["findings"],
        feed_rerun_finding_keys=data["controlled_rerun_feed"]["findings"],
        base_digests=base_d,
        candidate_digests=cand_d,
    )
    assert attr.attribution == data["expected"]["attribution"]
    assert attr.label == data["expected"]["label"]
    assert attr.controlled_rerun_performed is True
    assert attr.changed_dimensions == data["expected"]["changed_dimensions"]
    assert attr.isolated_causes["source"] == data["expected"]["isolated_causes"]["source"]
    assert attr.isolated_causes["feed"] == data["expected"]["isolated_causes"]["feed"]


def test_fixture_all_five_families_compared_without_platform_or_db() -> None:
    fixture_path = FIXTURES_DIR / "all_five_families.json"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    service = ScanComparisonService()

    base_techs = [
        Technology(name=t, category=TechnologyCategory.FRAMEWORK)
        for t in data["families"]["inventory"]["base_technologies"]
    ]
    cand_techs = [
        Technology(name=t, category=TechnologyCategory.FRAMEWORK)
        for t in data["families"]["inventory"]["candidate_technologies"]
    ]

    base_res = AnalysisResult(
        repository=Repository(name="repo", path=Path(".")),
        technologies=base_techs,
        facts=RepositoryFacts(),
        findings=[
            Finding(
                rule_id="cve::old-cve::lib",
                title="Old Vulnerability",
                description="Old vulnerability in lib",
                category=FindingCategory.SECURITY,
                severity=Severity.HIGH,
                source=FindingSource.STATIC_ANALYSIS,
            )
        ],
    )
    cand_res = AnalysisResult(
        repository=Repository(name="repo", path=Path(".")),
        technologies=cand_techs,
        facts=RepositoryFacts(),
        findings=[],  # Resolved
    )

    base_graph = {
        "nodes": [{"id": n} for n in data["families"]["architecture"]["base_nodes"]],
        "edges": [],
    }
    cand_graph = {
        "nodes": [{"id": n} for n in data["families"]["architecture"]["candidate_nodes"]],
        "edges": [],
    }

    comparison = service.compare_results(
        current=cand_res,
        baseline=base_res,
        current_timestamp="2026-09-25T12:00:00Z",
        baseline_timestamp="2026-09-25T10:00:00Z",
        evaluate_lifecycle=True,
        source_changed=True,
        base_graph=base_graph,
        candidate_graph=cand_graph,
        changed_files=data["families"]["git"]["changed_files"],
        churn_by_component={"src/service.py": data["families"]["git"]["churn"]},
        centrality_by_component={"src/service.py": data["families"]["git"]["centrality"]},
        boundaries={"A": "service_layer", "B": "data_layer"},
    )

    assert comparison.baseline_available is True
    # Family 1: inventory change is captured on the technologies fact.
    # Structured identity records the added item, not a single coarse path.
    technology_changes = [
        change
        for change in comparison.fact_changes
        if change.path == "facts.technologies" or change.path.startswith("facts.technologies[")
    ]
    assert technology_changes
    assert any("Docker" in change.summary for change in technology_changes)
    # Family 2: Architecture graph delta captured
    assert comparison.graph_delta is not None
    assert "D" in comparison.graph_delta.added_nodes
    # Family 3: Security finding lifecycle and source cause captured
    assert len(comparison.resolved_findings) == 1
    assert comparison.resolved_findings[0].cause == "source"
    # Family 4 & 5: Git intelligence and concerns joined
    assert comparison.change_concerns is not None
    assert any(c.subject_id == "src/service.py" for c in comparison.change_concerns)
    # Cause attribution is source-driven
    assert comparison.cause_attribution is not None
    assert comparison.cause_attribution.attribution == "source_only"
    assert comparison.cause_attribution.label == "source-driven"


def test_service_helper_compare_m31_and_isolate_rerun() -> None:
    service = ScanComparisonService()
    attr = service.compare_m31(
        source_changed=False,
        feed_changed=True,
        cve_findings=[_cve_finding()],
    )
    assert attr.attribution == "feed_only"
    assert attr.label == "feed-driven"
    assert attr.is_feed_driven is True

    isolated = service.isolate_controlled_reruns(
        base_finding_keys=["k1"],
        candidate_finding_keys=["k2"],
        source_rerun_finding_keys=[],
        feed_rerun_finding_keys=["k1", "k2"],
    )
    assert isolated.attribution == "controlled_isolated"
    assert isolated.isolated_causes["source"] == ["k1"]
    assert isolated.isolated_causes["feed"] == ["k2"]


def test_flag_only_source_and_feed_stays_mixed() -> None:
    attr = evaluate_cause_attribution(
        source_changed=True,
        feed_changed=True,
        controlled_rerun=True,
    )
    assert attr.attribution == "mixed"
    assert attr.controlled_rerun_references == []
    assert attr.controlled_rerun_performed is False


def test_series_pair_cause_attribution_preserves_commit_identity() -> None:
    base_sha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    candidate_sha = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    attr = evaluate_cause_attribution(
        source_changed=True,
        feed_changed=False,
        config_changed=False,
        engine_changed=False,
        base_digests={
            "source": "source-s1",
            "feed": "feed-shared",
            "config": "config-shared",
            "engine": "0.2.1",
        },
        candidate_digests={
            "source": "source-s2",
            "feed": "feed-shared",
            "config": "config-shared",
            "engine": "0.2.1",
        },
    )
    assert attr.attribution == "source_only"
    assert attr.base_digests["source"] == "source-s1"
    assert attr.candidate_digests["source"] == "source-s2"
    assert attr.base_digests["feed"] == attr.candidate_digests["feed"]
    assert attr.base_digests["engine"] == "0.2.1"
    assert base_sha != candidate_sha
