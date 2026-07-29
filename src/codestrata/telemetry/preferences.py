"""Local telemetry preferences (opt-in; disabled by default)."""

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


def mark_decision(enabled: bool, *, path: Path | None = None) -> dict[str, Any]:
    prefs = load_preferences(path=path)
    prefs["enabled"] = bool(enabled)
    prefs["decision_made"] = True
    prefs["decision_at"] = _now()
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
