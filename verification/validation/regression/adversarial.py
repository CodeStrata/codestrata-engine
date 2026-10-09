"""M33 adversarial kinds: planted runs, never silent PASS."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from verification.validation.regression.models import CheckOutcome, HarnessStatus
from verification.validation.regression.semantic import semantic_digest


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status", "")).upper()


def classify_resource_exhaustion(payload: Mapping[str, Any]) -> CheckOutcome:
    exceeded = bool(payload.get("budget_exceeded")) or bool(payload.get("deadline_exceeded"))
    status = _status(payload)
    if exceeded and status == "PASS":
        return CheckOutcome(
            "adversarial:resource-exhaustion",
            HarnessStatus.FAIL,
            "budget/deadline breach recorded as PASS",
        )
    if exceeded and status in {"ERROR", "FAIL"}:
        return CheckOutcome(
            "adversarial:resource-exhaustion",
            HarnessStatus.PASS,
            f"exhaustion is {status}",
        )
    return CheckOutcome(
        "adversarial:resource-exhaustion",
        HarnessStatus.FAIL,
        f"expected budget_exceeded with ERROR/FAIL, got status={status}",
    )


def classify_corruption(payload: Mapping[str, Any]) -> CheckOutcome:
    corrupt = bool(payload.get("corrupt")) or _status(payload) == "ERROR"
    empty_healthy = bool(payload.get("empty_table_looks_healthy"))
    if empty_healthy:
        return CheckOutcome(
            "adversarial:corruption",
            HarnessStatus.FAIL,
            "corrupt input projected as a healthy empty table",
        )
    if corrupt and _status(payload) in {"ERROR", "TAMPERED"}:
        return CheckOutcome("adversarial:corruption", HarnessStatus.PASS, _status(payload))
    return CheckOutcome(
        "adversarial:corruption",
        HarnessStatus.FAIL,
        f"corrupt artifact status={_status(payload)}",
    )


def classify_cancellation(payload: Mapping[str, Any]) -> CheckOutcome:
    status = _status(payload)
    if status == "PASS":
        return CheckOutcome(
            "adversarial:sigint-sigterm-hard-kill",
            HarnessStatus.FAIL,
            "cancelled run recorded as PASS",
        )
    if status in {"CANCELLED", "ERROR"}:
        return CheckOutcome(
            "adversarial:sigint-sigterm-hard-kill",
            HarnessStatus.PASS,
            status,
        )
    return CheckOutcome(
        "adversarial:sigint-sigterm-hard-kill",
        HarnessStatus.FAIL,
        f"expected cancelled_or_error, got {status}",
    )


def classify_disk_full(payload: Mapping[str, Any]) -> CheckOutcome:
    if bool(payload.get("disk_full")) and _status(payload) == "ERROR":
        return CheckOutcome("adversarial:disk-full", HarnessStatus.PASS, "ERROR")
    return CheckOutcome(
        "adversarial:disk-full",
        HarnessStatus.FAIL,
        f"disk_full={payload.get('disk_full')} status={_status(payload)}",
    )


def classify_output_collision(
    *,
    baseline_digest: str,
    after_digest: str,
    payload: Mapping[str, Any],
) -> CheckOutcome:
    if bool(payload.get("silent_overwrite")):
        return CheckOutcome(
            "adversarial:output-collision",
            HarnessStatus.FAIL,
            "active baseline overwritten silently",
        )
    if baseline_digest != after_digest:
        return CheckOutcome(
            "adversarial:output-collision",
            HarnessStatus.FAIL,
            "baseline digest changed under collision",
        )
    if _status(payload) != "ERROR":
        return CheckOutcome(
            "adversarial:output-collision",
            HarnessStatus.FAIL,
            f"collision status={_status(payload)}",
        )
    return CheckOutcome("adversarial:output-collision", HarnessStatus.PASS, "baseline retained")


def classify_concurrent_reader(
    *,
    reader_digests: tuple[str, ...],
) -> CheckOutcome:
    if len(reader_digests) < 2:
        return CheckOutcome(
            "adversarial:concurrent-reader",
            HarnessStatus.FAIL,
            "need at least two reader observations",
        )
    if len(set(reader_digests)) != 1:
        return CheckOutcome(
            "adversarial:concurrent-reader",
            HarnessStatus.FAIL,
            f"reader saw mutation {reader_digests}",
        )
    return CheckOutcome("adversarial:concurrent-reader", HarnessStatus.PASS, "stable_read")


def classify_retention(
    *,
    active_baseline_present: bool,
    payload: Mapping[str, Any],
) -> CheckOutcome:
    if not active_baseline_present:
        return CheckOutcome(
            "adversarial:retention-active-baseline",
            HarnessStatus.FAIL,
            "active baseline missing after retention",
        )
    if _status(payload) not in {"PASS", "RETAINED"} and not bool(payload.get("retained")):
        return CheckOutcome(
            "adversarial:retention-active-baseline",
            HarnessStatus.FAIL,
            "retention did not record retained",
        )
    return CheckOutcome(
        "adversarial:retention-active-baseline",
        HarnessStatus.PASS,
        "retained",
    )


def classify_audit_redaction(text: str) -> CheckOutcome:
    forbidden = ("pypi-secret", "ghs_planted", "cs_unredacted_secret")
    hits = [item for item in forbidden if item in text]
    if hits:
        return CheckOutcome("adversarial:audit-redaction", HarnessStatus.FAIL, f"leaked {hits}")
    return CheckOutcome("adversarial:audit-redaction", HarnessStatus.PASS, "redacted")


def classify_unknown_coverage(payload: Mapping[str, Any]) -> CheckOutcome:
    eligible = payload.get("eligible_units")
    evaluated = payload.get("evaluated_units")
    coverage_status = str(payload.get("coverage_status", "")).upper()
    if eligible in (None, "unknown"):
        if coverage_status == "UNKNOWN":
            return CheckOutcome(
                "coverage:unknown_denominator",
                HarnessStatus.PASS,
                "UNKNOWN",
            )
        return CheckOutcome(
            "coverage:unknown_denominator",
            HarnessStatus.FAIL,
            f"unknown denominator reported as {coverage_status or evaluated}",
        )
    return CheckOutcome(
        "coverage:unknown_denominator",
        HarnessStatus.NOT_APPLICABLE,
        f"denominator={eligible}",
    )


def classify_tamper(
    payload: Mapping[str, Any],
    *,
    expected_digest: str,
    fields: frozenset[str],
) -> CheckOutcome:
    actual = str(payload.get("body_digest", ""))
    if actual and actual != expected_digest and _status(payload) in {"TAMPERED", "ERROR"}:
        return CheckOutcome("contract:tamper", HarnessStatus.PASS, _status(payload))
    if semantic_digest(payload, fields) != expected_digest and _status(payload) == "PASS":
        return CheckOutcome("contract:tamper", HarnessStatus.FAIL, "tamper recorded as PASS")
    if _status(payload) in {"TAMPERED", "ERROR"}:
        return CheckOutcome("contract:tamper", HarnessStatus.PASS, _status(payload))
    return CheckOutcome("contract:tamper", HarnessStatus.FAIL, f"status={_status(payload)}")


def classify_report_escaping(rendered_html: str, raw_marker: str) -> CheckOutcome:
    if raw_marker in rendered_html:
        return CheckOutcome(
            "report:escaping",
            HarnessStatus.FAIL,
            "raw markup survived HTML projection",
        )
    if "&lt;script" not in rendered_html.lower() and "script" in raw_marker.lower():
        return CheckOutcome(
            "report:escaping",
            HarnessStatus.FAIL,
            "script payload missing after escape (lost evidence)",
        )
    return CheckOutcome("report:escaping", HarnessStatus.PASS, "escaped")
