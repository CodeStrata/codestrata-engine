"""Lightweight runtime timing and memory helpers."""

from __future__ import annotations

import resource
from dataclasses import dataclass, field
from time import perf_counter


def peak_rss_mb() -> float | None:
    """Return peak resident set size in MiB when available (POSIX)."""

    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
    except (AttributeError, ValueError, OSError):
        return None
    rss = float(usage.ru_maxrss)
    # Linux reports KiB; macOS reports bytes.
    if rss > 10_000_000:  # heuristic: treat as bytes
        return round(rss / (1024 * 1024), 2)
    return round(rss / 1024, 2)


@dataclass
class PhaseTimer:
    """Accumulate named phase durations (milliseconds)."""

    phases: dict[str, float] = field(default_factory=dict)
    _starts: dict[str, float] = field(default_factory=dict)

    def start(self, name: str) -> None:
        self._starts[name] = perf_counter()

    def stop(self, name: str) -> float:
        started = self._starts.pop(name, None)
        if started is None:
            return 0.0
        elapsed = round((perf_counter() - started) * 1000, 2)
        self.phases[name] = round(self.phases.get(name, 0.0) + elapsed, 2)
        return elapsed

    def get(self, name: str) -> float | None:
        return self.phases.get(name)
