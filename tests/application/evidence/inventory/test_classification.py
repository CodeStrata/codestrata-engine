"""M01 classification: mutually exclusive classes and detection vs support."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.inventory.classification import InventoryPrimaryClassifier
from codestrata.application.evidence.inventory.models import InventoryMetricStatus
from codestrata.application.evidence.inventory.service import ExtractorInventoryService
from codestrata.domain.repository_graph.enums import InventoryPrimaryClass

FIXTURES = Path(__file__).parent / "fixtures"


def test_primary_classes_are_mutually_exclusive() -> None:
    classifier = InventoryPrimaryClassifier()
    cases = {
        "src/main/java/com/example/App.java": InventoryPrimaryClass.SOURCE,
        "src/test/java/com/example/AppTest.java": InventoryPrimaryClass.TEST,
        "pom.xml": InventoryPrimaryClass.CONFIG,
        ".github/workflows/ci.yml": InventoryPrimaryClass.INFRA,
        "README.md": InventoryPrimaryClass.DOCS,
        "target/generated-sources/annotations/X.java": InventoryPrimaryClass.GENERATED,
        "vendor/lib.php": InventoryPrimaryClass.VENDOR,
        "logo.png": InventoryPrimaryClass.BINARY,
        "mystery.dat": InventoryPrimaryClass.BINARY,
        "notes.txt": InventoryPrimaryClass.UNKNOWN,
    }
    for path, expected in cases.items():
        assert classifier.classify(path) is expected


def test_generated_filename_is_not_a_path_marker_false_positive() -> None:
    classifier = InventoryPrimaryClassifier()
    assert (
        classifier.classify("src/main/java/com/example/GeneratedHelper.java")
        is InventoryPrimaryClass.SOURCE
    )


def test_go_is_detected_but_not_structurally_supported() -> None:
    service = ExtractorInventoryService()
    snapshot = service.inspect_tree(FIXTURES / "mixed_language")
    go = next(item for item in snapshot.files if item.relative_path.endswith("main.go"))
    java = next(item for item in snapshot.files if item.relative_path.endswith("App.java"))
    assert go.detected is True
    assert go.language == "Go"
    assert go.structurally_supported is False
    assert java.detected is True
    assert java.structurally_supported is True
    assert java.structural_language == "java"
    assert snapshot.metric.status is InventoryMetricStatus.OBSERVED
    assert snapshot.metric.denominator == snapshot.metric.eligible_files
    assert snapshot.metric.numerator == snapshot.metric.supported_eligible_files
    assert snapshot.metric.numerator < snapshot.metric.denominator


def test_generated_and_vendor_classes() -> None:
    snapshot = ExtractorInventoryService().inspect_tree(FIXTURES / "generated_vendor")
    by_path = {item.relative_path: item for item in snapshot.files}
    assert by_path["generated/Gen.java"].primary_class is InventoryPrimaryClass.GENERATED
    assert by_path["vendor/lib.php"].primary_class is InventoryPrimaryClass.VENDOR
    helper = by_path["src/main/java/com/example/GeneratedHelper.java"]
    assert helper.primary_class is InventoryPrimaryClass.SOURCE


def test_binary_extension_and_nul_bytes(tmp_path: Path) -> None:
    (tmp_path / "logo.png").write_text("not-png", encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(b"abc\x00def")
    snapshot = ExtractorInventoryService().inspect_tree(tmp_path)
    by_path = {item.relative_path: item for item in snapshot.files}
    assert by_path["logo.png"].primary_class is InventoryPrimaryClass.BINARY
    assert by_path["blob.bin"].primary_class is InventoryPrimaryClass.BINARY
    assert by_path["blob.bin"].content_digest


def test_empty_repo_is_not_applicable(tmp_path: Path) -> None:
    snapshot = ExtractorInventoryService().inspect_tree(tmp_path)
    assert snapshot.metric.status is InventoryMetricStatus.NOT_APPLICABLE
    assert snapshot.metric.denominator == 0
    assert snapshot.metric.ratio is None


def test_unreadable_subtree_is_unknown(tmp_path: Path) -> None:
    hidden = tmp_path / "secret" / "closed.py"
    hidden.parent.mkdir()
    hidden.write_text("x = 1\n", encoding="utf-8")

    def reader(path: Path) -> bytes:
        if path.name == "closed.py":
            raise PermissionError("denied")
        return path.read_bytes()

    from codestrata.application.evidence.inventory.walk import walk_repository

    walked = walk_repository(tmp_path, read_bytes=reader)
    closed = next(item for item in walked.files if item.relative_path.endswith("closed.py"))
    assert closed.primary_class is InventoryPrimaryClass.UNKNOWN
    assert closed.unread_reason == "unreadable"
    assert closed.content_digest == ""
