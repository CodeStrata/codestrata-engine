"""Parse cumulative gate and story ledgers under engine/docs/implementation/gates/."""

from __future__ import annotations

import re
from pathlib import Path

from verification.validation.release_gate.models import (
    GateLedgerEntry,
    ReleaseGatePolicy,
    ReviewDecision,
    StoryPrerequisite,
)

_DECISION = re.compile(r"Decision:\s*\*?\*?(PASS|FAIL|BLOCKED|NOT_YET_DUE|NOT_RUN)\*?\*?", re.I)
_STATUS_LINE = re.compile(r"^\|\s*Status\s*\|\s*(.+?)\s*\|", re.M)


def gates_dir(engine_root: Path) -> Path:
    return engine_root / "docs" / "implementation" / "gates"


def _read_ledger(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_gate_decision(text: str) -> ReviewDecision:
    matches = [token.upper() for token in _DECISION.findall(text)]
    if not matches:
        table = re.search(
            r"^\|\s*Decision\s*\|\s*\*?\*?(PASS|FAIL|BLOCKED|NOT_YET_DUE|NOT_RUN)\*?\*?",
            text,
            re.M | re.I,
        )
        if table:
            return ReviewDecision(table.group(1).upper())
        inline = re.search(
            r"Decision\s*\|\s*\*?\*?(PASS|FAIL|BLOCKED|NOT_YET_DUE|NOT_RUN)\*?\*?",
            text,
            re.I,
        )
        if inline:
            return ReviewDecision(inline.group(1).upper())
        banner = re.search(r"\*\*G00 PASS\*\*", text)
        if banner:
            return ReviewDecision.PASS
        return ReviewDecision.NOT_RUN
    for token in reversed(matches):
        if token == "PASS":
            return ReviewDecision.PASS
    return ReviewDecision(matches[-1])


def _story_status(text: str, policy: ReleaseGatePolicy) -> tuple[ReviewDecision, str]:
    if not text.strip():
        return ReviewDecision.BLOCKED, "ledger missing"
    status_match = _STATUS_LINE.search(text)
    status_blob = status_match.group(1) if status_match else text[:400]
    lowered = status_blob.lower()
    for marker in policy.blocked_status_markers:
        if marker.lower() in lowered:
            return ReviewDecision.BLOCKED, status_blob.strip()
    for marker in policy.integrated_status_markers:
        if marker.lower() in lowered:
            return ReviewDecision.PASS, status_blob.strip()
    if "ready for review" in lowered and "not integrated" in lowered:
        return ReviewDecision.BLOCKED, status_blob.strip()
    if "ready for review" in lowered:
        return ReviewDecision.BLOCKED, "not integrated (ready for review only)"
    return ReviewDecision.NOT_RUN, status_blob.strip() or "status not parsed"


def evaluate_checkpoint_gates(
    engine_root: Path,
    policy: ReleaseGatePolicy,
) -> tuple[GateLedgerEntry, ...]:
    root = gates_dir(engine_root)
    entries: list[GateLedgerEntry] = []
    for gate in policy.required_checkpoint_gates:
        path = root / gate.ledger
        text = _read_ledger(path)
        present = bool(text)
        decision = _parse_gate_decision(text) if present else ReviewDecision.NOT_RUN
        detail = "ledger present" if present else "ledger missing"
        if present and decision is ReviewDecision.NOT_RUN:
            detail = "no Decision line found"
        entries.append(
            GateLedgerEntry(
                gate_id=gate.id,
                ledger_path=str(path.relative_to(engine_root.parent)),
                present=present,
                decision=decision,
                detail=detail,
            )
        )
    return tuple(entries)


def evaluate_story_prerequisites(
    engine_root: Path,
    policy: ReleaseGatePolicy,
) -> tuple[StoryPrerequisite, ...]:
    root = gates_dir(engine_root)
    items: list[StoryPrerequisite] = []
    for story_id in policy.required_story_ledgers:
        path = root / f"{story_id}.md"
        text = _read_ledger(path)
        present = bool(text)
        status, detail = _story_status(text, policy) if present else (
            ReviewDecision.BLOCKED,
            "ledger missing",
        )
        items.append(
            StoryPrerequisite(
                story_id=story_id,
                ledger_path=str(path.relative_to(engine_root.parent)),
                present=present,
                status=status,
                detail=detail,
            )
        )
    return tuple(items)
