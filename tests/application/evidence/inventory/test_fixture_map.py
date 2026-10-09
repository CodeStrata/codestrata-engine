"""Fixture-map completeness for M01–M03 required cases."""

from __future__ import annotations

from codestrata.application.evidence.inventory.fixture_map import (
    E053_FIXTURE_MATRIX,
    INVENTORY_FIXTURE_MAP,
    REQUIRED_MEASUREMENT_FIXTURES,
)


def test_fixture_map_covers_required_measurement_cases() -> None:
    by_id = {item.fixture_id: item for item in INVENTORY_FIXTURE_MAP}
    for measurement, required in REQUIRED_MEASUREMENT_FIXTURES.items():
        assert required <= set(by_id)
        for fixture_id in required:
            assert by_id[fixture_id].measurement == measurement


def test_e053_matrix_covers_valid_absent_partial_unsupported_corrupt_deterministic() -> None:
    by_id = {item.fixture_id: item for item in INVENTORY_FIXTURE_MAP}
    required_cases = {
        "valid",
        "absent",
        "partial",
        "unsupported",
        "corrupt",
        "deterministic",
    }
    for measurement, cases in E053_FIXTURE_MATRIX.items():
        assert set(cases) == required_cases
        for fixture_id in cases.values():
            assert fixture_id in by_id
            assert by_id[fixture_id].measurement in {measurement, "M01"}
