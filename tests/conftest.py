"""Pytest path helpers for the Community Engine test suite.

ACTIVE_0_2_0_RELEASE_GATE vs HISTORICAL_FROZEN_CHARACTERIZATION
--------------------------------------------------------------
Default ``pytest tests`` (private main CI) collects only ACTIVE 0.2.0 gates.

HISTORICAL_FROZEN_CHARACTERIZATION suites remain in-tree and are collected when
``CODESTRATA_RUN_HISTORICAL_FROZEN=1``. They characterize superseded contracts
(Epic 11 frozen slice reports; SV.5/SV.11 report.json layout) and must not gate
the shipped 0.2.0 artifact contract.

REMOTE_VALIDATION
-----------------
Live pinned-public-remote validation is opt-in via ``CODESTRATA_RUN_REMOTE_VALIDATION=1``
(and ``@pytest.mark.remote_validation``). Default Engine CI stays deterministic and
does not clone or assess external repositories.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Directory names under tests/verification/ that are historical frozen suites.
_HISTORICAL_FROZEN_VERIFICATION_DIRS = frozenset(
    {
        "ai_provider_platform_completion",
        "assessment_report",
        "assessment_consistency",
        "repository_assessment",
        "curated_repository_validation",
        # SV.11.6/11.7 migration slices: characterize pre-OpenRouter package
        # boundaries and legacy wrapper exception types. Current 0.2.0 has
        # OpenRouter as a supported provider (count=3).
        "bedrock_provider_migration",
        "openai_provider_migration",
    }
)


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Omit historical frozen characterization from the 0.2.0 main release gate."""

    if os.environ.get("CODESTRATA_RUN_HISTORICAL_FROZEN") == "1":
        return None
    parts = set(Path(collection_path).parts)
    if parts & _HISTORICAL_FROZEN_VERIFICATION_DIRS:
        return True
    return None

ENGINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ENGINE_ROOT.parent
EXAMPLES_ROOT = (
    REPO_ROOT / "examples"
    if (REPO_ROOT / "examples").is_dir()
    else ENGINE_ROOT / "examples"
)
TEST_FIXTURES_ROOT = (
    REPO_ROOT / "test-fixtures"
    if (REPO_ROOT / "test-fixtures").is_dir()
    else ENGINE_ROOT / "test-fixtures"
)


@pytest.fixture(scope="session")
def engine_root() -> Path:
    return ENGINE_ROOT


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def examples_root() -> Path:
    return EXAMPLES_ROOT


@pytest.fixture(scope="session")
def test_fixtures_root() -> Path:
    return TEST_FIXTURES_ROOT
