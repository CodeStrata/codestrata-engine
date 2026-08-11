"""Regression guards for Slice 4.1 — schema and surface area unchanged."""

from __future__ import annotations

from codestrata.reporting.contract.constants import ASSESSMENT_JSON_SCHEMA_VERSION


def test_schema_remains_1_2() -> None:
    assert ASSESSMENT_JSON_SCHEMA_VERSION == "1.2"
