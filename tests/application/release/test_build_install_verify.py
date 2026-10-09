"""Unit tests for clean install environment checks."""

from __future__ import annotations

from codestrata.application.release.standalone.install_verify import (
    verify_install_environment,
    version_output_implies_database_dependency,
)


def test_pythonpath_forbidden() -> None:
    result = verify_install_environment({"PYTHONPATH": "/monorepo/engine/src"})
    assert result.ok is False


def test_version_output_without_db_markers() -> None:
    assert version_output_implies_database_dependency("CodeStrata 0.2.1") is False
