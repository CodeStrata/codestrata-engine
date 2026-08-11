"""Developer helper: regenerate committed telemetry catalog artifacts.

Usage (from repository root or engine package):

    python -m codestrata.telemetry.catalog_write

Does not alter the public CLI surface. Writes only the committed docs artifacts.
"""

from __future__ import annotations

from pathlib import Path

from codestrata.telemetry.catalog import build_privacy_first_telemetry_catalog
from codestrata.telemetry.catalog_formatting import (
    format_catalog_json,
    format_catalog_markdown,
)
from codestrata.telemetry.catalog_validation import reconcile_catalog_against_runtime

# Relative to the engine package docs directory when installed from source tree.
_ENGINE_DOCS = Path(__file__).resolve().parents[3] / "docs"
JSON_ARTIFACT_NAME = "telemetry-event-catalog.json"
MARKDOWN_ARTIFACT_NAME = "telemetry-event-catalog.md"


def catalog_artifact_paths(*, docs_dir: Path | None = None) -> tuple[Path, Path]:
    root = docs_dir or _ENGINE_DOCS
    return root / JSON_ARTIFACT_NAME, root / MARKDOWN_ARTIFACT_NAME


def write_catalog_artifacts(*, docs_dir: Path | None = None) -> tuple[Path, Path]:
    catalog = build_privacy_first_telemetry_catalog()
    reconcile_catalog_against_runtime(catalog)
    json_path, md_path = catalog_artifact_paths(docs_dir=docs_dir)
    json_path.write_text(format_catalog_json(catalog), encoding="utf-8")
    md_path.write_text(format_catalog_markdown(catalog), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    json_path, md_path = write_catalog_artifacts()
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
