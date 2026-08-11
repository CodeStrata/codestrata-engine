"""Packaged static resources for CodeStrata."""

from __future__ import annotations

from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path


def resources_root() -> Traversable:
    """Return the importlib resources root for ``codestrata.resources``."""

    return files("codestrata.resources")


def schema_resource(*parts: str) -> Traversable:
    """Return a packaged schema resource path under ``resources/schemas``."""

    node = resources_root().joinpath("schemas")
    for part in parts:
        node = node.joinpath(part)
    return node


def default_config_resource() -> Traversable:
    """Return the packaged default ``codestrata.defaults.toml`` resource."""

    return resources_root().joinpath("config").joinpath("codestrata.defaults.toml")


def read_default_config_text() -> str:
    """Load the packaged default configuration as text."""

    return default_config_resource().read_text(encoding="utf-8")


def write_default_config(destination: Path) -> Path:
    """Write the packaged default configuration to ``destination``."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(read_default_config_text(), encoding="utf-8")
    return destination


def assessment_report_schema() -> Traversable:
    """Return the AssessmentReport JSON schema resource (v1.2)."""

    return schema_resource("assessment", "codestrata.io", "v1.2", "AssessmentReport.json")


def branding_logo() -> Traversable:
    """Return the packaged CodeStrata brand mark asset."""

    return files("codestrata.reporting.assets").joinpath("codestrata-mark-mono.svg")
