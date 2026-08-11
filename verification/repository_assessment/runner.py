"""SV.4 repository assessment verification runner."""

from __future__ import annotations

import platform
import shutil
import sys
import tempfile
import time
import venv
from pathlib import Path

from verification.cli_installation.environment import (
    engine_root_from_package,
    scrub_environ,
    venv_codestrata,
    venv_python,
    with_venv_path,
)
from verification.repository_assessment.catalog import load_catalog
from verification.repository_assessment.commands import assessment_environ
from verification.repository_assessment.contract import (
    AssessmentVerificationContract,
    default_contract,
)
from verification.repository_assessment.models import ScenarioResult, VerificationReport
from verification.repository_assessment.reporting import report_contains_forbidden_leak
from verification.repository_assessment.scenarios import (
    scenario_a_catalog,
    scenario_b_local_fixture,
    scenario_c_spaces,
    scenario_d_nested,
    scenario_e_empty,
    scenario_f_unsupported,
    scenario_g_malformed_config,
    scenario_h_missing_config,
    scenario_i_invalid_output,
    scenario_j_existing_artifacts,
    scenario_k_failed_assessment,
    scenario_l_noninteractive,
    scenario_m_offline,
    scenario_n_determinism,
)


def _install_codestrata(
    *,
    engine_root: Path,
    venv_dir: Path,
    method: str,
    env: dict[str, str],
) -> tuple[bool, str]:
    import subprocess

    python = venv_python(venv_dir)
    if method == "pip_path_non_editable":
        proc = subprocess.run(
            [str(python), "-m", "pip", "install", str(engine_root)],
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
        return proc.returncode == 0, (
            "installed non-editable path" if proc.returncode == 0 else (proc.stderr or "")[-500:]
        )
    if method == "pip_wheel":
        dist = venv_dir.parent / "dist"
        if dist.exists():
            shutil.rmtree(dist)
        dist.mkdir(parents=True)
        build = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)],
            cwd=str(engine_root),
            env=scrub_environ(),
            check=False,
            text=True,
            capture_output=True,
        )
        wheels = sorted(dist.glob("*.whl"))
        if build.returncode != 0 or not wheels:
            return False, f"wheel build failed: {(build.stderr or '')[-500:]}"
        proc = subprocess.run(
            [str(python), "-m", "pip", "install", str(wheels[-1])],
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
        return proc.returncode == 0, (
            f"installed {wheels[-1].name}" if proc.returncode == 0 else (proc.stderr or "")[-500:]
        )
    return False, f"unsupported method: {method}"


def _cli_version(codestrata: Path, env: dict[str, str]) -> str | None:
    import subprocess

    proc = subprocess.run(
        [str(codestrata), "--version"],
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    return (proc.stdout or proc.stderr or "").strip().splitlines()[0][:80]


def _monorepo_root(engine_root: Path) -> Path:
    # engine/ → monorepo; catalog lives at validation/repository-catalog/
    parent = engine_root.parent
    if (parent / "validation" / "repository-catalog" / "catalog.json").is_file():
        return parent
    if (engine_root / "validation" / "repository-catalog" / "catalog.json").is_file():
        return engine_root
    return parent


def _scenario_is_catalog_gap(result: ScenarioResult) -> bool:
    return "catalog_qualification_gap" in result.failures or "network_disabled" in result.failures


def run_repository_assessment_verification(
    *,
    engine_root: Path | None = None,
    output_dir: Path | None = None,
    installation_method: str = "pip_path_non_editable",
    local_only: bool = False,
    with_catalog_network: bool = False,
    keep_output: bool = False,
    contract: AssessmentVerificationContract | None = None,
) -> VerificationReport:
    """Execute SV.4 scenarios against a non-editable installed CLI."""

    started = time.perf_counter()
    contract = contract or default_contract()
    engine_root = (engine_root or engine_root_from_package()).resolve()
    monorepo = _monorepo_root(engine_root)
    out = (output_dir or (engine_root / "reports" / "verification")).resolve()
    out.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    failures: list[str] = []
    limitations: list[str] = []
    scenarios: list[ScenarioResult] = []

    catalog = load_catalog(monorepo)
    if catalog.qualification_gap:
        limitations.append(
            "catalog qualification gap: no repository has qualified_revision; "
            "scenario A fails clearly without inventing a revision"
        )

    work_parent = Path(tempfile.mkdtemp(prefix="cs-sv4-"))
    venv_dir = work_parent / "venv"
    try:
        venv.create(str(venv_dir), with_pip=True, clear=True)
        base_env = scrub_environ()
        install_env = with_venv_path(base_env, venv_dir)
        ok_install, install_detail = _install_codestrata(
            engine_root=engine_root,
            venv_dir=venv_dir,
            method=installation_method,
            env=install_env,
        )
        if not ok_install:
            report = VerificationReport(
                ok=False,
                verdict="fail_install",
                catalog_id=catalog.catalog_id,
                installation_method=installation_method,
                platform=platform.platform(),
                python_version=platform.python_version(),
                failures=(f"install_failed:{install_detail}",),
                limitations=tuple(limitations),
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
            report.write_json(out / "repository-assessment-verification.json")
            return report

        codestrata = venv_codestrata(venv_dir)
        run_env = assessment_environ(with_venv_path(base_env, venv_dir), offline=True)
        cli_version = _cli_version(codestrata, run_env)

        allow_network = with_catalog_network and not local_only

        # A — catalog (may fail with qualification gap)
        scenarios.append(
            scenario_a_catalog(
                codestrata=codestrata,
                catalog=catalog,
                work_root=work_parent / "A",
                codestrata_root=monorepo,
                env=run_env,
                allow_network=allow_network,
            )
        )

        # B–N local harness scenarios
        fixture = contract.local_fixture_relative
        scenarios.append(
            scenario_b_local_fixture(
                codestrata=codestrata,
                monorepo_root=monorepo,
                work_root=work_parent / "B",
                fixture_relative=fixture,
                env=run_env,
            )
        )
        scenarios.append(
            scenario_c_spaces(
                codestrata=codestrata,
                monorepo_root=monorepo,
                work_root=work_parent / "C",
                fixture_relative=fixture,
                env=run_env,
            )
        )
        scenarios.append(
            scenario_d_nested(
                codestrata=codestrata,
                work_root=work_parent / "D",
                env=run_env,
            )
        )
        scenarios.append(
            scenario_e_empty(
                codestrata=codestrata,
                work_root=work_parent / "E",
                env=run_env,
            )
        )
        scenarios.append(
            scenario_f_unsupported(
                codestrata=codestrata,
                work_root=work_parent / "F",
                env=run_env,
            )
        )
        scenarios.append(
            scenario_g_malformed_config(
                codestrata=codestrata,
                work_root=work_parent / "G",
                env=run_env,
            )
        )
        scenarios.append(
            scenario_h_missing_config(
                codestrata=codestrata,
                work_root=work_parent / "H",
                env=run_env,
            )
        )
        scenarios.append(
            scenario_i_invalid_output(
                codestrata=codestrata,
                work_root=work_parent / "I",
                env=run_env,
            )
        )
        scenarios.append(
            scenario_j_existing_artifacts(
                codestrata=codestrata,
                monorepo_root=monorepo,
                work_root=work_parent / "J",
                fixture_relative=fixture,
                env=run_env,
            )
        )
        scenarios.append(
            scenario_k_failed_assessment(
                codestrata=codestrata,
                work_root=work_parent / "K",
                env=run_env,
            )
        )
        scenarios.append(
            scenario_l_noninteractive(
                codestrata=codestrata,
                monorepo_root=monorepo,
                work_root=work_parent / "L",
                fixture_relative=fixture,
                env=run_env,
            )
        )
        scenarios.append(
            scenario_m_offline(
                codestrata=codestrata,
                monorepo_root=monorepo,
                work_root=work_parent / "M",
                fixture_relative=fixture,
                env=run_env,
            )
        )
        scenarios.append(
            scenario_n_determinism(
                codestrata=codestrata,
                monorepo_root=monorepo,
                work_root=work_parent / "N",
                fixture_relative=fixture,
                env=run_env,
            )
        )

        for item in scenarios:
            warnings.extend(item.warnings)
            limitations.extend(item.limitations)
            if item.ok:
                continue
            if local_only and _scenario_is_catalog_gap(item):
                # Expected under local-only / unqualified catalog.
                continue
            failures.append(f"{item.scenario_id}:{','.join(item.failures) or item.detail}")

        gap_only = (
            local_only
            and all(s.ok or _scenario_is_catalog_gap(s) for s in scenarios)
            and any(_scenario_is_catalog_gap(s) for s in scenarios)
        )
        ok = not failures
        if gap_only and ok:
            verdict = "pass_with_catalog_qualification_gap"
        elif ok:
            verdict = "pass"
        else:
            verdict = "fail"

        report = VerificationReport(
            ok=ok,
            verdict=verdict,
            catalog_id=catalog.catalog_id,
            installation_method=installation_method,
            platform=platform.platform(),
            python_version=platform.python_version(),
            cli_version=cli_version,
            scenarios=tuple(scenarios),
            warnings=tuple(dict.fromkeys(warnings)),
            failures=tuple(failures),
            limitations=tuple(dict.fromkeys(limitations)),
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        payload = report.to_dict()
        leaks = report_contains_forbidden_leak(payload)
        if leaks:
            report = VerificationReport(
                ok=False,
                verdict="fail_privacy_leak",
                catalog_id=catalog.catalog_id,
                installation_method=installation_method,
                platform=platform.platform(),
                python_version=platform.python_version(),
                cli_version=cli_version,
                scenarios=tuple(scenarios),
                warnings=tuple(dict.fromkeys(warnings)),
                failures=tuple([*failures, f"privacy_leak:{','.join(leaks)}"]),
                limitations=tuple(dict.fromkeys(limitations)),
                elapsed_ms=(time.perf_counter() - started) * 1000,
            )
        report.write_json(out / "repository-assessment-verification.json")
        return report
    finally:
        if not keep_output:
            shutil.rmtree(work_parent, ignore_errors=True)
