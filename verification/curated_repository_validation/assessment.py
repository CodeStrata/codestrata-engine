"""Assessment workflow helpers for SV.10 — reuses SV.4 CLI commands."""

from __future__ import annotations

import shutil
import tempfile
import venv
from pathlib import Path

from verification.cli_installation.environment import (
    scrub_environ,
    venv_codestrata,
    venv_python,
    with_venv_path,
)
from verification.repository_assessment.commands import (
    assessment_environ,
    run_assess,
    run_doctor,
    run_init,
)


def install_codestrata_cli(engine_root: Path, *, venv_dir: Path | None = None) -> tuple[Path, Path]:
    """Create a non-editable install of the Engine CLI in a temporary venv."""

    target = venv_dir or Path(tempfile.mkdtemp(prefix="cs-sv10-venv-"))
    if not (target / "bin").exists() and not (target / "Scripts").exists():
        venv.create(target, with_pip=True, clear=False)
    python = venv_python(target)
    env = scrub_environ()
    env = with_venv_path(env, target)
    import subprocess

    proc = subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError("pip bootstrap failed for SV.10 venv")
    proc = subprocess.run(
        [str(python), "-m", "pip", "install", str(engine_root)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "")[-400:]
        raise RuntimeError(f"non-editable codestrata install failed: {detail}")
    codestrata = venv_codestrata(target)
    if not codestrata.is_file():
        raise RuntimeError("codestrata executable missing after install")
    return codestrata, target


def build_assessment_env(*, home: Path, venv_dir: Path, offline: bool = True) -> dict[str, str]:
    env = assessment_environ(offline=offline)
    env = with_venv_path(env, venv_dir)
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["XDG_CACHE_HOME"] = str(home / ".cache")
    (home / ".config").mkdir(parents=True, exist_ok=True)
    (home / ".cache").mkdir(parents=True, exist_ok=True)
    return env


def run_customer_workflow(
    codestrata: Path,
    *,
    repo_cwd: Path,
    env: dict[str, str],
    assess_timeout_s: float,
):
    """Customer workflow aligned with SV.3/SV.4.

    ``doctor`` before ``init`` is expected to report missing config (non-zero).
    Fail closed only on doctor traceback. ``init`` and ``assess`` must succeed.
    """

    doctor = run_doctor(codestrata, cwd=repo_cwd, env=env)
    if doctor.has_traceback:
        return {"doctor": doctor, "init": None, "assess": None, "stage": "doctor"}

    init = run_init(codestrata, cwd=repo_cwd, env=env)
    if init.exit_code != 0 or init.has_traceback:
        return {"doctor": doctor, "init": init, "assess": None, "stage": "init"}
    if not (repo_cwd / "codestrata.toml").is_file():
        return {"doctor": doctor, "init": init, "assess": None, "stage": "init_config_missing"}

    # Post-init doctor is advisory for environment health.
    doctor_post = run_doctor(codestrata, cwd=repo_cwd, env=env)
    if doctor_post.has_traceback:
        return {
            "doctor": doctor_post,
            "init": init,
            "assess": None,
            "stage": "doctor",
        }

    assess = run_assess(
        codestrata,
        cwd=repo_cwd,
        env=env,
        timeout_s=assess_timeout_s,
    )
    return {
        "doctor": doctor_post,
        "init": init,
        "assess": assess,
        "stage": "assess",
        "doctor_pre_exit": doctor.exit_code,
    }


def cleanup_venv(venv_dir: Path) -> None:
    shutil.rmtree(venv_dir, ignore_errors=True)
