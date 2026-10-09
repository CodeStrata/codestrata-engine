"""Cancel pending local collection (retry queue) on durable disable (E13.1).

Queued sends are local JSONL under CODESTRATA_HOME. Disable must drop them so a
later restart or re-enable cannot transmit leftover events. Never raises into
CLI or analysis.
"""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.constants import QUEUE_FILENAME
from codestrata.telemetry.queue import clear_queue, queue_depth


def queue_path_for_preference(preference_path: Path | None) -> Path | None:
    """Sibling ``telemetry-queue.jsonl`` next to a preference file, if given."""

    if preference_path is None:
        return None
    return preference_path.parent / QUEUE_FILENAME


def cancel_pending_collection(
    *,
    preference_path: Path | None = None,
    queue: Path | None = None,
) -> int:
    """Delete queued collection items. Return how many were discarded.

    ``queue`` wins when supplied. Otherwise a sibling of ``preference_path`` is
    used. ``None`` for both targets the process CODESTRATA_HOME queue.
    Failures are swallowed — disable must not fail analysis or the CLI.
    """

    try:
        target = queue if queue is not None else queue_path_for_preference(preference_path)
        discarded = queue_depth(path=target)
        clear_queue(path=target)
        return discarded
    except Exception:  # noqa: BLE001 - cancellation is best-effort
        try:
            target = queue if queue is not None else queue_path_for_preference(preference_path)
            clear_queue(path=target)
        except Exception:  # noqa: BLE001
            return 0
        return 0


__all__ = [
    "cancel_pending_collection",
    "queue_path_for_preference",
]
