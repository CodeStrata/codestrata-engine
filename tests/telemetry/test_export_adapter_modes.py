"""E13.3 adapter export-mode restrictions and no-export local utility."""

from __future__ import annotations

from pathlib import Path

from codestrata.domain.contracts.enums import ExportMode
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.export_models import CapabilityCheck
from codestrata.telemetry.export_serialize import build_scoped_export
from codestrata.telemetry.fake_collector import advertising_fake_collector
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.opt_in import (
    CollectionChannel,
    CollectionSubmitStatus,
    EngineCollectionAdapter,
    run_primary_with_isolated_collection,
)
from codestrata.telemetry.persisted_consent import persist_v2_yes

_SAFE_EVENT = RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)


def _pref(tmp_path: Path) -> Path:
    return tmp_path / "telemetry.json"


def test_no_export_retains_local_functionality_and_emits_no_transfer(tmp_path: Path) -> None:
    persist_v2_yes(path=_pref(tmp_path))
    capture = CaptureTelemetryTransport()
    collector = advertising_fake_collector()
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        transport=capture,
        collector=collector,
        automation_detected=False,
        export_mode=ExportMode.NONE,
    )
    assert adapter.may_transmit(CollectionChannel.EVIDENCE) is False
    assert adapter.may_transmit(CollectionChannel.GRAPH) is False
    evidence = adapter.submit(CollectionChannel.EVIDENCE, build_scoped_export("evidence"))
    graph = adapter.submit(CollectionChannel.GRAPH, build_scoped_export("graph"))
    assert evidence.status is CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE
    assert evidence.reason == CapabilityCheck.EXPORT_MODE_NO_EXPORT.value
    assert evidence.transmitted is False
    assert graph.transmitted is False
    assert collector.accepted == []
    assert adapter.inspect()["export_mode"] == "none"
    assert adapter.inspect()["withheld_categories"] == ["evidence", "graph"]

    marker = {"kept": True}

    def primary() -> dict[str, bool]:
        marker["kept"] = True
        return marker

    result = run_primary_with_isolated_collection(primary, adapter=adapter)
    assert result == marker
    assert marker["kept"] is True


def test_restricted_mode_withholds_graph_only(tmp_path: Path) -> None:
    persist_v2_yes(path=_pref(tmp_path))
    collector = advertising_fake_collector()
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        collector=collector,
        automation_detected=False,
        export_mode="restricted",
        withheld_categories=("graph",),
    )
    evidence = adapter.submit(CollectionChannel.EVIDENCE, build_scoped_export("evidence"))
    graph = adapter.submit(CollectionChannel.GRAPH, build_scoped_export("graph"))
    assert evidence.status is CollectionSubmitStatus.ACCEPTED
    assert graph.status is CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE
    assert graph.reason == CapabilityCheck.CATEGORY_WITHHELD.value
    assert graph.transmitted is False
    assert len(collector.accepted) == 1
    assert collector.accepted[0].category == "evidence"
