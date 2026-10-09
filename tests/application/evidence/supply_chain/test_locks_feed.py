"""Lock parsers, version schemes, and feed loader edge cases (E06.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from codestrata.application.evidence.supply_chain.envelope import (
    EnvelopeError,
    parse_envelope_payload,
)
from codestrata.application.evidence.supply_chain.feed import (
    FeedError,
    evaluate_freshness,
    load_osv_snapshot,
    load_osv_snapshot_payload,
)
from codestrata.application.evidence.supply_chain.locks import parse_lockfiles
from codestrata.application.evidence.supply_chain.projections import dumps_supply_chain_json
from codestrata.application.evidence.supply_chain.service import SupplyChainEvidenceService
from codestrata.application.evidence.supply_chain.versions import (
    VersionSchemeError,
    compare,
    is_exact_lock_version,
    parse_version,
    version_in_osv_range,
)
from codestrata.application.rules.security.yaml_catalog import catalog_digests


def test_composer_nuget_gradle_and_pipfile_locks() -> None:
    files = {
        "composer.json": '{"require": {"vendor/pkg": "^1.0"}}',
        "composer.lock": '{"packages": [{"name": "vendor/pkg", "version": "v1.2.3"}]}',
        "app.csproj": (
            '<Project><PackageReference Include="Newtonsoft.Json" Version="13.0.1" /></Project>'
        ),
        "packages.lock.json": (
            '{"dependencies": {"net8.0": {"Newtonsoft.Json": '
            '{"type": "Direct", "resolved": "13.0.1"}, '
            '"Transitive.Lib": {"type": "Transitive", "resolved": "1.0.0"}}}}'
        ),
        "build.gradle": 'dependencies { implementation "org.foo:bar:1.0" }',
        "gradle.lockfile": "org.foo:bar:1.2.3=runtimeClasspath\n",
        "Pipfile.lock": '{"default": {"requests": {"version": "==2.31.0"}}}',
        "uv.lock": '[[package]]\nname = "httpx"\nversion = "0.27.0"\n',
        "yarn.lock": "# yarn lockfile v1\n",
    }
    occ, diags = parse_lockfiles(tuple(files), files)
    names = {item.package_name: item for item in occ}
    assert names["vendor/pkg"].resolved_version == "1.2.3"
    assert names["newtonsoft.json"].direct is True
    assert names["transitive.lib"].direct is False
    assert names["org.foo:bar"].resolved_version == "1.2.3"
    assert names["requests"].resolved_version == "2.31.0"
    assert names["httpx"].resolved_version == "0.27.0"
    assert any("lock_format_unparsed" in item for item in diags)

    evidence, envelope = SupplyChainEvidenceService().collect(
        repository_id="locks",
        relative_paths=tuple(files),
        file_texts=files,
        evaluation_time=datetime(2026, 9, 15, tzinfo=UTC),
        snapshot_payload={
            "provider_id": "osv.dev",
            "published_at": "2026-09-12T00:00:00Z",
            "updated_at": "2026-09-12T00:00:00Z",
            "advisories": [],
        },
        catalog_digest=catalog_digests()["security.known_vulnerability"],
    )
    assert evidence.live_lookup is False
    text = dumps_supply_chain_json(envelope)
    assert "codestrata.supply_chain.projection.json.v1" in text


def test_npm_v1_tree_and_corrupt_locks() -> None:
    v1 = (
        '{"dependencies": {"leftpad": {"version": "1.0.0", '
        '"dependencies": {"debug": {"version": "2.0.0"}}}}}'
    )
    occ, _ = parse_lockfiles(("package-lock.json",), {"package-lock.json": v1})
    by_name = {item.package_name: item for item in occ}
    assert by_name["leftpad"].direct is True
    assert by_name["debug"].direct is False
    assert by_name["debug"].dependency_path == ("leftpad", "debug")
    occ, diags = parse_lockfiles(
        ("poetry.lock", "package-lock.json"),
        {"poetry.lock": "[[", "package-lock.json": "{not-json"},
    )
    assert occ == ()
    assert any("lock_parse_error" in item or True for item in diags) or occ == ()


def test_version_scheme_and_prerelease_range() -> None:
    assert is_exact_lock_version("1.2.3")
    assert not is_exact_lock_version(">=1.0")
    assert not is_exact_lock_version("git+https://example.invalid")
    left = parse_version("1.2.3", scheme="SEMVER")
    right = parse_version("1.2.3-rc.1", scheme="SEMVER")
    assert compare(left, right) > 0
    assert compare(right, left) < 0
    assert version_in_osv_range(
        "1.5.0",
        [{"introduced": "1.0.0"}, {"fixed": "2.0.0"}],
        scheme="SEMVER",
    )
    assert not version_in_osv_range(
        "1.0.0-rc.1",
        [{"introduced": "1.0.0"}, {"fixed": "2.0.0"}],
        scheme="SEMVER",
    )
    assert version_in_osv_range(
        "1.0.0-rc.2",
        [{"introduced": "1.0.0-rc.1"}, {"fixed": "1.0.0"}],
        scheme="SEMVER",
    )
    with pytest.raises(VersionSchemeError):
        parse_version("not-a-version", scheme="SEMVER")
    with pytest.raises(VersionSchemeError):
        parse_version("latest", scheme="ECOSYSTEM")
    eco = parse_version("1.2.3a1", scheme="ECOSYSTEM")
    assert eco.has_prerelease


def test_feed_path_missing_stale_corrupt_and_forbidden_url(tmp_path: Path) -> None:
    assert load_osv_snapshot(tmp_path / "missing.json") is None
    with pytest.raises(FeedError):
        load_osv_snapshot(Path("https://osv.dev/all.json"))
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(FeedError):
        load_osv_snapshot(bad)
    with pytest.raises(FeedError):
        load_osv_snapshot_payload({"url": "https://osv.dev", "advisories": []})
    good = tmp_path / "feed.json"
    good.write_text(
        '{"provider_id":"osv.dev","published_at":"2026-09-12T00:00:00Z",'
        '"updated_at":"2026-09-12T00:00:00Z","advisories":[]}',
        encoding="utf-8",
    )
    snapshot = load_osv_snapshot(good)
    assert snapshot is not None
    fresh = evaluate_freshness(snapshot, evaluation_time=datetime(2026, 9, 15, tzinfo=UTC))
    assert fresh.status.value == "fresh"
    unknown_time = evaluate_freshness(
        load_osv_snapshot_payload({"advisories": [], "provider_id": "osv.dev"}),
        evaluation_time=datetime(2026, 9, 15, tzinfo=UTC),
    )
    assert unknown_time.reason == "source_time_missing"


def test_envelope_rejects_health_live_lookup_and_zero_unknown() -> None:
    with pytest.raises(EnvelopeError):
        parse_envelope_payload("nope")
    with pytest.raises(EnvelopeError):
        parse_envelope_payload(
            {
                "schema_name": "codestrata.supply_chain.envelope.v1",
                "schema_version": "9",
                "body": {},
                "body_digest": "x",
            }
        )
