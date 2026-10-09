"""Build wheel and sdist artifacts for release verification."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class BuildError(RuntimeError):
    pass


def build_wheel_and_sdist(engine_root: Path, dist_dir: Path) -> tuple[Path, Path]:
    dist_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", str(dist_dir)],
        cwd=str(engine_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise BuildError(f"build failed: {completed.stderr[-800:]}")
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if not wheels or not sdists:
        raise BuildError("dist directory missing wheel or sdist after build")
    return wheels[-1], sdists[-1]
