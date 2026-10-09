"""E03.3 launch catalog budgets, cancellation, evidence and projections."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from codestrata.application.rules.execution import (
    CatalogEntry,
    IsolatedOutcome,
    LaunchCatalogService,
    PurposeAdmissionError,
    admit_execution_purpose,
    execution_budgets,
    memory_rss_for_workload,
    plan_launch_catalog,
    run_hang_until_killed,
    run_isolated_evaluation,
    wall_seconds_for_workload,
)
from codestrata.application.rules.execution.process_guard import in_process_evaluate
from codestrata.application.rules.execution.worker import evaluate_payload
from codestrata.domain.contracts.catalog import load_launch_ratification
from codestrata.domain.contracts.enums import (
    CoverageState,
    ExecutionPurpose,
    JobTerminalState,
    MetricStatus,
    ResultStatus,
)
from codestrata.domain.contracts.examples_e01_3 import example_rule
from codestrata.domain.contracts.invocation import LocalJobCancellation
from codestrata.domain.contracts.models import MetricComputation
from codestrata.domain.contracts.rules import unsigned_rule_payload
from codestrata.domain.rules.assessment import coverage_for_scope, interpret_operator_result
from codestrata.domain.rules.deadlines import (
    DeadlineAction,
    budgets_require_process_cap,
    next_deadline_action,
)
from codestrata.domain.rules.errors import RuleEvidenceError, RuleResultValidationError
from codestrata.domain.rules.evidence_contract import validate_launch_evidence
from codestrata.domain.rules.execution_models import (
    LaunchEvidence,
    LaunchExecutionBody,
    LaunchRuleRecord,
)
from codestrata.domain.rules.operators.models import (
    FactSlot,
    FactStatus,
    OperatorContext,
    OperatorEdge,
    OperatorGraph,
    OperatorResult,
    Truth,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e03.3"
EXPECTED = json.loads((FIXTURE_DIR / "expected-outcomes.json").read_text(encoding="utf-8"))
EXECUTION_SRC = (
    Path(__file__).resolve().parents[4]
    / "src"
    / "codestrata"
    / "application"
    / "rules"
    / "execution"
)
SERVICE = LaunchCatalogService()


def _yaml_for(rule_id: str, condition: dict[str, object], *, facts: list[str] | None = None) -> str:
    payload = unsigned_rule_payload(example_rule())
    payload["metadata"] = dict(payload["metadata"])
    payload["metadata"]["id"] = rule_id
    payload["condition"] = condition
    if facts is not None:
        payload["applies_to"] = dict(payload["applies_to"])
        payload["applies_to"]["facts"] = facts
    return yaml.safe_dump(payload, sort_keys=True)


CYCLE_CONDITION: dict[str, object] = {
    "dependency_view": None,
    "edge_types": ["imports"],
    "fact": None,
    "max_depth": 1,
    "operands": [],
    "operator": "cycle",
    "traversal": "direct",
    "value": None,
}

MATCHES_CONDITION: dict[str, object] = {
    "dependency_view": None,
    "edge_types": [],
    "fact": "source.span",
    "max_depth": None,
    "operands": [],
    "operator": "matches",
    "traversal": None,
    "value": "a",
}

EQUALS_CONDITION: dict[str, object] = {
    "dependency_view": None,
    "edge_types": [],
    "fact": "module.declaration",
    "max_depth": None,
    "operands": [],
    "operator": "equals",
    "traversal": None,
    "value": "mod.a",
}


def _cycle_graph(*, cyclic: bool, complete: bool = True, extra_nodes: int = 0) -> OperatorGraph:
    nodes = ["mod.a", "mod.b"]
    if extra_nodes:
        nodes.extend(f"n{index}" for index in range(extra_nodes))
    edges: tuple[OperatorEdge, ...]
    if cyclic:
        edges = (
            OperatorEdge(source="mod.a", target="mod.b", edge_type="imports"),
            OperatorEdge(source="mod.b", target="mod.a", edge_type="imports"),
        )
    else:
        edges = (OperatorEdge(source="mod.a", target="mod.b", edge_type="imports"),)
    return OperatorGraph(nodes=tuple(nodes), edges=edges, complete=complete)


def _run(
    entries: list[CatalogEntry],
    context: OperatorContext,
    *,
    purpose: ExecutionPurpose = ExecutionPurpose.PRODUCTION,
    package_purpose: ExecutionPurpose | None = None,
    evidence_paths: dict[str, str] | None = None,
    isolate: bool = False,
) -> LaunchExecutionBody:
    return SERVICE.execute(
        entries,
        context,
        purpose=purpose,
        package_purpose=package_purpose or purpose,
        isolate=isolate,
        evidence_paths=evidence_paths,
    )


def test_budgets_are_e01_1_ratification_not_a_second_set() -> None:
    ratified = load_launch_ratification().budgets
    bound = execution_budgets()
    assert bound == ratified
    assert bound.rule_soft_budget_seconds == 5
    assert bound.rule_hard_deadline_seconds == 15
    assert bound.cancellation_grace_seconds == 2
    assert bound.regex_match_timeout_milliseconds == 100
    assert bound.regex_max_steps == 1_000_000
    assert bound.max_effective_rules == 1000
    assert bound.process_enforced_hard_cap is True
    assert bound.cooperative_callback_only_forbidden is True


def test_cancellation_contract_rejects_cooperative_only() -> None:
    with pytest.raises(ValidationError):
        LocalJobCancellation(
            local_job_id="local-1",
            requested=True,
            grace_seconds=2,
            process_enforced_hard_cap=False,
        )


def test_deadline_arithmetic_uses_hard_cap_and_grace() -> None:
    budgets = execution_budgets()
    assert (
        next_deadline_action(
            elapsed_seconds=15,
            hard_deadline_seconds=float(budgets.rule_hard_deadline_seconds),
            cancel_requested=False,
            grace_elapsed_seconds=None,
            grace_seconds=float(budgets.cancellation_grace_seconds),
        )
        is DeadlineAction.KILL_HARD
    )
    assert (
        next_deadline_action(
            elapsed_seconds=1,
            hard_deadline_seconds=float(budgets.rule_hard_deadline_seconds),
            cancel_requested=True,
            grace_elapsed_seconds=2,
            grace_seconds=float(budgets.cancellation_grace_seconds),
        )
        is DeadlineAction.KILL_GRACE
    )


def test_noncooperative_hang_is_process_killed() -> None:
    outcome = run_hang_until_killed(budgets=execution_budgets())
    assert outcome.terminal is JobTerminalState.KILLED
    assert outcome.reason == "cancelled_grace_exceeded"
    assert "process_terminated" in outcome.diagnostics


def test_launch_catalog_has_no_sharedrule_evaluate_path() -> None:
    forbidden: list[str] = []
    for path in EXECUTION_SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "evaluate":
                forbidden.append(f"{path.name}:{node.lineno}")
            if isinstance(node, ast.Name) and node.id in {"LegacyRuleAdapter", "SharedRule"}:
                forbidden.append(f"{path.name}:{node.lineno}:{node.id}")
    assert forbidden == []


def _cycle_entry() -> CatalogEntry:
    return CatalogEntry(
        rule_id="architecture.dependency-cycle",
        yaml_text=_yaml_for("architecture.dependency-cycle", CYCLE_CONDITION),
    )


def test_fail_is_violation_error_is_processing() -> None:
    fail_body = _run(
        [_cycle_entry()],
        OperatorContext(declared_graph=_cycle_graph(cyclic=True)),
    )
    error_body = _run([_cycle_entry()], OperatorContext())
    fail_record = fail_body.records[0]
    error_record = error_body.records[0]
    assert fail_record.status is ResultStatus.FAIL
    assert fail_record.evidence
    assert error_record.status is ResultStatus.ERROR
    assert error_record.reason


@pytest.mark.parametrize("case", EXPECTED["cases"], ids=lambda item: item["id"])
def test_independent_expected_outcomes(case: dict[str, object]) -> None:
    case_id = str(case["id"])
    cycle_yaml = _yaml_for("architecture.dependency-cycle", CYCLE_CONDITION)
    matches_yaml = _yaml_for(
        "architecture.regex-subject",
        MATCHES_CONDITION,
        facts=["source.span"],
    )
    equals_yaml = _yaml_for("architecture.equals-declaration", EQUALS_CONDITION)
    if case_id == "cycle-violation":
        body = _run(
            [CatalogEntry(rule_id="architecture.dependency-cycle", yaml_text=cycle_yaml)],
            OperatorContext(declared_graph=_cycle_graph(cyclic=True)),
        )
    elif case_id == "cycle-compliant":
        body = _run(
            [CatalogEntry(rule_id="architecture.dependency-cycle", yaml_text=cycle_yaml)],
            OperatorContext(declared_graph=_cycle_graph(cyclic=False)),
        )
    elif case_id == "cycle-incomplete-graph":
        body = _run(
            [CatalogEntry(rule_id="architecture.dependency-cycle", yaml_text=cycle_yaml)],
            OperatorContext(declared_graph=_cycle_graph(cyclic=False, complete=False)),
        )
    elif case_id == "missing-graph":
        body = _run(
            [CatalogEntry(rule_id="architecture.dependency-cycle", yaml_text=cycle_yaml)],
            OperatorContext(),
        )
    elif case_id == "disabled-cycle":
        body = _run(
            [
                CatalogEntry(
                    rule_id="architecture.dependency-cycle",
                    yaml_text=cycle_yaml,
                    enabled=False,
                )
            ],
            OperatorContext(declared_graph=_cycle_graph(cyclic=True)),
        )
    elif case_id == "suppressed-cycle":
        body = _run(
            [
                CatalogEntry(
                    rule_id="architecture.dependency-cycle",
                    yaml_text=cycle_yaml,
                    suppressed=True,
                    suppression_ref="opaque-sup-1",
                )
            ],
            OperatorContext(declared_graph=_cycle_graph(cyclic=True)),
        )
    elif case_id == "regex-budget":
        body = _run(
            [CatalogEntry(rule_id="architecture.regex-subject", yaml_text=matches_yaml)],
            OperatorContext(
                facts={"source.span": FactSlot(status=FactStatus.COMPLETE, value="a" * 2_000_000)}
            ),
        )
    elif case_id == "graph-node-budget":
        budgets = execution_budgets()
        body = _run(
            [CatalogEntry(rule_id="architecture.dependency-cycle", yaml_text=cycle_yaml)],
            OperatorContext(
                declared_graph=_cycle_graph(
                    cyclic=False,
                    extra_nodes=budgets.graph_max_visited_nodes + 1,
                )
            ),
        )
    elif case_id == "equals-missing-fact":
        body = _run(
            [CatalogEntry(rule_id="architecture.equals-declaration", yaml_text=equals_yaml)],
            OperatorContext(),
        )
    elif case_id == "corrupt-absolute-evidence":
        body = _run(
            [CatalogEntry(rule_id="architecture.dependency-cycle", yaml_text=cycle_yaml)],
            OperatorContext(declared_graph=_cycle_graph(cyclic=True)),
            evidence_paths={"mod.a": "C:/secret/repo/mod.py", "mod.b": "C:/secret/repo/other.py"},
        )
    else:
        raise AssertionError(case_id)
    record = body.records[0]
    expected_status = case["status"]
    if expected_status is None:
        assert record.status is None
    else:
        assert record.status is ResultStatus(str(expected_status))
    assert record.coverage_state is CoverageState(str(case["coverage_state"]))
    if record.coverage_state is CoverageState.DISABLED:
        assert record.enabled is False
        assert record.status not in {ResultStatus.PASS, ResultStatus.NOT_APPLICABLE}
    if record.coverage_state is CoverageState.SUPPRESSED:
        assert record.suppressed is True
        assert record.status is not ResultStatus.PASS


def test_disabled_and_suppressed_remain_visible_in_projections() -> None:
    cycle_yaml = _yaml_for("architecture.dependency-cycle", CYCLE_CONDITION)
    body = _run(
        [
            CatalogEntry(
                rule_id="architecture.dependency-cycle",
                yaml_text=cycle_yaml,
                enabled=False,
            )
        ],
        OperatorContext(declared_graph=_cycle_graph(cyclic=True)),
    )
    json_proj = SERVICE.project_json(body)
    html = SERVICE.project_html(body)
    sarif = SERVICE.project_sarif(body)
    assert json_proj["records"][0]["coverage_state"] == "disabled"
    assert json_proj["health_verdict"] == "none"
    assert "coverage_state: disabled" in html
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"][0]["properties"]["enabled"] is False


def test_same_plan_and_facts_are_digest_identical() -> None:
    entry = CatalogEntry(
        rule_id="architecture.dependency-cycle",
        yaml_text=_yaml_for("architecture.dependency-cycle", CYCLE_CONDITION),
    )
    context = OperatorContext(declared_graph=_cycle_graph(cyclic=True))
    first = _run([entry], context)
    second = _run([entry], context)
    third = _run([entry], context)
    assert first.content_digest() == second.content_digest() == third.content_digest()


def test_preview_uses_same_compiler_and_operators() -> None:
    entry = CatalogEntry(
        rule_id="architecture.dependency-cycle",
        yaml_text=_yaml_for("architecture.dependency-cycle", CYCLE_CONDITION),
    )
    context = OperatorContext(declared_graph=_cycle_graph(cyclic=True))
    production = _run([entry], context, purpose=ExecutionPurpose.PRODUCTION)
    preview = _run([entry], context, purpose=ExecutionPurpose.PREVIEW)
    assert production.records[0].status == preview.records[0].status
    assert production.purpose is ExecutionPurpose.PRODUCTION
    assert preview.purpose is ExecutionPurpose.PREVIEW
    assert preview.preview_cannot_authorize_production is True


def test_preview_package_cannot_authorize_production() -> None:
    with pytest.raises(PurposeAdmissionError):
        admit_execution_purpose(
            package_purpose=ExecutionPurpose.PREVIEW,
            requested_purpose=ExecutionPurpose.PRODUCTION,
        )
    entry = CatalogEntry(
        rule_id="architecture.dependency-cycle",
        yaml_text=_yaml_for("architecture.dependency-cycle", CYCLE_CONDITION),
    )
    with pytest.raises(PurposeAdmissionError):
        _run(
            [entry],
            OperatorContext(declared_graph=_cycle_graph(cyclic=True)),
            purpose=ExecutionPurpose.PRODUCTION,
            package_purpose=ExecutionPurpose.PREVIEW,
        )


def test_malicious_regex_terminates_in_isolated_process() -> None:
    yaml_text = _yaml_for(
        "architecture.regex-subject",
        {
            **MATCHES_CONDITION,
            "value": "(a+)+$",
        },
        facts=["source.span"],
    )
    entry = CatalogEntry(rule_id="architecture.regex-subject", yaml_text=yaml_text)
    plan = SERVICE.plan([entry], purpose=ExecutionPurpose.PRODUCTION)
    compiled = plan.entries[0].plan
    assert compiled is not None
    assert compiled.condition is not None
    budgets = execution_budgets()
    payload = {
        "plan": compiled.condition.model_dump(mode="json"),
        "context": OperatorContext(
            facts={"source.span": FactSlot(status=FactStatus.COMPLETE, value=("a" * 28) + "b")}
        ).model_dump(mode="json"),
        "limits": None,
    }
    outcome = run_isolated_evaluation(
        payload,
        budgets=budgets,
        hard_deadline_seconds=budgets.regex_match_timeout_milliseconds / 1000,
    )
    allowed = {
        JobTerminalState.COMPLETED,
        JobTerminalState.KILLED,
        JobTerminalState.FAILED,
    }
    assert outcome.terminal in allowed
    if outcome.terminal is JobTerminalState.COMPLETED:
        assert outcome.result is not None
    else:
        assert outcome.reason in {
            "hard_deadline_exceeded",
            "cancelled_grace_exceeded",
            "worker_failed",
        }


def test_absolute_path_evidence_is_rejected() -> None:
    with pytest.raises(RuleEvidenceError):
        LaunchEvidence(
            subject_id="mod.a",
            source_kind="file",
            relative_path="C:/windows/abs.py",
            extractor_version="1.0.0",
        )


def test_interpret_cutoff_never_proves_absence() -> None:
    result = OperatorResult(truth=Truth.FALSE, cutoff=True, complete=False)
    assert interpret_operator_result(result) is ResultStatus.UNKNOWN
    fail = OperatorResult(truth=Truth.TRUE, cutoff=True, complete=False, members=("mod.a",))
    assert interpret_operator_result(fail) is ResultStatus.FAIL
    error = OperatorResult(error=True, reason="budget_exceeded")
    assert interpret_operator_result(error) is ResultStatus.ERROR


def test_in_process_evaluate_matches_isolated_payload_shape() -> None:
    yaml_text = _yaml_for("architecture.dependency-cycle", CYCLE_CONDITION)
    entry = CatalogEntry(rule_id="architecture.dependency-cycle", yaml_text=yaml_text)
    plan = SERVICE.plan([entry], purpose=ExecutionPurpose.PRODUCTION).entries[0].plan
    assert plan is not None and plan.condition is not None
    context = OperatorContext(declared_graph=_cycle_graph(cyclic=True))
    payload = {
        "plan": plan.condition.model_dump(mode="json"),
        "context": context.model_dump(mode="json"),
        "limits": None,
    }
    dumped = in_process_evaluate(payload)
    assert dumped["error"] is False
    assert dumped["truth"] == "true"


def test_workload_tiers_and_invalid_budget_flags() -> None:
    budgets = execution_budgets()
    assert wall_seconds_for_workload(budgets, eligible_files=10) == budgets.wall_seconds_tier_10k
    assert (
        wall_seconds_for_workload(budgets, eligible_files=10_001) == budgets.wall_seconds_tier_100k
    )
    assert memory_rss_for_workload(budgets, eligible_files=1) == (
        budgets.max_memory_rss_bytes_tier_10k
    )
    assert memory_rss_for_workload(budgets, eligible_files=50_000) == (
        budgets.max_memory_rss_bytes_tier_100k
    )
    with pytest.raises(ValueError):
        budgets_require_process_cap(budgets.model_copy(update={"process_enforced_hard_cap": False}))
    with pytest.raises(ValueError):
        budgets_require_process_cap(
            budgets.model_copy(update={"cooperative_callback_only_forbidden": False})
        )


def test_compile_failure_id_mismatch_and_overflow_stay_visible() -> None:
    broken = CatalogEntry(rule_id="architecture.dependency-cycle", yaml_text="kind: NotARule\n")
    mismatch = CatalogEntry(
        rule_id="architecture.other-cycle",
        yaml_text=_yaml_for("architecture.dependency-cycle", CYCLE_CONDITION),
    )
    planned = plan_launch_catalog(
        (broken, mismatch),
        purpose=ExecutionPurpose.PRODUCTION,
    )
    assert all(item.selected is False for item in planned.entries)
    assert {item.coverage_state for item in planned.entries} == {CoverageState.ERROR}
    tiny = execution_budgets().model_copy(update={"max_effective_rules": 1})
    overflow = plan_launch_catalog(
        (
            _cycle_entry(),
            CatalogEntry(
                rule_id="architecture.equals-declaration",
                yaml_text=_yaml_for("architecture.equals-declaration", EQUALS_CONDITION),
            ),
        ),
        purpose=ExecutionPurpose.PRODUCTION,
        budgets=tiny,
    )
    assert len(overflow.selected_rule_ids) == 1
    assert overflow.overflow_rule_ids
    assert "max_effective_rules" in overflow.limitations


def test_process_hard_deadline_zero_kills_without_callback() -> None:
    yaml_text = _yaml_for("architecture.dependency-cycle", CYCLE_CONDITION)
    entry = CatalogEntry(rule_id="architecture.dependency-cycle", yaml_text=yaml_text)
    plan = SERVICE.plan([entry], purpose=ExecutionPurpose.PRODUCTION).entries[0].plan
    assert plan is not None and plan.condition is not None
    payload = {
        "plan": plan.condition.model_dump(mode="json"),
        "context": OperatorContext(declared_graph=_cycle_graph(cyclic=True)).model_dump(
            mode="json"
        ),
        "limits": None,
    }
    outcome = run_isolated_evaluation(
        payload,
        budgets=execution_budgets(),
        hard_deadline_seconds=0,
    )
    assert outcome.terminal is JobTerminalState.KILLED
    assert outcome.reason == "hard_deadline_exceeded"


def test_evaluate_payload_rejects_unknown_operator() -> None:
    payload = {
        "plan": {"operator": "not-an-operator", "operands": []},
        "context": {},
        "limits": None,
    }
    with pytest.raises(ValidationError):
        evaluate_payload(payload)


def test_metric_and_scope_interpretation() -> None:
    na = OperatorResult(
        metric=MetricComputation(status=MetricStatus.NOT_APPLICABLE, reason="empty")
    )
    unknown = OperatorResult(
        metric=MetricComputation(status=MetricStatus.UNKNOWN, reason="partial")
    )
    errored = OperatorResult(metric=MetricComputation(status=MetricStatus.ERROR, reason="broken"))
    value = OperatorResult(metric=MetricComputation(status=MetricStatus.VALUE))
    assert interpret_operator_result(na) is ResultStatus.NOT_APPLICABLE
    assert interpret_operator_result(unknown) is ResultStatus.UNKNOWN
    assert interpret_operator_result(errored) is ResultStatus.ERROR
    assert interpret_operator_result(value) is ResultStatus.UNKNOWN
    assert (
        coverage_for_scope(enabled=False, suppressed=False, status=None) is CoverageState.DISABLED
    )
    assert (
        coverage_for_scope(enabled=True, suppressed=True, status=ResultStatus.FAIL)
        is CoverageState.SUPPRESSED
    )
    assert (
        coverage_for_scope(enabled=True, suppressed=False, status=ResultStatus.ERROR)
        is CoverageState.ERROR
    )
    assert (
        coverage_for_scope(enabled=True, suppressed=False, status=ResultStatus.NOT_APPLICABLE)
        is CoverageState.NOT_APPLICABLE
    )
    assert (
        coverage_for_scope(enabled=True, suppressed=False, status=ResultStatus.UNKNOWN)
        is CoverageState.UNKNOWN
    )


def test_projections_cover_fail_error_and_suppressed() -> None:
    fail = _run(
        [_cycle_entry()],
        OperatorContext(declared_graph=_cycle_graph(cyclic=True)),
    )
    text = SERVICE.project_json_text(fail)
    assert '"status": "fail"' in text
    suppressed = _run(
        [
            CatalogEntry(
                rule_id="architecture.dependency-cycle",
                yaml_text=_yaml_for("architecture.dependency-cycle", CYCLE_CONDITION),
                suppressed=True,
            )
        ],
        OperatorContext(declared_graph=_cycle_graph(cyclic=True)),
    )
    sarif = SERVICE.project_sarif(suppressed)
    assert sarif["runs"][0]["results"][0]["properties"]["suppressed"] is True
    error = _run([_cycle_entry()], OperatorContext())
    html = SERVICE.project_html(error)
    assert "status: error" in html


def test_purpose_candidate_and_production_preview_admit() -> None:
    with pytest.raises(PurposeAdmissionError):
        admit_execution_purpose(
            package_purpose=ExecutionPurpose.CANDIDATE_VALIDATION,
            requested_purpose=ExecutionPurpose.PRODUCTION,
        )
    admit_execution_purpose(
        package_purpose=ExecutionPurpose.PRODUCTION,
        requested_purpose=ExecutionPurpose.PREVIEW,
    )


def test_duplicate_evidence_and_record_validators() -> None:
    item = LaunchEvidence(
        subject_id="mod.a",
        source_kind="operator_members",
        extractor_version="1.0.0",
    )
    assert len(validate_launch_evidence((item, item))) == 1
    with pytest.raises(RuleResultValidationError):
        LaunchRuleRecord(
            rule_id="architecture.dependency-cycle",
            rule_revision="1.0.0",
            plan_digest="abc",
            status=ResultStatus.FAIL,
            coverage_state=CoverageState.COMPLETE,
            enabled=True,
            suppressed=False,
        )
    with pytest.raises(RuleResultValidationError):
        LaunchRuleRecord(
            rule_id="architecture.dependency-cycle",
            rule_revision="1.0.0",
            plan_digest="abc",
            status=ResultStatus.PASS,
            coverage_state=CoverageState.DISABLED,
            enabled=False,
            suppressed=False,
        )


def test_isolate_fn_error_and_not_applicable_coverage() -> None:
    def boom(*_args: object, **_kwargs: object) -> IsolatedOutcome:
        return IsolatedOutcome(terminal=JobTerminalState.FAILED, reason="worker_failed")

    body = SERVICE.execute(
        [_cycle_entry()],
        OperatorContext(declared_graph=_cycle_graph(cyclic=True)),
        purpose=ExecutionPurpose.PRODUCTION,
        isolate=True,
        isolate_fn=boom,
    )
    assert body.records[0].status is ResultStatus.ERROR
    na = interpret_operator_result(
        OperatorResult(
            metric=MetricComputation(status=MetricStatus.NOT_APPLICABLE, reason="empty_ratio")
        )
    )
    assert na is ResultStatus.NOT_APPLICABLE

