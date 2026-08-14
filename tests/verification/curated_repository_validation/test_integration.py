"""Thin module coverage for test_integration (logic covered in test_contract/test_summary).

HISTORICAL_FROZEN_CHARACTERIZATION: superseded curated-repository validation
slice. Not an ACTIVE 0.2.0 release gate. Collect with
``CODESTRATA_RUN_HISTORICAL_FROZEN=1``.
"""

from __future__ import annotations

def test_test_integration_module_importable() -> None:
    import verification.curated_repository_validation as pkg
    assert pkg.CURATED_REPOSITORY_VALIDATION_ID
