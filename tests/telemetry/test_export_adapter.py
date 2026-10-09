"""E13.2 adapter: capability-gated evidence/graph upload via fake collector."""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.consent_scope import CommunityConsentState, resolve_consent_capabilities
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.export_models import CapabilityCheck, CollectorKind
from codestrata.telemetry.export_serialize import build_scoped_export
from codestrata.telemetry.fake_collector import (
    UnadvertisedLiveCollector,
    advertising_fake_collector,
    collector_from_mapping,
)
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.opt_in import (
    CollectionChannel,
    CollectionSubmitStatus,
    EngineCollectionAdapter,
)
from codestrata.telemetry.persisted_consent import persist_v2_yes

_SAFE_EVENT = RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)


def _pref(tmp_path: Path) -> Path:
    return tmp_path / "telemetry.json"


def test_default_adapter_keeps_evidence_graph_unavailable(tmp_path: Path) -> None:
    persist_v2_yes(path=_pref(tmp_path))
    capture = CaptureTelemetryTransport()
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        transport=capture,
        automation_detected=False,
    )
    assert adapter.may_transmit(CollectionChannel.TELEMETRY) is True
    assert adapter.may_transmit(CollectionChannel.EVIDENCE) is False
    assert adapter.may_transmit(CollectionChannel.GRAPH) is False
    evidence = adapter.submit(CollectionChannel.EVIDENCE, {"digest": "abc", "schema": "x"})
    graph = adapter.submit(CollectionChannel.GRAPH, {"nodes": [], "edges": []})
    assert evidence.status is CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE
    assert graph.status is CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE
    assert evidence.reason == CapabilityCheck.SCHEMA_UNADVERTISED.value
    inspect = adapter.inspect()
    assert inspect["collector"]["kind"] == "none"
    assert inspect["collector"]["server_ready"] is False
    assert inspect["collector"]["live_v2_calls"] is False
    assert len(capture.captured) == 0


def test_unadvertised_live_collector_does_not_probe_v2(tmp_path: Path) -> None:
    persist_v2_yes(path=_pref(tmp_path))
    live = UnadvertisedLiveCollector()
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        collector=live,
        automation_detected=False,
    )
    result = adapter.submit(
        CollectionChannel.EVIDENCE,
        build_scoped_export("evidence"),
    )
    assert result.status is CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE
    assert result.transmitted is False
    assert live.live_v2_invoked is False
    assert live.http_calls == []
    assert live.accepted == []


def test_fake_collector_accepts_only_with_consent_and_advertisement(tmp_path: Path) -> None:
    pref = _pref(tmp_path)
    collector = advertising_fake_collector()
    adapter = EngineCollectionAdapter(
        preference_path=pref,
        collector=collector,
        automation_detected=False,
    )
    denied = adapter.submit(CollectionChannel.EVIDENCE, build_scoped_export("evidence"))
    assert denied.status is CollectionSubmitStatus.DROPPED_NO_CONSENT
    assert collector.accepted == []

    adapter.enable()
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.V2_YES
    assert adapter.may_transmit(CollectionChannel.EVIDENCE) is True
    accepted = adapter.submit(
        CollectionChannel.EVIDENCE,
        build_scoped_export("evidence", collector_kind=CollectorKind.FAKE, schema_advertised=True),
    )
    assert accepted.status is CollectionSubmitStatus.ACCEPTED
    assert accepted.transmitted is True
    assert accepted.reason == "fake_collector_local"
    assert len(collector.accepted) == 1
    assert collector.accepted[0].server_readiness == "not_ready"
    assert collector.accepted[0].transmission_performed is False
    assert collector.live_v2_invoked is False
    assert collector.receipts[0].server_ready is False


def test_partial_collector_does_not_open_graph(tmp_path: Path) -> None:
    persist_v2_yes(path=_pref(tmp_path))
    collector = collector_from_mapping(
        {
            "kind": "fake",
            "advertised_schemas": ["codestrata.evidence-export.v1"],
            "receipts_supported": True,
        }
    )
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        collector=collector,
        automation_detected=False,
    )
    evidence = adapter.submit(CollectionChannel.EVIDENCE, build_scoped_export("evidence"))
    graph = adapter.submit(CollectionChannel.GRAPH, build_scoped_export("graph"))
    assert evidence.status is CollectionSubmitStatus.ACCEPTED
    assert graph.status is CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE
    assert graph.reason == CapabilityCheck.PARTIAL_ADVERTISEMENT.value


def test_prohibited_export_fields_drop_before_collector(tmp_path: Path) -> None:
    persist_v2_yes(path=_pref(tmp_path))
    collector = advertising_fake_collector()
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        collector=collector,
        automation_detected=False,
    )
    result = adapter.submit(
        CollectionChannel.EVIDENCE,
        {
            "category": "evidence",
            "schema": "codestrata.evidence-export.v1",
            "findings": ["leak"],
            "repository_name": "VERY_PRIVATE_REPO_123",
            "snippet": "print(1)",
        },
    )
    assert result.status is CollectionSubmitStatus.DROPPED_PROHIBITED
    assert result.transmitted is False
    assert collector.accepted == []


def test_unsupported_export_payload_with_advertised_collector(tmp_path: Path) -> None:
    persist_v2_yes(path=_pref(tmp_path))
    collector = advertising_fake_collector()
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        collector=collector,
        automation_detected=False,
    )
    result = adapter.submit(CollectionChannel.GRAPH, {"digest": "abc", "schema": "x"})
    assert result.status is CollectionSubmitStatus.DROPPED_UNSUPPORTED
    assert collector.accepted == []


def test_empty_mapping_builds_channel_envelope(tmp_path: Path) -> None:
    persist_v2_yes(path=_pref(tmp_path))
    collector = advertising_fake_collector()
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        collector=collector,
        automation_detected=False,
    )
    result = adapter.submit(CollectionChannel.GRAPH, {})
    assert result.status is CollectionSubmitStatus.ACCEPTED
    assert collector.accepted[0].category == "graph"
