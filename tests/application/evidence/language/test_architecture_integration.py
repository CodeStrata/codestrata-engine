"""Architecture view equivalence via language evidence providers."""

from __future__ import annotations

from codestrata.application.evidence.language.factory import create_language_evidence_service
from codestrata.application.evidence.language.legacy_adapter import build_view_via_legacy_evidence
from codestrata.application.rules.architecture.view_builder import build_architecture_analysis_view
from codestrata.config.settings import (
    CodestrataSettings,
    EvidenceSettings,
    LanguageEvidenceSettings,
    RepositorySettings,
)


def _fixture_paths_and_texts() -> tuple[tuple[str, ...], dict[str, str]]:
    paths = (
        "src/demo/application/service.py",
        "src/demo/infrastructure/adapter.py",
        "src/demo/domain/model.py",
    )
    texts = {
        "src/demo/application/service.py": (
            "from demo.infrastructure.adapter import Client\n"
            "from demo.domain.model import Entity\n"
        ),
        "src/demo/infrastructure/adapter.py": (
            "from demo.application.service import Service\n"
            "from demo.domain.model import Entity\n"
        ),
        "src/demo/domain/model.py": "class Entity:\n    pass\n",
    }
    return paths, texts


def test_legacy_path_unchanged_when_pipeline_disabled() -> None:
    paths, texts = _fixture_paths_and_texts()
    legacy = build_architecture_analysis_view(relative_paths=paths, file_texts=texts)
    via_facts = build_view_via_legacy_evidence(relative_paths=paths, file_texts=texts)
    assert legacy.graph_fingerprint == via_facts.graph_fingerprint
    assert legacy.primary_unit_count == via_facts.primary_unit_count
    assert legacy.included_edge_count == via_facts.included_edge_count


def test_provider_pipeline_view_matches_legacy_for_python_fixture() -> None:
    paths, texts = _fixture_paths_and_texts()
    legacy = build_architecture_analysis_view(relative_paths=paths, file_texts=texts)
    service = create_language_evidence_service(
        CodestrataSettings(
            repository=RepositorySettings(path="."),
            evidence=EvidenceSettings(
                language=LanguageEvidenceSettings(enabled=True)
            ),
        )
    )
    result = service.collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        build_architecture_view=True,
    )
    assert result.architecture_view is not None
    provider_view = result.architecture_view
    assert provider_view.primary_unit_count == legacy.primary_unit_count
    assert provider_view.included_edge_count == legacy.included_edge_count
    assert {unit.unit_id for unit in provider_view.units} == {
        unit.unit_id for unit in legacy.units
    }
    assert {
        (edge.source_unit_id, edge.target_unit_id, edge.edge_kind)
        for edge in provider_view.edges
    } == {
        (edge.source_unit_id, edge.target_unit_id, edge.edge_kind)
        for edge in legacy.edges
    }


def test_type_only_import_excluded_through_provider_path() -> None:
    paths = ("src/app/services/mod.py", "src/app/domain/types_mod.py")
    texts = {
        "src/app/services/mod.py": (
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from app.domain.types_mod import Hint\n"
            "x = 1\n"
        ),
        "src/app/domain/types_mod.py": "class Hint:\n    pass\n",
    }
    service = create_language_evidence_service()
    result = service.collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        build_architecture_view=True,
    )
    assert result.architecture_view is not None
    # TYPE_CHECKING edge should not appear as included runtime coupling.
    assert result.architecture_view.included_edge_count == 0
    type_only = [
        dep
        for dep in result.aggregated.dependencies
        if dep.semantics.value == "type_only"
    ]
    assert type_only
