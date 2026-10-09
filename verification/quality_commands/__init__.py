"""Executable Engine quality-command manifest (E00.2).

``load_manifest`` reads YAML; ``run_quality_commands`` executes it and
classifies each true exit code. Root CI job ``engine-tests`` is not this runner.
"""

from __future__ import annotations

from verification.quality_commands.manifest import load_manifest
from verification.quality_commands.models import CommandStatus, QualityRunReport
from verification.quality_commands.runner import classify_status, run_quality_commands

__all__ = [
    "CommandStatus",
    "QualityRunReport",
    "classify_status",
    "load_manifest",
    "run_quality_commands",
]
