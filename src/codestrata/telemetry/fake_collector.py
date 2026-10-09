"""Local fake collector for evidence/graph capability contracts (E13.2).

Never performs HTTP or live v2 calls. Advertised schemas and receipts are
in-process only. An unadvertised live collector probe also never issues
network calls and never claims server readiness.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from codestrata.domain.contracts.serialization import digest_canonical
from codestrata.telemetry.export_gate import evaluate_export_capability
from codestrata.telemetry.export_models import (
    CapabilityCheck,
    CollectorCapability,
    CollectorKind,
    CollectorReceipt,
    ExportEnvelopeError,
    ReceiptDecision,
    ScopedExportEnvelope,
)
from codestrata.telemetry.export_policy import default_export_policy


class FakeCollector:
    """In-process collector used to prove schema/receipt contracts locally."""

    def __init__(
        self,
        *,
        advertised_schemas: Iterable[str] = (),
        receipts_supported: bool = True,
        now_unix: int | None = None,
        receipt_ttl_seconds: int | None = None,
    ) -> None:
        self._advertised = tuple(sorted(set(str(item) for item in advertised_schemas)))
        self._receipts_supported = bool(receipts_supported)
        self.accepted: list[ScopedExportEnvelope] = []
        self.receipts: list[CollectorReceipt] = []
        self.live_v2_invoked = False
        self._now_unix = now_unix
        self._ttl = receipt_ttl_seconds
        self._by_id: dict[str, CollectorReceipt] = {}
        self._revoked: set[str] = set()
        self._expired: set[str] = set()

    @property
    def transport_category(self) -> str:
        return "fake_local"

    def capability(self) -> CollectorCapability:
        return CollectorCapability(
            kind=CollectorKind.FAKE.value,
            advertised_schemas=self._advertised,
            receipts_supported=self._receipts_supported,
            live_v2_calls=False,
            server_ready=False,
        )

    def accept(self, envelope: ScopedExportEnvelope) -> CollectorReceipt:
        if self.live_v2_invoked:
            raise ExportEnvelopeError("fake collector must never invoke live v2")
        decision = evaluate_export_capability(self, envelope.category)
        check = decision.reason if not decision.allowed else CapabilityCheck.PASSED.value
        accepted = bool(decision.allowed)
        issued = self._now_unix
        expires = None if self._ttl is None or issued is None else issued + self._ttl
        receipt = _receipt_for(
            envelope,
            accepted=accepted,
            check=check,
            issued_at_unix=issued,
            expires_at_unix=expires,
        )
        self.receipts.append(receipt)
        self._by_id[receipt.receipt_id] = receipt
        if accepted:
            self.accepted.append(envelope)
        return receipt

    def revoke(self, receipt_id: str) -> CollectorReceipt:
        """Mark a previously issued receipt revoked. Does not call a server."""

        current = self._require_receipt(receipt_id)
        self._revoked.add(receipt_id)
        updated = _copy_receipt(
            current,
            accepted=False,
            revoked=True,
            receipt_status="revoked",
            check=CapabilityCheck.RECEIPT_REVOKED.value,
        )
        self._replace_receipt(updated)
        return updated

    def expire(self, receipt_id: str) -> CollectorReceipt:
        """Mark a previously issued receipt expired. Does not call a server."""

        current = self._require_receipt(receipt_id)
        self._expired.add(receipt_id)
        updated = _copy_receipt(
            current,
            accepted=False,
            revoked=current.revoked,
            receipt_status="expired",
            check=CapabilityCheck.RECEIPT_EXPIRED.value,
            expires_at_unix=current.issued_at_unix or self._now_unix or 0,
        )
        self._replace_receipt(updated)
        return updated

    def evaluate_receipt(
        self,
        receipt_id: str,
        *,
        now_unix: int | None = None,
    ) -> ReceiptDecision:
        """Local receipt lifecycle. Server deletion/admission remain follow-on."""

        current = self._by_id.get(receipt_id)
        if current is None:
            return ReceiptDecision(
                receipt_id=receipt_id,
                status="missing",
                accepted=False,
                reason="receipt_missing",
            )
        clock = now_unix if now_unix is not None else self._now_unix
        if receipt_id in self._revoked or current.revoked:
            return ReceiptDecision(
                receipt_id=receipt_id,
                status="revoked",
                accepted=False,
                reason=CapabilityCheck.RECEIPT_REVOKED.value,
            )
        if receipt_id in self._expired or current.receipt_status == "expired":
            return ReceiptDecision(
                receipt_id=receipt_id,
                status="expired",
                accepted=False,
                reason=CapabilityCheck.RECEIPT_EXPIRED.value,
            )
        if (
            clock is not None
            and current.expires_at_unix is not None
            and clock >= current.expires_at_unix
        ):
            return ReceiptDecision(
                receipt_id=receipt_id,
                status="expired",
                accepted=False,
                reason=CapabilityCheck.RECEIPT_EXPIRED.value,
            )
        if not current.accepted:
            return ReceiptDecision(
                receipt_id=receipt_id,
                status=current.receipt_status or "rejected",
                accepted=False,
                reason=current.capability_check,
            )
        return ReceiptDecision(
            receipt_id=receipt_id,
            status="accepted",
            accepted=True,
            reason=CapabilityCheck.PASSED.value,
        )

    def _require_receipt(self, receipt_id: str) -> CollectorReceipt:
        current = self._by_id.get(receipt_id)
        if current is None:
            raise ExportEnvelopeError("receipt_id is not known to this fake collector")
        return current

    def _replace_receipt(self, receipt: CollectorReceipt) -> None:
        self._by_id[receipt.receipt_id] = receipt
        self.receipts = [
            receipt if item.receipt_id == receipt.receipt_id else item
            for item in self.receipts
        ]

    def clear(self) -> None:
        self.accepted.clear()
        self.receipts.clear()
        self._by_id.clear()
        self._revoked.clear()
        self._expired.clear()


class UnadvertisedLiveCollector:
    """Stand-in for an actual collector that has not advertised support.

    Never issues HTTP, never claims v2, never returns a successful receipt.
    """

    def __init__(self) -> None:
        self.accepted: list[ScopedExportEnvelope] = []
        self.receipts: list[CollectorReceipt] = []
        self.live_v2_invoked = False
        self.http_calls: list[str] = []

    @property
    def transport_category(self) -> str:
        return "unadvertised_live"

    def capability(self) -> CollectorCapability:
        return CollectorCapability(
            kind=CollectorKind.UNADVERTISED_LIVE.value,
            advertised_schemas=(),
            receipts_supported=False,
            live_v2_calls=False,
            server_ready=False,
        )

    def accept(self, envelope: ScopedExportEnvelope) -> CollectorReceipt:
        # Deliberately no HTTP and no v2 probe.
        if self.http_calls:
            raise ExportEnvelopeError("unadvertised live collector must not record HTTP")
        receipt = _receipt_for(
            envelope,
            accepted=False,
            check=CapabilityCheck.NOT_FAKE_LOCAL.value,
        )
        self.receipts.append(receipt)
        return receipt


def default_unadvertised_collector() -> UnadvertisedLiveCollector:
    return UnadvertisedLiveCollector()


def collector_from_mapping(payload: Mapping[str, Any]) -> FakeCollector | UnadvertisedLiveCollector:
    """Load a collector capability fixture. Never constructs a live HTTP client."""

    kind = str(payload.get("kind", CollectorKind.FAKE.value)).strip().lower()
    advertised_raw = payload.get("advertised_schemas") or ()
    advertised = tuple(str(item) for item in advertised_raw)
    receipts = bool(payload.get("receipts_supported", False))
    if kind == CollectorKind.UNADVERTISED_LIVE.value or kind == CollectorKind.NONE.value:
        return UnadvertisedLiveCollector()
    if kind != CollectorKind.FAKE.value:
        raise ExportEnvelopeError("unsupported collector kind")
    if payload.get("live_v2_calls") or payload.get("server_ready"):
        raise ExportEnvelopeError("collector fixture cannot enable live v2 or server readiness")
    now_raw = payload.get("now_unix")
    ttl_raw = payload.get("receipt_ttl_seconds")
    now_unix = int(now_raw) if now_raw is not None else None
    ttl = int(ttl_raw) if ttl_raw is not None else None
    return FakeCollector(
        advertised_schemas=advertised,
        receipts_supported=receipts,
        now_unix=now_unix,
        receipt_ttl_seconds=ttl,
    )


def advertising_fake_collector() -> FakeCollector:
    policy = default_export_policy()
    return FakeCollector(
        advertised_schemas=(policy.evidence_schema, policy.graph_schema),
        receipts_supported=True,
    )


def _receipt_for(
    envelope: ScopedExportEnvelope,
    *,
    accepted: bool,
    check: str,
    issued_at_unix: int | None = None,
    expires_at_unix: int | None = None,
    revoked: bool = False,
    receipt_status: str = "",
) -> CollectorReceipt:
    receipt_id = digest_canonical(
        {
            "accepted": accepted,
            "capability_check": check,
            "digest": envelope.digest,
            "schema": envelope.schema,
        }
    )
    return CollectorReceipt(
        receipt_id=receipt_id,
        schema=envelope.schema,
        category=envelope.category,
        accepted=accepted,
        capability_check=check,
        live_v2_invoked=False,
        server_ready=False,
        receipt_status=receipt_status,
        issued_at_unix=issued_at_unix,
        expires_at_unix=expires_at_unix,
        revoked=revoked,
        server_deletion_performed=False,
        server_admission_performed=False,
    )


def _copy_receipt(
    current: CollectorReceipt,
    *,
    accepted: bool,
    revoked: bool,
    receipt_status: str,
    check: str,
    expires_at_unix: int | None = None,
) -> CollectorReceipt:
    return CollectorReceipt(
        receipt_id=current.receipt_id,
        schema=current.schema,
        category=current.category,
        accepted=accepted,
        capability_check=check,
        live_v2_invoked=False,
        server_ready=False,
        receipt_status=receipt_status,
        issued_at_unix=current.issued_at_unix,
        expires_at_unix=current.expires_at_unix if expires_at_unix is None else expires_at_unix,
        revoked=revoked,
        server_deletion_performed=False,
        server_admission_performed=False,
    )


__all__ = [
    "FakeCollector",
    "UnadvertisedLiveCollector",
    "advertising_fake_collector",
    "collector_from_mapping",
    "default_unadvertised_collector",
]
