"""G40-D005: missing artifact schemas and unbound roots are rejected."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.knowledge.artifact_evidence import (
    LocalArtifactEvidenceService,
)
from codestrata.application.knowledge.queries.errors import (
    ArtifactPathSecurityError,
    UnknownArtifactVersionError,
)
from codestrata.interfaces.mcp.tools.artifact_queries import default_evidence_service


def test_findings_without_schema_version_are_rejected() -> None:
    service = LocalArtifactEvidenceService(allowed_root=Path("."))
    with pytest.raises(UnknownArtifactVersionError):
        service.validate_artifact_version({"findings": [{"id": "x"}]})


def test_unbound_service_rejects_a_directory(tmp_path: Path) -> None:
    service = LocalArtifactEvidenceService()
    with pytest.raises(ArtifactPathSecurityError, match="authorized root"):
        service.validate_scope(tmp_path)


def test_default_tool_service_uses_the_authorized_root(tmp_path: Path) -> None:
    service = default_evidence_service(str(tmp_path))
    assert service.validate_scope(tmp_path) == tmp_path.resolve()
    outside = tmp_path.parent
    if outside != tmp_path.resolve():
        with pytest.raises(ArtifactPathSecurityError):
            service.validate_scope(outside)
