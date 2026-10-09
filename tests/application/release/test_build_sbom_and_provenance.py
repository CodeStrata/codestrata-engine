"""E14.2 runtime SBOM and provenance binding."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from codestrata import __version__
from codestrata.application.release.standalone.models import SourceBinding
from codestrata.application.release.standalone.policy import runtime_lock_digest
from codestrata.application.release.standalone.provenance import (
    build_provenance_manifest,
    committed_source_binding,
    development_source_binding,
)
from codestrata.application.release.standalone.sbom import (
    build_runtime_sbom,
    cyclonedx_document,
    sbom_digest,
)


def test_runtime_sbom_covers_lock_inputs() -> None:
    sbom = build_runtime_sbom()
    names = {item.name for item in sbom.components}
    assert names == {
        "certifi",
        "cryptography",
        "pydantic",
        "PyYAML",
        "rich",
        "typer",
    }
    digest = sbom_digest(sbom)
    assert len(digest) == 64
    doc = cyclonedx_document(sbom)
    assert doc["bomFormat"] == "CycloneDX"
    assert len(doc["components"]) == 6


def test_provenance_binds_wheel_and_sdist_digests(tmp_path: Path) -> None:
    wheel = tmp_path / "codestrata-0.2.1-py3-none-any.whl"
    sdist = tmp_path / "codestrata-0.2.1.tar.gz"
    wheel.write_bytes(b"wheel-bytes")
    sdist.write_bytes(b"sdist-bytes")
    sbom_path = tmp_path / "runtime-sbom.cdx.json"
    sbom_path.write_text(json.dumps({"components": []}), encoding="utf-8")
    manifest = build_provenance_manifest(wheel=wheel, sdist=sdist, sbom_path=sbom_path)
    assert manifest.runtime_lock_digest == runtime_lock_digest()
    assert manifest.primary_artifact_digest("wheel") is not None
    assert manifest.primary_artifact_digest("sdist") is not None
    assert manifest.sbom_digest == sbom_digest(build_runtime_sbom())
    assert manifest.engine_version == __version__ == "0.3.0"
    assert manifest.catalog_package_revision == "ENGINE-2026-09-15-R1"
    assert manifest.source_binding.status == "development"
    assert manifest.source_binding.source_sha is None


def test_provenance_modules_do_not_discover_git() -> None:
    root = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "codestrata"
        / "application"
        / "release"
        / "standalone"
    )
    for name in ("provenance.py", "models.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "rev-parse" not in text
        assert "subprocess" not in text
        assert ".git" not in text
    service = (root / "service.py").read_text(encoding="utf-8")
    assert "rev-parse" not in service


def test_source_binding_is_explicit_and_does_not_invent_a_sha() -> None:
    development = development_source_binding(source_root="engine")
    assert development.source_sha is None
    committed = committed_source_binding(source_sha="a" * 40, source_root="engine")
    assert committed.status == "committed"
    assert committed.source_sha == "a" * 40
    try:
        committed_source_binding(source_sha="not-a-commit", source_root="engine")
    except ValidationError:
        pass
    else:
        raise AssertionError("unverified text was accepted as a source SHA")
    try:
        SourceBinding(
            status="development",
            source_sha="b" * 40,
            source_root="engine",
            toolchain="Python 3.12.2",
            build_procedure="test",
            note="development",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("a development binding accepted a source SHA")
