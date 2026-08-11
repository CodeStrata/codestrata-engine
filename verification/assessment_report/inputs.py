"""Prepare SV.4 assessment runs as inputs for SV.5 (no second workflow)."""

from __future__ import annotations

import shutil
import tempfile
import venv
from dataclasses import dataclass
from pathlib import Path

from verification.cli_installation.environment import (
    engine_root_from_package,
    scrub_environ,
    venv_codestrata,
    venv_python,
    with_venv_path,
)
from verification.repository_assessment.artifacts import find_latest_run_directory
from verification.repository_assessment.catalog import load_catalog, select_smoke_repository
from verification.repository_assessment.clone import clone_qualified_repository
from verification.repository_assessment.commands import assessment_environ, run_assess, run_doctor, run_init
from verification.repository_assessment.workspace import (
    assert_outside_codestrata_tree,
    copy_fixture,
    resolve_local_fixture,
)


@dataclass(frozen=True, slots=True)
class PreparedRun:
    label: str
    source: str
    run_directory: Path
    assessment_run_reference: str
    repository_id: str | None = None
    project_name: str | None = None
    github_repository: str | None = None
    qualified_revision_type: str | None = None
    qualified_revision_value: str | None = None
    checked_out_sha: str | None = None


def _install(engine_root: Path, venv_dir: Path, env: dict[str, str]) -> Path:
    import subprocess

    venv.create(str(venv_dir), with_pip=True, clear=True)
    python = venv_python(venv_dir)
    proc = subprocess.run(
        [str(python), "-m", "pip", "install", str(engine_root)],
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"install failed: {(proc.stderr or '')[-400:]}")
    return venv_codestrata(venv_dir)


def _assess_repo(codestrata: Path, repo: Path, env: dict[str, str]) -> Path:
    run_doctor(codestrata, cwd=repo, env=env)
    init = run_init(codestrata, cwd=repo, env=env)
    if init.exit_code != 0:
        raise RuntimeError(f"init failed: {init.exit_code}")
    assess = run_assess(codestrata, cwd=repo, env=env)
    if assess.exit_code != 0:
        raise RuntimeError(f"assess failed: {assess.exit_code}")
    run_dir = find_latest_run_directory(repo / "reports")
    if run_dir is None or not (run_dir / "report.json").is_file():
        raise RuntimeError("assessment artifacts missing")
    return run_dir


def prepare_assessment_inputs(
    *,
    engine_root: Path | None = None,
    work_root: Path | None = None,
    local_only: bool = False,
    with_catalog_network: bool = False,
    keep_output: bool = True,
) -> tuple[list[PreparedRun], Path]:
    """Run SV.4-style assessments and return durable run directories for SV.5.

    Temporary clones live outside the CodeStrata tree. Assessment artifacts are
    copied into ``work_root/runs/`` with repository-relative references only.
    """

    engine_root = (engine_root or engine_root_from_package()).resolve()
    monorepo = engine_root.parent
    if not (monorepo / "validation" / "repository-catalog" / "catalog.json").is_file():
        monorepo = engine_root

    owned_temp = work_root is None
    artifact_root = (work_root or Path(tempfile.mkdtemp(prefix="cs-sv5-artifacts-"))).resolve()
    runs_root = artifact_root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    # Clones/venvs must remain outside the CodeStrata source tree.
    scratch = Path(tempfile.mkdtemp(prefix="cs-sv5-scratch-")).resolve()
    assert_outside_codestrata_tree(scratch, monorepo)

    base_env = scrub_environ()
    venv_dir = scratch / "venv"
    install_env = with_venv_path(base_env, venv_dir)
    codestrata = _install(engine_root, venv_dir, install_env)
    run_env = assessment_environ(with_venv_path(base_env, venv_dir), offline=True)

    prepared: list[PreparedRun] = []

    # Local controlled fixture (always)
    fixture = resolve_local_fixture(monorepo, "test-fixtures/sample-js-app")
    local_repo = scratch / "local" / "sample-js-app"
    copy_fixture(fixture, local_repo)
    local_run = _assess_repo(codestrata, local_repo, run_env)
    local_dest = runs_root / "local-sample-js-app"
    if local_dest.exists():
        shutil.rmtree(local_dest)
    shutil.copytree(local_run, local_dest)
    prepared.append(
        PreparedRun(
            label="local-sample-js-app",
            source="local_fixture",
            run_directory=local_dest,
            assessment_run_reference="runs/local-sample-js-app",
            repository_id="sample-js-app",
            project_name="sample-js-app",
        )
    )

    # Second equivalent local run for deterministic-render comparison (same venv).
    local_repo_b = scratch / "local-b" / "sample-js-app"
    copy_fixture(fixture, local_repo_b)
    local_run_b = _assess_repo(codestrata, local_repo_b, run_env)
    local_dest_b = runs_root / "local-sample-js-app-b"
    if local_dest_b.exists():
        shutil.rmtree(local_dest_b)
    shutil.copytree(local_run_b, local_dest_b)
    prepared.append(
        PreparedRun(
            label="local-sample-js-app-b",
            source="local_fixture_repeat",
            run_directory=local_dest_b,
            assessment_run_reference="runs/local-sample-js-app-b",
            repository_id="sample-js-app",
            project_name="sample-js-app",
        )
    )

    # Catalog-backed remote (when requested / not local-only)
    if with_catalog_network and not local_only:
        catalog = load_catalog(monorepo)
        entry, reason = select_smoke_repository(catalog)
        if entry is None or entry.qualified_revision is None:
            raise RuntimeError(f"catalog qualification gap: {reason}")
        clone_dest = scratch / "catalog" / entry.id
        assert_outside_codestrata_tree(clone_dest, monorepo)
        clone = clone_qualified_repository(entry, clone_dest)
        if not clone.ok:
            raise RuntimeError(f"clone failed: {clone.detail}")
        offline = assessment_environ(run_env, offline=True)
        remote_run = _assess_repo(codestrata, clone_dest, offline)
        remote_dest = runs_root / f"catalog-{entry.id}"
        if remote_dest.exists():
            shutil.rmtree(remote_dest)
        shutil.copytree(remote_run, remote_dest)
        prepared.append(
            PreparedRun(
                label=f"catalog-{entry.id}",
                source="catalog",
                run_directory=remote_dest,
                assessment_run_reference=f"runs/catalog-{entry.id}",
                repository_id=entry.id,
                project_name=entry.project_name,
                github_repository=entry.github_repository,
                qualified_revision_type=clone.revision_type,
                qualified_revision_value=clone.revision_value,
                checked_out_sha=clone.checked_out_sha,
            )
        )

    # Drop scratch (venv/clones) after copying required artifacts out.
    shutil.rmtree(scratch, ignore_errors=True)
    return prepared, artifact_root
