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
    read_installation_id,
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

# Imported for product facade typing / singleton; not used for active legacy emit.
from codestrata.telemetry.disabled_service import DisabledTelemetryFacade


class TelemetryService:
    """LEGACY Phase 14.3 telemetry coordinator (compatibility / explicit tests only).

    Not constructed by default product execution (Slice 9.2). Normal CLI and
    assessment paths use ``DisabledTelemetryFacade`` via ``get_telemetry_service``.
    Prefer ``get_legacy_telemetry_service`` or direct construction for focused
    legacy tests and the ``codestrata telemetry`` preference commands.
    """

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
        # Read-only: do not generate an installation ID on status inspection.
        try:
            installation_id = read_installation_id(path=self._id_path()) or "unavailable"
        except OSError:
            installation_id = "unavailable"
        prefs = load_preferences(path=self._prefs_path())
        return {
            "enabled": self.is_enabled(),
            "decision_made": bool(prefs.get("decision_made")),
            "disabled_by_default": True,
            "force_disabled_by_env": self.force_disabled_by_env(),
            "installation_id": installation_id,
            "legacy_service": True,
            "runtime_not_activated_by_legacy_consent": True,
            "schema_version": prefs.get("schema_version"),
            "endpoint_configured": configured_endpoint() is not None,
            "queue_depth": queue_depth(path=self._queue_path()),
            "local_counters": dict(prefs.get("local_counters") or {}),
            "codestrata_version": get_package_version(),
            "last_codestrata_version": prefs.get("last_codestrata_version"),
        }

    def enable(self, *, emit_events: bool = True) -> dict[str, Any]:
        installation_id, created = self.ensure_identity()
        prefs = mark_decision(True, path=self._prefs_path())
        if created or not prefs.get("installation_created_at"):
            prefs["installation_created_at"] = prefs.get("decision_at")
            save_preferences(prefs, path=self._prefs_path())
        if emit_events:
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

    def disable(self, *, emit_events: bool = True) -> dict[str, Any]:
        was_enabled = self.is_enabled()
        if emit_events:
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


_PRODUCT: DisabledTelemetryFacade | None = None
_LEGACY: TelemetryService | None = None
# Backward-compatible alias used by older tests that reset the singleton.
_SERVICE: TelemetryService | None = None
_PROMPT_ATTEMPTED: bool = False
_LAST_PROMPT_RESULT: object | None = None


def get_telemetry_service(*, home: Path | None = None) -> DisabledTelemetryFacade:
    """Product telemetry entry — process facade (default disabled until interactive).

    ``home`` is ignored: product execution must not bind to a legacy home or
    construct an active ``TelemetryService``. Use ``get_legacy_telemetry_service``
    for explicit legacy preference commands and tests.

    Eligible interactive commands should call
    ``ensure_interactive_product_telemetry`` once before recording events.
    """

    global _PRODUCT
    _ = home
    if _PRODUCT is None:
        from codestrata.telemetry.enforcement import create_enforced_product_telemetry

        _PRODUCT = create_enforced_product_telemetry()
    return _PRODUCT


def ensure_interactive_product_telemetry(
    *,
    command: str,
    quiet: bool = False,
    json_output: bool = False,
    input_func: Any = None,
    echo_func: Any = None,
    stdin_interactive: bool | None = None,
    automation_detected: bool | None = None,
    output_interactive: bool | None = None,
    telemetry_allow: bool = False,
    telemetry_deny: bool = False,
    explicit_consent: Any = None,
    transport: Any = None,
) -> DisabledTelemetryFacade:
    """Ensure process telemetry, prompting at most once for eligible commands.

    CLI flag conflicts raise ``CliTelemetryConsentConflict`` (not fail-silent).
    Other telemetry failures become denial/default. Explicit Yes/No may be
    persisted locally under ``CODESTRATA_HOME``.
    Interactive tests must pass ``automation_detected=False`` explicitly.

    ``transport`` is an optional injection seam (tests / explicit callers).
    Normal CLI construction does not pass it. Unauthorized consent keeps
    ``UnavailableTelemetryTransport``. Authorized consent resolves production
    Community HTTP transport when ``CODESTRATA_COMMUNITY_CLIENT_CREDENTIAL`` is set.
    """

    global _PRODUCT, _PROMPT_ATTEMPTED, _LAST_PROMPT_RESULT
    if _PRODUCT is not None and _PROMPT_ATTEMPTED:
        return _PRODUCT
    if _PRODUCT is not None and _PRODUCT.runtime.session.consent.explicit:
        _PROMPT_ATTEMPTED = True
        return _PRODUCT

    # Flag conflict is a CLI configuration error — raise before fail-silent wrap.
    cli_selection = None
    if telemetry_allow or telemetry_deny:
        from codestrata.telemetry.cli_consent import select_cli_telemetry_consent

        cli_selection = select_cli_telemetry_consent(
            allow=telemetry_allow,
            deny=telemetry_deny,
        )

    try:
        from codestrata.telemetry.prompt_runtime_factory import (
            create_interactive_session_telemetry,
        )

        facade, prompt_result = create_interactive_session_telemetry(
            command=command,
            quiet=quiet,
            json_output=json_output,
            decision_already_explicit=(
                _PRODUCT is not None and _PRODUCT.runtime.session.consent.explicit
            ),
            prompt_already_attempted=_PROMPT_ATTEMPTED,
            transport=transport,
            input_func=input_func,
            echo_func=echo_func,
            stdin_interactive=stdin_interactive,
            automation_detected=automation_detected,
            output_interactive=output_interactive,
            explicit_consent=explicit_consent,
            cli_selection=cli_selection,
        )
        # Suppression is not a prompt attempt; mark attempted only when prompted
        # or when a definitive session decision was established for this command.
        if prompt_result.prompted or prompt_result.attempts > 0:
            _PROMPT_ATTEMPTED = True
        else:
            # Still lock the process facade so later hooks do not re-evaluate
            # into a prompt mid-command.
            _PROMPT_ATTEMPTED = True
        _LAST_PROMPT_RESULT = prompt_result
        _PRODUCT = facade
        return _PRODUCT
    except Exception:  # noqa: BLE001 - telemetry must never break CLI
        from codestrata.telemetry.enforcement import create_enforced_product_telemetry

        _PROMPT_ATTEMPTED = True
        if _PRODUCT is None:
            _PRODUCT = create_enforced_product_telemetry()
        return _PRODUCT


def get_last_interactive_prompt_result() -> object | None:
    """Return the last prompt result for diagnostics/tests (may be None)."""

    return _LAST_PROMPT_RESULT


def get_legacy_telemetry_service(*, home: Path | None = None) -> TelemetryService:
    """Explicit legacy TelemetryService for CLI preference commands and tests."""

    global _LEGACY, _SERVICE
    if home is not None:
        return TelemetryService(home=home)
    if _LEGACY is None:
        _LEGACY = TelemetryService()
        _SERVICE = _LEGACY
    return _LEGACY


def reset_telemetry_singletons() -> None:
    """Reset product and legacy singletons (tests only)."""

    global _PRODUCT, _LEGACY, _SERVICE, _PROMPT_ATTEMPTED, _LAST_PROMPT_RESULT
    _PRODUCT = None
    _LEGACY = None
    _SERVICE = None
    _PROMPT_ATTEMPTED = False
    _LAST_PROMPT_RESULT = None


__all__ = [
    "TelemetryService",
    "ensure_interactive_product_telemetry",
    "get_last_interactive_prompt_result",
    "get_legacy_telemetry_service",
    "get_telemetry_service",
    "reset_telemetry_singletons",
]
