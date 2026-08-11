"""Negative catalog drift fixtures (Slice 9.8 scenarios A–R subset)."""

from __future__ import annotations

import dataclasses

import pytest

from codestrata.telemetry.catalog import build_privacy_first_telemetry_catalog
from codestrata.telemetry.catalog_models import TelemetryCatalogField
from codestrata.telemetry.catalog_validation import (
    CatalogReconciliationError,
    reconcile_catalog_against_runtime,
)


def test_A_omitting_event_fails_reconcile() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    broken = dataclasses.replace(catalog, events=catalog.events[1:])
    with pytest.raises(CatalogReconciliationError, match="event drift"):
        reconcile_catalog_against_runtime(broken)


def test_B_unknown_event_fails_reconcile() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    extra = dataclasses.replace(catalog.events[0], name="legacy_assessment_completed")
    broken = dataclasses.replace(catalog, events=catalog.events + (extra,))
    with pytest.raises(CatalogReconciliationError, match="event drift"):
        reconcile_catalog_against_runtime(broken)


def test_D_unknown_field_fails_reconcile() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    extra = TelemetryCatalogField(
        name="repository_name",
        field_type="string",
        requiredness="optional",
        omitted_when_unavailable=True,
        enum_ref=None,
        max_length=None,
        privacy_classification="low_cardinality_category",
        source="command_runtime_categorical_context",
        normalization="none",
        bucketed=False,
        set_ordering_normalized=False,
        event_specific=False,
        transmitted_currently=False,
        example="acme",
    )
    broken = dataclasses.replace(
        catalog, shared_fields=catalog.shared_fields + (extra,)
    )
    with pytest.raises(CatalogReconciliationError):
        reconcile_catalog_against_runtime(broken)


def test_G_forbidden_field_in_catalog_fails() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    assert "repository_name" not in {f.name for f in catalog.shared_fields}
    assert "installation_id" not in {f.name for f in catalog.shared_fields}
    assert "path" not in {f.name for f in catalog.shared_fields}
    assert "model_id" not in {f.name for f in catalog.shared_fields}
    assert "cost" not in {f.name for f in catalog.shared_fields}
    assert "token_count" not in {f.name for f in catalog.shared_fields}


def test_PQR_catalog_claims_are_honest() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    assert catalog.transmission_status == "not_operational"
    assert catalog.consent_persistence == "none"
    assert catalog.consent_expands_fields is False
    assert catalog.privacy_filtering_required is True
    assert catalog.installation_identity_status == "not_used"
    assert catalog.client_name == "codestrata_cli"
