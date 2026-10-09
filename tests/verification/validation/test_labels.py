"""Independent labels exist on disk before any analyzer tuning."""

from __future__ import annotations

from pathlib import Path

from verification.validation.loader import load_bundle

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_flagship_and_adversarial_labels_precede_tuning() -> None:
    bundle = load_bundle()
    assert bundle.flagship_labels
    assert bundle.adversarial_labels
    for label in (*bundle.flagship_labels, *bundle.adversarial_labels):
        assert label.independent_of_engine_output
        assert label.precedes_tuning


def test_planted_fixtures_are_present_and_synthetic() -> None:
    secret = (FIXTURES / "planted-secret" / "README.txt").read_text(encoding="utf-8")
    assert "cs_planted_not_a_credential_0000" in secret
    assert "AKIA" not in secret
    package = (FIXTURES / "planted-cve-dep" / "package.json").read_text(encoding="utf-8")
    assert "4.17.4" in package
    alpha = FIXTURES / "planted-architecture" / "pkg" / "a" / "Alpha.java"
    beta = FIXTURES / "planted-architecture" / "pkg" / "b" / "Beta.java"
    assert "import pkg.b.Beta" in alpha.read_text(encoding="utf-8")
    assert "import pkg.a.Alpha" in beta.read_text(encoding="utf-8")
    rust = (FIXTURES / "unsupported-rust" / "main.rs").read_text(encoding="utf-8")
    assert "fn main" in rust


def test_label_sources_point_at_engine_owned_or_public_docs() -> None:
    bundle = load_bundle()
    by_id = {label.id: label for label in bundle.flagship_labels}
    assert by_id["planted-secret-fixture"].source.endswith("fixtures/planted-secret")
    assert (FIXTURES / "planted-secret").is_dir()
