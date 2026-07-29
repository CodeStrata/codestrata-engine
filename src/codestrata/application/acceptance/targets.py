"""Dogfood repository targets for MVP acceptance."""

from __future__ import annotations

from pathlib import Path

from codestrata.paths import engine_root, test_fixtures_root, workspace_root

_ENGINE = engine_root()
_FIXTURES = test_fixtures_root()
_WORKSPACE = workspace_root()

# Back-compat alias for CLI/scripts that imported ROOT as the workspace root.
ROOT = _WORKSPACE

ACCEPTANCE_TARGETS: tuple[tuple[str, Path], ...] = (
    ("codestrata", _ENGINE),
    (
        "spring-petclinic",
        _WORKSPACE / ".codestrata" / "workspace" / "spring-petclinic",
    ),
    ("synthetic-multilang", _FIXTURES / "sample-js-app"),
    ("sample-php-app", _FIXTURES / "sample-php-app"),
    ("sample-csharp-app", _FIXTURES / "sample-csharp-app"),
)

PREDEFINED_QUESTIONS: tuple[str, ...] = (
    "How is the repository architecture organized?",
    "What are the highest-severity security findings?",
    "Which dependencies create modernization risk?",
    "Where is authentication implemented?",
    "What testing limitations were identified?",
    "What performance risks exist?",
    "How is cloud configuration handled?",
    "What technical-debt recommendations were generated?",
)

# Live onboard creates a new scan_id each run; treat as volatile for determinism.
LIVE_DETERMINISM_EXTRA_PATHS: tuple[str, ...] = ("manifest.scan_id",)
