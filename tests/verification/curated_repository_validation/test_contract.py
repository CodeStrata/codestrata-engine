"""SV.10 curated repository validation unit tests (offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from verification.curated_repository_validation.batches import (
    resolve_batches,
    select_determinism_sample,
)
from verification.curated_repository_validation.catalog import (
    load_release_validation_entries,
    monorepo_root_from_engine,
)
from verification.curated_repository_validation.contract import (
    ASSESSMENT_TIMEOUT_S,
    RELEASE_VALIDATION_TARGET,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    TIER_ORDER,
    default_contract,
)
from verification.curated_repository_validation.retries import should_retry_clone
from verification.curated_repository_validation.safety import check_disk_for_tier
from verification.curated_repository_validation.timeouts import (
    assessment_timeout_for_tier,
    is_timeout_exit,
)
from verification.cli_installation.environment import engine_root_from_package


ENGINE = engine_root_from_package()


def test_contract_constants() -> None:
    contract = default_contract()
    assert contract.schema_name == SCHEMA_NAME
    assert contract.schema_version == SCHEMA_VERSION
    assert contract.target_repository_count == 22
    assert contract.ai_enabled is False
    assert RELEASE_VALIDATION_TARGET == 22


def test_catalog_loads_exactly_22_release_validation() -> None:
    entries = load_release_validation_entries(ENGINE)
    assert len(entries) == 22
    assert all(e.roles.get("release_validation") for e in entries)
    assert all(len(e.qualified_revision.value) == 40 for e in entries)
    assert "hivemind" not in {e.repository_id for e in entries}
    assert "bookstack" in {e.repository_id for e in entries}


def test_batches_match_catalog_tiers_not_hardcoded_prompt() -> None:
    entries = load_release_validation_entries(ENGINE)
    batches = resolve_batches(entries)
    assert tuple(batches) == TIER_ORDER
    # Spot-check expected membership without hardcoding the full runtime list elsewhere.
    assert {e.repository_id for e in batches["tier1"]} == {
        "cleanarchitecture",
        "express",
        "flask",
        "slim",
        "spring-petclinic",
    }
    assert [e.repository_id for e in batches["tier3"]] == ["bookstack"]
    assert "typescript" in {e.repository_id for e in batches["tier4"]}


def test_determinism_sample_selection() -> None:
    entries = load_release_validation_entries(ENGINE)
    sample = select_determinism_sample(resolve_batches(entries))
    assert sample[0] in {e.repository_id for e in resolve_batches(entries)["tier1"]}
    assert "bookstack" in sample


def test_timeouts_by_tier() -> None:
    assert assessment_timeout_for_tier("tier1") == ASSESSMENT_TIMEOUT_S["tier1"]
    assert assessment_timeout_for_tier("tier4") == 30 * 60
    assert is_timeout_exit(124)
    assert not is_timeout_exit(1)


def test_retry_policy_transient_only() -> None:
    assert should_retry_clone("connection reset by peer")
    assert not should_retry_clone("revision mismatch")


def test_disk_check_runs() -> None:
    check = check_disk_for_tier("tier1", path=ENGINE)
    assert check.available_gb > 0


def test_monorepo_resolution() -> None:
    root = monorepo_root_from_engine(ENGINE)
    assert (root / "validation" / "repository-catalog" / "catalog.json").is_file()
