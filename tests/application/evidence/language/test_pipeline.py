"""Tests for language evidence registry, planner, executor, aggregation."""

from __future__ import annotations

import pytest

from codestrata.application.evidence.language.executor import LanguageEvidenceProviderExecutor
from codestrata.application.evidence.language.factory import create_language_evidence_service
from codestrata.application.evidence.language.planner import LanguageEvidenceProviderPlanner
from codestrata.application.evidence.language.providers import (
    JavaLanguageEvidenceProvider,
    PythonLanguageEvidenceProvider,
)
from codestrata.application.evidence.language.registry import LanguageEvidenceProviderRegistry
from codestrata.domain.evidence.language.contracts import LanguageEvidenceContext
from codestrata.domain.evidence.language.errors import LanguageEvidenceRegistryError


def test_registry_register_and_list() -> None:
    registry = LanguageEvidenceProviderRegistry()
    registry.register(PythonLanguageEvidenceProvider())
    registry.register(JavaLanguageEvidenceProvider())
    assert registry.size == 2
    by_lang = registry.list_by_language("python")
    assert len(by_lang) == 1
    assert str(by_lang[0].provider_id) == "language.python.core"
    by_cap = registry.list_by_capability("dependencies.imports")
    assert {str(item.provider_id) for item in by_cap} == {
        "language.python.core",
        "language.java.core",
    }


def test_registry_rejects_duplicates() -> None:
    registry = LanguageEvidenceProviderRegistry()
    registry.register(PythonLanguageEvidenceProvider())
    with pytest.raises(LanguageEvidenceRegistryError):
        registry.register(PythonLanguageEvidenceProvider())


def test_planner_auto_detect_and_precedence() -> None:
    registry = LanguageEvidenceProviderRegistry()
    registry.register_collection(
        [PythonLanguageEvidenceProvider(), JavaLanguageEvidenceProvider()]
    )
    planner = LanguageEvidenceProviderPlanner(registry)
    context = LanguageEvidenceContext(
        repository_id="demo",
        relative_paths=("src/app.py", "src/Main.java"),
        file_texts={"src/app.py": "import x\n", "src/Main.java": "package a;\n"},
    )
    plan = planner.plan(context)
    assert plan.detected_languages == ("java", "python")
    assert plan.execution_order[0] == "language.python.core"
    assert "language.java.core" in plan.execution_order


def test_executor_isolates_failure() -> None:
    class BoomProvider(PythonLanguageEvidenceProvider):
        def collect(self, context):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    registry = LanguageEvidenceProviderRegistry()
    boom = BoomProvider()
    # Force same id/version registration path via subclass that keeps metadata.
    registry.register(boom)
    executor = LanguageEvidenceProviderExecutor(registry, fail_fast=False)
    planner = LanguageEvidenceProviderPlanner(registry)
    context = LanguageEvidenceContext(
        repository_id="demo",
        relative_paths=("a.py",),
        file_texts={"a.py": "import b\n"},
    )
    plan = planner.plan(context)
    result = executor.execute(context, plan)
    assert result.failed_provider_ids == ("language.python.core",)
    assert result.bundles == ()


def test_aggregator_dedup_preserves_provenance() -> None:
    service = create_language_evidence_service()
    result = service.collect(
        repository_id="demo",
        relative_paths=("pkg/a.py", "pkg/b.py"),
        file_texts={
            "pkg/a.py": "from pkg import b\n",
            "pkg/b.py": "x = 1\n",
        },
        build_architecture_view=True,
    )
    assert result.aggregated.source_units
    assert result.architecture_view is not None
    assert result.architecture_view.primary_unit_count >= 1


def test_service_list_providers_deterministic() -> None:
    service = create_language_evidence_service()
    rows = service.list_providers()
    ids = [row["provider_id"] for row in rows]
    assert ids == sorted(ids)
    assert "language.python.core" in ids
