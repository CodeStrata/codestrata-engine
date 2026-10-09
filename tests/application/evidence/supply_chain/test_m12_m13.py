"""M12/M13 fixtures: lock resolution, OSV matching, envelope (E06.2)."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codestrata.application.evidence.supply_chain.consumer import (
    ConsumerContractError,
    consume_envelope,
)
from codestrata.application.evidence.supply_chain.coverage import coverage_not_above_one
from codestrata.application.evidence.supply_chain.feed import load_osv_snapshot
from codestrata.application.evidence.supply_chain.models import MatchingStatus, MetricStatusName
from codestrata.application.evidence.supply_chain.projections import (
    project_supply_chain_html,
    project_supply_chain_json,
    project_supply_chain_sarif,
)
from codestrata.application.evidence.supply_chain.service import SupplyChainEvidenceService
from codestrata.application.rules.security.rules import KnownVulnerabilityRule
from codestrata.application.rules.security.yaml_catalog import (
    KNOWN_VULNERABILITY_RULE_ID,
    catalog_digests,
    load_known_vulnerability_rule,
)
from codestrata.domain.contracts.formulas import m12_resolution_coverage
from codestrata.domain.rules.context import (
    LanguageInventoryView,
    RepositoryFactView,
    RuleExecutionContext,
)
from codestrata.domain.rules.enums import RuleResultStatus

EVAL = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
FRESH_FEED_TIME = "2026-09-12T00:00:00Z"
STALE_FEED_TIME = "2026-08-01T00:00:00Z"


def _service() -> SupplyChainEvidenceService:
    return SupplyChainEvidenceService()


def _run(
    paths: tuple[str, ...],
    texts: dict[str, str],
    *,
    snapshot: dict[str, object] | None = None,
    snapshot_path: Path | None = None,
    evaluation_time: datetime = EVAL,
    git_repo: str | None = None,
):
    return _service().collect(
        repository_id="fixture",
        relative_paths=paths,
        file_texts=texts,
        evaluation_time=evaluation_time,
        snapshot_payload=snapshot,
        snapshot_path=snapshot_path,
        catalog_digest=catalog_digests()[KNOWN_VULNERABILITY_RULE_ID],
        assessed_git_repo=git_repo,
    )


def _npm_lock(packages: dict[str, dict[str, str]]) -> str:
    import json

    payload = {"lockfileVersion": 2, "packages": {"": {}, **packages}}
    return json.dumps(payload)


def _advisory(
    *,
    advisory_id: str,
    aliases: list[str],
    ecosystem: str,
    name: str,
    introduced: str = "0",
    fixed: str | None = "2.0.0",
    withdrawn: str | None = None,
    severity: str | None = "HIGH",
    versions: list[str] | None = None,
    extra_ranges: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    events: list[dict[str, str]] = [{"introduced": introduced}]
    if fixed:
        events.append({"fixed": fixed})
    ranges: list[dict[str, object]] = [{"type": "ECOSYSTEM", "events": events}]
    if extra_ranges:
        ranges.extend(extra_ranges)
    record: dict[str, object] = {
        "id": advisory_id,
        "aliases": aliases,
        "affected": [
            {
                "package": {"ecosystem": ecosystem, "name": name},
                "ranges": ranges,
                "versions": versions or [],
            }
        ],
    }
    if withdrawn:
        record["withdrawn"] = withdrawn
    if severity:
        record["database_specific"] = {"severity": severity}
    return record


def _snapshot(
    advisories: list[dict[str, object]],
    *,
    published: str = FRESH_FEED_TIME,
) -> dict[str, object]:
    return {
        "provider_id": "osv.dev",
        "published_at": published,
        "updated_at": published,
        "license": "CC-BY-4.0",
        "advisories": advisories,
    }


def test_m12_formula_fixtures_match_ratification() -> None:
    partial = m12_resolution_coverage(("d1", "d2", "d3", "d4"), ("d1", "d2", "d3"))
    assert partial.status.value == "value"
    assert partial.serialized == "0.750000"
    none = m12_resolution_coverage(("d1", "d2", "d3", "d4"), ())
    assert none.serialized == "0.000000"
    zero = m12_resolution_coverage((), ())
    assert zero.status.value == "not_applicable"
    unknown = m12_resolution_coverage(None, ("d1",))
    assert unknown.status.value == "unknown"
    assert unknown.reason == "unknown_denominator"


def test_pinned_vs_wildcard_and_missing_lock() -> None:
    package_json = """
    {
      "dependencies": {
        "leftpad": "1.2.3",
        "debug": "*"
      }
    }
    """
    evidence, _ = _run(("package.json",), {"package.json": package_json})
    scope = evidence.scopes[0]
    assert scope.status is MetricStatusName.VALUE
    assert scope.denominator == 2
    assert scope.numerator == 0
    assert scope.missing_resolution is True
    lock = _npm_lock(
        {
            "node_modules/leftpad": {"version": "1.2.3"},
            "node_modules/debug": {"version": "4.3.4"},
        }
    )
    resolved, _ = _run(
        ("package.json", "package-lock.json"),
        {"package.json": package_json, "package-lock.json": lock},
    )
    scope = resolved.scopes[0]
    assert scope.numerator == 2
    assert scope.denominator == 2
    assert scope.serialized == "1.000000"


def test_duplicate_conflict_and_lock_mismatch() -> None:
    package_json = """
    {
      "dependencies": { "leftpad": "1.0.0" },
      "devDependencies": { "leftpad": "2.0.0" }
    }
    """
    lock = _npm_lock({"node_modules/leftpad": {"version": "9.9.9"}})
    evidence, _ = _run(
        ("package.json", "package-lock.json"),
        {"package.json": package_json, "package-lock.json": lock},
    )
    assert evidence.hygiene.conflicting >= 1
    versions = {item.resolved_version for item in evidence.occurrences if item.declaration_id}
    assert "9.9.9" in versions


def test_transitive_and_one_declaration_two_versions_do_not_inflate() -> None:
    package_json = '{"dependencies": {"leftpad": "^1.0.0"}}'
    lock = _npm_lock(
        {
            "node_modules/leftpad": {"version": "1.0.0"},
            "node_modules/leftpad/node_modules/leftpad": {"version": "1.2.0"},
            "node_modules/debug": {"version": "4.0.0"},
        }
    )
    evidence, envelope = _run(
        ("package.json", "package-lock.json"),
        {"package.json": package_json, "package-lock.json": lock},
    )
    scope = evidence.scopes[0]
    assert scope.denominator == 1
    assert scope.numerator == 0  # two exact versions => not complete
    assert scope.occurrence_count >= 2
    assert scope.transitive_count >= 1
    assert coverage_not_above_one(scope)
    m12 = next(
        item
        for item in envelope.body.coverage
        if item.capability_id.endswith("m12.resolution_hygiene")
    )
    assert m12.eligible == 1
    assert m12.evaluated == 0


def test_partial_contexts_zero_and_unknown_denominator() -> None:
    files = {
        "app/package.json": '{"dependencies": {"leftpad": "1.0.0"}}',
        "app/package-lock.json": _npm_lock({"node_modules/leftpad": {"version": "1.0.0"}}),
        "lib/package.json": '{"dependencies": {"debug": "1.0.0"}}',
    }
    evidence, _ = _run(tuple(files), files)
    by_manifest = {item.manifest_path: item for item in evidence.scopes}
    assert by_manifest["app/package.json"].numerator == 1
    assert by_manifest["lib/package.json"].numerator == 0
    assert by_manifest["lib/package.json"].missing_resolution is True
    empty, _ = _run((), {})
    assert empty.scopes[0].status is MetricStatusName.NOT_APPLICABLE
    unknown, _ = _run(("Cargo.toml",), {"Cargo.toml": "[package]\nname='x'\n"})
    assert any(item.status is MetricStatusName.UNKNOWN for item in unknown.scopes)


def test_unknown_version_scheme_is_not_exact() -> None:
    package_json = '{"dependencies": {"foo": "1.0.0"}}'
    lock = _npm_lock({"node_modules/foo": {"version": "git+https://example.invalid/foo.git"}})
    evidence, _ = _run(
        ("package.json", "package-lock.json"),
        {"package.json": package_json, "package-lock.json": lock},
    )
    assert evidence.scopes[0].numerator == 0
    assert evidence.unknown_version_packages


def test_affected_unaffected_withdrawn_alias_and_prerelease() -> None:
    package_json = '{"dependencies": {"demo": "1.5.0", "other": "2.5.0", "pre": "1.0.0-rc.1"}}'
    lock = _npm_lock(
        {
            "node_modules/demo": {"version": "1.5.0"},
            "node_modules/other": {"version": "2.5.0"},
            "node_modules/pre": {"version": "1.0.0-rc.1"},
        }
    )
    snapshot = _snapshot(
        [
            _advisory(
                advisory_id="GHSA-aaaa",
                aliases=["CVE-2024-1"],
                ecosystem="npm",
                name="demo",
                introduced="1.0.0",
                fixed="2.0.0",
            ),
            _advisory(
                advisory_id="CVE-2024-1",
                aliases=["GHSA-aaaa"],
                ecosystem="npm",
                name="demo",
                introduced="1.0.0",
                fixed="2.0.0",
            ),
            _advisory(
                advisory_id="GHSA-withdrawn",
                aliases=["CVE-2024-9"],
                ecosystem="npm",
                name="demo",
                withdrawn="2024-01-01T00:00:00Z",
            ),
            _advisory(
                advisory_id="GHSA-pre",
                aliases=[],
                ecosystem="npm",
                name="pre",
                introduced="1.0.0",
                fixed="2.0.0",
            ),
        ]
    )
    evidence, envelope = _run(
        ("package.json", "package-lock.json"),
        {"package.json": package_json, "package-lock.json": lock},
        snapshot=snapshot,
    )
    packages = {item.package_name for item in evidence.matches}
    assert "demo" in packages
    assert "other" not in packages
    assert "pre" not in packages  # prerelease boundary
    assert all(item.advisory_id != "GHSA-withdrawn" for item in evidence.matches)
    groups = {item.alias_group for item in evidence.matches if item.package_name == "demo"}
    assert len(groups) == 1
    assert evidence.matching.status is MatchingStatus.COMPLETE
    assert evidence.matching.match_count == 1
    consume_envelope(envelope.model_dump(mode="json"))
    html = project_supply_chain_html(envelope)
    assert "GHSA-aaaa" in html
    assert "health_verdict: none" in html
    json_proj = project_supply_chain_json(envelope)
    assert json_proj["live_lookup"] is False
    sarif = project_supply_chain_sarif(envelope)
    assert sarif["runs"][0]["results"][0]["properties"]["alias_group"]


def test_stale_and_missing_feed_never_report_zero_cves() -> None:
    package_json = '{"dependencies": {"demo": "1.5.0"}}'
    lock = _npm_lock({"node_modules/demo": {"version": "1.5.0"}})
    files = {"package.json": package_json, "package-lock.json": lock}
    missing, envelope = _run(("package.json", "package-lock.json"), files, snapshot=None)
    assert missing.matching.status is MatchingStatus.UNKNOWN
    assert missing.matching.match_count is None
    assert missing.matching.cannot_prove_clean is True
    consume_envelope(envelope.model_dump(mode="json"))
    stale_snapshot = _snapshot(
        [
            _advisory(
                advisory_id="GHSA-stale",
                aliases=[],
                ecosystem="npm",
                name="demo",
                introduced="0",
                fixed="9.0.0",
            )
        ],
        published=STALE_FEED_TIME,
    )
    stale, stale_env = _run(("package.json", "package-lock.json"), files, snapshot=stale_snapshot)
    assert stale.freshness.status.value == "stale"
    assert stale.matching.status is MatchingStatus.UNKNOWN
    assert stale.matching.match_count == 1
    assert stale.matches[0].qualified is True
    consume_envelope(stale_env.model_dump(mode="json"))
    empty_stale = _snapshot([], published=STALE_FEED_TIME)
    empty, empty_env = _run(("package.json", "package-lock.json"), files, snapshot=empty_stale)
    assert empty.matching.match_count is None
    consume_envelope(empty_env.model_dump(mode="json"))


def test_same_code_new_advisory_increases_distinct_matches() -> None:
    package_json = '{"dependencies": {"demo": "1.5.0"}}'
    lock = _npm_lock({"node_modules/demo": {"version": "1.5.0"}})
    files = {"package.json": package_json, "package-lock.json": lock}
    first = _snapshot(
        [
            _advisory(
                advisory_id="GHSA-old",
                aliases=["CVE-1"],
                ecosystem="npm",
                name="demo",
                introduced="0",
                fixed="2.0.0",
            )
        ]
    )
    second = _snapshot(
        [
            _advisory(
                advisory_id="GHSA-old",
                aliases=["CVE-1"],
                ecosystem="npm",
                name="demo",
                introduced="0",
                fixed="2.0.0",
            ),
            _advisory(
                advisory_id="GHSA-new",
                aliases=["CVE-2"],
                ecosystem="npm",
                name="demo",
                introduced="0",
                fixed="2.0.0",
            ),
        ]
    )
    old, _ = _run(("package.json", "package-lock.json"), files, snapshot=first)
    new, _ = _run(("package.json", "package-lock.json"), files, snapshot=second)
    assert old.matching.match_count == 1
    assert new.matching.match_count == 2


def test_yaml_rule_unknown_is_not_clean_and_matches_use_feed_severity() -> None:
    package_json = '{"dependencies": {"demo": "1.5.0"}}'
    lock = _npm_lock({"node_modules/demo": {"version": "1.5.0"}})
    snapshot = _snapshot(
        [
            _advisory(
                advisory_id="GHSA-sev",
                aliases=[],
                ecosystem="npm",
                name="demo",
                introduced="0",
                fixed="9.0.0",
                severity="CRITICAL",
            )
        ]
    )
    evidence, _ = _run(
        ("package.json", "package-lock.json"),
        {"package.json": package_json, "package-lock.json": lock},
        snapshot=snapshot,
    )
    rule = KnownVulnerabilityRule()
    context = RuleExecutionContext(
        repository=RepositoryFactView(repository_id="fixture"),
        languages=LanguageInventoryView(languages=("javascript",)),
        assessment_graph=evidence,
    )
    assert rule.evaluate_applicability(context).is_applicable
    result = rule.evaluate(context)
    assert result.status is RuleResultStatus.MATCHED
    assert result.matches[0].severity.value == "critical"
    assert "osv_feed_deterministic" in result.matches[0].severity_basis
    missing, _ = _run(
        ("package.json", "package-lock.json"),
        {"package.json": package_json, "package-lock.json": lock},
        snapshot=None,
    )
    unknown = rule.evaluate(
        RuleExecutionContext(
            repository=RepositoryFactView(repository_id="fixture"),
            languages=LanguageInventoryView(languages=("javascript",)),
            assessment_graph=missing,
        )
    )
    assert unknown.status is RuleResultStatus.NOT_APPLICABLE


def test_python_lock_paths_and_no_network_in_feed_module() -> None:
    pyproject = """
