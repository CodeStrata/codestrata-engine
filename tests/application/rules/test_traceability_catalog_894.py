"""Phase 8.9.4 — catalog traceability metadata (no detection changes)."""

from __future__ import annotations

from codestrata.application.rules.factory import create_rule_analysis_service
from codestrata.application.rules.testing.registration import register_testing_pack
from codestrata.application.rules.traceability_catalog import (
    LEGACY_RUNTIME_TO_CATALOG,
    RUNTIME_TO_CATALOG,
    catalog_id_for_runtime,
    concept_id_for_runtime,
)


def test_shared_rule_catalog_covers_registered_production_rules() -> None:
    service = create_rule_analysis_service()
    registry = service._registry  # noqa: SLF001 — test inspects composition
    register_testing_pack(registry, production=True)

    production_ids = [
        view.metadata.rule_id.root
        if hasattr(view.metadata.rule_id, "root")
        else str(view.metadata.rule_id)
        for view in registry.list_rules(include_non_production=False)
    ]
    missing = sorted({rid for rid in production_ids if rid not in RUNTIME_TO_CATALOG})
    assert missing == [], f"Catalog missing runtime rules: {missing}"
    # Catalog may list rules not loaded in this composition — that's OK.
    # Ensure every loaded production rule is mapped.
    assert len(production_ids) >= 77


def test_catalog_helpers_resolve_known_rule() -> None:
    assert catalog_id_for_runtime("architecture.dependency-cycle") == "AR-001"
    assert concept_id_for_runtime("architecture.dependency-cycle") == "ARCH-CON-001"
    assert catalog_id_for_runtime("codestrata-rule-missing-readme") == "LEG-001"
    assert "codestrata-rule-missing-readme" in LEGACY_RUNTIME_TO_CATALOG


def test_catalog_ids_are_unique() -> None:
    catalog_ids = [entry["catalog_id"] for entry in RUNTIME_TO_CATALOG.values()]
    catalog_ids += [entry["catalog_id"] for entry in LEGACY_RUNTIME_TO_CATALOG.values()]
    assert len(catalog_ids) == len(set(catalog_ids))


def test_runtime_ids_are_unique_in_catalog() -> None:
    assert len(RUNTIME_TO_CATALOG) == len(set(RUNTIME_TO_CATALOG))
    assert len(LEGACY_RUNTIME_TO_CATALOG) == len(set(LEGACY_RUNTIME_TO_CATALOG))
