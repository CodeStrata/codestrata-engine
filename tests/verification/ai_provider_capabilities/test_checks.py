"""Unit tests: every check module in verification.ai_provider_capabilities passes standalone."""

from __future__ import annotations

from verification.ai_provider_capabilities.runner import engine_root_from_package

from verification.ai_provider_capabilities import (
    catalogs,
    determinism,
    inventory,
    privacy,
    runtime_unwired,
    serialization,
    validation,
)

ENGINE_ROOT = engine_root_from_package()
PACKAGE_DIR = ENGINE_ROOT / "src" / "codestrata" / "ai" / "provider_contracts"


def test_inventory_checks_all_pass() -> None:
    checks, matrix = inventory.run_inventory_checks(ENGINE_ROOT, PACKAGE_DIR)
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert len(matrix["modules"]) > 0


def test_catalog_checks_all_pass() -> None:
    checks, matrix = catalogs.run_catalog_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert "bedrock_profile" in matrix
    assert "openai_profile" in matrix


def test_validation_checks_all_pass() -> None:
    checks, matrix = validation.run_validation_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert "check_names" in matrix


def test_serialization_checks_all_pass() -> None:
    checks, matrix = serialization.run_serialization_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert "sample_capability_serialization" in matrix


def test_privacy_checks_all_pass() -> None:
    checks, matrix = privacy.run_privacy_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert "sample_capability_diagnostic_view" in matrix


def test_runtime_unwired_checks_all_pass() -> None:
    checks, matrix = runtime_unwired.run_runtime_unwired_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert "capability_modules_checked" in matrix


def test_determinism_helpers_round_trip() -> None:
    payload = {"b": 2, "a": 1}
    text = determinism.canonical_json(payload)
    assert text == '{"a":1,"b":2}'
    assert determinism.reports_are_identical(payload, {"a": 1, "b": 2})
    assert determinism.stable_hash(payload) == determinism.stable_hash({"a": 1, "b": 2})
