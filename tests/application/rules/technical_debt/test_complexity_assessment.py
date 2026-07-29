"""Technical Debt complexity assessment vertical integration tests (Phase 4.3.4)."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.rules.technical_debt.assessment import (
    complexity_evidence_collection_enabled,
    evaluate_technical_debt_pack_for_context_detailed,
    technical_debt_pack_enabled,
)
from codestrata.application.technical_debt.assessment.artifacts import (
    write_technical_debt_assessment_artifact,
)
from codestrata.application.technical_debt.assessment.assembler import (
    TechnicalDebtAssessmentAssembler,
)
from codestrata.application.technical_debt.assessment.factory import (
    technical_debt_assessment_section_enabled,
)
from codestrata.config.settings import (
    AssessmentSectionsSettings,
    AssessmentSettings,
    CodestrataSettings,
    ComplexityEvidenceSettings,
    EvidenceSettings,
    RepositorySettings,
    RulesSettings,
    TechnicalDebtAssessmentSectionSettings,
    TechnicalDebtComplexityLargeCallableSettings,
    TechnicalDebtComplexitySettings,
    TechnicalDebtRulesSettings,
    load_settings,
)
from codestrata.domain.findings.enums import FindingSeverity
from codestrata.domain.technical_debt.assessment.enums import TechnicalDebtAssessmentStatus
from codestrata.domain.technical_debt.assessment.models import TechnicalDebtAssessmentSection
from codestrata.domain.technical_debt.ids import RULE_LARGE_CALLABLE
from codestrata.models import Repository
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json
from codestrata.services.graph_assessment import GraphAssessmentPipeline
from codestrata.services.rule_engine import rule_context_from_pipeline


def _write_repo(root: Path, paths: dict[str, str]) -> Repository:
    root.mkdir(parents=True, exist_ok=True)
    for relative, text in paths.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    files = sorted(paths)
    return Repository(
        name="fixture",
        path=root.resolve(),
        files=files,
        total_files=len(files),
    )


def _settings(
    *,
    rules_enabled: bool = True,
    debt_enabled: bool = True,
    complexity_enabled: bool = True,
    section_enabled: bool = True,
    large_callable_max: int = 50,
) -> CodestrataSettings:
    return CodestrataSettings(
        repository=RepositorySettings(path="."),
        rules=RulesSettings(
            enabled=rules_enabled,
            technical_debt=TechnicalDebtRulesSettings(
                enabled=debt_enabled,
                complexity=TechnicalDebtComplexitySettings(
                    enabled=True,
                    large_callable=TechnicalDebtComplexityLargeCallableSettings(
                        max_physical_lines=large_callable_max
                    ),
                ),
            ),
        ),
        evidence=EvidenceSettings(
            complexity=ComplexityEvidenceSettings(enabled=complexity_enabled)
        ),
        assessment=AssessmentSettings(
            sections=AssessmentSectionsSettings(
                technical_debt=TechnicalDebtAssessmentSectionSettings(
                    enabled=section_enabled
                )
            )
        ),
    )


def test_feature_gate_matrix(tmp_path: Path) -> None:
    config = tmp_path / "codestrata.toml"
    config.write_text('[repository]\npath = "."\n', encoding="utf-8")
    defaults = load_settings(config)
    assert technical_debt_pack_enabled(defaults) is False
    assert technical_debt_assessment_section_enabled(defaults) is False
    assert complexity_evidence_collection_enabled(defaults) is True
    assert technical_debt_pack_enabled(_settings(rules_enabled=False)) is False
    assert technical_debt_pack_enabled(_settings(debt_enabled=False)) is False
    assert technical_debt_pack_enabled(_settings()) is True


def test_orchestration_exclusions_roles_thresholds(tmp_path: Path) -> None:
    paths = {
        "src/app.py": "def big():\n" + ("    x = 1\n" * 80),
        "src/edge.py": "def edge():\n" + ("    x = 1\n" * 49),
        "src/web.js": "function f(a,b,c,d,e,f){ if(a){ if(b){ return c; }} }",
        "tests/test_app.py": "def test_ok():\n    assert True\n",
        ".codestrata/workspace/clone/Bad.java": (
            "public class Bad { public void m(){ " + ("if(true){ " * 8) + ("}" * 8) + "} }"
        ),
    }
    repo = _write_repo(tmp_path / "repo", paths)
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    settings = _settings(large_callable_max=50)
    result = evaluate_technical_debt_pack_for_context_detailed(
        legacy_context=context,
        settings=settings,
        repository_root=repo.path,
        file_texts=paths,
    )
    assert result.complexity_evidence is not None
    assert all(".codestrata/" not in item.path for item in result.complexity_evidence.files)
    assert all(not item.path.endswith(".js") for item in result.complexity_evidence.files)
    test_files = [item for item in result.complexity_evidence.files if "tests/" in item.path]
    assert test_files
    assert all(item.classification.value == "test" for item in test_files)
    assert any(item.rule_id == RULE_LARGE_CALLABLE for item in result.evaluation.findings)

    measured = next(
        item
        for item in result.complexity_evidence.callables
        if item.name == "edge" and item.physical_line_count.value is not None
    )
    threshold = int(measured.physical_line_count.value or 0)
    boundary = evaluate_technical_debt_pack_for_context_detailed(
        legacy_context=context,
        settings=_settings(large_callable_max=threshold),
        repository_root=repo.path,
        file_texts=paths,
    )
    assert all(
        measured.qualified_signature not in (item.metadata.get("subject_keys") or "")
        for item in boundary.evaluation.findings
        if item.rule_id == RULE_LARGE_CALLABLE
    )
    plus = evaluate_technical_debt_pack_for_context_detailed(
        legacy_context=context,
        settings=_settings(large_callable_max=max(threshold - 1, 1)),
        repository_root=repo.path,
        file_texts=paths,
    )
    assert any(
        measured.qualified_signature in (item.metadata.get("subject_keys") or "")
        for item in plus.evaluation.findings
        if item.rule_id == RULE_LARGE_CALLABLE
    )


def test_complexity_disabled_yields_no_findings(tmp_path: Path) -> None:
    paths = {"src/app.py": "def big():\n" + ("    x=1\n" * 80)}
    repo = _write_repo(tmp_path / "repo", paths)
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    result = evaluate_technical_debt_pack_for_context_detailed(
        legacy_context=context,
        settings=_settings(complexity_enabled=False),
        repository_root=repo.path,
        file_texts=paths,
    )
    assert result.complexity_evidence is None
    assert result.evaluation.findings == ()
    assert "complexity_evidence_disabled" in result.diagnostics


def test_empty_repository_section_status(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path / "repo", {"README.md": "# empty\n"})
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    result = evaluate_technical_debt_pack_for_context_detailed(
        legacy_context=context,
        settings=_settings(),
        repository_root=repo.path,
        file_texts={},
    )
    section = TechnicalDebtAssessmentAssembler().assemble(
        repository_id="repo:empty",
        findings=result.evaluation.findings,
        pack_enabled=True,
        complexity_evidence_enabled=True,
        complexity_evidence=result.complexity_evidence,
        files_considered=result.files_considered,
        files_analyzed=result.files_analyzed,
        evidence_pipeline=result.evidence_pipeline,
        evidence_fingerprint=result.evidence_fingerprint,
        diagnostics=result.diagnostics,
    )
    assert section.status in {
        TechnicalDebtAssessmentStatus.INSUFFICIENT_EVIDENCE,
        TechnicalDebtAssessmentStatus.SUCCEEDED,
    }


def test_section_disabled_vs_pack_disabled() -> None:
    disabled = TechnicalDebtAssessmentAssembler().assemble_disabled(repository_id="repo:demo")
    assert disabled.status is TechnicalDebtAssessmentStatus.DISABLED
    assert technical_debt_assessment_section_enabled(_settings(section_enabled=False)) is False


def test_deterministic_artifact_round_trip(tmp_path: Path) -> None:
    paths = {"src/app.py": "def big(a,b,c,d,e,f):\n" + ("    if a:\n        x=1\n" * 40)}
    repo = _write_repo(tmp_path / "repo", paths)
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    settings = _settings(large_callable_max=10)
    first = evaluate_technical_debt_pack_for_context_detailed(
        legacy_context=context,
        settings=settings,
        repository_root=repo.path,
        file_texts=paths,
    )
    second = evaluate_technical_debt_pack_for_context_detailed(
        legacy_context=context,
        settings=settings,
        repository_root=repo.path,
        file_texts=paths,
    )
    assert [item.id for item in first.evaluation.findings] == [
        item.id for item in second.evaluation.findings
    ]
    assert first.evidence_fingerprint == second.evidence_fingerprint
    assembler = TechnicalDebtAssessmentAssembler()
    section_one = assembler.assemble(
        repository_id="repo:demo",
        findings=first.evaluation.findings,
        pack_enabled=True,
        complexity_evidence_enabled=True,
        complexity_evidence=first.complexity_evidence,
        evidence_pipeline=first.evidence_pipeline,
        evidence_fingerprint=first.evidence_fingerprint,
        files_considered=first.files_considered,
        files_analyzed=first.files_analyzed,
        files_excluded=first.files_excluded,
        files_failed=first.files_failed,
        debt_rules_planned=5,
        rules_executed=len(first.evaluation.rules_evaluated),
        rules_matched=len(first.evaluation.findings),
        diagnostics=first.diagnostics,
        configuration_payload="stable-payload",
    )
    section_two = assembler.assemble(
        repository_id="repo:demo",
        findings=second.evaluation.findings,
        pack_enabled=True,
        complexity_evidence_enabled=True,
        complexity_evidence=second.complexity_evidence,
        evidence_pipeline=second.evidence_pipeline,
        evidence_fingerprint=second.evidence_fingerprint,
        files_considered=second.files_considered,
        files_analyzed=second.files_analyzed,
        files_excluded=second.files_excluded,
        files_failed=second.files_failed,
        debt_rules_planned=5,
        rules_executed=len(second.evaluation.rules_evaluated),
        rules_matched=len(second.evaluation.findings),
        diagnostics=second.diagnostics,
        configuration_payload="stable-payload",
    )
    assert section_one == section_two
    written = write_technical_debt_assessment_artifact(section_one, tmp_path / "out")
    restored = TechnicalDebtAssessmentSection.model_validate(
        loads_stable_json(written.path.read_text(encoding="utf-8"))
    )
    assert restored == section_one
    assert dumps_stable_json(section_one.model_dump(mode="json")) == written.path.read_text(
        encoding="utf-8"
    )


def test_severity_high_requires_two_times_threshold(tmp_path: Path) -> None:
    huge = {"src/huge.py": "def huge():\n" + ("    x = 1\n" * 100)}
    repo = _write_repo(tmp_path / "huge", huge)
    context = rule_context_from_pipeline(GraphAssessmentPipeline().run(repo))
    result = evaluate_technical_debt_pack_for_context_detailed(
        legacy_context=context,
        settings=_settings(large_callable_max=50),
        repository_root=repo.path,
        file_texts=huge,
    )
    large = [item for item in result.evaluation.findings if item.rule_id == RULE_LARGE_CALLABLE]
    assert large
    assert large[0].severity is FindingSeverity.HIGH
    assert large[0].metadata.get("severity_basis") == "value>50*2"
    assert large[0].metadata.get("metric") == "physical_line_count"
    assert int(large[0].metadata.get("value") or 0) > 100
    assert large[0].metadata.get("classification") == "source"
    assert large[0].evidence[0].excerpt

    medium_paths = {"src/med.py": "def med():\n" + ("    x = 1\n" * 60)}
    med_repo = _write_repo(tmp_path / "med", medium_paths)
    med_context = rule_context_from_pipeline(GraphAssessmentPipeline().run(med_repo))
    medium = evaluate_technical_debt_pack_for_context_detailed(
        legacy_context=med_context,
        settings=_settings(large_callable_max=50),
        repository_root=med_repo.path,
        file_texts=medium_paths,
    )
    med_findings = [
        item for item in medium.evaluation.findings if item.rule_id == RULE_LARGE_CALLABLE
    ]
    assert med_findings
    assert med_findings[0].severity is FindingSeverity.MEDIUM
    assert med_findings[0].metadata.get("severity_basis") == "value>50"