[project]
name = "demo"
version = "0.1.0"
dependencies = ["requests==2.31.0"]
"""
    poetry = """
[[package]]
name = "requests"
version = "2.31.0"

[[package]]
name = "urllib3"
version = "2.2.0"
"""
    snapshot = _snapshot(
        [
            _advisory(
                advisory_id="PYSEC-1",
                aliases=["CVE-2023-1"],
                ecosystem="PyPI",
                name="requests",
                introduced="0",
                fixed="2.32.0",
            )
        ]
    )
    evidence, _ = _run(
        ("pyproject.toml", "poetry.lock"),
        {"pyproject.toml": pyproject, "poetry.lock": poetry},
        snapshot=snapshot,
    )
    assert evidence.scopes[0].numerator == 1
    assert any(
        item.package_name == "urllib3" and not item.direct for item in evidence.occurrences
    ) or any(item.package_name == "urllib3" for item in evidence.occurrences)
    assert any(item.package_name == "requests" for item in evidence.matches)
    source = Path(inspect.getfile(load_osv_snapshot)).read_text(encoding="utf-8")
    assert "import urllib" not in source
    assert "from urllib" not in source
    assert "import requests" not in source
    assert "from requests" not in source
    assert "http.client" not in source
    assert "urlopen" not in source


def test_catalog_and_consumer_reject_health_and_zero_on_unknown() -> None:
    loaded = load_known_vulnerability_rule()
    assert loaded["rule_id"] == KNOWN_VULNERABILITY_RULE_ID
    assert loaded["measurement"] == "M13"
    digests = catalog_digests()
    assert KNOWN_VULNERABILITY_RULE_ID in digests
    with pytest.raises(ConsumerContractError):
        consume_envelope(
            {"schema_name": "nope", "schema_version": "1", "body": {}, "body_digest": "x"}
        )


def test_deterministic_repeat() -> None:
    package_json = '{"dependencies": {"leftpad": "1.0.0"}}'
    lock = _npm_lock({"node_modules/leftpad": {"version": "1.0.0"}})
    files = {"package.json": package_json, "package-lock.json": lock}
    snapshot = _snapshot([])
    first, env1 = _run(("package.json", "package-lock.json"), files, snapshot=snapshot)
    second, env2 = _run(("package.json", "package-lock.json"), files, snapshot=snapshot)
    third, env3 = _run(("package.json", "package-lock.json"), files, snapshot=snapshot)
    assert env1.body_digest == env2.body_digest == env3.body_digest
    assert first.matching.match_count == 0
    assert first.matching.status is MatchingStatus.COMPLETE
    assert "zero_matches_is_not_secure" in env1.body.limitations


def test_git_range_only_when_repo_matches_and_missing_severity_is_visible() -> None:
    package_json = '{"dependencies": {"demo": "1.5.0"}}'
    lock = _npm_lock({"node_modules/demo": {"version": "1.5.0"}})
    git_advisory = _advisory(
        advisory_id="GHSA-git",
        aliases=[],
        ecosystem="npm",
        name="demo",
        extra_ranges=[{"type": "GIT", "repo": "https://example.invalid/demo.git", "events": []}],
        severity=None,
    )
    git_advisory["affected"][0]["ranges"] = [
        {
            "type": "GIT",
            "repo": "https://example.invalid/demo.git",
            "events": [{"introduced": "abc"}],
        }
    ]
    unmatched, _ = _run(
        ("package.json", "package-lock.json"),
        {"package.json": package_json, "package-lock.json": lock},
        snapshot=_snapshot([git_advisory]),
        git_repo="https://other.invalid/demo.git",
    )
    assert unmatched.matching.match_count == 0
    missing_sev = _advisory(
        advisory_id="GHSA-nosev",
        aliases=[],
        ecosystem="npm",
        name="demo",
        introduced="0",
        fixed="9.0.0",
        severity=None,
    )
    evidence, _ = _run(
        ("package.json", "package-lock.json"),
        {"package.json": package_json, "package-lock.json": lock},
        snapshot=_snapshot([missing_sev]),
    )
    assert evidence.matches[0].feed_severity == "unknown"
    assert "feed_severity_unknown" in evidence.matches[0].severity_basis
