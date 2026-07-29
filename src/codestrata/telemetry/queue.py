"""Local durable telemetry queue (never blocks assessment)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codestrata.telemetry.paths import ensure_home, queue_path
from codestrata.telemetry.validate import validate_payload

DEFAULT_MAX_QUEUE = 500


def enqueue(
    payload: dict[str, Any],
    *,
    path: Path | None = None,
    max_queue: int = DEFAULT_MAX_QUEUE,
) -> None:
    validate_payload(payload)
    ensure_home()
    target = path or queue_path()
    line = json.dumps(payload, sort_keys=True)
    try:
        with target.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return
    _trim_queue(target, max_queue=max_queue)


def load_queue(*, path: Path | None = None) -> list[dict[str, Any]]:
    target = path or queue_path()
    if not target.is_file():
        return []
    items: list[dict[str, Any]] = []
    try:
        raw = target.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            items.append(item)
    return items


def replace_queue(items: list[dict[str, Any]], *, path: Path | None = None) -> None:
    ensure_home()
    target = path or queue_path()
    body = "".join(json.dumps(item, sort_keys=True) + "\n" for item in items)
    try:
        target.write_text(body, encoding="utf-8")
    except OSError:
        return


def clear_queue(*, path: Path | None = None) -> None:
    target = path or queue_path()
    try:
        if target.is_file():
            target.unlink()
    except OSError:
        return


def queue_depth(*, path: Path | None = None) -> int:
    return len(load_queue(path=path))


def _trim_queue(path: Path, *, max_queue: int) -> None:
    items = load_queue(path=path)
    if len(items) <= max_queue:
        return
    replace_queue(items[-max_queue:], path=path)
