"""Focused complexity evidence tests (Phase 4.3.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.evidence.language.complexity.artifacts import (
    complexity_evidence_payload,
    write_complexity_evidence_artifact,
)
from codestrata.application.evidence.language.complexity.paths import (
    is_complexity_source_path,
)
from codestrata.application.evidence.language.complexity.service import (
    ComplexityEvidenceService,
    create_complexity_evidence_service,
)
from codestrata.application.technical_debt.evidence import (
    complexity_evidence_for_debt,
    complexity_taxonomy_category,
)
from codestrata.config.settings import ComplexityEvidenceSettings
from codestrata.domain.evidence.language.capabilities import SourceClassification
from codestrata.domain.evidence.language.complexity.enums import MetricAvailability
from codestrata.domain.evidence.language.complexity.models import (
    AggregatedComplexityEvidence,
    IntMetric,
)
from codestrata.domain.technical_debt.taxonomy import TechnicalDebtCategory
from codestrata.services.artifact_serialization import dumps_stable_json, loads_stable_json

FIXTURES = Path(__file__).parent / "fixtures"


def _load_tree(root: Path) -> tuple[tuple[str, ...], dict[str, str]]:
    paths: list[str] = []
    texts: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".java", ".php", ".cs"}:
            continue
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        paths.append(relative)
        texts[relative] = path.read_text(encoding="utf-8")
    return tuple(paths), texts


def test_int_metric_availability_contract() -> None:
    assert IntMetric.available(0).value == 0
    assert IntMetric.unsupported().value is None
    assert IntMetric.unavailable().value is None
    with pytest.raises(ValueError):
        IntMetric(availability=MetricAvailability.AVAILABLE, value=None)
    with pytest.raises(ValueError):
        IntMetric(availability=MetricAvailability.UNSUPPORTED, value=0)


def test_python_normal_nested_branching_and_params() -> None:
    paths, texts = _load_tree(FIXTURES / "python")
    settings = ComplexityEvidenceSettings().model_copy(
        update={
            "java": ComplexityEvidenceSettings().java.model_copy(update={"enabled": False})
        }
    )
    result = ComplexityEvidenceService(settings).collect(
        repository_id="repo:fixture",
        relative_paths=paths,
        file_texts=texts,
    )
    normal = next(item for item in result.files if item.path.endswith("normal.py"))
    assert normal.physical_line_count.availability is MetricAvailability.AVAILABLE
    assert normal.physical_line_count.value is not None and normal.physical_line_count.value > 0
    compute = next(item for item in result.callables if item.name == "compute")
    assert compute.parameter_count.value == 5  # a,b,c,*args,**kwargs
    assert compute.branch_point_count.value is not None
    assert compute.branch_point_count.value >= 5
    assert compute.max_nesting_depth.value is not None
    assert compute.max_nesting_depth.value >= 2
    nested = next(item for item in result.callables if item.name == "nested")
    assert nested.max_nesting_depth.value is not None
    assert nested.max_nesting_depth.value >= 3
    assert nested.parameter_count.value == 1  # value; self excluded
    init = next(item for item in result.callables if item.name == "__init__")
    assert init.parameter_count.value == 1  # seed; self excluded
    empty = next(item for item in result.callables if item.name == "empty_fn")
    assert empty.parameter_count.value == 0
    assert empty.branch_point_count.value == 0
    calc = next(item for item in result.types if item.name == "Calculator")
    assert calc.callable_count.value == 2
    module = next(
        item for item in result.types if item.type_kind.value == "module" and "normal" in item.path
    )
    assert module.physical_line_count.value == normal.physical_line_count.value


def test_python_test_role_preserved() -> None:
    paths, texts = _load_tree(FIXTURES / "python")
    settings = ComplexityEvidenceSettings().model_copy(
        update={
            "java": ComplexityEvidenceSettings().java.model_copy(update={"enabled": False})
        }
    )
    result = ComplexityEvidenceService(settings).collect(
        repository_id="repo:fixture",
        relative_paths=paths,
        file_texts=texts,
    )
    test_file = next(item for item in result.files if "tests/" in item.path)
    assert test_file.classification is SourceClassification.TEST
    test_callable = next(item for item in result.callables if item.name == "test_add")
    assert test_callable.classification is SourceClassification.TEST


def test_python_syntax_error_keeps_physical_lines() -> None:
    paths, texts = _load_tree(FIXTURES / "python")
    settings = ComplexityEvidenceSettings().model_copy(
        update={
            "java": ComplexityEvidenceSettings().java.model_copy(update={"enabled": False})
        }
    )
    result = ComplexityEvidenceService(settings).collect(
        repository_id="repo:fixture",
        relative_paths=paths,
        file_texts=texts,
    )
    broken = next(item for item in result.files if item.path.endswith("unsupported_syntax.py"))
    assert broken.physical_line_count.availability is MetricAvailability.AVAILABLE
    assert broken.type_count.availability is MetricAvailability.UNAVAILABLE
    assert any("python_syntax_error" in item for item in result.diagnostics)


def test_java_normal_and_empty() -> None:
    paths, texts = _load_tree(FIXTURES / "java")
    settings = ComplexityEvidenceSettings().model_copy(
        update={
            "python": ComplexityEvidenceSettings().python.model_copy(update={"enabled": False})
        }
    )
    result = ComplexityEvidenceService(settings).collect(
        repository_id="repo:fixture",
        relative_paths=paths,
        file_texts=texts,
    )
    sample = next(item for item in result.types if item.name == "Sample")
    assert sample.callable_count.value == 3
    compute = next(item for item in result.callables if item.name == "compute")
    assert compute.parameter_count.value == 3
    assert compute.branch_point_count.value is not None
    assert compute.branch_point_count.value >= 5
    assert compute.max_nesting_depth.value is not None
    assert compute.max_nesting_depth.value >= 2
    empty = next(item for item in result.types if item.name == "EmptyClass")
    assert empty.callable_count.value == 0
    empty_method = next(item for item in result.callables if item.name == "emptyMethod")
    assert empty_method.parameter_count.value == 0
    assert empty_method.branch_point_count.value == 0


def test_php_normal_branching_and_params() -> None:
    paths, texts = _load_tree(FIXTURES / "php")
    settings = ComplexityEvidenceSettings().model_copy(
        update={
            "python": ComplexityEvidenceSettings().python.model_copy(update={"enabled": False}),
            "java": ComplexityEvidenceSettings().java.model_copy(update={"enabled": False}),
        }
    )
    result = ComplexityEvidenceService(settings).collect(
        repository_id="repo:php-fixture",
        relative_paths=paths,
        file_texts=texts,
    )
    assert "language.php.complexity" in result.contributing_provider_ids
    sample = next(item for item in result.types if item.name == "Sample")
    assert sample.callable_count.value is not None and sample.callable_count.value >= 3
    compute = next(item for item in result.callables if item.name == "compute")
    assert compute.language == "php"
    assert compute.parameter_count.value == 3
    assert compute.branch_point_count.value is not None
    assert compute.branch_point_count.value >= 5
    assert compute.max_nesting_depth.value is not None
    assert compute.max_nesting_depth.value >= 2
    ctor = next(item for item in result.callables if item.name == "__construct")
    assert ctor.parameter_count.value == 1
    helper = next(item for item in result.callables if item.name == "top_level_helper")
    assert helper.parameter_count.value == 1
    assert helper.branch_point_count.value is not None
    assert helper.branch_point_count.value >= 1


def test_csharp_normal_branching_and_params() -> None:
    paths, texts = _load_tree(FIXTURES / "csharp")
    settings = ComplexityEvidenceSettings().model_copy(
        update={
            "python": ComplexityEvidenceSettings().python.model_copy(update={"enabled": False}),
            "java": ComplexityEvidenceSettings().java.model_copy(update={"enabled": False}),
            "php": ComplexityEvidenceSettings().php.model_copy(update={"enabled": False}),
        }
    )
    result = ComplexityEvidenceService(settings).collect(
        repository_id="repo:csharp-fixture",
        relative_paths=paths,
        file_texts=texts,
    )
    assert "language.csharp.complexity" in result.contributing_provider_ids
    sample = next(item for item in result.types if item.name == "Calculator")
    assert sample.callable_count.value is not None and sample.callable_count.value >= 2
    complex_score = next(item for item in result.callables if item.name == "ComplexScore")
    assert complex_score.language == "csharp"
    assert complex_score.parameter_count.value == 1
    assert complex_score.branch_point_count.value is not None
    assert complex_score.branch_point_count.value >= 4


def test_java_test_role_preserved() -> None:
    paths, texts = _load_tree(FIXTURES / "java")
    settings = ComplexityEvidenceSettings().model_copy(
        update={
            "python": ComplexityEvidenceSettings().python.model_copy(update={"enabled": False})
        }
    )
    result = ComplexityEvidenceService(settings).collect(
        repository_id="repo:fixture",
        relative_paths=paths,
        file_texts=texts,
    )
    test_file = next(item for item in result.files if "tests/" in item.path)
    assert test_file.classification is SourceClassification.TEST


def test_codestrata_workspace_excluded_from_measurement() -> None:
    product_java = (FIXTURES / "java" / "Sample.java").read_text(encoding="utf-8")
    contaminated = (FIXTURES / "codestrata_workspace" / "Contaminated.java").read_text(
        encoding="utf-8"
    )
    relative_paths = (
        "src/main/java/com/example/Sample.java",
        ".codestrata/workspace/spring-petclinic/src/Contaminated.java",
        "vendor/lib/Skip.java",
    )
    file_texts = {
        relative_paths[0]: product_java,
        relative_paths[1]: contaminated,
        relative_paths[2]: contaminated,
    }
    assert is_complexity_source_path(relative_paths[1], language="java") is False
    result = create_complexity_evidence_service().collect(
        repository_id="repo:assess",
        relative_paths=relative_paths,
        file_texts=file_texts,
    )
    measured_paths = {item.path for item in result.files}
    assert relative_paths[0] in measured_paths
    assert relative_paths[1] not in measured_paths
    assert relative_paths[2] not in measured_paths
    assert all(".codestrata" not in item.path for item in result.callables)


def test_deterministic_serialization_and_repeated_identity() -> None:
    paths, texts = _load_tree(FIXTURES / "python")
    # Include a java file too for multi-language stability.
    java_paths, java_texts = _load_tree(FIXTURES / "java")
    all_paths = tuple(sorted(set(paths) | set(java_paths)))
    all_texts = {**texts, **java_texts}
    service = create_complexity_evidence_service()
    first = service.collect(
        repository_id="repo:stable",
        relative_paths=all_paths,
        file_texts=all_texts,
        configuration_fingerprint="fp-1",
    )
    second = service.collect(
        repository_id="repo:stable",
        relative_paths=all_paths,
        file_texts=all_texts,
        configuration_fingerprint="fp-1",
    )
    assert first == second
    payload = dumps_stable_json(complexity_evidence_payload(first))
    assert payload == dumps_stable_json(complexity_evidence_payload(second))
    restored = AggregatedComplexityEvidence.model_validate(loads_stable_json(payload))
    assert restored == first
    assert [item.evidence_id for item in first.files] == [
        item.evidence_id for item in second.files
    ]
    assert [item.evidence_id for item in first.callables] == [
        item.evidence_id for item in second.callables
    ]


def test_artifact_write(tmp_path: Path) -> None:
    evidence = create_complexity_evidence_service().collect(
        repository_id="repo:demo",
        relative_paths=("demo.py",),
        file_texts={"demo.py": "def f(x):\n    return x\n"},
    )
    written = write_complexity_evidence_artifact(evidence, tmp_path)
    assert written.path.name == "complexity-evidence.json"
    assert written.file_count == 1
    restored = AggregatedComplexityEvidence.model_validate(
        loads_stable_json(written.path.read_text(encoding="utf-8"))
    )
    assert restored == evidence


def test_debt_projection_is_passthrough() -> None:
    evidence = create_complexity_evidence_service().collect(
        repository_id="repo:demo",
        relative_paths=("demo.py",),
        file_texts={"demo.py": "def f():\n    pass\n"},
    )
    assert complexity_evidence_for_debt(evidence) is evidence
    assert complexity_taxonomy_category() is TechnicalDebtCategory.COMPLEXITY


def test_javascript_not_measured() -> None:
    result = create_complexity_evidence_service().collect(
        repository_id="repo:js",
        relative_paths=("app.js",),
        file_texts={"app.js": "function f(a,b){ if(a){ return b; } }"},
    )
    assert result.files == ()
    assert result.callables == ()
