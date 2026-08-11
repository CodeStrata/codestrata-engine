"""Anonymous installation identity privacy and boundary tests (Slice 10.2)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from codestrata.telemetry.analytics.installation_identity import (
    ensure_anonymous_installation_identity,
    generate_anonymous_installation_id,
    new_anonymous_installation_identity,
)
from codestrata.telemetry.analytics.installation_identity_policy import (
    default_installation_identity_policy,
)
from codestrata.telemetry.analytics.installation_identity_serialization import (
    identity_to_stable_json,
)
from codestrata.telemetry.analytics.policy import default_analytics_policy
from codestrata.telemetry import identity as legacy_identity


_FORBIDDEN_RECORD_KEYS = frozenset(
    {
        "username",
        "email",
        "hostname",
        "host",
        "ip",
        "ip_address",
        "repository",
        "repository_name",
        "project",
        "project_name",
        "path",
        "customer_id",
        "organization_id",
        "org_id",
        "source_code",
        "findings",
        "evidence",
        "credentials",
        "secret",
        "mac",
        "mac_address",
        "serial",
        "machine_id",
        "os_username",
    }
)


def test_identity_record_only_allows_approved_keys() -> None:
    record = new_anonymous_installation_identity()
    keys = set(record.to_stable_dict().keys())
    assert keys == {
        "installation_id",
        "policy_version",
        "schema_id",
        "schema_version",
    }
    assert keys.isdisjoint(_FORBIDDEN_RECORD_KEYS)


def test_persisted_file_has_no_forbidden_keys(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ensure_anonymous_installation_identity(home=home)
    payload = json.loads(
        (home / "anonymous-installation-identity.json").read_text(encoding="utf-8")
    )
    assert set(payload.keys()).isdisjoint(_FORBIDDEN_RECORD_KEYS)


def test_generation_source_has_no_machine_fingerprint_apis() -> None:
    source = inspect.getsource(generate_anonymous_installation_id)
    for token in (
        "gethostname",
        "getuser",
        "getnode",
        "uuid1(",
        "platform.",
        "socket.",
        "os.environ",
        "Path.home",
        "mac_address",
        "machine_id",
    ):
        assert token not in source


def test_identity_independent_from_analytics_event_allowance() -> None:
    analytics = default_analytics_policy()
    identity = default_installation_identity_policy()
    assert analytics.installation_id_allowed is False
    assert analytics.collection_enabled is False
    assert identity.transmission_allowed is False
    assert identity.local_persistence_allowed is True


def test_stable_json_does_not_embed_paths_or_hostnames(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USER", "alice-secret-user")
    monkeypatch.setenv("HOSTNAME", "corp-laptop.example.invalid")
    record = new_anonymous_installation_identity()
    blob = identity_to_stable_json(record)
    assert "alice-secret-user" not in blob
    assert "corp-laptop" not in blob
    assert str(tmp_path) not in blob


def test_does_not_call_legacy_identity_module(tmp_path: Path, monkeypatch) -> None:
    called = {"ensure": False}

    def _boom(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        called["ensure"] = True
        raise AssertionError("legacy identity must not be used")

    monkeypatch.setattr(legacy_identity, "ensure_installation_id", _boom)
    ensure_anonymous_installation_identity(home=tmp_path / "home")
    assert called["ensure"] is False


def test_product_telemetry_still_does_not_create_anonymous_identity_file(
    tmp_path: Path, monkeypatch
) -> None:
    from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    get_telemetry_service().record_report_opened()
    assert not (home / "anonymous-installation-identity.json").exists()
    assert list(home.iterdir()) == []
