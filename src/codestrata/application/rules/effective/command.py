"""Release-time sealing of prebuilt Community packages. Not a customer-authoring CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codestrata.application.rules.effective.errors import EffectiveSealError
from codestrata.application.rules.effective.packages import seal_bundled_community
from codestrata.domain.contracts.enums import ExecutionPurpose
from codestrata.domain.contracts.serialization import dumps_canonical


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Seal the prebuilt Community Effective RuleSet. No customer YAML authoring surface."
        )
    )
    parser.add_argument(
        "--bundled",
        action="store_true",
        help="Seal the in-memory Community engineering catalog shipped with Engine",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory that receives canonical Effective RuleSet JSON",
    )
    args = parser.parse_args(argv)
    if not args.bundled:
        parser.error("provide --bundled; customer-authoring catalogs are not a Community CLI")
    try:
        effective, _catalog = seal_bundled_community(purpose=ExecutionPurpose.PRODUCTION)
    except EffectiveSealError as error:
        sys.stderr.write(f"{error}\n")
        return 2
    args.output.mkdir(parents=True, exist_ok=True)
    name = f"{effective.ruleset_id}@{effective.ruleset_version}.effective.json"
    path = args.output / name.replace("/", ".")
    path.write_text(dumps_canonical(effective.model_dump(mode="json")) + "\n", encoding="utf-8")
    sys.stdout.write(f"sealed {path.name}\n")
    return 0
