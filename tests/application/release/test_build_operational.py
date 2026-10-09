"""E14.2 operational limits, health protocol and audit redaction."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestrata.application.release.standalone.models import LocalHealthStatus
from codestrata.application.release.standalone.operational import (
    BoundedOperationalAudit,
    bind_headless_operational_limits,
    read_local_health_status,
    retention_config,
    write_local_health_status,
)
from codestrata.domain.contracts.examples_e01_3 import example_invocation


def test_bind_headless_operational_limits_matches_ratification() -> None:
    binding = bind_headless_operational_limits(example_invocation())
    assert binding.operational_limits_profile_id == "codestrata.release.headless-runtime.v1"
    assert len(binding.operational_limits_digest) == 64
    assert len(binding.invocation_digest) == 64
    assert len(binding.budgets_digest) == 64


def test_local_health_status_file_protocol(tmp_path: Path) -> None:
    status = LocalHealthStatus(ok=True, phase="ready")
    path = write_local_health_status(tmp_path, status)
    assert path.name == "codestrata-local-health.json"
    loaded = read_local_health_status(tmp_path)
    assert loaded.ok is True
    assert loaded.database is False
    assert loaded.http_service is False


def test_bounded_audit_redacts_secrets_and_pr_text() -> None:
    audit = BoundedOperationalAudit(max_events=8, max_event_bytes=256)
    audit.append(event_id="1", kind="start", message="ok")
    audit.append(
        event_id="2",
        kind="credential",
        message="api_key=super-secret-value",
    )
    audit.append(
        event_id="3",
        kind="context",
        message="Pull request #12345 changed everything",
    )
    messages = {event.message for event in audit.events}
    assert "redacted:credential_marker" in messages
    assert "redacted:pr_narrative" in messages

    bounded = BoundedOperationalAudit(max_events=2, max_event_bytes=256)
    bounded.append(event_id="a", kind="start", message="one")
    bounded.append(event_id="b", kind="start", message="two")
    bounded.append(event_id="c", kind="start", message="three")
    assert len(bounded.events) == 2
    assert bounded.events[-1].message == "three"


def test_retention_config_preserves_active_baseline() -> None:
    config = retention_config()
    assert config.get("preserve_active_baseline") is True


def test_read_only_source_fixture_fails_write(tmp_path: Path) -> None:
    target = tmp_path / "readonly.txt"
    target.write_text("x", encoding="utf-8")
    if hasattr(Path, "chmod"):
        target.chmod(0o444)
        with pytest.raises(PermissionError):
            target.write_text("y", encoding="utf-8")
        target.chmod(0o644)
