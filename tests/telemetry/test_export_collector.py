"""E13.2 local fake collector capability and receipt contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.telemetry.export_gate import evaluate_export_capability
from codestrata.telemetry.export_models import (
    CapabilityCheck,
    CollectorKind,
    ExportEnvelopeError,
)
from codestrata.telemetry.export_serialize import build_scoped_export
from codestrata.telemetry.fake_collector import (
    FakeCollector,
    UnadvertisedLiveCollector,
    advertising_fake_collector,
    collector_from_mapping,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "export"


def _collector(name: str):
    return collector_from_mapping(json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")))


def test_advertised_fake_collector_accepts_local_envelope_without_live_v2() -> None:
    collector = _collector("collector-advertised.json")
    assert isinstance(collector, FakeCollector)
    envelope = build_scoped_export(
        "evidence",
        collector_kind=CollectorKind.FAKE,
        schema_advertised=True,
    )
    receipt = collector.accept(envelope)
    assert receipt.accepted is True
    assert receipt.capability_check == CapabilityCheck.PASSED.value
    assert receipt.live_v2_invoked is False
    assert receipt.server_ready is False
    assert collector.live_v2_invoked is False
    assert len(collector.accepted) == 1
    assert envelope.server_readiness == "not_ready"
    assert envelope.transmission_performed is False


def test_unadvertised_live_collector_never_calls_v2() -> None:
    collector = _collector("collector-unadvertised.json")
    assert isinstance(collector, UnadvertisedLiveCollector)
    envelope = build_scoped_export("graph")
    decision = evaluate_export_capability(collector, "graph")
    assert decision.allowed is False
    assert decision.reason == CapabilityCheck.NOT_FAKE_LOCAL.value
    receipt = collector.accept(envelope)
    assert receipt.accepted is False
    assert collector.live_v2_invoked is False
    assert collector.http_calls == []
    assert collector.accepted == []


def test_partial_advertisement_allows_evidence_not_graph() -> None:
    collector = _collector("collector-partial.json")
    evidence = evaluate_export_capability(collector, "evidence")
    graph = evaluate_export_capability(collector, "graph")
    assert evidence.allowed is True
    assert graph.allowed is False
    assert graph.reason == CapabilityCheck.PARTIAL_ADVERTISEMENT.value
    rejected = collector.accept(build_scoped_export("graph", collector_kind=CollectorKind.FAKE))
    assert rejected.accepted is False
    assert rejected.capability_check == CapabilityCheck.PARTIAL_ADVERTISEMENT.value


def test_unsupported_schema_and_missing_receipts_fail_closed() -> None:
    unsupported = _collector("collector-unsupported-schema.json")
    decision = evaluate_export_capability(unsupported, "evidence")
    assert decision.allowed is False
    assert decision.reason == CapabilityCheck.SCHEMA_UNSUPPORTED.value

    no_receipts = _collector("collector-no-receipts.json")
    blocked = evaluate_export_capability(no_receipts, "evidence")
    assert blocked.allowed is False
    assert blocked.reason == CapabilityCheck.RECEIPTS_UNAVAILABLE.value
    receipt = no_receipts.accept(
        build_scoped_export("evidence", collector_kind=CollectorKind.FAKE, schema_advertised=True)
    )
    assert receipt.accepted is False


def test_default_none_collector_is_unadvertised() -> None:
    decision = evaluate_export_capability(None, "evidence")
    assert decision.allowed is False
    assert decision.reason == CapabilityCheck.SCHEMA_UNADVERTISED.value


def test_advertising_helper_covers_both_schemas() -> None:
    collector = advertising_fake_collector()
    assert evaluate_export_capability(collector, "evidence").allowed is True
    assert evaluate_export_capability(collector, "graph").allowed is True


def test_collector_fixture_cannot_enable_live_v2() -> None:
    with pytest.raises(ExportEnvelopeError):
        collector_from_mapping(
            {
                "kind": "fake",
                "advertised_schemas": ["codestrata.evidence-export.v1"],
                "receipts_supported": True,
                "live_v2_calls": True,
            }
        )


def test_none_kind_fixture_and_clear() -> None:
    none = collector_from_mapping({"kind": "none"})
    assert isinstance(none, UnadvertisedLiveCollector)
    collector = advertising_fake_collector()
    envelope = build_scoped_export(
        "evidence",
        collector_kind=CollectorKind.FAKE,
        schema_advertised=True,
    )
    collector.accept(envelope)
    assert collector.accepted
    collector.clear()
    assert collector.accepted == []
    assert collector.receipts == []
