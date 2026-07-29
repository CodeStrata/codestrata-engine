"""Runtime performance helpers (Phase 5.19).

Distinct from Performance Intelligence (``application/performance``), which is a
product assessment dimension. This package measures and optimizes platform
runtime without changing assessment semantics.
"""

from codestrata.application.runtime_performance.file_text_cache import (
    FileTextLoadStats,
    load_shared_source_texts,
)
from codestrata.application.runtime_performance.metrics import (
    PhaseTimer,
    peak_rss_mb,
)

__all__ = [
    "FileTextLoadStats",
    "PhaseTimer",
    "load_shared_source_texts",
    "peak_rss_mb",
]
