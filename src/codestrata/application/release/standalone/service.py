"""Orchestrate E14.2 build verification (library entrypoint)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from codestrata import __version__
from codestrata.application.release.standalone.artifacts import build_wheel_and_sdist
from codestrata.application.release.standalone.install_verify import (
    scrubbed_environ,
    verify_install_environment,
    version_output_implies_database_dependency,
)
from codestrata.application.release.standalone.models import BuildVerificationSummary
from codestrata.application.release.standalone.packaging import (
    verify_public_source_export,
    verify_sdist_inventory,
    verify_wheel_inventory,
)
from codestrata.application.release.standalone.provenance import (
    build_provenance_manifest,
    committed_source_binding,
    development_source_binding,
)
from codestrata.application.release.standalone.sbom import build_runtime_sbom, cyclonedx_document


def run_build_verification(
    *,
    engine_root: Path,
    output_directory: Path,
    dist_directory: Path | None = None,
    verified_source_sha: str | None = None,
) -> BuildVerificationSummary:
    output_directory.mkdir(parents=True, exist_ok=True)
    dist = dist_directory or (output_directory / "dist")
    wheel, sdist = build_wheel_and_sdist(engine_root, dist)
    sbom = build_runtime_sbom()
    sbom_path = output_directory / "runtime-sbom.cdx.json"
    sbom_path.write_text(
        json.dumps(cyclonedx_document(sbom), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    provenance = build_provenance_manifest(
        wheel=wheel,
        sdist=sdist,
        sbom_path=sbom_path,
        source_binding=(
            committed_source_binding(
                source_sha=verified_source_sha,
                source_root=engine_root.name,
            )
            if verified_source_sha is not None
            else development_source_binding(source_root=engine_root.name)
        ),
    )
    (output_directory / "provenance.json").write_text(
        provenance.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    packaging_checks = (
        verify_public_source_export(engine_root),
        verify_wheel_inventory(wheel),
        verify_sdist_inventory(sdist),
    )
    install_ok = _verify_clean_wheel_install(wheel, outside_root=engine_root.parent)
    ok = install_ok and all(item.ok for item in packaging_checks)
    summary = BuildVerificationSummary(
        ok=ok,
        engine_version=__version__,
        provenance=provenance,
        packaging_checks=packaging_checks,
        install_outside_checkout=install_ok,
        detail="ok" if ok else "build verification failed",
    )
    (output_directory / "build-verification-summary.json").write_text(
        summary.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def _verify_clean_wheel_install(wheel: Path, *, outside_root: Path) -> bool:
    env_check = verify_install_environment(scrubbed_environ())
    if not env_check.ok:
        return False
    tmp = Path(tempfile.mkdtemp(prefix="codestrata-e142-install-", dir=str(outside_root)))
    try:
        venv_dir = tmp / "venv"
        venv.create(venv_dir, with_pip=True, clear=True)
        python = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        env = scrubbed_environ()
        env["VIRTUAL_ENV"] = str(venv_dir)
        env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
        install = subprocess.run(  # noqa: S603
            [str(python), "-m", "pip", "install", str(wheel)],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if install.returncode != 0:
            return False
        bin_name = "codestrata.exe" if sys.platform == "win32" else "codestrata"
        codestrata_bin = python.parent / bin_name
        version = subprocess.run(  # noqa: S603
            [str(codestrata_bin), "--version"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            cwd=str(tmp),
        )
        if version.returncode != 0:
            return False
        combined = (version.stdout or "") + (version.stderr or "")
        if version_output_implies_database_dependency(combined):
            return False
        return "CodeStrata" in combined
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
