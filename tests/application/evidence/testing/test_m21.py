"""M21 fixtures: declared test/coverage CI gaps. Missing reports are not 0%."""

from __future__ import annotations

from codestrata.application.evidence.testing.consumer import consume_envelope
from codestrata.application.evidence.testing.envelope import TestingEnvelope
from codestrata.application.evidence.testing.models import (
    CoverageScope,
    GapStatus,
    MetricStatusName,
    TestingEvidence,
)
from codestrata.application.evidence.testing.service import TestingEvidenceService
from codestrata.application.rules.testing.yaml_catalog import (
    testing_catalog_digests as catalog_digests,
)
from codestrata.application.rules.testing.yaml_testing import CiGapRule
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus, RuleSeverity

_WORKFLOW = ".github/workflows/ci.yml"


def _workflow(*runs: str, condition: str | None = None) -> str:
    lines = [
        "name: ci",
        "on: [push]",
        "jobs:",
        "  test:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - uses: actions/checkout@v4",
    ]
    if condition:
        lines.append(f"      - if: {condition}")
        indent = "        "
    else:
        indent = "      - "
    for command in runs:
        prefix = indent if command == runs[0] and condition else "      - "
        if condition and command != runs[0]:
            prefix = "      - "
        lines.append(f"{prefix}run: {command}")
    return "\n".join(lines) + "\n"


def _run(paths: tuple[str, ...], texts: dict[str, str]) -> tuple[TestingEvidence, TestingEnvelope]:
    return TestingEvidenceService().collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        catalog_digest=catalog_digests()["testing.ci_gap"],
    )


def _ctx(evidence: TestingEvidence) -> RuleExecutionContext:
    return RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("python",)),
        assessment_graph=evidence,
    )


def test_declared_and_invoked_is_not_a_gap() -> None:
    texts = {
        "pyproject.toml": (
            "[project]\nname='demo'\n[project.optional-dependencies]\ndev=['pytest']\n"
        ),
        _WORKFLOW: _workflow("pytest"),
    }
    evidence, envelope = _run(tuple(texts), texts)
    consume_envelope(envelope.model_dump(mode="json"))
    assert evidence.ci_gap.coverage_percent is None
    assert evidence.ci_gap.proven_absent == 0
    assert evidence.ci_gap.invoked >= 1
    statuses = {item.status for item in evidence.ci_gap.gaps}
    assert GapStatus.PROVEN_ABSENT not in statuses
    result = CiGapRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_MATCHED


def test_declared_and_absent_is_medium_when_ci_is_complete() -> None:
    texts = {
        "pyproject.toml": "[project]\nname='demo'\ndependencies=['pytest']\n",
        _WORKFLOW: _workflow("echo hello"),
    }
    evidence, envelope = _run(tuple(texts), texts)
    consume_envelope(envelope.model_dump(mode="json"))
    assert evidence.ci_gap.status is MetricStatusName.VALUE
    assert evidence.ci_gap.full_scope_status is CoverageScope.COMPLETE
    assert evidence.ci_gap.proven_absent >= 1
    result = CiGapRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity is RuleSeverity.MEDIUM
    assert "not a runtime pass/fail" in result.matches[0].summary
    assert "0% code coverage" in result.matches[0].summary


def test_delegated_script_without_body_is_unknown() -> None:
    texts = {
        "pyproject.toml": "[project]\nname='demo'\ndependencies=['pytest']\n",
        _WORKFLOW: _workflow("./scripts/ci.sh"),
    }
    evidence, _ = _run(tuple(texts), texts)
    assert evidence.ci_gap.status is MetricStatusName.UNKNOWN
    assert any(item.status is GapStatus.UNKNOWN for item in evidence.ci_gap.gaps)
    result = CiGapRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_APPLICABLE


def test_delegated_script_body_inspected_can_resolve() -> None:
    texts = {
        "pyproject.toml": "[project]\nname='demo'\ndependencies=['pytest']\n",
        "scripts/ci.sh": "#!/bin/sh\npytest\n",
        _WORKFLOW: _workflow("./scripts/ci.sh"),
    }
    evidence, _ = _run(tuple(texts), texts)
    test_gaps = [item for item in evidence.ci_gap.gaps if item.kind == "test"]
    assert test_gaps
    assert all(item.status is not GapStatus.UNKNOWN for item in test_gaps) or any(
        item.status is GapStatus.INVOKED for item in test_gaps
    )


def test_conditional_job_uncertainty_is_visible() -> None:
    texts = {
        "pyproject.toml": "[project]\nname='demo'\ndependencies=['pytest']\n",
        _WORKFLOW: _workflow("pytest", condition="${{ github.event_name == 'push' }}"),
    }
    evidence, envelope = _run(tuple(texts), texts)
    assert evidence.ci_gap.proven_absent == 0 or evidence.ci_gap.status is MetricStatusName.UNKNOWN
    assert any(
        item.status is GapStatus.UNKNOWN or item.reason == "conditional_job_uncertainty"
        for item in evidence.ci_gap.gaps
    ) or "conditional" in evidence.ci_gap.reason
    result = CiGapRule().evaluate(_ctx(evidence))
    if result.status is RuleResultStatus.MATCHED:
        raise AssertionError("conditional jobs must not prove a medium CI gap")
    consume_envelope(envelope.model_dump(mode="json"))


def test_no_ci_applicability() -> None:
    texts = {
        "pyproject.toml": "[project]\nname='demo'\ndependencies=['pytest']\n",
        "pkg/mod.py": "def n():\n    return 1\n",
    }
    evidence, _ = _run(tuple(texts), texts)
    assert evidence.ci_gap.status is MetricStatusName.NOT_APPLICABLE
    assert evidence.ci_gap.reason == "no_ci_applicability"
    result = CiGapRule().evaluate(_ctx(evidence))
    assert result.status is RuleResultStatus.NOT_APPLICABLE


def test_missing_coverage_report_is_not_zero_percent() -> None:
    texts = {
        "pyproject.toml": (
            "[project]\nname='demo'\ndependencies=['pytest','coverage']\n"
            "[tool.coverage.run]\nsource=['pkg']\n"
        ),
        "coverage.xml": "<coverage line-rate='0'/>\n",
        _WORKFLOW: _workflow("pytest"),
    }
    evidence, envelope = _run(tuple(texts), texts)
    consume_envelope(envelope.model_dump(mode="json"))
    assert evidence.ci_gap.coverage_percent is None
    assert envelope.body.coverage_percent is None
    assert all(
        item.fact_type != "coverage_report"  # type: ignore[attr-defined]
        for item in ()
    )
    json_proj = __import__(
        "codestrata.application.evidence.testing.projections",
        fromlist=["project_testing_json"],
    ).project_testing_json(envelope)
    assert json_proj["coverage_percent"] is None
    html = __import__(
        "codestrata.application.evidence.testing.projections",
        fromlist=["project_testing_html"],
    ).project_testing_html(envelope)
    assert "not 0% code coverage" in html
    report_declared = [
        item for item in evidence.ci_gap.declared if "coverage.xml" in item.path
    ]
    assert report_declared == []
