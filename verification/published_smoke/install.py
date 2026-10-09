"""Install published wheels outside the Engine checkout."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from codestrata.application.release.standalone.install_verify import scrubbed_environ
from verification.published_smoke.models import InstalledPublished


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_published_semver(
    *,
    project: str,
    semver: str,
    expected_wheel_sha256: str,
    outside_root: Path,
) -> InstalledPublished:
    workspace = Path(
        tempfile.mkdtemp(prefix=f"codestrata-published-{semver}-", dir=str(outside_root))
    )
    venv_dir = workspace / "venv"
    venv.create(venv_dir, with_pip=True, clear=True)
    python = venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    env = scrubbed_environ()
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = str(python.parent) + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONPATH", None)

    dist = workspace / "dist"
    dist.mkdir()
    download = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "download",
            f"{project}=={semver}",
            "--only-binary",
            ":all:",
            "--no-deps",
            "-d",
            str(dist),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if download.returncode != 0:
        raise RuntimeError(f"pip download failed: {download.stderr[-800:]}")
    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        raise RuntimeError("pip download produced no wheel")
    wheel = wheels[-1]
    observed = sha256_file(wheel)
    if expected_wheel_sha256 and observed != expected_wheel_sha256.lower():
        raise ValueError(
            f"wheel digest mismatch: expected {expected_wheel_sha256}, observed {observed}"
        )
    install_wheel = subprocess.run(
        [str(python), "-m", "pip", "install", str(wheel)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if install_wheel.returncode != 0:
        raise RuntimeError(f"wheel install failed: {install_wheel.stderr[-800:]}")
    codestrata = python.parent / ("codestrata.exe" if sys.platform == "win32" else "codestrata")
    if not codestrata.is_file():
        raise RuntimeError(f"missing console script: {codestrata}")
    return InstalledPublished(
        semver=semver,
        wheel_sha256=observed,
        wheel_path=str(wheel),
        codestrata=str(codestrata),
        python=str(python),
        workspace=str(workspace),
        env=env,
    )
