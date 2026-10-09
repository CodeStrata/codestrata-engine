"""Engine-only scope and compatibility guard (E00.2).

Public entry: ``evaluate_scope`` (git path check) and
``collect_consumer_imports`` (read-only Platform/extension import scan).
"""

from __future__ import annotations

from verification.engine_scope.consumer_imports import (
    ConsumerImport,
    collect_consumer_imports,
    summarize_imports,
)
from verification.engine_scope.guard import classify_changes, evaluate_scope
from verification.engine_scope.inventory import (
    dump_inventory,
    load_inventory,
    write_inventory,
)
from verification.engine_scope.models import PathChange, ScopeReport, ScopeViolation
from verification.engine_scope.paths import is_engine_owned

__all__ = [
    "ConsumerImport",
    "PathChange",
    "ScopeReport",
    "ScopeViolation",
    "classify_changes",
    "collect_consumer_imports",
    "dump_inventory",
    "evaluate_scope",
    "is_engine_owned",
    "load_inventory",
    "summarize_imports",
    "write_inventory",
]
