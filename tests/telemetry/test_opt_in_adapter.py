"""E13.1 Engine collection adapter: durable opt-in and no-egress defaults."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.telemetry.consent_scope import CommunityConsentState, resolve_consent_capabilities
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.opt_in import (
    CollectionChannel,
    CollectionSubmitStatus,
    EngineCollectionAdapter,
    create_collection_adapter,
    run_primary_with_isolated_collection,
)
from codestrata.telemetry.persisted_consent import persist_disabled, persist_v2_yes
from codestrata.telemetry.queue import enqueue, load_queue, queue_depth
from codestrata.telemetry.service import TelemetryService

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "opt_in"

_SAFE_EVENT = RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)


def _pref(tmp_path: Path) -> Path:
    return tmp_path / "telemetry.json"


def _queue(tmp_path: Path) -> Path:
    return tmp_path / "telemetry-queue.jsonl"


def _copy_fixture(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "telemetry.json"
    target.write_bytes((FIXTURE_DIR / name).read_bytes())
    return target


def test_no_consent_means_no_channel_transmissions(tmp_path: Path) -> None:
    capture = CaptureTelemetryTransport()
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        transport=capture,
        automation_detected=False,
    )
    assert adapter.inspect()["state"] == CommunityConsentState.UNDECIDED.value
    for channel in CollectionChannel:
        assert adapter.may_transmit(channel) is False
        result = adapter.submit(channel, _SAFE_EVENT)
        assert result.transmitted is False
        assert result.status in {
            CollectionSubmitStatus.DROPPED_NO_CONSENT,
            CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE,
        }
    assert capture.captured == []
    assert not _pref(tmp_path).exists()


def test_ci_and_env_never_invent_consent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CI", "1")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("CODESTRATA_TELEMETRY", "1")
    monkeypatch.setenv("CODESTRATA_TELEMETRY_ENDPOINT", "https://example.invalid/t")
    capture = CaptureTelemetryTransport()
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        transport=capture,
        environ={
            "CI": "1",
            "GITHUB_ACTIONS": "true",
            "CODESTRATA_TELEMETRY": "1",
        },
    )
    assert adapter.inspect()["automation_detected"] is True
    assert adapter.inspect()["state"] == "undecided"
    assert adapter.inspect()["transmission_authorized"] is False
    sent = adapter.submit(CollectionChannel.TELEMETRY, _SAFE_EVENT)
    assert sent.status is CollectionSubmitStatus.DROPPED_NO_CONSENT
    assert capture.captured == []
    assert not _pref(tmp_path).exists()


def test_unsupported_and_partial_preferences_fail_closed(tmp_path: Path) -> None:
    unsupported = _copy_fixture(tmp_path / "u", "unsupported_scope.json")
    adapter = EngineCollectionAdapter(preference_path=unsupported, automation_detected=False)
    caps = resolve_consent_capabilities(path=unsupported)
    assert caps.state is CommunityConsentState.UNDECIDED
    assert adapter.may_transmit(CollectionChannel.TELEMETRY) is False

    partial = _copy_fixture(tmp_path / "p", "partial_undecided.json")
    adapter = EngineCollectionAdapter(preference_path=partial, automation_detected=False)
    assert adapter.inspect()["state"] == "undecided"
    assert adapter.may_transmit(CollectionChannel.TELEMETRY) is False

    corrupt = _copy_fixture(tmp_path / "c", "corrupt.json")
    adapter = EngineCollectionAdapter(preference_path=corrupt, automation_detected=False)
    assert adapter.inspect()["state"] == "undecided"
    assert adapter.submit(CollectionChannel.TELEMETRY, _SAFE_EVENT).transmitted is False


def test_enable_allows_telemetry_not_evidence_or_graph(tmp_path: Path) -> None:
    pref = _pref(tmp_path)
    capture = CaptureTelemetryTransport()
    adapter = EngineCollectionAdapter(
        preference_path=pref,
        transport=capture,
        automation_detected=False,
    )
    adapter.enable()
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.V2_YES
    assert adapter.may_transmit(CollectionChannel.TELEMETRY) is True
    assert adapter.may_transmit(CollectionChannel.EVIDENCE) is False
    assert adapter.may_transmit(CollectionChannel.GRAPH) is False
    telemetry = adapter.submit(CollectionChannel.TELEMETRY, _SAFE_EVENT)
    assert telemetry.status is CollectionSubmitStatus.ACCEPTED
    assert len(capture.captured) == 1
    evidence = adapter.submit(CollectionChannel.EVIDENCE, {"digest": "abc", "schema": "x"})
    graph = adapter.submit(CollectionChannel.GRAPH, {"nodes": [], "edges": []})
    assert evidence.status is CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE
    assert graph.status is CollectionSubmitStatus.DROPPED_CHANNEL_UNAVAILABLE
    assert len(capture.captured) == 1


def test_per_run_deny_blocks_durable_opt_in_without_persisting(tmp_path: Path) -> None:
    pref = _pref(tmp_path)
    persist_v2_yes(path=pref)
    capture = CaptureTelemetryTransport()
    adapter = EngineCollectionAdapter(
        preference_path=pref,
        per_run_deny=True,
        transport=capture,
        automation_detected=False,
    )
    assert adapter.inspect()["state"] == "v2_yes"
    assert adapter.inspect()["per_run_deny"] is True
    assert adapter.may_transmit(CollectionChannel.TELEMETRY) is False
    result = adapter.submit(CollectionChannel.TELEMETRY, _SAFE_EVENT)
    assert result.status is CollectionSubmitStatus.DROPPED_PER_RUN_DENY
    assert capture.captured == []
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.V2_YES


def test_disable_survives_restart_and_cancels_queued_sends(tmp_path: Path) -> None:
    pref = _pref(tmp_path)
    queue = _queue(tmp_path)
    persist_v2_yes(path=pref)
    enqueue(
        {
            "schema_version": "1.0.0",
            "event": "assessment_started",
            "installation_id": "11111111-1111-4111-8111-111111111111",
            "codestrata_version": "0.0.0",
            "os": "Windows",
            "python_version": "3.12.0",
            "timestamp": "2026-01-01T00:00:00Z",
        },
        path=queue,
    )
    assert queue_depth(path=queue) == 1
    first = EngineCollectionAdapter(preference_path=pref, automation_detected=False)
    first.stage_pending({"event": "held"})
    first.disable()
    assert resolve_consent_capabilities(path=pref).state is CommunityConsentState.DISABLED
    assert queue_depth(path=queue) == 0
    assert first.pending_count() == 0

    restarted = EngineCollectionAdapter(preference_path=pref, automation_detected=False)
    assert restarted.inspect()["state"] == "disabled"
    assert restarted.may_transmit(CollectionChannel.TELEMETRY) is False
    assert restarted.queue_depth() == 0
    capture = CaptureTelemetryTransport()
    restarted._transport = capture
    sent = restarted.submit(CollectionChannel.TELEMETRY, _SAFE_EVENT)
    assert sent.transmitted is False
    assert capture.captured == []


def test_legacy_disable_cancels_queue_and_does_not_send(tmp_path: Path) -> None:
    service = TelemetryService(home=tmp_path)
    service.enable(emit_events=False)
    enqueue(
        {
            "schema_version": "1.0.0",
            "event": "assessment_completed",
            "installation_id": "11111111-1111-4111-8111-111111111111",
            "codestrata_version": "0.0.0",
            "os": "Windows",
            "python_version": "3.12.0",
            "timestamp": "2026-01-01T00:00:00Z",
        },
        path=_queue(tmp_path),
    )
    with patch("codestrata.telemetry.transport.send_payload", return_value=True) as send:
        status = service.disable()
        assert status["enabled"] is False
        assert queue_depth(path=_queue(tmp_path)) == 0
        send.assert_not_called()
        assert service.flush_queue() == 0


def test_upload_failure_cannot_fail_analysis(tmp_path: Path) -> None:
    pref = _pref(tmp_path)
    persist_v2_yes(path=pref)
    boom = CaptureTelemetryTransport(raise_on_send=True)
    adapter = EngineCollectionAdapter(
        preference_path=pref,
        transport=boom,
        automation_detected=False,
    )

    def primary() -> str:
        return "canonical-ok"

    assert run_primary_with_isolated_collection(primary, adapter=adapter) == "canonical-ok"

    def failing() -> str:
        raise RuntimeError("analysis-failed")

    with pytest.raises(RuntimeError, match="analysis-failed"):
        run_primary_with_isolated_collection(failing, adapter=adapter)


def test_unsupported_channel_and_budget_failure(tmp_path: Path) -> None:
    adapter = create_collection_adapter(preference_path=_pref(tmp_path))
    unknown = adapter.submit("lake", {"a": 1})
    assert unknown.status is CollectionSubmitStatus.DROPPED_UNSUPPORTED
    huge = adapter.submit(CollectionChannel.EVIDENCE, {"blob": "x" * 10_000})
    assert huge.status is CollectionSubmitStatus.DROPPED_BUDGET
    assert huge.transmitted is False


def test_inspect_does_not_write_preference(tmp_path: Path) -> None:
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        automation_detected=False,
    )
    payload = adapter.inspect()
    assert payload["opt_in_policy_version"] == "1.0"
    assert payload["channels"]["telemetry"] is False
    assert payload["channels"]["evidence"] is False
    assert payload["channels"]["graph"] is False
    assert list(tmp_path.iterdir()) == []


def test_cancel_pending_swallows_queue_errors(tmp_path: Path, monkeypatch) -> None:
    from codestrata.telemetry.pending import cancel_pending_collection

    def boom(*_args: object, **_kwargs: object) -> int:
        raise OSError("disk")

    monkeypatch.setattr("codestrata.telemetry.pending.queue_depth", boom)
    monkeypatch.setattr("codestrata.telemetry.pending.clear_queue", boom)
    assert cancel_pending_collection(preference_path=tmp_path / "telemetry.json") == 0


def test_persist_disabled_cancels_existing_queue(tmp_path: Path) -> None:
    pref = _pref(tmp_path)
    persist_v2_yes(path=pref)
    queue = _queue(tmp_path)
    queue.write_text("{}\n", encoding="utf-8")
    persist_disabled(path=pref)
    assert load_queue(path=queue) == []
    assert not queue.is_file() or queue.read_text(encoding="utf-8") == ""
