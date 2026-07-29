"""Lightweight stage timing / memory recorder (no-op when disabled)."""

from __future__ import annotations

import contextvars
import resource
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter

from codestrata.application.runtime_performance.metrics import peak_rss_mb

_active: contextvars.ContextVar[BenchmarkRecorder | None] = contextvars.ContextVar(
    "codestrata_benchmark_recorder",
    default=None,
)


def get_active_recorder() -> BenchmarkRecorder:
    """Return the active recorder or a disabled no-op instance."""

    current = _active.get()
    if current is None:
        return BenchmarkRecorder(enabled=False)
    return current


@dataclass
class BenchmarkRecorder:
    """Accumulate stage timings and memory samples without mutating assessment."""

    enabled: bool = False
    stages_ms: dict[str, float] = field(default_factory=dict)
    stage_order: list[str] = field(default_factory=list)
    memory_samples_mb: list[float] = field(default_factory=list)
    meta: dict[str, object] = field(default_factory=dict)
    _starts: dict[str, float] = field(default_factory=dict)
    _token: contextvars.Token[BenchmarkRecorder | None] | None = field(default=None, repr=False)

    @classmethod
    def create(cls, *, enabled: bool) -> BenchmarkRecorder:
        return cls(enabled=enabled)

    def activate(self) -> None:
        self._token = _active.set(self)

    def deactivate(self) -> None:
        if self._token is not None:
            _active.reset(self._token)
            self._token = None

    def start(self, name: str) -> None:
        if not self.enabled:
            return
        self._starts[name] = perf_counter()

    def stop(self, name: str) -> float:
        if not self.enabled:
            return 0.0
        started = self._starts.pop(name, None)
        if started is None:
            return 0.0
        elapsed = round((perf_counter() - started) * 1000, 2)
        if name not in self.stages_ms:
            self.stage_order.append(name)
        self.stages_ms[name] = round(self.stages_ms.get(name, 0.0) + elapsed, 2)
        self.sample_memory()
        return elapsed

    def record(self, name: str, duration_ms: float | None) -> None:
        if not self.enabled or duration_ms is None:
            return
        value = round(max(0.0, float(duration_ms)), 2)
        if name not in self.stages_ms:
            self.stage_order.append(name)
        self.stages_ms[name] = round(self.stages_ms.get(name, 0.0) + value, 2)

    def sample_memory(self) -> float | None:
        if not self.enabled:
            return None
        value = peak_rss_mb()
        if value is not None:
            self.memory_samples_mb.append(value)
        return value

    def set_meta(self, key: str, value: object) -> None:
        if not self.enabled:
            return
        self.meta[key] = value

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        self.start(name)
        try:
            yield
        finally:
            self.stop(name)

    def cpu_time_ms(self) -> float | None:
        if not self.enabled:
            return None
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
        except (AttributeError, ValueError, OSError):
            return None
        return round((float(usage.ru_utime) + float(usage.ru_stime)) * 1000.0, 2)

    def peak_rss(self) -> float | None:
        if self.memory_samples_mb:
            return round(max(self.memory_samples_mb), 2)
        return peak_rss_mb() if self.enabled else None

    def average_rss(self) -> float | None:
        if not self.memory_samples_mb:
            return None
        return round(sum(self.memory_samples_mb) / len(self.memory_samples_mb), 2)
