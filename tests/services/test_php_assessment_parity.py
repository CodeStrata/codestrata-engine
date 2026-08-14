"""Phase 5.17.1 PHP assessment parity focused tests."""

from __future__ import annotations

from pathlib import Path

from codestrata.application.evidence.language.complexity.service import (
    ComplexityEvidenceService,
)
from codestrata.application.rules.dependency.pack import DependencyRulePack
from codestrata.application.rules.technical_debt.pack import TechnicalDebtRulePack
from codestrata.config.settings import ComplexityEvidenceSettings
from codestrata.models import Repository
from codestrata.services.detectors.php_technology_detector import PhpTechnologyDetector

_ENGINE_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = _ENGINE_ROOT.parent


def _sample_php_app() -> Path:
    for candidate in (
        _REPO_ROOT / "test-fixtures" / "sample-php-app",
        _ENGINE_ROOT / "test-fixtures" / "sample-php-app",
        Path("test-fixtures/sample-php-app"),
    ):
        if candidate.is_dir():
            return candidate
    return Path("test-fixtures/sample-php-app")


def test_php_packs_include_language_gate() -> None:
    assert "php" in TechnicalDebtRulePack().supported_languages
    assert "php" in DependencyRulePack().supported_languages


def test_sample_php_app_complexity_collects(tmp_path: Path) -> None:
    sample = _sample_php_app()
    if not sample.is_dir():
        return
    paths = tuple(
        path.relative_to(sample).as_posix()
        for path in sample.rglob("*.php")
        if path.is_file()
    )
    texts = {
        relative: (sample / relative).read_text(encoding="utf-8")
        for relative in paths
    }
    settings = ComplexityEvidenceSettings().model_copy(
        update={
            "python": ComplexityEvidenceSettings().python.model_copy(
                update={"enabled": False}
            ),
            "java": ComplexityEvidenceSettings().java.model_copy(update={"enabled": False}),
        }
    )
    result = ComplexityEvidenceService(settings).collect(
        repository_id="sample-php-app",
        relative_paths=paths,
        file_texts=texts,
    )
    assert result.callables
    assert all(item.language == "php" for item in result.callables)
    assert "language.php.complexity" in result.contributing_provider_ids


def test_sample_php_detector_still_laravel(tmp_path: Path) -> None:
    sample = _sample_php_app()
    files = [
        path.relative_to(sample).as_posix()
        for path in sample.rglob("*")
        if path.is_file()
    ]
    repository = Repository(name="sample-php-app", path=sample.resolve(), files=files)
    names = {item.name for item in PhpTechnologyDetector().detect(repository)}
    assert "PHP" in names
    assert "Composer" in names
    assert "Laravel" in names
