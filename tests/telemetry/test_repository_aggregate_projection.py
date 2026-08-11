"""Repository aggregate collection/projection/privacy/determinism (Slice 10.5)."""

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
from codestrata.telemetry.analytics.repository_aggregate import (
    collect_repository_aggregate_analytics,
)
from codestrata.telemetry.analytics.repository_aggregate_compatibility import (
    RepositoryAggregateAnalyticsCompatibilityError,
    assert_repository_aggregate_schema_compatible,
)
from codestrata.telemetry.analytics.repository_aggregate_extractor import (
    extract_repository_aggregate_input,
)
from codestrata.telemetry.analytics.repository_aggregate_projection import (
    APPROVED_REPOSITORY_AGGREGATE_FIELD_NAMES,
    project_repository_aggregate_to_analytics_event,
)
from codestrata.telemetry.analytics.repository_aggregate_serialization import (
    repository_aggregate_event_to_stable_json,
)
from codestrata.telemetry.analytics.repository_aggregate_validation import (
    validate_repository_aggregate_analytics_event,
)


def _id() -> AnonymousInstallationIdentity:
    return AnonymousInstallationIdentity(
        installation_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    )


def _input(**kwargs):  # type: ignore[no-untyped-def]
    defaults = dict(
        language_label_counts={"python": 2, "java": 1},
        attempted=10,
        completed=8,
        skipped=1,
        failed=1,
    )
    defaults.update(kwargs)
    return extract_repository_aggregate_input(**defaults)


def test_collect_and_base_event_identity_free(tmp_path: Path) -> None:
    event = collect_repository_aggregate_analytics(
        home=tmp_path / "home",
        identity=_id(),
        aggregate_input=_input(),
    )
    assert event.category == "repository_aggregates"
    analytics = project_repository_aggregate_to_analytics_event(event)
    assert analytics.category is AnalyticsCategory.REPOSITORY_AGGREGATES
    payload = analytics.to_intake_dict()
    assert "installation_id" not in payload
    assert payload["language_mix"][0]["language_group"] == "java"
    assert payload["rule_execution_summary"]["attempted"] == 10


def test_determinism_reordered_labels() -> None:
    a = collect_repository_aggregate_analytics(
        identity=_id(),
        aggregate_input=_input(language_label_counts={"java": 1, "python": 2}),
    )
    b = collect_repository_aggregate_analytics(
        identity=_id(),
        aggregate_input=_input(language_label_counts={"python": 2, "java": 1}),
    )
    assert repository_aggregate_event_to_stable_json(a) == (
        repository_aggregate_event_to_stable_json(b)
    )
    parsed = json.loads(repository_aggregate_event_to_stable_json(a))
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_privacy_forbidden_fields() -> None:
    for field in (
        "repository_name",
        "file_path",
        "rule_id",
        "finding_id",
        "source_code",
        "provider",
    ):
        assert field not in APPROVED_REPOSITORY_AGGREGATE_FIELD_NAMES


def test_unknown_schema() -> None:
    with pytest.raises(RepositoryAggregateAnalyticsCompatibilityError):
        assert_repository_aggregate_schema_compatible("2.0")


def test_no_transport(tmp_path: Path) -> None:
    with patch("codestrata.telemetry.transport.send_payload") as send:
        collect_repository_aggregate_analytics(
            home=tmp_path / "home",
            identity=new_anonymous_installation_identity(),
            aggregate_input=_input(),
        )
        send.assert_not_called()


def test_validate_rejects_privacy_required() -> None:
    from dataclasses import replace

    event = collect_repository_aggregate_analytics(
        identity=_id(), aggregate_input=_input()
    )
    bad = replace(event, privacy_projection_applied=False)
    with pytest.raises(AnalyticsError) as exc:
        validate_repository_aggregate_analytics_event(bad)
    assert exc.value.code is AnalyticsErrorCode.PRIVACY_REQUIRED


def test_product_path_unwired(tmp_path: Path, monkeypatch) -> None:
    from codestrata.telemetry.service import get_telemetry_service, reset_telemetry_singletons

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("CODESTRATA_HOME", str(home))
    reset_telemetry_singletons()
    get_telemetry_service().record_report_opened()
    assert list(home.iterdir()) == []


def test_assess_cli_not_wired() -> None:
    import codestrata.cli.assess as assess_mod

    source = Path(assess_mod.__file__).read_text(encoding="utf-8")
    assert "collect_repository_aggregate_analytics" not in source
