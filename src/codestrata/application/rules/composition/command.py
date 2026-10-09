"""Release-time pre-resolution of a local bundled RuleSet catalog."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codestrata.application.rules.composition.bundled import bundled_community_catalog
from codestrata.application.rules.composition.catalog import catalog_from_directory
from codestrata.application.rules.composition.errors import ResolutionError
from codestrata.application.rules.composition.models import ComposedRuleSet
from codestrata.application.rules.composition.resolver import resolve_ruleset
from codestrata.domain.contracts.serialization import dumps_canonical


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pre-resolve pinned RuleSets from a local catalog. No network fetch."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help="Local directory of pinned Rule and RuleSet JSON/YAML documents",
    )
    parser.add_argument(
        "--bundled",
        action="store_true",
        help="Resolve the in-memory Community engineering catalog shipped with Engine",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory that receives canonical composed JSON files",
    )
    args = parser.parse_args(argv)
    if not args.catalog and not args.bundled:
        parser.error("provide --catalog and/or --bundled")
    try:
        count = prerresolve(
            catalog_dir=args.catalog,
            bundled=bool(args.bundled),
            output_dir=args.output,
        )
    except ResolutionError as error:
        sys.stderr.write(f"{error}\n")
        return 2
    sys.stdout.write(f"resolved {count} RuleSet(s)\n")
    return 0


def prerresolve(
    *,
    catalog_dir: Path | None,
    bundled: bool,
    output_dir: Path,
) -> int:
    catalogs = []
    if bundled:
        catalogs.append(bundled_community_catalog())
    if catalog_dir is not None:
        catalogs.append(catalog_from_directory(catalog_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for catalog in catalogs:
        for ruleset in catalog.rulesets():
            composed = resolve_ruleset(ruleset, catalog)
            _write_composed(output_dir, composed)
            written += 1
    return written


def _write_composed(output_dir: Path, composed: ComposedRuleSet) -> None:
    name = f"{composed.ruleset_id}@{composed.ruleset_version}.composed.json"
    path = output_dir / name.replace("/", ".")
    path.write_text(dumps_canonical(composed.model_dump(mode="json")) + "\n", encoding="utf-8")
