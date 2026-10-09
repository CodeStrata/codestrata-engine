"""Tests for E10.1 / M28 versioned finding matching and compatible metric deltas."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.incremental.lifecycle import (
    FindingLifecycleState,
    MagnitudeComparator,
    RuleMagnitudeSpec,
    canonical_state_from_analysis_result,
    evaluate_finding_lifecycle,
)
from codestrata.models.analysis_result import AnalysisResult
from codestrata.models.enums import FindingCategory, FindingSource, Severity
from codestrata.models.evidence import Evidence
from codestrata.models.finding import Finding
from codestrata.models.repository import Repository
from codestrata.models.repository_facts import RepositoryFacts
from codestrata.services.scan_comparison_service import ScanComparisonService


def _finding(
    *,
    rule_id: str,
    title: str = "Test Finding",
    severity: Severity = Severity.MEDIUM,
    file_path: str = "src/module.py",
    line_number: int = 42,
    detected_value: str | None = None,
    magnitude: float | int | None = None,
    is_binary: bool = True,
    is_override: bool = False,
    occurrence_id: str = "0",
    identity_key: str | None = None,
    rule_version: str = "1.0.0",
) -> Finding:
    metadata: dict[str, object] = {
        "rule_version": rule_version,
        "occurrence_id": occurrence_id,
        "is_binary": is_binary,
    }
    if magnitude is not None:
        metadata["violation_magnitude"] = magnitude
        metadata["magnitude"] = magnitude
    if is_override:
        metadata["severity_override"] = True
        metadata["is_policy_override"] = True
    if identity_key:
        metadata["identity_key"] = identity_key

    det_val = detected_value or (str(magnitude) if magnitude is not None else None)
    return Finding(
        rule_id=rule_id,
        title=title,
        description=f"Description for {title}",
        category=FindingCategory.MAINTAINABILITY,
        severity=severity,
        source=FindingSource.DETERMINISTIC,
        evidence=[
            Evidence(
                file_path=file_path,
                line_number=line_number,
                detected_value=det_val,
                description=f"Evidence description for {title}",
            )
        ],
        metadata=metadata,
    )


def _result(
    tmp_path: Path,
    findings: list[Finding] | None = None,
    *,
    coverage_status: str = "pass",
    ruleset_version: str = "1.0.0",
    metrics: dict[str, dict[str, object]] | None = None,
    evaluated_rules: list[str] | None = None,
    disabled_rules: list[str] | None = None,
) -> AnalysisResult:
    f_list = findings or []
    eval_rules = (
        evaluated_rules
        if evaluated_rules is not None
        else [f.rule_id for f in f_list if f.rule_id]
    )
    return AnalysisResult(
        repository=Repository(name="sample", path=tmp_path / "sample", files=["src/module.py"]),
        facts=RepositoryFacts(),
        findings=f_list,
        ruleset_version=ruleset_version,
        metadata={
            "coverage_status": coverage_status,
            "evaluated_rule_ids": eval_rules,
            "disabled_rule_ids": disabled_rules or [],
            "metrics": metrics or {},
            "artifact_digest": "sha256:dummy",
        },
    )


# --- 1. Stable (binary persistence) ---
def test_fixture_stable_binary_persistence(tmp_path: Path) -> None:
    """Stable binary violation present in both states has lifecycle UNCHANGED."""
    f = _finding(rule_id="arch.no-circular-deps")
    base = _result(tmp_path, [f])
    candidate = _result(tmp_path, [f])

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
    )

    assert len(comparison.unchanged_findings) == 1
    assert comparison.unchanged_findings[0].lifecycle == FindingLifecycleState.UNCHANGED.value
    assert comparison.summary.unchanged_findings == 1
    assert comparison.summary.new_findings == 0
    assert comparison.summary.resolved_findings == 0
    assert comparison.summary.improved_findings == 0
    assert comparison.summary.worsened_findings == 0


# --- 2. Fixed (resolved finding after complete coverage) ---
def test_fixture_fixed_resolved_after_complete_reevaluation(tmp_path: Path) -> None:
    """Finding present in baseline, absent in candidate with PASS coverage resolves."""
    f = _finding(rule_id="arch.no-circular-deps")
    base = _result(tmp_path, [f])
    candidate = _result(
        tmp_path,
        [],
        coverage_status="pass",
        evaluated_rules=["arch.no-circular-deps"],
    )

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
    )

    assert len(comparison.resolved_findings) == 1
    assert comparison.resolved_findings[0].lifecycle == FindingLifecycleState.RESOLVED.value
    assert comparison.summary.resolved_findings == 1


# --- 3. New finding ---
def test_fixture_new_finding(tmp_path: Path) -> None:
    """Finding absent in baseline, present in candidate has lifecycle NEW."""
    f = _finding(rule_id="sec.no-hardcoded-keys")
    base = _result(tmp_path, [], coverage_status="pass")
    candidate = _result(tmp_path, [f], coverage_status="pass")

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
    )

    assert len(comparison.new_findings) == 1
    assert comparison.new_findings[0].lifecycle == FindingLifecycleState.NEW.value
    assert comparison.summary.new_findings == 1


# --- 4. Message-only change ---
def test_fixture_message_only_preserves_identity(tmp_path: Path) -> None:
    """Title and description changes keep stable identity and do not look like code fixes."""
    f_base = _finding(
        rule_id="quality.complexity",
        title="Original Title",
        file_path="src/calc.py",
        line_number=10,
    )
    f_cand = _finding(
        rule_id="quality.complexity",
        title="Revised Reworded Title With Better Grammar",
        file_path="src/calc.py",
        line_number=10,
    )
    base = _result(tmp_path, [f_base])
    candidate = _result(tmp_path, [f_cand])

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
    )

    assert len(comparison.unchanged_findings) == 1
    assert comparison.unchanged_findings[0].lifecycle == FindingLifecycleState.UNCHANGED.value
    assert comparison.summary.new_findings == 0
    assert comparison.summary.resolved_findings == 0


# --- 5. Rename mapping preserves identity ---
def test_fixture_rename_preserves_identity(tmp_path: Path) -> None:
    """Finding whose file was renamed matches via rename_map without churn."""
    f_base = _finding(
        rule_id="sec.sql-injection",
        file_path="src/legacy_query.py",
        line_number=50,
    )
    f_cand = _finding(
        rule_id="sec.sql-injection",
        file_path="src/query_service.py",
        line_number=50,
    )
    base = _result(tmp_path, [f_base])
    candidate = _result(tmp_path, [f_cand])

    rename_map = {"src/legacy_query.py": "src/query_service.py"}
    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
        rename_map=rename_map,
    )

    assert len(comparison.unchanged_findings) == 1
    assert comparison.unchanged_findings[0].lifecycle == FindingLifecycleState.UNCHANGED.value
    assert comparison.summary.new_findings == 0
    assert comparison.summary.resolved_findings == 0


# --- 6. Coverage loss: NEVER resolves a finding ---
def test_fixture_coverage_loss_never_resolves(tmp_path: Path) -> None:
    """Absence under failed or incomplete coverage NEVER resolves a finding (marked UNKNOWN)."""
    f = _finding(rule_id="sec.auth-bypass")
    base = _result(tmp_path, [f])
    candidate = _result(
        tmp_path,
        [],
        coverage_status="incomplete",
        evaluated_rules=[],
    )

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
    )

    assert len(comparison.resolved_findings) == 0
    assert comparison.summary.resolved_findings == 0
    assert len(comparison.unknown_findings) == 1
    rec = comparison.unknown_findings[0]
    assert rec.lifecycle == FindingLifecycleState.UNKNOWN.value
    assert "incomplete_candidate_coverage" in rec.compatibility_reasons


# --- 7 & 10. Policy severity change / severity-only override ---
def test_fixture_policy_severity_override_is_not_code_fix(tmp_path: Path) -> None:
    """Severity override is a configuration change, not a source code fix."""
    f_base = _finding(
        rule_id="sec.tls-v1",
        severity=Severity.HIGH,
        is_override=False,
    )
    f_cand = _finding(
        rule_id="sec.tls-v1",
        severity=Severity.LOW,
        is_override=True,
    )
    base = _result(tmp_path, [f_base])
    candidate = _result(tmp_path, [f_cand])

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
    )

    assert comparison.summary.improved_findings == 0
    assert comparison.summary.resolved_findings == 0
    assert len(comparison.unchanged_findings) == 1
    assert comparison.unchanged_findings[0].lifecycle == FindingLifecycleState.UNCHANGED.value
    assert comparison.unchanged_findings[0].is_policy_override is True
    assert comparison.unchanged_findings[0].cause == "configuration"
    assert len(comparison.severity_changes) == 1
    assert comparison.severity_changes[0].direction == "decreased"
    assert comparison.severity_changes[0].is_policy_override is True


# --- 8. Reduced magnitude that still violates: IMPROVED ---
def test_fixture_reduced_magnitude_still_violating(tmp_path: Path) -> None:
    """Persistent finding with favorably reduced magnitude is IMPROVED even if still violating."""
    rule_spec = RuleMagnitudeSpec(
        rule_id="quality.cyclomatic-complexity",
        is_binary=False,
        comparator=MagnitudeComparator.LOWER_IS_BETTER,
        threshold=15,
    )
    f_base = _finding(
        rule_id="quality.cyclomatic-complexity",
        magnitude=25,
        is_binary=False,
    )
    f_cand = _finding(
        rule_id="quality.cyclomatic-complexity",
        magnitude=18,
        is_binary=False,
    )
    base = _result(tmp_path, [f_base])
    candidate = _result(tmp_path, [f_cand])

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
        rule_specs={"quality.cyclomatic-complexity": rule_spec},
    )

    assert len(comparison.improved_findings) == 1
    assert comparison.improved_findings[0].lifecycle == FindingLifecycleState.IMPROVED.value
    assert comparison.improved_findings[0].magnitude_delta == -7
    assert comparison.summary.improved_findings == 1
    assert comparison.summary.worsened_findings == 0
    assert comparison.summary.resolved_findings == 0


def test_fixture_worsened_magnitude(tmp_path: Path) -> None:
    """Persistent finding with increased magnitude is WORSENED."""
    rule_spec = RuleMagnitudeSpec(
        rule_id="quality.cyclomatic-complexity",
        is_binary=False,
        comparator=MagnitudeComparator.LOWER_IS_BETTER,
        threshold=15,
    )
    f_base = _finding(rule_id="quality.cyclomatic-complexity", magnitude=18, is_binary=False)
    f_cand = _finding(rule_id="quality.cyclomatic-complexity", magnitude=25, is_binary=False)
    base = _result(tmp_path, [f_base])
    candidate = _result(tmp_path, [f_cand])

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
        rule_specs={"quality.cyclomatic-complexity": rule_spec},
    )

    assert len(comparison.worsened_findings) == 1
    assert comparison.worsened_findings[0].lifecycle == FindingLifecycleState.WORSENED.value
    assert comparison.worsened_findings[0].magnitude_delta == 7
    assert comparison.summary.worsened_findings == 1


# --- 11. Unknown comparator ---
def test_fixture_unknown_comparator_yields_unknown(tmp_path: Path) -> None:
    """Without a comparable magnitude or unknown comparator, do not invent movement."""
    rule_spec = RuleMagnitudeSpec(
        rule_id="maint.custom-metric",
        is_binary=False,
        comparator=MagnitudeComparator.UNKNOWN,
    )
    f_base = _finding(rule_id="maint.custom-metric", magnitude=10, is_binary=False)
    f_cand = _finding(rule_id="maint.custom-metric", magnitude=5, is_binary=False)
    base = _result(tmp_path, [f_base])
    candidate = _result(tmp_path, [f_cand])

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
        rule_specs={"maint.custom-metric": rule_spec},
    )

    assert len(comparison.unknown_findings) == 1
    assert comparison.unknown_findings[0].lifecycle == FindingLifecycleState.UNKNOWN.value
    assert "unknown_comparator" in comparison.unknown_findings[0].compatibility_reasons


# --- Rule version incompatibility ---
def test_incompatible_rule_version_yields_unknown(tmp_path: Path) -> None:
    """Incompatible rule major version forces UNKNOWN lifecycle."""
    f_base = _finding(rule_id="rule.api", rule_version="1.0.0")
    f_cand = _finding(rule_id="rule.api", rule_version="2.0.0")
    base = _result(tmp_path, [f_base])
    candidate = _result(tmp_path, [f_cand])

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
    )

    assert len(comparison.unknown_findings) == 1
    assert comparison.unknown_findings[0].lifecycle == FindingLifecycleState.UNKNOWN.value
    assert "incompatible_rule_version" in comparison.unknown_findings[0].compatibility_reasons


# --- Empty outcome and disabled-all scope ---
def test_empty_outcome_and_disabled_all_scope(tmp_path: Path) -> None:
    """Empty outcome and disabled-all scope are explicitly recorded, never synthetic health."""
    base = _result(tmp_path, [])
    candidate = _result(
        tmp_path,
        [],
        evaluated_rules=[],
        disabled_rules=["rule.a", "rule.b"],
    )

    m28_res = ScanComparisonService().compare_m28(candidate, base)
    assert m28_res.empty_outcome is True
    assert m28_res.disabled_all is True


# --- Compatible Metric Deltas ---
def test_compatible_metric_deltas(tmp_path: Path) -> None:
    """Metric deltas = candidate - base with pinned units and scope."""
    base_metrics = {
        "m_count": {
            "value": 10,
            "unit": "count",
            "scope": "repository",
            "direction": "lower_is_better",
        },
        "m_ratio": {
            "value": 0.25,
            "unit": "ratio",
            "scope": "repository",
            "direction": "higher_is_better",
        },
        "m_unsupported": {"value": 5, "unit": "count", "scope": "repository"},
    }
    cand_metrics = {
        "m_count": {
            "value": 7,
            "unit": "count",
            "scope": "repository",
            "direction": "lower_is_better",
        },
        "m_ratio": {
            "value": 0.50,
            "unit": "ratio",
            "scope": "repository",
            "direction": "higher_is_better",
        },
        "m_unsupported": {"value": 5, "unit": "bytes", "scope": "repository"},
    }
    base = _result(tmp_path, [], metrics=base_metrics)
    candidate = _result(tmp_path, [], metrics=cand_metrics)

    comparison = ScanComparisonService().compare_with_lifecycle(
        current=candidate,
        baseline=base,
        current_timestamp="2026-09-15T12:00:00Z",
        baseline_timestamp="2026-09-14T12:00:00Z",
    )

    deltas_by_name = {m.metric_name: m for m in comparison.metric_deltas}

    # Count: 7 - 10 = -3 (favorable because lower is better)
    m_count = deltas_by_name["m_count"]
    assert m_count.compatible is True
    assert m_count.delta == -3
    assert m_count.direction == "favorable"

    # Ratio: 0.50 - 0.25 = 0.25 (favorable because higher is better)
    m_ratio = deltas_by_name["m_ratio"]
    assert m_ratio.compatible is True
    assert m_ratio.delta == 0.25
    assert m_ratio.direction == "favorable"

    # Unit mismatch: incompatible!
    m_unsupported = deltas_by_name["m_unsupported"]
    assert m_unsupported.compatible is False
    assert "unit_mismatch" in m_unsupported.compatibility_reason


# --- Repeatability (determinism check) ---
def test_m28_evaluation_is_deterministic(tmp_path: Path) -> None:
    """Three repeat evaluations on identical inputs produce identical JSON dumps."""
    f = _finding(rule_id="sec.rule-1", magnitude=10, is_binary=False)
    base = _result(tmp_path, [f])
    candidate = _result(tmp_path, [f])

    runs = [
        ScanComparisonService().compare_m28(candidate, base).model_dump(mode="json")
        for _ in range(3)
    ]
    assert runs[0] == runs[1] == runs[2]


def test_compare_results_with_evaluate_lifecycle(tmp_path: Path) -> None:
    """ScanComparisonService.compare_results respects evaluate_lifecycle=True."""
    f1 = _finding(rule_id="sec.rule-1", magnitude=10, is_binary=False)
    f2 = _finding(rule_id="sec.rule-1", magnitude=5, is_binary=False)
    base = _result(tmp_path, [f1])
    cand = _result(tmp_path, [f2])

    rule_spec = RuleMagnitudeSpec(
        rule_id="sec.rule-1",
        is_binary=False,
        comparator=MagnitudeComparator.LOWER_IS_BETTER,
    )

    service = ScanComparisonService()
    comp = service.compare_results(
        cand,
        base,
        "2026-09-15T12:00:00Z",
        "2026-09-14T12:00:00Z",
        evaluate_lifecycle=True,
        rule_specs={"sec.rule-1": rule_spec},
    )
    assert len(comp.improved_findings) == 1
    assert comp.improved_findings[0].lifecycle == FindingLifecycleState.IMPROVED.value


def test_metric_delta_edge_cases(tmp_path: Path) -> None:
    """Test metric delta branches: scope mismatch, formula mismatch, single-state metrics."""
    base_metrics: dict[str, dict[str, object]] = {
        "m_scope": {"value": 10, "unit": "count", "scope": "file"},
        "m_formula": {
            "value": 10,
            "unit": "count",
            "scope": "repo",
            "formula_version": "1.0",
        },
        "m_base_only": {"value": 5, "unit": "count", "scope": "repo"},
        "m_str": {"value": "abc", "unit": "tag", "scope": "repo"},
    }
    cand_metrics: dict[str, dict[str, object]] = {
        "m_scope": {"value": 10, "unit": "count", "scope": "repo"},
        "m_formula": {
            "value": 10,
            "unit": "count",
            "scope": "repo",
            "formula_version": "2.0",
        },
        "m_cand_only": {"value": 15, "unit": "count", "scope": "repo"},
        "m_str": {"value": "xyz", "unit": "tag", "scope": "repo"},
    }
    base = _result(tmp_path, [], metrics=base_metrics)
    cand = _result(tmp_path, [], metrics=cand_metrics)

    res = ScanComparisonService().compare_m28(cand, base)
    deltas = {d.metric_name: d for d in res.metric_deltas}

    assert deltas["m_scope"].compatible is False
    assert "scope_mismatch" in deltas["m_scope"].compatibility_reason
    assert deltas["m_formula"].compatible is False
    assert "formula_version_mismatch" in deltas["m_formula"].compatibility_reason
    assert deltas["m_base_only"].compatible is True
    assert deltas["m_cand_only"].compatible is True
    assert deltas["m_str"].compatible is True
    assert deltas["m_str"].delta is None


def test_identity_key_and_rename_map(tmp_path: Path) -> None:
    """Explicit identity_key with rename_map and duplicate key handling."""
    f = _finding(
        rule_id="sec.rule-1",
        identity_key="custom:old_path.py:line10",
    )
    base = _result(tmp_path, [f])
    cand = _result(
        tmp_path,
        [_finding(rule_id="sec.rule-1", identity_key="custom:new_path.py:line10")],
    )

    state_b = canonical_state_from_analysis_result(base)
    state_c = canonical_state_from_analysis_result(
        cand,
        rename_map={"old_path.py": "new_path.py"},
    )

    lifecycle = evaluate_finding_lifecycle(state_b, state_c)
    assert len(lifecycle) == 1
    assert lifecycle[0].lifecycle == FindingLifecycleState.UNCHANGED


def test_higher_is_better_comparator(tmp_path: Path) -> None:
    """Higher-is-better comparator correctly distinguishes improved and worsened."""
    f_base = _finding(rule_id="cov.rule", magnitude=60.0, is_binary=False)
    f_cand_better = _finding(rule_id="cov.rule", magnitude=80.0, is_binary=False)
    f_cand_worse = _finding(rule_id="cov.rule", magnitude=40.0, is_binary=False)

    spec = RuleMagnitudeSpec(
        rule_id="cov.rule",
        unit="percent",
        comparator=MagnitudeComparator.HIGHER_IS_BETTER,
        is_binary=False,
    )

    res_better = evaluate_finding_lifecycle(
        canonical_state_from_analysis_result(_result(tmp_path, [f_base])),
        canonical_state_from_analysis_result(_result(tmp_path, [f_cand_better])),
        rule_specs={"cov.rule": spec},
    )
    assert res_better[0].lifecycle == FindingLifecycleState.IMPROVED

    res_worse = evaluate_finding_lifecycle(
        canonical_state_from_analysis_result(_result(tmp_path, [f_base])),
        canonical_state_from_analysis_result(_result(tmp_path, [f_cand_worse])),
        rule_specs={"cov.rule": spec},
    )
    assert res_worse[0].lifecycle == FindingLifecycleState.WORSENED


def test_series_pairs_do_not_leak_later_findings(tmp_path: Path) -> None:
    early = _finding(rule_id="quality.complexity", file_path="src/app.js", title="early")
    later = _finding(
        rule_id="security.hardcoded-secret",
        file_path="src/later.js",
        title="laterOnlyLeakageMarker",
    )
    s1 = _result(tmp_path, [early])
    s2 = _result(tmp_path, [early])
    s5 = _result(tmp_path, [early, later])
    adjacent = ScanComparisonService().compare_results(
        current=s2,
        baseline=s1,
        current_timestamp="s2",
        baseline_timestamp="s1",
        evaluate_lifecycle=True,
        changed_files=["src/app.js"],
    )
    span = ScanComparisonService().compare_results(
        current=s5,
        baseline=s1,
        current_timestamp="s5",
        baseline_timestamp="s1",
        evaluate_lifecycle=True,
        changed_files=["src/app.js", "src/later.js"],
    )
    assert adjacent.new_findings == []
    assert all("later.js" not in (item.file_path or "") for item in adjacent.unchanged_findings)
    assert any("later.js" in (item.file_path or "") for item in span.new_findings)

