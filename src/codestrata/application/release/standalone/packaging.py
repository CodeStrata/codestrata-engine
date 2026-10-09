"""Verify wheel/sdist include packaged resources separately."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

from codestrata.application.release.standalone.models import PackagingCheckResult
from codestrata.application.release.standalone.policy import load_packaging_inventory


def _wheel_members(archive: zipfile.ZipFile) -> set[str]:
    return set(archive.namelist())


def _sdist_members(archive: tarfile.TarFile) -> set[str]:
    return {member.name.replace("\\", "/") for member in archive.getmembers() if member.isfile()}


def verify_wheel_inventory(wheel_path: Path) -> PackagingCheckResult:
    inventory = load_packaging_inventory()
    required = inventory.get("wheel_required_members")
    if not isinstance(required, list):
        return PackagingCheckResult(
            name="wheel_inventory",
            ok=False,
            detail="inventory missing wheel_required_members",
        )
    with zipfile.ZipFile(wheel_path) as archive:
        names = _wheel_members(archive)
    missing = sorted(str(item) for item in required if str(item) not in names)
    return PackagingCheckResult(
        name="wheel_inventory",
        ok=not missing,
        detail="ok" if not missing else f"missing {len(missing)} packaged members",
        missing=tuple(missing),
    )


def verify_sdist_inventory(sdist_path: Path) -> PackagingCheckResult:
    inventory = load_packaging_inventory()
    required = inventory.get("sdist_required_paths")
    if not isinstance(required, list):
        return PackagingCheckResult(
            name="sdist_inventory",
            ok=False,
            detail="inventory missing sdist_required_paths",
        )
    with tarfile.open(sdist_path, mode="r:gz") as archive:
        names = _sdist_members(archive)
    missing = sorted(
        str(item)
        for item in required
        if not any(name.endswith(str(item)) or str(item) in name for name in names)
    )
    return PackagingCheckResult(
        name="sdist_inventory",
        ok=not missing,
        detail="ok" if not missing else f"missing {len(missing)} sdist paths",
        missing=tuple(missing),
    )


def verify_public_source_export(engine_root: Path) -> PackagingCheckResult:
    inventory = load_packaging_inventory()
    globs = inventory.get("public_source_export_globs")
    if not isinstance(globs, list):
        return PackagingCheckResult(
            name="public_source_export",
            ok=False,
            detail="inventory missing public_source_export_globs",
        )
    missing: list[str] = []
    for pattern in globs:
        text = str(pattern)
        if text.endswith("/**/*.py"):
            base = text.removesuffix("/**/*.py")
            root = engine_root / base
            if not any(root.rglob("*.py")):
                missing.append(text)
        elif text.endswith("/**/*.yaml"):
            base = text.removesuffix("/**/*.yaml")
            root = engine_root / base
            if not any(root.rglob("*.yaml")):
                missing.append(text)
        elif text.endswith("/**/*"):
            base = text.removesuffix("/**/*")
            root = engine_root / base
            if not root.exists():
                missing.append(text)
        else:
            if not (engine_root / text).exists():
                missing.append(text)
    return PackagingCheckResult(
        name="public_source_export",
        ok=not missing,
        detail="ok" if not missing else "missing export paths",
        missing=tuple(missing),
    )
