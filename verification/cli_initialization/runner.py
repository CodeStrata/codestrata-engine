"""SV.3 CLI initialization verification runner."""

from __future__ import annotations

import platform
import shutil
import sys
import tempfile
import time
import venv
from pathlib import Path

from verification.cli_initialization.contract import (
    InitializationContract,
    default_contract,
)
from verification.cli_initialization.models import ScenarioResult, VerificationReport
from verification.cli_initialization.reporting import report_contains_forbidden_leak
from verification.cli_initialization.scenarios import (
    run_scenario_a_minimal,
    run_scenario_b_empty,
    run_scenario_c_existing_valid,
    run_scenario_d_malformed,
    run_scenario_e_unwritable,
    run_scenario_f_nested,
    run_scenario_g_spaces,
    run_scenario_h_noninteractive,
    run_scenario_i_unsupported,
    run_scenario_j_unrelated,
    run_scenario_k_determinism,
)
from verification.cli_installation.environment import (
    engine_root_from_package,
    scrub_environ,
    venv_codestrata,
    venv_python,
    with_venv_path,
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
            "installed non-editable path" if proc.returncode == 0 else proc.stderr[-500:]
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
            return False, f"wheel build failed: {build.stderr[-500:]}"
        proc = subprocess.run(
            [str(python), "-m", "pip", "install", str(wheels[-1])],
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
        return proc.returncode == 0, (
            f"installed {wheels[-1].name}" if proc.returncode == 0 else proc.stderr[-500:]
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
    parts = (proc.stdout or "").strip().split()
    return parts[-1] if parts else None


def run_cli_initialization_verification(
    *,
    engine_root: Path | None = None,
    output_dir: Path | None = None,
    contract: InitializationContract | None = None,
    installation_method: str = "pip_path_non_editable",
) -> VerificationReport:
    """Run SV.3 init workflow verification against a clean non-editable CLI."""

    started = time.perf_counter()
    active = contract or default_contract()
    root = (engine_root or engine_root_from_package()).resolve()
    out = (output_dir or (root / "reports" / "verification")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "cli-initialization-verification.json"

    limitations = list(active.notes)
    warnings: list[str] = []
    scenarios: list[ScenarioResult] = []

    tmp = Path(tempfile.mkdtemp(prefix="codestrata-sv3-init-"))
    try:
        venv_dir = tmp / "venv"
        venv.create(venv_dir, with_pip=True, clear=True)
        host_env = scrub_environ()
        env = with_venv_path(host_env, venv_dir)
        # Isolate HOME/config so init never touches developer state.
        fake_home = tmp / "home"
        fake_home.mkdir()
        env["HOME"] = str(fake_home)
        env["USERPROFILE"] = str(fake_home)
        env.pop("PYTHONPATH", None)

        ok_install, install_detail = _install_codestrata(
            engine_root=root,
            venv_dir=venv_dir,
            method=installation_method,
            env=env,
        )
        codestrata = venv_codestrata(venv_dir)
        if not ok_install or not codestrata.exists():
            report = VerificationReport(
                ok=False,
                verdict="fail",
                installation_method=installation_method,
                platform=sys.platform,
                python_version=platform.python_version(),
                failures=("install_failed",),
                warnings=(f"install_detail_class={installation_method}",),
                limitations=tuple(limitations),
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
            )
            report.write_json(report_path)
            return report

        version = _cli_version(codestrata, env)
        work = tmp / "repos"
        work.mkdir()

        scenario_runners = [
            ("A", lambda: run_scenario_a_minimal(work / "A", codestrata=codestrata, env=env, contract=active)),
            ("B", lambda: run_scenario_b_empty(work / "B", codestrata=codestrata, env=env)),
            ("C", lambda: run_scenario_c_existing_valid(work / "C", codestrata=codestrata, env=env)),
            ("D", lambda: run_scenario_d_malformed(work / "D", codestrata=codestrata, env=env)),
            ("E", lambda: run_scenario_e_unwritable(work / "E", codestrata=codestrata, env=env)),
            ("F", lambda: run_scenario_f_nested(work / "F", codestrata=codestrata, env=env, contract=active)),
            ("G", lambda: run_scenario_g_spaces(work / "G_parent", codestrata=codestrata, env=env)),
            ("H", lambda: run_scenario_h_noninteractive(work / "H", codestrata=codestrata, env=env)),
            ("I", lambda: run_scenario_i_unsupported(work / "I", codestrata=codestrata, env=env)),
            ("J", lambda: run_scenario_j_unrelated(work / "J", codestrata=codestrata, env=env)),
            (
                "K",
                lambda: run_scenario_k_determinism(
                    work / "K1", work / "K2", codestrata=codestrata, env=env
                ),
            ),
        ]

        for _label, runner in scenario_runners:
            result = runner()
            scenarios.append(result)
            warnings.extend(result.warnings)
            limitations.extend(result.limitations)

        failures = [item.scenario_id for item in scenarios if not item.ok]
        for item in scenarios:
            failures.extend(item.failures)

        report = VerificationReport(
            ok=not any(not item.ok for item in scenarios),
            verdict="pass" if not any(not item.ok for item in scenarios) else "fail",
            installation_method=installation_method,
            platform=sys.platform,
            python_version=platform.python_version(),
            cli_version=version,
            scenarios=tuple(scenarios),
            warnings=tuple(dict.fromkeys(warnings)),
            failures=tuple(dict.fromkeys(failures)),
            limitations=tuple(dict.fromkeys(limitations)),
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )
        # Privacy gate before write.
        leaks = report_contains_forbidden_leak(report.to_dict())
        if leaks:
            report = VerificationReport(
                ok=False,
                verdict="fail",
                installation_method=installation_method,
                platform=sys.platform,
                python_version=platform.python_version(),
                cli_version=version,
                scenarios=tuple(scenarios),
                warnings=tuple(dict.fromkeys(warnings)),
                failures=tuple(dict.fromkeys([*failures, *(f"report_leak:{x}" for x in leaks)])),
                limitations=tuple(dict.fromkeys(limitations)),
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
            )
        report.write_json(report_path)
        return report
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
