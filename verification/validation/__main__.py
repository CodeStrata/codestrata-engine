"""CLI: ``python -m verification.validation``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verification.validation.checks import evaluate, overall_status
from verification.validation.loader import load_bundle
from verification.validation.render import render_corpus


def _repo_root_from_cwd() -> Path:
    cwd = Path.cwd()
    if cwd.name == "engine":
        return cwd.parent
    return cwd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="E15.1 pin corpus manifests (read-only; does not clone remotes).",
    )
    parser.add_argument("--repo-root", type=Path, default=_repo_root_from_cwd())
    parser.add_argument(
        "--write-docs",
        type=Path,
        default=None,
        nargs="?",
        const=Path("engine/docs/validation/corpus.md"),
        help="Write engine/docs/validation/corpus.md (or a given path).",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    bundle = load_bundle()
    results = evaluate(bundle, engine_root=args.repo_root.resolve() / "engine")
    status = overall_status(results)
    if args.write_docs is not None:
        target = args.write_docs
        if not target.is_absolute():
            target = args.repo_root.resolve() / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_corpus(bundle, results), encoding="utf-8")
    if args.json:
        payload = {
            "status": status.value,
            "external_count": len(bundle.external_large),
            "dogfood_count": len(bundle.dogfood),
            "flagship_labels": len(bundle.flagship_labels),
            "adversarial_labels": len(bundle.adversarial_labels),
            "discovery_22_meets_fifty": bundle.discovery_lead.meets_fifty_large_bar,
            "failed": [
                {"id": item.id, "detail": item.detail}
                for item in results
                if item.status.value != "PASS"
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_corpus(bundle, results))
    return 0 if status.value == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
