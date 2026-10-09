"""E13.3 fake-collector revocation and expiry. No server deletion."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.telemetry.export_models import CapabilityCheck, CollectorKind
from codestrata.telemetry.export_serialize import build_scoped_export
from codestrata.telemetry.fake_collector import collector_from_mapping

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "export_projection"


def test_fake_collector_revokes_and_expires_without_server_deletion() -> None:
    collector = collector_from_mapping(
        json.loads((FIXTURE_DIR / "collector-ttl.json").read_text(encoding="utf-8"))
    )
    envelope = build_scoped_export(
        "evidence",
        collector_kind=CollectorKind.FAKE,
        schema_advertised=True,
    )
    receipt = collector.accept(envelope)
    assert receipt.accepted is True
    assert receipt.server_deletion_performed is False
    assert receipt.server_admission_performed is False
    live = collector.evaluate_receipt(receipt.receipt_id, now_unix=1_700_000_000)
    assert live.accepted is True
    assert live.server_deletion_performed is False
    assert live.server_admission_performed is False

    revoked = collector.revoke(receipt.receipt_id)
    assert revoked.revoked is True
    assert revoked.accepted is False
    decision = collector.evaluate_receipt(receipt.receipt_id)
    assert decision.status == "revoked"
    assert decision.reason == CapabilityCheck.RECEIPT_REVOKED.value
    assert decision.server_deletion_performed is False

    collector.clear()
    collector = collector_from_mapping(
        json.loads((FIXTURE_DIR / "collector-ttl.json").read_text(encoding="utf-8"))
    )
    fresh = collector.accept(envelope)
    expired = collector.expire(fresh.receipt_id)
    assert expired.receipt_status == "expired"
    assert expired.accepted is False
    expired_decision = collector.evaluate_receipt(fresh.receipt_id)
    assert expired_decision.status == "expired"
    assert expired_decision.reason == CapabilityCheck.RECEIPT_EXPIRED.value
    assert expired_decision.server_admission_performed is False


def test_receipt_expires_when_clock_passes_ttl() -> None:
    collector = collector_from_mapping(
        json.loads((FIXTURE_DIR / "collector-ttl.json").read_text(encoding="utf-8"))
    )
    envelope = build_scoped_export(
        "graph",
        collector_kind=CollectorKind.FAKE,
        schema_advertised=True,
    )
    receipt = collector.accept(envelope)
    still_valid = collector.evaluate_receipt(receipt.receipt_id, now_unix=1_700_000_030)
    assert still_valid.accepted is True
    timed_out = collector.evaluate_receipt(receipt.receipt_id, now_unix=1_700_000_060)
    assert timed_out.status == "expired"
    assert timed_out.accepted is False
    missing = collector.evaluate_receipt("0" * 64)
    assert missing.status == "missing"
