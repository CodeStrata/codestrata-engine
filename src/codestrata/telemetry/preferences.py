"""Local telemetry preferences (opt-in; disabled by default).

Slice 20.9 additive fields:
  consent_scope: 1 | 2 | null  (null + enabled + decision_made ⇒ legacy V1_YES)
  v2_upgrade_declined: bool    (suppress repeated v2-upgrade prompts)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codestrata.telemetry.constants import SCHEMA_VERSION
from codestrata.telemetry.paths import ensure_home, preferences_path


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_preferences() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": False,
        "decision_made": False,
        "decision_at": None,
        "consent_scope": None,
        "v2_upgrade_declined": False,
        "installation_created_at": None,
        "installation_event_sent": False,
        "last_codestrata_version": None,
        "local_counters": {},
    }


def load_preferences(*, path: Path | None = None) -> dict[str, Any]:
    target = path or preferences_path()
    if not target.is_file():
        return default_preferences()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_preferences()
    if not isinstance(data, dict):
        return default_preferences()
    merged = default_preferences()
    for key in merged:
        if key in data:
            merged[key] = data[key]
    if not isinstance(merged.get("local_counters"), dict):
        merged["local_counters"] = {}
    merged["enabled"] = bool(merged.get("enabled"))
    merged["decision_made"] = bool(merged.get("decision_made"))
    merged["installation_event_sent"] = bool(merged.get("installation_event_sent"))
    merged["v2_upgrade_declined"] = bool(merged.get("v2_upgrade_declined"))
    # Preserve raw consent_scope for capability resolver (may be invalid).
    if "consent_scope" not in data:
        merged["consent_scope"] = None
    else:
        merged["consent_scope"] = data.get("consent_scope")
    return merged


def save_preferences(data: dict[str, Any], *, path: Path | None = None) -> Path:
    ensure_home()
    target = path or preferences_path()
    payload = default_preferences()
    payload.update(data)
    payload["schema_version"] = SCHEMA_VERSION
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def mark_decision(
    enabled: bool,
    *,
    path: Path | None = None,
    consent_scope: int | None = None,
    v2_upgrade_declined: bool | None = None,
) -> dict[str, Any]:
    """Persist an explicit consent decision.

    When enabling without an explicit scope, defaults to consent_scope=2 (v2).
    Legacy V1 fixtures omit consent_scope on disk; callers that need V1 must pass
    ``consent_scope=1`` or write the file without the field before load.
    """

    prefs = load_preferences(path=path)
    prefs["enabled"] = bool(enabled)
    prefs["decision_made"] = True
    prefs["decision_at"] = _now()
    if enabled:
        prefs["consent_scope"] = 2 if consent_scope is None else int(consent_scope)
    else:
        # Disable retains prior scope for diagnostics but capabilities ignore it.
        if consent_scope is not None:
            prefs["consent_scope"] = int(consent_scope)
    if v2_upgrade_declined is not None:
        prefs["v2_upgrade_declined"] = bool(v2_upgrade_declined)
    save_preferences(prefs, path=path)
    return prefs


def mark_v2_upgrade_declined(*, path: Path | None = None) -> dict[str, Any]:
    """Keep V1_YES and suppress future interactive v2-upgrade prompts."""

    prefs = load_preferences(path=path)
    prefs["v2_upgrade_declined"] = True
    # Ensure legacy V1 shape: enabled + decision_made, scope 1 or absent.
    if prefs.get("consent_scope") == 2:
        prefs["consent_scope"] = 1
    save_preferences(prefs, path=path)
    return prefs


def bump_counter(name: str, *, path: Path | None = None, amount: int = 1) -> None:
    prefs = load_preferences(path=path)
    counters = dict(prefs.get("local_counters") or {})
    counters[name] = int(counters.get(name) or 0) + amount
    prefs["local_counters"] = counters
    save_preferences(prefs, path=path)


def reset_preferences(*, path: Path | None = None) -> dict[str, Any]:
    prefs = default_preferences()
    save_preferences(prefs, path=path)
    return prefs
