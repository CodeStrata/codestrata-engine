"""Runtime analytics collection and projection tests (Epic 10 Slice 10.3)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from codestrata.telemetry.analytics.errors import AnalyticsError, AnalyticsErrorCode
from codestrata.telemetry.analytics.events import AnalyticsCategory
from codestrata.telemetry.analytics.installation_identity import (
    AnonymousInstallationIdentity,
    new_anonymous_installation_identity,
)
from codestrata.telemetry.analytics.runtime_analytics import (
    COMMUNITY_RUNTIME_ANALYTICS_POLICY_URN,
    CommunityRuntimeAnalyticsPolicy,
    RuntimeAnalyticsEvent,
    RuntimeAnalyticsPolicyError,
    classify_architecture,
    classify_os_family,
    classify_release_adoption,
    collect_runtime_analytics,
    default_runtime_analytics_policy,
)
from codestrata.telemetry.analytics.runtime_analytics_compatibility import (
    RuntimeAnalyticsCompatibilityError,
    assert_runtime_analytics_schema_compatible,
    compatible_runtime_analytics_schema_versions,
)
from codestrata.telemetry.analytics.runtime_analytics_diagnostics import (
    empty_runtime_analytics_diagnostics,
    runtime_analytics_diagnostics_for_event,
)
from codestrata.telemetry.analytics.runtime_analytics_projection import (
    project_runtime_analytics_event,
    project_runtime_analytics_to_analytics_event,
)
from codestrata.telemetry.analytics.runtime_analytics_serialization import (
    runtime_analytics_event_to_stable_json,
    runtime_analytics_policy_to_stable_json,
)
from codestrata.telemetry.analytics.runtime_analytics_validation import (
    validate_runtime_analytics_event,
    validate_runtime_analytics_mapping,
)


def _fixed_identity() -> AnonymousInstallationIdentity:
    return AnonymousInstallationIdentity(
        installation_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    )


def _sample_event(**overrides: object) -> RuntimeAnalyticsEvent:
    base = {
        "installation_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        "cli_version": "0.2.0",
        "os_family": "macos",
        "architecture": "arm64",
        "runtime_version": "3.12",
        "release_adoption": "0.2",
        "privacy_projection_applied": True,
    }
    base.update(overrides)
    return RuntimeAnalyticsEvent(**base)  # type: ignore[arg-type]


def test_collect_runtime_analytics_local_only(tmp_path: Path) -> None:
    home = tmp_path / "home"
    event = collect_runtime_analytics(
        home=home,
        cli_version="0.2.0",
        os_family="linux",
        architecture="x86_64",
        runtime_version="3.12",
    )
    assert event.category == "runtime"
    assert event.cli_version == "0.2.0"
    assert event.os_family == "linux"
    assert event.architecture == "x86_64"
    assert event.runtime_version == "3.12"
    assert event.release_adoption == "0.2"
    assert event.privacy_projection_applied is True
    # Only identity file may be persisted — no analytics payload file.
    names = {path.name for path in home.iterdir()}
    assert names == {"anonymous-installation-identity.json"}


def test_collect_reuses_installation_identity(tmp_path: Path) -> None:
    home = tmp_path / "home"
    first = collect_runtime_analytics(
        home=home,
        cli_version="0.2.0",
        os_family="linux",
        architecture="x86_64",
        runtime_version="3.11",
    )
    second = collect_runtime_analytics(
        home=home,
        cli_version="0.2.0",
        os_family="linux",
        architecture="x86_64",
        runtime_version="3.11",
    )
    assert first.installation_id == second.installation_id


def test_collect_uses_provided_identity(tmp_path: Path) -> None:
    identity = _fixed_identity()
    event = collect_runtime_analytics(
        home=tmp_path / "home",
        identity=identity,
        cli_version="0.2.1",
        os_family="windows",
        architecture="x86_64",
        runtime_version="3.10",
    )
    assert event.installation_id == identity.installation_id
    assert not (tmp_path / "home" / "anonymous-installation-identity.json").exists()


def test_produces_analytics_event_without_installation_id() -> None:
    event = _sample_event()
    analytics = project_runtime_analytics_to_analytics_event(event)
    assert analytics.category is AnalyticsCategory.RUNTIME
    payload = analytics.to_intake_dict()
    assert "installation_id" not in payload
    assert payload["cli_version"] == "0.2.0"
    assert payload["architecture"] == "arm64"
    assert payload["runtime_version"] == "3.12"
    assert payload["release_adoption"] == "0.2"


def test_projection_includes_installation_id() -> None:
    projected = project_runtime_analytics_event(_sample_event())
    assert projected.installation_id == "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    assert projected.fields["category"] == "runtime"


def test_privacy_required() -> None:
    event = _sample_event(privacy_projection_applied=False)
    with pytest.raises(AnalyticsError) as exc:
        project_runtime_analytics_event(event)
    assert exc.value.code is AnalyticsErrorCode.PRIVACY_REQUIRED


def test_validation_and_determinism() -> None:
    event = _sample_event()
    a = validate_runtime_analytics_event(event)
    b = validate_runtime_analytics_event(event)
    assert a.to_stable_dict() == b.to_stable_dict()
    assert runtime_analytics_event_to_stable_json(event) == (
        runtime_analytics_event_to_stable_json(event)
    )
    parsed = json.loads(runtime_analytics_event_to_stable_json(event))
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_policy_invariants() -> None:
    policy = default_runtime_analytics_policy()
    assert policy.transmission_enabled is False
    assert policy.persistence_enabled is False
    assert policy.installation_id_required is True
    assert COMMUNITY_RUNTIME_ANALYTICS_POLICY_URN.endswith(":1.0")
    assert runtime_analytics_policy_to_stable_json(policy) == (
        runtime_analytics_policy_to_stable_json(CommunityRuntimeAnalyticsPolicy.default())
    )
    with pytest.raises(RuntimeAnalyticsPolicyError):
        CommunityRuntimeAnalyticsPolicy(transmission_enabled=True)


def test_compatibility() -> None:
    assert compatible_runtime_analytics_schema_versions() == frozenset({"1.0"})
    assert_runtime_analytics_schema_compatible("1.0")
    with pytest.raises(RuntimeAnalyticsCompatibilityError):
        assert_runtime_analytics_schema_compatible("2.0")


def test_unsupported_schema_on_event() -> None:
    event = _sample_event(schema_version="9.9")
    with pytest.raises(AnalyticsError) as exc:
        validate_runtime_analytics_event(event)
    assert exc.value.code is AnalyticsErrorCode.INCOMPATIBLE_SCHEMA


def test_classifiers() -> None:
    assert classify_os_family("Darwin") == "macos"
    assert classify_os_family("Linux") == "linux"
    assert classify_architecture("aarch64") == "arm64"
    assert classify_architecture("AMD64") == "x86_64"
    assert classify_release_adoption("0.2.0") == "0.2"


def test_diagnostics_never_include_identifier() -> None:
    event = _sample_event()
    diag = runtime_analytics_diagnostics_for_event(
        installation_id_present=True,
        privacy_projection_applied=True,
        projected=True,
        validated=True,
        rejected=False,
        limitation_codes=default_runtime_analytics_policy().limitations,
    )
    blob = diag.to_stable_json()
    assert event.installation_id not in blob
    assert "installation_id" not in diag.to_stable_dict()
    empty = empty_runtime_analytics_diagnostics()
    assert empty.transmission_enabled is False
    assert list(empty.to_stable_dict().keys()) == sorted(empty.to_stable_dict().keys())


def test_mapping_validation() -> None:
    projected = validate_runtime_analytics_mapping(_sample_event().to_stable_dict())
    assert projected.fields["os_family"] == "macos"


def test_does_not_invoke_transport(tmp_path: Path) -> None:
    with patch("codestrata.telemetry.transport.send_payload") as send:
        collect_runtime_analytics(
            home=tmp_path / "home",
            identity=new_anonymous_installation_identity(),
            cli_version="0.2.0",
            os_family="linux",
            architecture="x86_64",
            runtime_version="3.12",
        )
        send.assert_not_called()


def test_product_path_still_does_not_auto_collect(tmp_path: Path, monkeypatch) -> None:
    from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    get_telemetry_service().record_report_opened()
    assert list(home.iterdir()) == []
