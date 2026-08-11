"""Input loading and negative input scenarios."""

from __future__ import annotations

import pytest

from verification.assessment_consistency.inputs import Sv10InputError, load_sv10_records
from verification.assessment_consistency.scenarios import minimal_record


def test_minimal_record_shape() -> None:
    row = minimal_record(repository_id="flask")
    assert row["report_schema"] == "1.2"
    assert row["ai_executed"] is False


def test_load_records_fail_closed_on_missing(tmp_path) -> None:
    with pytest.raises(Sv10InputError):
        load_sv10_records(tmp_path)
