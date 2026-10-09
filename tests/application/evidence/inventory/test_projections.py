"""E05.3 capability manifests, envelope, projections and consumer contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestrata.application.evidence.inventory.capability import (
    CAPABILITY_MANIFEST_SCHEMA,
    capability_manifests,
)
from codestrata.application.evidence.inventory.consumer import (
    ConsumerContractError,
    consume_envelope,
    consume_envelope_text,
    consume_html_projection,
    consume_json_projection,
    consume_sarif_projection,
    project_and_consume,
)
from codestrata.application.evidence.inventory.emission import InventoryFactEmitter
from codestrata.application.evidence.inventory.envelope import (
    EnvelopeError,
    InventoryOperationalMetadata,
    parse_envelope_payload,
    seal_inventory_envelope,
)
from codestrata.application.evidence.inventory.facts import CAP_M01, CAP_M02, CAP_M03, CAP_M04
from codestrata.application.evidence.inventory.fixture_map import (
    E053_FIXTURE_MATRIX,
    INVENTORY_FIXTURE_MAP,
)
from codestrata.application.evidence.inventory.models import ResolutionObservation
from codestrata.application.evidence.inventory.projections import (
    dumps_inventory_json,
    project_inventory_html,
    project_inventory_json,
    project_inventory_sarif,
)
from codestrata.application.evidence.inventory.registry import (
    ANALYZER_REQUIRED_FACT_KINDS,
    INVENTORY_ANALYZER_ID,
    register_inventory_facts,
)

FIXTURES = Path(__file__).parent / "fixtures"
_BY_ID = {item.fixture_id: item for item in INVENTORY_FIXTURE_MAP}

_CASES = (
    "valid",
    "absent",
    "partial",
    "unsupported",
    "corrupt",
    "deterministic",
)


def _emit_named(name: str, *, key: str = "demo"):
    return InventoryFactEmitter().emit_tree(FIXTURES / name, repository_key=key)


def _resolve_directory(directory: str, tmp_path: Path) -> Path:
    if directory == "m04_corrupt_source":
        source = tmp_path / "src"
        source.mkdir()
        (source / "broken.py").write_text("def broken(\n    return\n", encoding="utf-8")
        return tmp_path
    path = FIXTURES / directory
    if path.is_dir():
        return path
    if directory in {"empty_repo", "unreadable_subtree", "symlink_escape"}:
        return tmp_path
    raise AssertionError(f"missing fixture directory {directory}")


def _seal_tree(root: Path, *, key: str = "demo"):
    bundle = InventoryFactEmitter().emit_tree(root, repository_key=key)
    return seal_inventory_envelope(bundle)


def test_capability_manifests_cover_m01_to_m04_without_health_or_yaml() -> None:
    manifests = capability_manifests()
    ids = [item.capability_id for item in manifests]
    assert ids == [CAP_M01, CAP_M02, CAP_M03, CAP_M04]
    for item in manifests:
        assert item.schema_name == CAPABILITY_MANIFEST_SCHEMA
        assert item.family.value == "inventory"
        assert item.outcome.value == "context"
        assert item.health_verdict is False
        assert item.yaml_rule is False
        assert item.network.value == "none"
        assert item.direction.value == "neutral"
        assert item.freshness == "not_applicable"


def test_e053_matrix_covers_required_cases() -> None:
    for measurement, cases in E053_FIXTURE_MATRIX.items():
        assert set(cases) == set(_CASES)
        for fixture_id in cases.values():
            assert _BY_ID[fixture_id].measurement in {measurement, "M01"}


@pytest.mark.parametrize("measurement", ("M01", "M02", "M03", "M04"))
@pytest.mark.parametrize("case", _CASES)
def test_m01_m04_envelope_projections_cover_matrix(
    measurement: str, case: str, tmp_path: Path
) -> None:
    fixture_id = E053_FIXTURE_MATRIX[measurement][case]
    spec = _BY_ID[fixture_id]
    root = _resolve_directory(spec.directory, tmp_path)
    envelope = _seal_tree(root, key=f"{measurement}-{case}")
    json_payload, html, sarif = project_and_consume(envelope)
    assert json_payload["health_verdict"] == "none"
    assert json_payload["descriptive_only"] is True
    assert envelope.body.health_verdict == "none"
    coverage_ids = {item["capability_id"] for item in json_payload["coverage"]}
    assert coverage_ids == {CAP_M01, CAP_M02, CAP_M03, CAP_M04}
    assert "health_verdict: none" in html
    assert len(sarif["runs"][0]["results"]) == 4
    if case == "deterministic":
        second = _seal_tree(root, key=f"{measurement}-{case}")
        third = _seal_tree(root, key=f"{measurement}-{case}")
        assert envelope.body_digest == second.body_digest == third.body_digest
        assert envelope.canonical_body() == second.canonical_body() == third.canonical_body()


def test_empty_repo_coverage_is_not_applicable_in_projections(tmp_path: Path) -> None:
    envelope = _seal_tree(tmp_path, key="empty")
    payload = consume_json_projection(project_inventory_json(envelope))
    m01 = next(item for item in payload["coverage"] if item["capability_id"] == CAP_M01)
    assert m01["coverage_ratio"] is None
    assert m01["coverage_reason"] == "zero_eligible_files"
    assert m01["applicability"] == "not_applicable"


def test_npm_missing_lock_is_unknown_not_zero_in_json_projection() -> None:
    envelope = _seal_tree(FIXTURES / "npm_missing_lock")
    payload = consume_json_projection(project_inventory_json(envelope))
    facts = envelope.body.registered_facts.facts_of("inventory.declaration")
    assert facts
    assert all(item.attributes["resolution"] == "unknown" for item in facts)
    m02 = next(item for item in payload["coverage"] if item["capability_id"] == CAP_M02)
    assert m02["unknown"] >= 1
    assert m02["eligible"] >= 1


def test_go_manifest_is_unknown_depth_not_zero_dependencies() -> None:
    bundle = _emit_named("m02_unsupported_go")
    envelope = seal_inventory_envelope(bundle)
    m02 = next(item for item in envelope.body.coverage if item.capability_id == CAP_M02)
    assert m02.coverage_ratio is None
    assert m02.coverage_reason == "unsupported_manifest_unknown_depth"
    payload = consume_json_projection(project_inventory_json(envelope))
    assert payload["health_verdict"] == "none"


def test_yarn_lock_stays_unparsed_in_envelope() -> None:
    bundle = _emit_named("m02_yarn_unparsed")
    npm = [item for item in bundle.declarations if item.ecosystem == "npm"]
    assert npm
    assert all(item.resolution is ResolutionObservation.UNKNOWN for item in npm)
    assert not bundle.resolutions


def test_corrupt_manifest_and_source_are_visible(tmp_path: Path) -> None:
    corrupt_npm = _emit_named("m02_corrupt_manifest")
    index = register_inventory_facts(corrupt_npm)
    assert index.facts_of("inventory.coverage")
    source = tmp_path / "src"
    source.mkdir()
    (source / "broken.py").write_text("def broken(\n    return\n", encoding="utf-8")
    corrupt_py = InventoryFactEmitter().emit_tree(tmp_path, repository_key="demo")
    assert any(item.declaration_kind == "parse_failure" for item in corrupt_py.surfaces)


def test_operational_metadata_is_excluded_from_body_digest() -> None:
    bundle = _emit_named("ci_direct_command")
    first = seal_inventory_envelope(
        bundle, operational=InventoryOperationalMetadata(run_id="a", generated_at="t1")
    )
    second = seal_inventory_envelope(
        bundle, operational=InventoryOperationalMetadata(run_id="b", generated_at="t2")
    )
    assert first.body_digest == second.body_digest
    assert first.canonical_body() == second.canonical_body()
    dumped = json.dumps(first.model_dump(mode="json"))
    assert "tenant" not in dumped
    assert "workspace" not in dumped
    assert "portfolio" not in dumped


def test_corrupt_and_wrong_schema_envelopes_are_rejected() -> None:
    with pytest.raises(ConsumerContractError, match="corrupt"):
        consume_envelope_text("{not-json")
    sealed = _seal_tree(FIXTURES / "ci_none")
    payload = sealed.model_dump(mode="json")
    payload["schema_version"] = "2"
    with pytest.raises((ConsumerContractError, EnvelopeError)):
        consume_envelope(payload)
    payload = sealed.model_dump(mode="json")
    payload["unexpected"] = True
    with pytest.raises((ConsumerContractError, EnvelopeError)):
        consume_envelope(payload)
    payload = sealed.model_dump(mode="json")
    payload["body_digest"] = "0" * 64
    with pytest.raises((ConsumerContractError, EnvelopeError)):
        consume_envelope(payload)
    payload = sealed.model_dump(mode="json")
    payload["body"]["health_verdict"] = "healthy"
    with pytest.raises((ConsumerContractError, EnvelopeError)):
        consume_envelope(payload)


def test_consumer_rejects_invented_health_score_in_projections() -> None:
    envelope = _seal_tree(FIXTURES / "mixed_language")
    json_payload = project_inventory_json(envelope)
    json_payload["health_score"] = 97
    with pytest.raises(ConsumerContractError, match="health"):
        consume_json_projection(json_payload)
    html = project_inventory_html(envelope).replace("health_verdict: none", "healthy")
    with pytest.raises(ConsumerContractError):
        consume_html_projection(html)
    sarif = project_inventory_sarif(envelope)
    sarif["runs"][0]["results"][0]["level"] = "error"
    with pytest.raises(ConsumerContractError):
        consume_sarif_projection(sarif)


def test_consumer_module_does_not_import_parsers() -> None:
    import codestrata.application.evidence.inventory.consumer as consumer

    source = Path(consumer.__file__).read_text(encoding="utf-8")
    assert "github_actions_parser" not in source
    assert "inventory.npm" not in source
    assert "inventory.surfaces" not in source
    assert "maven_collector" not in source


def test_enabled_analyzers_see_registered_fact_kinds() -> None:
    envelope = _seal_tree(FIXTURES / "mixed_language")
    enabled = (
        INVENTORY_ANALYZER_ID,
        "architecture",
        "dependency",
        "cicd",
        "repository_metrics",
        "security",
    )
    report = envelope.body.registered_facts.compatible_with(enabled)
    assert report.compatible is True
    assert report.missing_kinds == ()
    present = envelope.body.registered_facts.kinds()
    for analyzer_id in enabled:
        assert ANALYZER_REQUIRED_FACT_KINDS[analyzer_id] <= present


def test_inventory_projection_binds_launch_catalog_digest() -> None:
    envelope = _seal_tree(FIXTURES / "mixed_language")
    from codestrata.application.rules.execution.family_bind import inventory_launch_body
    from codestrata.application.rules.execution.projections import JSON_SCHEMA

    launch = inventory_launch_body(envelope)
    json_payload = project_inventory_json(envelope)
    assert json_payload["launch_projection_schema"] == JSON_SCHEMA
    assert json_payload["launch_catalog_body_digest"] == launch.content_digest()
    assert json_payload["launch_catalog"]["body_digest"] == launch.content_digest()
    assert json_payload["launch_catalog"]["health_verdict"] == "none"
    html = project_inventory_html(envelope)
    assert f"launch_catalog_body_digest: {launch.content_digest()}" in html
    sarif = project_inventory_sarif(envelope)
    assert sarif["runs"][0]["properties"]["launch_catalog_body_digest"] == launch.content_digest()
    project_and_consume(envelope)


def test_json_round_trip_preserves_digest() -> None:
    envelope = _seal_tree(FIXTURES / "maven_declared")
    text = json.dumps(envelope.model_dump(mode="json"), sort_keys=True)
    restored = parse_envelope_payload(json.loads(text))
    assert restored.body_digest == envelope.body_digest
    consume_json_projection(json.loads(dumps_inventory_json(envelope)))
