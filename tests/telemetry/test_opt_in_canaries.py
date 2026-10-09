"""E13.1 prohibited-data canaries for logs, retry queues, and serialization."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from tests.telemetry.privacy_canaries import (
    ALL_CANARIES,
    PATH,
    REPO_NAME,
    SECRET,
    assert_no_canaries,
)

from codestrata.telemetry.canaries import (
    collection_surface_violations,
    drop_prohibited_queue_items,
    log_records_contain_prohibited,
)
from codestrata.telemetry.events import RuntimeEventType, RuntimeTelemetryEvent
from codestrata.telemetry.infrastructure.capture_transport import CaptureTelemetryTransport
from codestrata.telemetry.opt_in import (
    CollectionChannel,
    CollectionSubmitStatus,
    EngineCollectionAdapter,
)
from codestrata.telemetry.pending import cancel_pending_collection
from codestrata.telemetry.persisted_consent import persist_v2_yes
from codestrata.telemetry.queue import load_queue, queue_depth

_SAFE_EVENT = RuntimeTelemetryEvent(event_type=RuntimeEventType.FEATURE_INVOKED)


def _pref(tmp_path: Path) -> Path:
    return tmp_path / "telemetry.json"


def _queue(tmp_path: Path) -> Path:
    return tmp_path / "telemetry-queue.jsonl"


def test_serialization_drops_canary_payloads(tmp_path: Path) -> None:
    persist_v2_yes(path=_pref(tmp_path))
    capture = CaptureTelemetryTransport()
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        transport=capture,
        automation_detected=False,
    )
    poisoned = {
        "repository_name": REPO_NAME,
        "path": PATH,
        "secret": SECRET,
        "source_code": "print('leak')",
    }
    assert collection_surface_violations(poisoned)
    result = adapter.submit(CollectionChannel.TELEMETRY, poisoned)
    assert result.status is CollectionSubmitStatus.DROPPED_PROHIBITED
    assert capture.captured == []
    accepted = adapter.submit(CollectionChannel.TELEMETRY, _SAFE_EVENT)
    assert accepted.status is CollectionSubmitStatus.ACCEPTED
    assert_no_canaries(capture.captured[0].to_stable_dict())


def test_retry_queue_canaries_are_dropped_and_cancelled(tmp_path: Path) -> None:
    queue = _queue(tmp_path)
    leftover = {
        "schema_version": "1.0.0",
        "event": "assessment_started",
        "repository_name": REPO_NAME,
        "source_code": SECRET,
        "path": PATH,
    }
    queue.write_text(json.dumps(leftover) + "\n", encoding="utf-8")
    raw = load_queue(path=queue)
    assert raw
    assert collection_surface_violations(raw[0])
    cleaned = drop_prohibited_queue_items(raw)
    assert cleaned == []
    persist_v2_yes(path=_pref(tmp_path))
    adapter = EngineCollectionAdapter(preference_path=_pref(tmp_path), automation_detected=False)
    adapter.disable()
    assert queue_depth(path=queue) == 0
    cancel_pending_collection(preference_path=_pref(tmp_path))
    assert not queue.is_file() or queue.read_text(encoding="utf-8").strip() == ""


def test_log_scanner_flags_canaries_and_survives_bad_records() -> None:
    hits = log_records_contain_prohibited(
        [
            logging.LogRecord(
                name="codestrata.telemetry",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="leak %s",
                args=(SECRET,),
                exc_info=None,
            )
        ],
        extra_needles=ALL_CANARIES,
    )
    assert SECRET in hits

    class _Bad(logging.LogRecord):
        def getMessage(self) -> str:  # type: ignore[override]
            raise RuntimeError("boom")

    bad = _Bad(
        name="codestrata.telemetry",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=SECRET,
        args=(),
        exc_info=None,
    )
    found = log_records_contain_prohibited([bad], extra_needles=(SECRET,))
    assert SECRET in found


def test_logs_do_not_record_canaries(tmp_path: Path) -> None:
    persist_v2_yes(path=_pref(tmp_path))
    adapter = EngineCollectionAdapter(
        preference_path=_pref(tmp_path),
        transport=CaptureTelemetryTransport(),
        automation_detected=False,
    )
    logger = logging.getLogger("codestrata.telemetry")
    captured: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = _Handler()
    logger.addHandler(handler)
    try:
        previous = logger.level
        logger.setLevel(logging.DEBUG)
        adapter.submit(
            CollectionChannel.EVIDENCE,
            {
                "repository_name": REPO_NAME,
                "findings": ALL_CANARIES[0],
                "secret": SECRET,
            },
        )
        adapter.submit(CollectionChannel.TELEMETRY, _SAFE_EVENT)
        adapter.inspect()
        adapter.disable()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)

    hits = log_records_contain_prohibited(captured, extra_needles=ALL_CANARIES)
    assert hits == ()
    for record in captured:
        blob = record.getMessage()
        for canary in ALL_CANARIES:
            assert canary not in blob
