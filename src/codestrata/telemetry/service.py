"""High-level anonymous telemetry service (opt-in; never blocks assessment)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from codestrata.package_metadata import get_package_version
from codestrata.telemetry.bands import (
    duration_band,
    repository_size_band,
    scan_anonymous_repo_stats,
)
from codestrata.telemetry.constants import (
    FORCE_DISABLE_ENV,
    EventName,
)
from codestrata.telemetry.identity import (
    ensure_installation_id,
    reset_installation_id,
)
from codestrata.telemetry.preferences import (
    bump_counter,
    load_preferences,
    mark_decision,
    reset_preferences,
    save_preferences,
)
from codestrata.telemetry.queue import (
    clear_queue,
    enqueue,
    load_queue,
    queue_depth,
    replace_queue,
)
from codestrata.telemetry.transport import configured_endpoint, send_payload
from codestrata.telemetry.validate import build_event_payload, redact_for_display


class TelemetryService:
    """Privacy-preserving telemetry coordinator."""

    def __init__(self, *, home: Path | None = None) -> None:
        self._home = home

    def _prefs_path(self) -> Path | None:
        if self._home is None:
            return None
        return self._home / "telemetry.json"

    def _id_path(self) -> Path | None:
        if self._home is None:
            return None
        return self._home / "installation_id"

    def _queue_path(self) -> Path | None:
        if self._home is None:
            return None
        return self._home / "telemetry-queue.jsonl"

    def force_disabled_by_env(self) -> bool:
        value = os.environ.get(FORCE_DISABLE_ENV, "").strip().lower()
        if value in {"0", "false", "no", "off"}:
            return True
        return False

    def is_enabled(self) -> bool:
        value = os.environ.get(FORCE_DISABLE_ENV, "").strip().lower()
        if value in {"0", "false", "no", "off"}:
            return False
        if value in {"1", "true", "yes", "on"}:
            return True
        prefs = load_preferences(path=self._prefs_path())
        return bool(prefs.get("enabled")) and bool(prefs.get("decision_made"))

    def decision_made(self) -> bool:
        return bool(load_preferences(path=self._prefs_path()).get("decision_made"))

    def ensure_identity(self) -> tuple[str, bool]:
        return ensure_installation_id(path=self._id_path())

    def status(self) -> dict[str, Any]:
        try:
            installation_id, _ = self.ensure_identity()
        except OSError:
            installation_id = "unavailable"
        prefs = load_preferences(path=self._prefs_path())
        return {
            "enabled": self.is_enabled(),
            "decision_made": bool(prefs.get("decision_made")),
            "disabled_by_default": True,
            "force_disabled_by_env": self.force_disabled_by_env(),
            "installation_id": installation_id,
            "schema_version": prefs.get("schema_version"),
            "endpoint_configured": configured_endpoint() is not None,
            "queue_depth": queue_depth(path=self._queue_path()),
            "local_counters": dict(prefs.get("local_counters") or {}),
            "codestrata_version": get_package_version(),
            "last_codestrata_version": prefs.get("last_codestrata_version"),
        }

    def enable(self) -> dict[str, Any]:
        installation_id, created = self.ensure_identity()
        prefs = mark_decision(True, path=self._prefs_path())
        if created or not prefs.get("installation_created_at"):
            prefs["installation_created_at"] = prefs.get("decision_at")
            save_preferences(prefs, path=self._prefs_path())
        self.emit(
            EventName.TELEMETRY_ENABLED,
            command="telemetry enable",
        )
        if not prefs.get("installation_event_sent"):
            self.emit(EventName.INSTALLATION_CREATED, command="telemetry enable")
            prefs = load_preferences(path=self._prefs_path())
            prefs["installation_event_sent"] = True
            save_preferences(prefs, path=self._prefs_path())
        self._maybe_upgrade_event()
        self.flush_queue()
        return self.status()

    def disable(self) -> dict[str, Any]:
        was_enabled = self.is_enabled()
        self.ensure_identity()
        if was_enabled:
            # Record disable while still enabled so the event can queue/send.
            self.emit(EventName.TELEMETRY_DISABLED, command="telemetry disable")
        mark_decision(False, path=self._prefs_path())
        return self.status()

    def reset(self) -> dict[str, Any]:
        reset_preferences(path=self._prefs_path())
        clear_queue(path=self._queue_path())
        new_id = reset_installation_id(path=self._id_path())
        prefs = load_preferences(path=self._prefs_path())
        prefs["installation_created_at"] = None
        prefs["installation_event_sent"] = False
        save_preferences(prefs, path=self._prefs_path())
        status = self.status()
        status["installation_id"] = new_id
        return status

    def show_sample_payload(
        self,
        *,
        event: EventName | str = EventName.ASSESSMENT_COMPLETED,
    ) -> dict[str, Any]:
        installation_id, _ = self.ensure_identity()
        payload = build_event_payload(
            installation_id=installation_id,
            event=event,
            command="assess",
            enabled_assessment_domains=["architecture", "security"],
            language_categories=["python"],
            repository_size_band="101-500",
            duration_band="5-30s",
            ai_enabled=False,
            success=True,
            queue_depth=queue_depth(path=self._queue_path()),
        )
        return redact_for_display(payload)

    def emit(
        self,
        event: EventName | str,
        *,
        command: str | None = None,
        enabled_assessment_domains: list[str] | None = None,
        language_categories: list[str] | None = None,
        repository_size_band: str | None = None,
        duration_band: str | None = None,
        ai_enabled: bool | None = None,
        success: bool | None = None,
        previous_version: str | None = None,
        force: bool = False,
    ) -> dict[str, Any] | None:
        """Emit an event when enabled (or ``force``). Never raises."""

        try:
            if not force and not self.is_enabled():
                return None
            installation_id, _ = self.ensure_identity()
            payload = build_event_payload(
                installation_id=installation_id,
                event=event,
                command=command,
                enabled_assessment_domains=enabled_assessment_domains,
                language_categories=language_categories,
                repository_size_band=repository_size_band,
                duration_band=duration_band,
                ai_enabled=ai_enabled,
                success=success,
                previous_version=previous_version,
                queue_depth=queue_depth(path=self._queue_path()),
            )
            bump_counter(str(event), path=self._prefs_path())
            if send_payload(payload):
                return payload
            enqueue(payload, path=self._queue_path())
            return payload
        except Exception:  # noqa: BLE001 - telemetry must never break CLI
            return None

    def flush_queue(self) -> int:
        """Retry queued events. Return count successfully sent."""

        if not self.is_enabled():
            return 0
        items = load_queue(path=self._queue_path())
        if not items:
            return 0
        remaining: list[dict[str, Any]] = []
        sent = 0
        for item in items:
            if send_payload(item):
                sent += 1
            else:
                remaining.append(item)
        replace_queue(remaining, path=self._queue_path())
        return sent

    def record_assessment_started(
        self,
        *,
        ai_enabled: bool,
        domains: list[str] | None = None,
        repo_root: Path | None = None,
    ) -> None:
        size_band = None
        languages = None
        if repo_root is not None and self.is_enabled():
            count, languages = scan_anonymous_repo_stats(repo_root)
            size_band = repository_size_band(count)
        self.emit(
            EventName.ASSESSMENT_STARTED,
            command="assess",
            ai_enabled=ai_enabled,
            enabled_assessment_domains=domains,
            language_categories=languages,
            repository_size_band=size_band,
        )

    def record_assessment_completed(
        self,
        *,
        ai_enabled: bool,
        ai_executed: bool,
        success: bool,
        duration_ms: float | None,
        domains: list[str] | None = None,
        repo_root: Path | None = None,
    ) -> None:
        size_band = None
        languages = None
        if repo_root is not None and self.is_enabled():
            count, languages = scan_anonymous_repo_stats(repo_root)
            size_band = repository_size_band(count)
        event = EventName.ASSESSMENT_COMPLETED if success else EventName.ASSESSMENT_FAILED
        self.emit(
            event,
            command="assess",
            ai_enabled=ai_enabled,
            success=success,
            duration_band=duration_band(duration_ms),
            enabled_assessment_domains=domains,
            language_categories=languages,
            repository_size_band=size_band,
        )
        if success and ai_executed:
            self.emit(
                EventName.AI_USED,
                command="assess",
                ai_enabled=True,
                success=True,
            )

    def record_report_opened(self) -> None:
        self.emit(EventName.REPORT_OPENED, command="open")

    def record_version_check(self) -> None:
        self.emit(EventName.VERSION_CHECK, command="version")

    def _maybe_upgrade_event(self) -> None:
        prefs = load_preferences(path=self._prefs_path())
        current = get_package_version()
        previous = prefs.get("last_codestrata_version")
        if previous and previous != current:
            self.emit(
                EventName.UPGRADE_COMPLETED,
                command="telemetry",
                previous_version=str(previous)[:32],
            )
        prefs["last_codestrata_version"] = current
        save_preferences(prefs, path=self._prefs_path())


_SERVICE: TelemetryService | None = None


def get_telemetry_service(*, home: Path | None = None) -> TelemetryService:
    global _SERVICE
    if home is not None:
        return TelemetryService(home=home)
    if _SERVICE is None:
        _SERVICE = TelemetryService()
    return _SERVICE
