"""MVP end-to-end acceptance harness (Phase 5.13).

Orchestrates existing onboard → validate → ask → MCP health → determinism.
Does not add assessment rules, AI capabilities, or retrieval algorithms.
"""

from codestrata.application.acceptance.models import (
    AcceptanceCheckResult,
    AcceptanceHarnessResult,
    RepositoryAcceptanceResult,
)
from codestrata.application.acceptance.service import (
    MvpAcceptanceService,
    run_mvp_acceptance,
)
from codestrata.application.acceptance.summary import (
    load_acceptance_summary,
    write_acceptance_summaries,
)

__all__ = [
    "AcceptanceCheckResult",
    "AcceptanceHarnessResult",
    "MvpAcceptanceService",
    "RepositoryAcceptanceResult",
    "load_acceptance_summary",
    "run_mvp_acceptance",
    "write_acceptance_summaries",
]
