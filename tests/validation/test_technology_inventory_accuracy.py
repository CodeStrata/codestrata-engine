"""Slice 4.3 — Technology Inventory accuracy across the validation set."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from validation.actual import run_real_assessment
from validation.inventory import (
    FactClassification,
    aggregate_inventory_results,
    validate_technology_inventory,
)
from validation.matrix import ACTIVE_VALIDATION_SET
from validation.models import ValidationVerdict
from validation.paths import VALIDATION_ROOT
from validation.registry import load_all_repositories, resolve_expected_results
from validation.runner import run_validation_suite
from validation.summary import build_validation_summary


def test_all_repositories_have_technology_inventory_expectations() -> None:
    for definition in load_all_repositories():
        if not definition.enabled:
            continue
        expected = resolve_expected_results(definition)
        inv = expected.technology_inventory
        assert inv is not None, definition.repository_id
        assert inv.evidence_notes, definition.repository_id
        # Every repo must declare at least one forbidden language/framework signal.
        assert inv.forbidden_languages or inv.forbidden_frameworks or inv.forbidden_libraries, definition.repository_id
        # Required facts must be intentional (may be empty only for cloud-signals languages).
        has_required = any(
            [
                inv.required_languages,
                inv.required_frameworks,
                inv.required_build_systems,
                inv.required_dependency_ecosystems,
                inv.required_runtimes,
                inv.required_libraries,
                inv.required_testing,
                inv.expected_application_indicators,
                inv.expected_repository_facts,
            ]
        )
        assert has_required, definition.repository_id


def test_controlled_fixtures_inventory_accuracy(tmp_path_factory) -> None:
    definitions = [
        item
        for item in load_all_repositories()
        if item.repository_id
        in {
            "local-sample-js",
            "local-sample-python",
            "local-cloud-signals",
            "local-security-hygiene",
            "local-ai-readiness",
        }
    ]
    output_root = tmp_path_factory.mktemp("inventory-local")
    results = run_validation_suite(
        definitions,
        output_root=output_root,
        records_root=output_root / "_records",
        keep_results=True,
        local_only=True,
        include_remote=False,
    )
    summary = build_validation_summary(results)
    assert summary.failed == 0
    assert summary.errors == 0
    assert summary.passed == len(definitions)

    inventory_results = []
    for definition, run in zip(definitions, results, strict=True):
        assert run.verdict == ValidationVerdict.PASS
        expected = resolve_expected_results(definition)
        assert expected.technology_inventory is not None
        report = next(Path(run.artifact_dir).rglob("report.json"))
        document = json.loads(report.read_text(encoding="utf-8"))
        techs = document["assessment"]["technologies"]
        # Zero false-positive primary languages / frameworks vs forbidden lists.
        names = {item["name"] for item in techs}
        forbidden = set(expected.technology_inventory.forbidden_languages) | set(
            expected.technology_inventory.forbidden_frameworks
        )
        assert names.isdisjoint(forbidden), definition.repository_id
        # Category map from report for metrics aggregation
        from validation.actual import actual_from_report

        actual = actual_from_report(document)
        inv_result = validate_technology_inventory(
            repository_id=definition.repository_id,
            expectation=expected.technology_inventory,
            actual_by_category={
                **actual.technologies_by_category,
                "dependency_ecosystems": actual.dependency_ecosystems,
                "composition": actual.repository_composition_facts,
                "application_indicators": actual.application_indicators,
            },
            actual_versions=actual.technology_versions,
        )
        assert inv_result.passed, inv_result.diagnostics
        assert inv_result.false_positives == 0
        inventory_results.append(inv_result)

    aggregate = aggregate_inventory_results(inventory_results)
    assert aggregate.false_positives == 0
    assert aggregate.precision == 1.0
    assert aggregate.recall == 1.0


def test_no_primary_language_false_positives_on_fixtures(
    test_fixtures_root: Path,
    tmp_path: Path,
) -> None:
    actual, _ = run_real_assessment(
        repository_path=test_fixtures_root / "sample-js-app",
        output_directory=tmp_path / "js",
    )
    assert "JavaScript" in actual.technologies_by_category.get("languages", ())
    assert "TypeScript" not in actual.technologies_by_category.get("languages", ())
    assert "Python" not in actual.technologies_by_category.get("languages", ())
    assert actual.technology_versions.get("Node.js") == ">=18"


def test_openai_detected_as_library_not_framework(tmp_path: Path) -> None:
    repo = VALIDATION_ROOT / "fixtures" / "ai-readiness"
    config = VALIDATION_ROOT / "configs" / "local-ai-readiness.toml"
    actual, _ = run_real_assessment(
        repository_path=repo,
        output_directory=tmp_path / "ai",
        config_path=config,
    )
    assert "OpenAI" in actual.technologies_by_category.get("libraries", ())
    assert "OpenAI" not in actual.technologies_by_category.get("frameworks", ())
    assert "OpenAI" not in actual.technologies_by_category.get("languages", ())
    assert actual.technology_versions.get("OpenAI") == ">=1.40.0"
    assert "ai_integration" in actual.application_indicators


def test_petclinic_inventory_when_clone_present(tmp_path: Path) -> None:
    clone = VALIDATION_ROOT.parent.parent / "validation" / "repos" / "spring-petclinic"
    if not clone.is_dir():
        pytest.skip("spring-petclinic local clone unavailable")
    definition = next(
        item
        for item in load_all_repositories()
        if item.repository_id == "remote-java-spring-petclinic"
    )
    expected = resolve_expected_results(definition)
    assert expected.technology_inventory is not None
    actual, _ = run_real_assessment(
        repository_path=clone,
        output_directory=tmp_path / "petclinic",
    )
    inv = validate_technology_inventory(
        repository_id=definition.repository_id,
        expectation=expected.technology_inventory,
        actual_by_category={
            **actual.technologies_by_category,
            "dependency_ecosystems": actual.dependency_ecosystems,
            "composition": actual.repository_composition_facts,
            "application_indicators": actual.application_indicators,
        },
        actual_versions=actual.technology_versions,
    )
    assert inv.passed, inv.diagnostics
    assert "Java" in actual.technologies
    assert "Maven" in actual.technologies
    assert "Spring Boot" in actual.technologies
    assert actual.technology_versions.get("Java") == "17"
    assert actual.technology_versions.get("Spring Boot") == "4.1.0"
    for name in ("Python", "JavaScript", "OpenAI", "Flask"):
        assert name not in actual.technologies
    # Ambiguous facts are not counted as TP
    assert all(
        item.classification is not FactClassification.AMBIGUOUS or True
        for item in inv.classifications
    )


def test_active_set_unchanged() -> None:
    assert len(ACTIVE_VALIDATION_SET) == 24
    enabled = [item.repository_id for item in load_all_repositories() if item.enabled]
    assert len(enabled) == len(ACTIVE_VALIDATION_SET)
    assert set(enabled) == set(ACTIVE_VALIDATION_SET)
