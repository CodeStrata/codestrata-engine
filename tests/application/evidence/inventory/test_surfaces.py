"""M04 API and configuration surface fixtures."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.inventory.emission import InventoryFactEmitter
from codestrata.application.evidence.inventory.facts import CAP_M04, ExtractionStatus
from codestrata.application.evidence.inventory.models import SupportKind

FIXTURES = Path(__file__).parent / "fixtures"


def _emit(name: str):
    return InventoryFactEmitter().emit_tree(FIXTURES / name, repository_key="m04")


def test_supported_literal_routes_are_structural() -> None:
    bundle = _emit("m04_supported_route")
    routes = [item for item in bundle.surfaces if item.declaration_kind == "http_route"]
    values = {item.value for item in routes}
    assert "/hello" in values
    assert "/api/hello" in values
    assert all(item.support is SupportKind.STRUCTURAL for item in routes)
    assert all(item.extraction_status is ExtractionStatus.COMPLETE for item in routes)
    assert all(item.line for item in routes)
    assert all(item.subject_id.startswith("repo:m04:file:") for item in routes)
    m04 = next(item for item in bundle.coverage if item.capability_id == CAP_M04)
    assert m04.evaluated >= 1


def test_no_routes_is_empty_surfaces_not_a_health_score() -> None:
    bundle = _emit("m04_no_routes")
    routes = [item for item in bundle.surfaces if item.declaration_kind == "http_route"]
    assert routes == []
    assert all(item.capability_id != "health" for item in bundle.coverage)


def test_dynamic_route_is_unknown() -> None:
    bundle = _emit("m04_dynamic_route")
    dynamic = [item for item in bundle.surfaces if item.limitation == "dynamic_route"]
    assert dynamic
    assert all(item.extraction_status is ExtractionStatus.UNKNOWN for item in dynamic)
    assert all(item.support is SupportKind.DETECTION_ONLY for item in dynamic)


def test_generated_config_is_detected_only() -> None:
    bundle = _emit("m04_generated_config")
    generated = [item for item in bundle.surfaces if item.declaration_kind == "generated_config"]
    assert generated
    assert generated[0].support is SupportKind.DETECTION_ONLY
    assert generated[0].limitation == "generated_config_not_runtime_surface"


def test_unresolved_framework_is_unknown_area() -> None:
    bundle = _emit("m04_unresolved_framework")
    unknown = [item for item in bundle.surfaces if item.declaration_kind == "unresolved_framework"]
    assert unknown
    assert any(item.value == "django" for item in unknown)
    assert all(item.extraction_status is ExtractionStatus.UNKNOWN for item in unknown)
    assert any("django_unresolved_framework" in note for note in bundle.limitations)


def test_csharp_literal_route_and_express_dynamic(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "Api.cs").write_text(
        '[HttpGet("/items")]\nclass Api {}\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "server.js").write_text(
        'const path = "/x";\napp.get(path, handler);\napp.get("/ok", handler);\n',
        encoding="utf-8",
    )
    bundle = InventoryFactEmitter().emit_tree(tmp_path, repository_key="m04")
    values = {item.value for item in bundle.surfaces if item.declaration_kind == "http_route"}
    assert "/items" in values
    assert "/ok" in values
    dynamic = [
        item
        for item in bundle.surfaces
        if item.limitation == "dynamic_route" and item.relative_path.endswith("server.js")
    ]
    assert dynamic


def test_parse_failure_is_bounded_to_the_file(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "broken.py").write_text("def broken(\n    return\n", encoding="utf-8")
    bundle = InventoryFactEmitter().emit_tree(tmp_path, repository_key="m04")
    failed = [item for item in bundle.surfaces if item.declaration_kind == "parse_failure"]
    assert failed
    assert failed[0].extraction_status is ExtractionStatus.ERROR
    assert failed[0].relative_path.endswith("broken.py")
    assert any("python_parse_failure" in note for note in bundle.limitations)
