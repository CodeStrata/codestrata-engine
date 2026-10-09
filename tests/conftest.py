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

import faulthandler
import os
from collections.abc import Iterator, MutableMapping
from pathlib import Path

import pytest

KEEP_HOST_KNOWLEDGE_ENV = "CODESTRATA_KEEP_HOST_KNOWLEDGE"
KNOWLEDGE_DIRECTORY_ENV = "CODESTRATA_KNOWLEDGE_DIRECTORY"
LOCK_TIMEOUT_ENV = "CODESTRATA_KNOWLEDGE_LOCK_TIMEOUT_SECONDS"
_TEST_LOCK_TIMEOUT_SECONDS = "2"
_TEST_HANG_TRACEBACK_SECONDS = 45.0

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
    REPO_ROOT / "examples" if (REPO_ROOT / "examples").is_dir() else ENGINE_ROOT / "examples"
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


def apply_test_knowledge_isolation(
    environ: MutableMapping[str, str],
    isolated: Path,
    *,
    keep_host: bool = False,
) -> dict[str, str]:
    """Force the suite onto an isolated knowledge dir and a 2s lock cap.

    ``setdefault`` is not enough: a host ``codestrata assess`` exports
    ``CODESTRATA_KNOWLEDGE_DIRECTORY`` to ``engine/.codestrata/knowledge``.
    Tests then share that lock and appear stuck at ~88% for up to an hour.
    """

    previous = {
        key: environ[key]
        for key in (KNOWLEDGE_DIRECTORY_ENV, LOCK_TIMEOUT_ENV)
        if key in environ
    }
    if not keep_host:
        environ[KNOWLEDGE_DIRECTORY_ENV] = str(isolated)
    environ[LOCK_TIMEOUT_ENV] = _TEST_LOCK_TIMEOUT_SECONDS
    return previous


def _clear_stale_host_knowledge_locks() -> None:
    host_locks = ENGINE_ROOT / ".codestrata" / "knowledge" / "locks"
    if not host_locks.is_dir():
        return
    from codestrata.infrastructure.knowledge_store.sqlite.locking import _remove_stale_lock

    for lock_path in host_locks.glob("*.lock"):
        try:
            _remove_stale_lock(lock_path)
        except OSError:
            continue


@pytest.fixture(scope="session", autouse=True)
def isolate_host_knowledge_directory(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    """Keep the active suite off engine/.codestrata/knowledge and cap lock waits."""

    _clear_stale_host_knowledge_locks()
    isolated = tmp_path_factory.mktemp("isolated-knowledge")
    keep_host = os.environ.get(KEEP_HOST_KNOWLEDGE_ENV) == "1"
    previous = apply_test_knowledge_isolation(
        os.environ,
        isolated,
        keep_host=keep_host,
    )
    try:
        yield
    finally:
        for key in (KNOWLEDGE_DIRECTORY_ENV, LOCK_TIMEOUT_ENV):
            if key in previous:
                os.environ[key] = previous[key]
            else:
                os.environ.pop(key, None)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    """Dump stacks if a single test goes silent (Windows lock waits, hung assess)."""

    del item
    faulthandler.dump_traceback_later(_TEST_HANG_TRACEBACK_SECONDS, repeat=False)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Coverage term-missing is large; say so instead of looking stuck at 96%."""

    del exitstatus
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminal is None:
        return
    terminal.write_line(
        "Combining coverage term-missing (partial files only). "
        "A pause after the last test is report generation, not a lock wait."
    )
