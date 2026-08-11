"""Clean CLI installation verification runner (SV.2)."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import tempfile
import time
import venv
from pathlib import Path
from typing import Any

from verification.cli_installation.artifacts import (
    config_is_user_writable,
    list_workspace_files,
    validate_init_artifacts,
)
from verification.cli_installation.contract import (
    InstallationContract,
    default_contract,
    os_family_supported,
    python_version_supported,
)
from verification.cli_installation.environment import (
    engine_root_from_package,
    scrub_environ,
    venv_codestrata,
    venv_python,
    with_venv_path,
)
from verification.cli_installation.expected import (
    CommandResultView,
    doctor_ok,
    help_ok,
    help_subcommand_absent,
    init_ok,
    version_flag_ok,
)
from verification.cli_installation.models import (
    VerificationCheck,
    VerificationReport,
    build_report,
)
from verification.cli_installation.scenarios import (
    evaluate_doctor_without_config,
    evaluate_existing_configuration,
    evaluate_invalid_workspace,
    evaluate_missing_dependency,
    evaluate_missing_python_version,
)


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> CommandResultView:
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    return CommandResultView(
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def _record_command(
    name: str,
    argv: list[str],
    result: CommandResultView,
    *,
    ok: bool,
    detail: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "argv": argv,
        "ok": ok,
        "exit_code": result.exit_code,
        "detail": detail,
        "stdout_tail": result.stdout[-1500:],
        "stderr_tail": result.stderr[-1500:],
    }


def _build_wheel(engine_root: Path, dist_dir: Path, env: dict[str, str]) -> tuple[Path | None, str]:
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)
    try:
        import build  # noqa: F401
    except ImportError:
        install_build = _run(
            [sys.executable, "-m", "pip", "install", "build"],
            env=env,
        )
        if install_build.exit_code != 0:
            return None, "failed to install build tooling"

    built = _run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)],
        cwd=engine_root,
        env=env,
    )
    if built.exit_code != 0:
        return None, f"wheel build failed: {built.stderr[-500:]}"
    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        return None, "no wheel produced"
    return wheels[-1], "wheel built"


def run_cli_installation_verification(
    *,
    engine_root: Path | None = None,
    output_dir: Path | None = None,
    contract: InstallationContract | None = None,
    installation_method: str = "pip_wheel",
    keep_workspace: bool = False,
) -> VerificationReport:
    """Run SV.2 clean CLI installation verification.

    Creates a fresh virtualenv, installs CodeStrata without editable mode or
    PYTHONPATH, then exercises version/help/init/doctor and failure scenarios.
    """

    started = time.perf_counter()
    active = contract or default_contract()
    root = (engine_root or engine_root_from_package()).resolve()
    out = (output_dir or (root / "reports" / "verification")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "cli-installation-verification.json"

    checks: list[VerificationCheck] = []
    commands: list[dict[str, Any]] = []
    codestrata_version: str | None = None

    environment: dict[str, Any] = {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": sys.platform,
        "system": platform.system(),
        "machine": platform.machine(),
        "installation_method": installation_method,
        "engine_root": str(root),
        "editable_install": False,
        "developer_pythonpath": False,
    }

    # Prerequisite: host Python / OS contract.
    py_ok = python_version_supported()
    checks.append(
        VerificationCheck(
            name="host_python_supported",
            ok=py_ok,
            detail=(
                f"Python {platform.python_version()} meets minimum "
                f"{active.minimum_python[0]}.{active.minimum_python[1]}"
                if py_ok
                else f"Python {platform.python_version()} below minimum"
            ),
            evidence={"minimum_python": list(active.minimum_python)},
        )
    )
    os_ok = os_family_supported()
    checks.append(
        VerificationCheck(
            name="host_os_supported",
            ok=os_ok,
            detail=f"platform {sys.platform}",
            evidence={"supported": list(active.supported_os_families)},
        )
    )

    # Documented missing-Python scenario (synthetic).
    missing_py_ok, missing_py_detail = evaluate_missing_python_version((3, 11))
    checks.append(
        VerificationCheck(
            name="failure_missing_python_version",
            ok=missing_py_ok,
            detail=missing_py_detail,
            evidence={"example_version": [3, 11]},
        )
    )

    if not py_ok:
        report = build_report(
            ok=False,
            checks=checks,
            environment=environment,
            commands=commands,
            codestrata_version=None,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            report_path=str(report_path),
        )
        report.write_json(report_path)
        return report

    host_env = scrub_environ()
    tmp = Path(tempfile.mkdtemp(prefix="codestrata-sv2-cli-"))
    try:
        workspace = tmp / "workspace"
        workspace.mkdir()
        venv_dir = tmp / "venv"
        dist_dir = tmp / "dist"
        venv.create(venv_dir, with_pip=True, clear=True)
        python = venv_python(venv_dir)
        codestrata_bin = venv_codestrata(venv_dir)
        env = with_venv_path(host_env, venv_dir)
        environment["verification_workspace"] = str(workspace)
        environment["venv"] = str(venv_dir)

        # Ensure no pre-existing configuration.
        pre_config = workspace / "codestrata.toml"
        checks.append(
            VerificationCheck(
                name="no_existing_configuration",
                ok=not pre_config.exists(),
                detail="workspace has no codestrata.toml before init",
                evidence={"path": str(pre_config)},
            )
        )

        # Install
        install_detail = ""
        install_ok = False
        if installation_method == "pip_wheel":
            wheel, install_detail = _build_wheel(root, dist_dir, scrub_environ())
            if wheel is not None:
                installed = _run(
                    [str(python), "-m", "pip", "install", str(wheel)],
                    env=env,
                )
                install_ok = installed.exit_code == 0
                install_detail = (
                    f"installed {wheel.name}"
                    if install_ok
                    else f"pip install wheel failed: {installed.stderr[-500:]}"
                )
                environment["artifact"] = wheel.name
            else:
                install_ok = False
        elif installation_method == "pip_sdist":
            # Build sdist then install.
            if dist_dir.exists():
                shutil.rmtree(dist_dir)
            dist_dir.mkdir(parents=True)
            built = _run(
                [sys.executable, "-m", "build", "--sdist", "--outdir", str(dist_dir)],
                cwd=root,
                env=scrub_environ(),
            )
            sdists = sorted(dist_dir.glob("*.tar.gz"))
            if built.exit_code == 0 and sdists:
                installed = _run(
                    [str(python), "-m", "pip", "install", str(sdists[-1])],
                    env=env,
                )
                install_ok = installed.exit_code == 0
                install_detail = (
                    f"installed {sdists[-1].name}"
                    if install_ok
                    else installed.stderr[-500:]
                )
                environment["artifact"] = sdists[-1].name
            else:
                install_detail = f"sdist build failed: {built.stderr[-500:]}"
        elif installation_method == "pip_path_non_editable":
            installed = _run(
                [str(python), "-m", "pip", "install", str(root)],
                env=env,
            )
            install_ok = installed.exit_code == 0
            install_detail = (
                "installed engine path (non-editable)"
                if install_ok
                else installed.stderr[-500:]
            )
            environment["artifact"] = str(root)
        else:
            install_detail = f"unsupported installation_method: {installation_method}"

        checks.append(
            VerificationCheck(
                name="pip_install",
                ok=install_ok,
                detail=install_detail,
                evidence={"method": installation_method, "editable": False},
            )
        )
        checks.append(
            VerificationCheck(
                name="no_editable_install",
                ok=install_ok and installation_method in {
                    "pip_wheel",
                    "pip_sdist",
                    "pip_path_non_editable",
                },
                detail="installation used non-editable pip install",
                evidence={"method": installation_method, "editable": False},
            )
        )
        checks.append(
            VerificationCheck(
                name="no_developer_pythonpath",
                ok="PYTHONPATH" not in env,
                detail="PYTHONPATH absent in verification environment",
            )
        )

        if not install_ok or not codestrata_bin.exists():
            report = build_report(
                ok=False,
                checks=checks,
                environment=environment,
                commands=commands,
                codestrata_version=None,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                report_path=str(report_path),
            )
            report.write_json(report_path)
            return report

        # Missing dependency scenario: import with a throwaway python -c against
        # a fresh empty venv would be expensive; instead verify uninstall leaves
        # import broken after we snapshot success, then reinstall — too heavy.
        # Use a secondary empty venv for the missing-dependency check.
        missing_venv = tmp / "empty-venv"
        venv.create(missing_venv, with_pip=True, clear=True)
        empty_python = venv_python(missing_venv)
        empty_env = with_venv_path(host_env, missing_venv)
        missing_import = _run(
            [str(empty_python), "-c", "import codestrata"],
            env=empty_env,
        )
        missing_ok, missing_detail = evaluate_missing_dependency(
            import_exit_code=missing_import.exit_code
        )
        checks.append(
            VerificationCheck(
                name="failure_missing_dependency",
                ok=missing_ok,
                detail=missing_detail,
                evidence={"exit_code": missing_import.exit_code},
            )
        )

        # Version
        version_result = _run([str(codestrata_bin), "--version"], cwd=workspace, env=env)
        v_ok, v_detail = version_flag_ok(version_result)
        commands.append(
            _record_command(
                "codestrata_version_flag",
                [str(codestrata_bin), "--version"],
                version_result,
                ok=v_ok,
                detail=v_detail,
            )
        )
        checks.append(
            VerificationCheck(name="codestrata_version_flag", ok=v_ok, detail=v_detail)
        )
        if v_ok:
            # "CodeStrata 0.1.0"
            parts = version_result.stdout.strip().split()
            if len(parts) >= 2:
                codestrata_version = parts[-1]

        version_cmd = _run([str(codestrata_bin), "version"], cwd=workspace, env=env)
        version_cmd_ok = version_cmd.exit_code == 0 and "Engine:" in version_cmd.stdout
        commands.append(
            _record_command(
                "codestrata_version",
                [str(codestrata_bin), "version"],
                version_cmd,
                ok=version_cmd_ok,
                detail="version command ok" if version_cmd_ok else "version command failed",
            )
        )
        checks.append(
            VerificationCheck(
                name="codestrata_version",
                ok=version_cmd_ok,
                detail="version command ok" if version_cmd_ok else "version command failed",
            )
        )

        # Help
        help_result = _run([str(codestrata_bin), "--help"], cwd=workspace, env=env)
        h_ok, h_detail = help_ok(help_result)
        commands.append(
            _record_command(
                "codestrata_help",
                [str(codestrata_bin), "--help"],
                help_result,
                ok=h_ok,
                detail=h_detail,
            )
        )
        checks.append(VerificationCheck(name="codestrata_help", ok=h_ok, detail=h_detail))

        help_sub = _run([str(codestrata_bin), "help"], cwd=workspace, env=env)
        hs_ok, hs_detail = help_subcommand_absent(help_sub)
        commands.append(
            _record_command(
                "codestrata_help_subcommand_absent",
                [str(codestrata_bin), "help"],
                help_sub,
                ok=hs_ok,
                detail=hs_detail,
            )
        )
        checks.append(
            VerificationCheck(
                name="codestrata_help_subcommand_absent",
                ok=hs_ok,
                detail=hs_detail,
            )
        )

        # Doctor before init (expected failure)
        doctor_pre = _run(
            [str(codestrata_bin), "doctor", "--config", str(workspace / "codestrata.toml")],
            cwd=workspace,
            env=env,
        )
        dp_ok, dp_detail = evaluate_doctor_without_config(doctor_pre)
        commands.append(
            _record_command(
                "doctor_without_config",
                [str(codestrata_bin), "doctor"],
                doctor_pre,
                ok=dp_ok,
                detail=dp_detail,
            )
        )
        checks.append(
            VerificationCheck(
                name="failure_doctor_without_config",
                ok=dp_ok,
                detail=dp_detail,
            )
        )

        # Init
        init_result = _run(
            [str(codestrata_bin), "init", "--config", str(workspace / "codestrata.toml")],
            cwd=workspace,
            env=env,
        )
        i_ok, i_detail = init_ok(init_result)
        commands.append(
            _record_command(
                "codestrata_init",
                [str(codestrata_bin), "init"],
                init_result,
                ok=i_ok,
                detail=i_detail,
            )
        )
        checks.append(VerificationCheck(name="codestrata_init", ok=i_ok, detail=i_detail))

        art_ok, art_detail, art_evidence = validate_init_artifacts(
            workspace, contract=active
        )
        art_evidence["files"] = list_workspace_files(workspace)
        art_evidence["writable"] = config_is_user_writable(workspace / "codestrata.toml")
        checks.append(
            VerificationCheck(
                name="init_artifacts",
                ok=art_ok and bool(art_evidence.get("writable")),
                detail=art_detail,
                evidence=art_evidence,
            )
        )

        # Existing configuration failure
        init_again = _run(
            [str(codestrata_bin), "init", "--config", str(workspace / "codestrata.toml")],
            cwd=workspace,
            env=env,
        )
        ex_ok, ex_detail = evaluate_existing_configuration(init_again)
        commands.append(
            _record_command(
                "init_existing_config",
                [str(codestrata_bin), "init"],
                init_again,
                ok=ex_ok,
                detail=ex_detail,
            )
        )
        checks.append(
            VerificationCheck(
                name="failure_existing_configuration",
                ok=ex_ok,
                detail=ex_detail,
            )
        )

        # Doctor after init
        doctor_result = _run(
            [
                str(codestrata_bin),
                "doctor",
                "--config",
                str(workspace / "codestrata.toml"),
                "--output",
                str(workspace / "reports"),
            ],
            cwd=workspace,
            env=env,
        )
        d_ok, d_detail = doctor_ok(doctor_result)
        commands.append(
            _record_command(
                "codestrata_doctor",
                [str(codestrata_bin), "doctor"],
                doctor_result,
                ok=d_ok,
                detail=d_detail,
            )
        )
        checks.append(
            VerificationCheck(name="codestrata_doctor", ok=d_ok, detail=d_detail)
        )

        # Invalid workspace: point --config at a path whose parent is a file
        blocker = workspace / "not-a-directory"
        blocker.write_text("x", encoding="utf-8")
        invalid_target = blocker / "codestrata.toml"
        invalid_init = _run(
            [str(codestrata_bin), "init", "--config", str(invalid_target)],
            cwd=workspace,
            env=env,
        )
        inv_ok, inv_detail = evaluate_invalid_workspace(
            workspace_is_file=blocker.is_file(),
            init_exit_code=invalid_init.exit_code,
            combined_output=invalid_init.combined,
        )
        commands.append(
            _record_command(
                "init_invalid_workspace",
                [str(codestrata_bin), "init", "--config", str(invalid_target)],
                invalid_init,
                ok=inv_ok,
                detail=inv_detail,
            )
        )
        checks.append(
            VerificationCheck(
                name="failure_invalid_workspace",
                ok=inv_ok,
                detail=inv_detail,
            )
        )

        overall = all(item.ok for item in checks)
        report = build_report(
            ok=overall,
            checks=checks,
            environment=environment,
            commands=commands,
            codestrata_version=codestrata_version,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            report_path=str(report_path),
        )
        report.write_json(report_path)
        return report
    finally:
        if keep_workspace:
            environment_note = tmp / "KEEP_WORKSPACE.txt"
            environment_note.write_text(
                "SV.2 keep_workspace=1 — delete this directory manually.\n",
                encoding="utf-8",
            )
        else:
            shutil.rmtree(tmp, ignore_errors=True)
