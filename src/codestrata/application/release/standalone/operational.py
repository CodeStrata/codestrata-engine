"""Headless operational limits, health file protocol, retention and audit."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from codestrata.application.release.standalone.models import (
    LocalHealthStatus,
    OperationalAuditEvent,
)
from codestrata.application.release.standalone.policy import (
    budgets_from_packaged_limits,
    headless_runtime_limits_digest,
    load_headless_runtime_limits,
    operational_profile_id,
)
from codestrata.domain.contracts.catalog import load_launch_ratification
from codestrata.domain.contracts.invocation import HeadlessInvocation
from codestrata.domain.contracts.serialization import (
    digest_canonical,
    walk_forbidden_credentials,
    walk_forbidden_identity,
)

_PR_TEXT = re.compile(r"(?i)(pull request|merge request|#\d{2,}|lorem ipsum)")


class HeadlessOperationalBinding(BaseModel):
    """Binds packaged measured limits to a parsed headless invocation envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_name: str = "codestrata.headless-operational-binding.v1"
    schema_version: str = "1.0.0"
    operational_limits_profile_id: str
    operational_limits_digest: str
    invocation_digest: str
    budgets_digest: str

    @model_validator(mode="after")
    def digest_matches_profile(self) -> HeadlessOperationalBinding:
        if self.operational_limits_profile_id != operational_profile_id():
            raise ValueError("operational_limits_profile_id mismatch")
        if self.operational_limits_digest != headless_runtime_limits_digest():
            raise ValueError("operational_limits_digest mismatch")
        return self


def bind_headless_operational_limits(invocation: HeadlessInvocation) -> HeadlessOperationalBinding:
    packaged = budgets_from_packaged_limits()
    ratified = load_launch_ratification().budgets
    if packaged.model_dump(mode="json") != ratified.model_dump(mode="json"):
        raise ValueError("packaged runtime budgets diverge from launch ratification")
    invocation_payload = invocation.model_dump(mode="json")
    walk_forbidden_identity(invocation_payload)
    walk_forbidden_credentials(invocation_payload)
    return HeadlessOperationalBinding(
        operational_limits_profile_id=operational_profile_id(),
        operational_limits_digest=headless_runtime_limits_digest(),
        invocation_digest=digest_canonical(invocation_payload),
        budgets_digest=digest_canonical(packaged.model_dump(mode="json")),
    )


def health_status_path(base: Path) -> Path:
    limits = load_headless_runtime_limits()
    health = limits.get("health_status")
    if not isinstance(health, dict):
        raise ValueError("health_status missing from runtime limits")
    filename = str(health.get("relative_filename") or "codestrata-local-health.json")
    return base / filename


def write_local_health_status(base: Path, status: LocalHealthStatus) -> Path:
    path = health_status_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(status.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def read_local_health_status(base: Path) -> LocalHealthStatus:
    payload = json.loads(health_status_path(base).read_text(encoding="utf-8"))
    return LocalHealthStatus.model_validate(payload)


class BoundedOperationalAudit:
    """Append-only audit log with size bounds and redaction."""

    def __init__(
        self,
        *,
        max_events: int | None = None,
        max_event_bytes: int | None = None,
    ) -> None:
        limits = load_headless_runtime_limits().get("audit")
        configured_events = 256
        configured_bytes = 4096
        if isinstance(limits, dict):
            configured_events = int(limits.get("max_events") or configured_events)
            configured_bytes = int(limits.get("max_event_bytes") or configured_bytes)
        self._max_events = configured_events if max_events is None else max_events
        self._max_event_bytes = configured_bytes if max_event_bytes is None else max_event_bytes
        self._events: list[OperationalAuditEvent] = []

    @property
    def events(self) -> tuple[OperationalAuditEvent, ...]:
        return tuple(self._events)

    def append(self, *, event_id: str, kind: str, message: str) -> None:
        redacted = _redact_operational_message(message)
        if len(redacted.encode("utf-8")) > self._max_event_bytes:
            redacted = redacted.encode("utf-8")[: self._max_event_bytes].decode(
                "utf-8",
                errors="replace",
            )
        if len(self._events) >= self._max_events:
            self._events.pop(0)
        self._events.append(
            OperationalAuditEvent(event_id=event_id, kind=kind, message=redacted),
        )


def _redact_operational_message(message: str) -> str:
    lowered = message.lower()
    if "api_key=" in lowered or "password=" in lowered or "secret" in lowered:
        return "redacted:credential_marker"
    if _PR_TEXT.search(message):
        return "redacted:pr_narrative"
    return message


def retention_config() -> dict[str, Any]:
    limits = load_headless_runtime_limits()
    retention = limits.get("retention")
    if not isinstance(retention, dict):
        raise ValueError("retention missing from runtime limits")
    return dict(retention)
