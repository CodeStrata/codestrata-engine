"""Community example catalogue must match published repositories."""

from __future__ import annotations

from pathlib import Path

from codestrata.cli.examples_cmd import OFFICIAL_EXAMPLES, format_examples


def _engine_fixtures() -> Path:
    """Locate test-fixtures in monorepo or flat engine checkout."""

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "test-fixtures" / "sample-js-app"
        if candidate.is_dir():
            return parent / "test-fixtures"
    raise AssertionError("Unable to locate test-fixtures/sample-js-app")


ENGINE_FIXTURES = _engine_fixtures()


def test_official_examples_only_list_published_community_samples() -> None:
    names = {item.name for item in OFFICIAL_EXAMPLES}
    assert names == {"sample-js-app", "codestrata-examples"}
    unpublished = {
        "sample-python-app",
        "sample-java-app",
        "sample-php-app",
        "sample-csharp-app",
    }
    assert names.isdisjoint(unpublished)


def test_sample_js_fixture_exists_in_engine() -> None:
    assert (ENGINE_FIXTURES / "sample-js-app").is_dir()


def test_format_examples_mentions_codestrata_examples_clone() -> None:
    text = format_examples()
    assert "sample-js-app" in text
    assert "codestrata-examples" in text
    assert "sample-python-app" not in text
    assert "run_showcase.py" in text
