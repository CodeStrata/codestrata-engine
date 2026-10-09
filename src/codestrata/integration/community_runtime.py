"""Community Engine surface policy after E02.3.

Canonical Community execution is local YAML assessment against file artifacts.
Hosted Platform ingest, Community Cloud report/EIR publish, portfolio lifecycle,
and customer rule authoring are not Community runtime paths.

Compatibility types such as ``RestPlatformClient`` remain importable for
outside-Engine hosts and tests. Community composition must not construct them.
"""

from __future__ import annotations

HOSTED_SUBMISSION_REMOVED = (
    "Hosted Platform submission is not part of Community Engine execution. "
    "Local assessment artifacts are unchanged."
)
COMMUNITY_CLOUD_PUBLISH_REMOVED = (
    "codestrata report publish is deprecated. Community Engine does not upload "
    "Assessment or Engineering Intelligence reports. Use a local report path "
    "(codestrata report open / codestrata open)."
)
PORTFOLIO_LIFECYCLE_REMOVED = (
    "Portfolio and Engineering Intelligence Report lifecycle is not part of "
    "Community Engine execution. Existing intelligence/ files are left untouched."
)
CUSTOMER_RULE_AUTHORING_REMOVED = (
    "Customer rule authoring is not available through Community CLI or MCP. "
    "codestrata rules and MCP shared-rule tools are read-only inspect surfaces."
)
STRATEGIC_AGENT_REMOVED = (
    "Strategic/enterprise agent paths are not part of Community Engine execution. "
    "Local Agent Framework workflows remain repository-scoped and file-backed."
)
SQLITE_EXPORT_HELP = (
    "Legacy SQLite snapshot export is a maintainer helper, invoked separately as "
    "`python -m codestrata.infrastructure.knowledge_store.sqlite.export`. "
    "Community runtime composition never imports it."
)


class CommunitySurfaceRemoved(RuntimeError):
    """Raised when a removed Community surface is invoked."""

    def __init__(self, message: str, *, surface: str) -> None:
        super().__init__(message)
        self.surface = surface


__all__ = [
    "COMMUNITY_CLOUD_PUBLISH_REMOVED",
    "CUSTOMER_RULE_AUTHORING_REMOVED",
    "CommunitySurfaceRemoved",
    "HOSTED_SUBMISSION_REMOVED",
    "PORTFOLIO_LIFECYCLE_REMOVED",
    "SQLITE_EXPORT_HELP",
    "STRATEGIC_AGENT_REMOVED",
]
