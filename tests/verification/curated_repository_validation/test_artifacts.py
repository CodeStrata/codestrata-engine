"""Artifact / privacy scan coverage for SV.10."""

from __future__ import annotations

import getpass

from verification.curated_repository_validation.artifacts import _scan_harness_leaks


def test_test_artifacts_module_importable() -> None:
    import verification.curated_repository_validation as pkg

    assert pkg.CURATED_REPOSITORY_VALIDATION_ID


def test_ci_home_runner_paths_are_not_harness_leaks() -> None:
    """OSS CI scripts often mention /home/runner/; that is not operator identity."""
    document = {
        "evidence": [
            {"snippet": '#export TMPDIR=/home/runner/work/doris/doris/.tmp'},
            {"path": "build-support/ci.sh"},
        ]
    }
    assert _scan_harness_leaks(document) == []


def test_operator_home_path_is_harness_leak() -> None:
    user = getpass.getuser()
    document = {"repo_root": f"/Users/{user}/Documents/workspace-ai/tmp-clone"}
    assert "harness_absolute_path_detected" in _scan_harness_leaks(document)


def test_var_folders_and_harness_markers_are_leaks() -> None:
    assert "harness_absolute_path_detected" in _scan_harness_leaks(
        {"tmp": "/var/folders/xx/yy/T/cs-work"}
    )
    assert "harness_absolute_path_detected" in _scan_harness_leaks(
        {"workspace": "cs-sv10-aspnetcore-abc"}
    )
