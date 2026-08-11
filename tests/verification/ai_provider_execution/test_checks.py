"""Unit tests: every remaining verification.ai_provider_execution check module passes standalone."""

from __future__ import annotations

from verification.ai_provider_execution.runner import engine_root_from_package

from verification.ai_provider_execution import (
    determinism,
    errors,
    executor,
    fail_soft,
    inventory,
    policy,
    privacy,
    retries,
    runtime_unwired,
    timeout,
)

ENGINE_ROOT = engine_root_from_package()
PACKAGE_DIR = ENGINE_ROOT / "src" / "codestrata" / "ai" / "provider_contracts"


def test_inventory_checks_all_pass() -> None:
    checks, matrix = inventory.run_inventory_checks(ENGINE_ROOT, PACKAGE_DIR)
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert len(matrix["modules"]) > 0


def test_policy_checks_all_pass() -> None:
    checks, _matrix = policy.run_policy_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]


def test_timeout_checks_all_pass() -> None:
    checks, _matrix = timeout.run_timeout_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]


def test_retry_checks_all_pass() -> None:
    checks, _matrix = retries.run_retry_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]


def test_error_classification_checks_all_pass() -> None:
    checks, _matrix = errors.run_error_classification_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]


def test_executor_checks_all_pass() -> None:
    checks, _matrix = executor.run_executor_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert len(checks) == 10


def test_fail_soft_checks_all_pass() -> None:
    checks, _matrix = fail_soft.run_fail_soft_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]


def test_privacy_checks_all_pass() -> None:
    checks, matrix = privacy.run_privacy_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    assert "sample_diagnostic_view" in matrix


def test_runtime_unwired_checks_all_pass() -> None:
    checks, _matrix = runtime_unwired.run_runtime_unwired_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]


def test_determinism_checks_all_pass() -> None:
    checks, _matrix = determinism.run_determinism_checks()
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
