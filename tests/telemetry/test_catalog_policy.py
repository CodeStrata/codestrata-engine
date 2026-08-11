"""Catalog policy and model smoke tests (Slice 9.8)."""

from __future__ import annotations

import pytest

from codestrata.telemetry.catalog import build_privacy_first_telemetry_catalog
from codestrata.telemetry.catalog_diagnostics import diagnostics_from_catalog
from codestrata.telemetry.catalog_policy import (
    COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_URN,
    CatalogPolicyError,
    CommunityTelemetryPublicCatalogPolicy,
    default_catalog_policy,
)
from codestrata.telemetry.catalog_validation import reconcile_catalog_against_runtime


def test_catalog_policy_defaults() -> None:
    policy = default_catalog_policy()
    assert policy.policy_token == COMMUNITY_TELEMETRY_PUBLIC_CATALOG_POLICY_URN
    assert policy.transmission_operational is False
    assert policy.legacy_events_included is False
    assert policy.client_name == "codestrata_cli"


def test_policy_rejects_transmission() -> None:
    with pytest.raises(CatalogPolicyError):
        CommunityTelemetryPublicCatalogPolicy(transmission_operational=True)


def test_catalog_build_and_reconcile() -> None:
    catalog = build_privacy_first_telemetry_catalog()
    reconcile_catalog_against_runtime(catalog)
    assert catalog.schema_name == "privacy-first-telemetry-catalog"
    assert catalog.schema_version == "1.0.0"
    assert catalog.runtime_event_schema_version == "1.0"
    assert len(catalog.events) == 5
    assert len(catalog.shared_fields) == 15
    diag = diagnostics_from_catalog(catalog)
    assert diag.event_count == 5
    assert diag.field_count == 15
    assert diag.transmission_status == "not_operational"
