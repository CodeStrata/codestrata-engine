"""Local durable telemetry queue (never blocks assessment)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codestrata.telemetry.paths import queue_path
from codestrata.telemetry.validate import validate_payload

DEFAULT_MAX_QUEUE = 500


def _resolve_queue_path(path: Path | None) -> Path:
    """Use the caller's path when given; never substitute a different home."""

    if path is not None:
        return path
    return queue_path()


def _ensure_queue_parent(target: Path) -> None:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def enqueue(
    payload: dict[str, Any],
    *,
    path: Path | None = None,
    max_queue: int = DEFAULT_MAX_QUEUE,
) -> None:
    validate_payload(payload)
    target = _resolve_queue_path(path)
    _ensure_queue_parent(target)
    line = json.dumps(payload, sort_keys=True)
    try:
        with target.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        return
    _trim_queue(target, max_queue=max_queue)


def load_queue(*, path: Path | None = None) -> list[dict[str, Any]]:
    target = _resolve_queue_path(path)
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
    target = _resolve_queue_path(path)
    _ensure_queue_parent(target)
    body = "".join(json.dumps(item, sort_keys=True) + "\n" for item in items)
    try:
        target.write_text(body, encoding="utf-8")
    except OSError:
        return


def clear_queue(*, path: Path | None = None) -> None:
    target = _resolve_queue_path(path)
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
