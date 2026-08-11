"""Thin module coverage for test_workspace (logic covered in test_contract/test_summary)."""

from __future__ import annotations

def test_test_workspace_module_importable() -> None:
    import verification.curated_repository_validation as pkg
    assert pkg.CURATED_REPOSITORY_VALIDATION_ID
