"""Artifact expectations after ``codestrata init``."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from verification.cli_installation.contract import InstallationContract, default_contract


def validate_init_artifacts(
    workspace: Path,
    *,
    config_name: str = "codestrata.toml",
    contract: InstallationContract | None = None,
) -> tuple[bool, str, dict[str, object]]:
    """Validate config creation and absence of unexpected trees."""

    active = contract or default_contract()
    config = workspace / config_name
    evidence: dict[str, object] = {"config": str(config)}

    if not config.is_file():
        return False, "codestrata.toml was not created", evidence

    text = config.read_text(encoding="utf-8")
    missing = [marker for marker in active.required_config_markers if marker not in text]
    if missing:
        evidence["missing_markers"] = missing
        return False, f"config missing markers: {missing}", evidence

    mode = config.stat().st_mode
    evidence["mode"] = oct(mode & 0o777)
    if not (mode & stat.S_IRUSR):
        return False, "config is not user-readable", evidence

    # init must not create workspace/knowledge directories by itself.
    workspace_dir = workspace / ".codestrata" / "workspace"
    knowledge_dir = workspace / ".codestrata" / "knowledge"
    evidence["workspace_dir_exists"] = workspace_dir.exists()
    evidence["knowledge_dir_exists"] = knowledge_dir.exists()
    if workspace_dir.exists() or knowledge_dir.exists():
        return (
            False,
            "init unexpectedly created workspace/knowledge directories",
            evidence,
        )

    unexpected_present = [
        name
        for name in active.unexpected_after_init
        if (workspace / name).exists() and name not in {".git"}  # .git may exist if nested
    ]
    # Only flag unexpected product trees that init should never create.
    product_leaks = [
        name
        for name in ("platform", "infrastructure", "node_modules")
        if (workspace / name).exists()
    ]
    if product_leaks:
        evidence["unexpected"] = product_leaks
        return False, f"unexpected paths after init: {product_leaks}", evidence

    evidence["size_bytes"] = config.stat().st_size
    evidence["owner_readable"] = bool(mode & stat.S_IRUSR)
    _ = unexpected_present
    return True, "init artifacts valid", evidence


def list_workspace_files(workspace: Path) -> list[str]:
    """Return relative file paths under the verification workspace."""

    files: list[str] = []
    for path in sorted(workspace.rglob("*")):
        if path.is_file():
            files.append(path.relative_to(workspace).as_posix())
    return files


def config_is_user_writable(path: Path) -> bool:
    return os.access(path, os.R_OK | os.W_OK)
