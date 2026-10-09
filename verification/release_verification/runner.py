"""Evaluate committed E14.1 cryptographic fixtures (not shipped in the wheel)."""

from __future__ import annotations

import json
from pathlib import Path

from codestrata.application.release.verification import verify_payload

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "application"
    / "release"
    / "fixtures"
    / "verification"
)


def load_expected() -> dict[str, dict[str, str]]:
    path = FIXTURE_DIR / "expected-outcomes.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected-outcomes.json must be an object")
    return {str(key): dict(value) for key, value in payload.items()}


def evaluate_fixtures() -> list[dict[str, str]]:
    expected = load_expected()
    rows: list[dict[str, str]] = []
    for name, want in sorted(expected.items()):
        payload = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
        result = verify_payload(payload)
        rows.append(
            {
                "name": name,
                "expected_status": str(want["status"]),
                "actual_status": result.status.value,
                "expected_reason": str(want["reason"]),
                "actual_reason": result.reason,
                "ok": str(
                    result.status.value == want["status"] and result.reason == want["reason"]
                ).lower(),
            }
        )
    return rows


def main() -> int:
    rows = evaluate_fixtures()
    failed = [row for row in rows if row["ok"] != "true"]
    for row in rows:
        mark = "PASS" if row["ok"] == "true" else "FAIL"
        print(f"{mark} {row['name']}: {row['actual_status']}/{row['actual_reason']}")
    return 1 if failed else 0
