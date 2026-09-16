"""Guards against production publish credentials in normal tests and the harness."""

from __future__ import annotations

from pathlib import Path

ENGINE = Path(__file__).resolve().parents[2]


def _iter_text_files() -> tuple[Path, ...]:
    roots = (ENGINE / "verification", ENGINE / "tests" / "verification")
    files: list[Path] = []
    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".yaml", ".yml", ".json", ".md"}:
                files.append(path)
    return tuple(files)


FORBIDDEN_SUBSTRINGS = (
    "pypi-" + "AgE",
    "AK" + "IA",
    "-----BEGIN " + "PRIVATE KEY-----",
    "gh" + "p_",
)


def test_no_production_publish_credential_material_in_harness_or_tests() -> None:
    offenders: list[str] = []
    for path in _iter_text_files():
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_SUBSTRINGS:
            if marker in text:
                offenders.append(f"{path}: {marker}")
    assert offenders == []


def test_quality_manifest_does_not_embed_registry_tokens() -> None:
    text = (ENGINE / "verification" / "quality-commands.yaml").read_text(encoding="utf-8")
    assert "PYPI_TOKEN" not in text
    assert "TWINE_PASSWORD" not in text
    assert "OIDC_TOKEN=" not in text
    assert "password:" not in text.lower()
