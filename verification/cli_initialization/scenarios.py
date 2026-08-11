"""Scenario executors for SV.3 initialization verification."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from verification.cli_initialization.artifacts import (
    classify_artifacts,
    forbidden_present,
    required_missing,
)
from verification.cli_initialization.contract import InitializationContract, default_contract
from verification.cli_initialization.models import ScenarioResult
from verification.cli_initialization.reporting import classify_output, command_record, sanitize_text
from verification.cli_initialization.validation import (
    configs_byte_identical,
    validate_generated_config,
)
from verification.cli_initialization.workspace import (
    compare_snapshots,
    create_empty_repository,
    create_minimal_repository,
    create_nested_repository,
    create_space_path_repository,
    create_unsupported_shape_repository,
    create_unrelated_files_repository,
    ensure_no_codestrata_config,
    file_digest,
    list_relative_files,
    make_unwritable,
    restore_writable,
    snapshot_workspace,
)


@dataclass(frozen=True, slots=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


RunFn = Callable[[list[str], Path, dict[str, str]], CommandResult]


def _run_cli(
    codestrata: Path,
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> CommandResult:
    completed = subprocess.run(
        [str(codestrata), *args],
        cwd=str(cwd),
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    return CommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def _fail(
    scenario_id: str,
    detail: str,
    *,
    commands: list[dict[str, Any]] | None = None,
    failures: list[str] | None = None,
    warnings: list[str] | None = None,
    limitations: list[str] | None = None,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        ok=False,
        detail=sanitize_text(detail),
        commands=tuple(commands or ()),
        failures=tuple(failures or [detail]),
        warnings=tuple(warnings or ()),
        limitations=tuple(limitations or ()),
    )


def _success(
    scenario_id: str,
    detail: str,
    *,
    commands: list[dict[str, Any]],
    expected_artifacts: list[str],
    actual_artifacts: list[str],
    digests: dict[str, str],
    classifications: dict[str, str],
    warnings: list[str] | None = None,
    limitations: list[str] | None = None,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        ok=True,
        detail=detail,
        commands=tuple(commands),
        expected_artifacts=tuple(expected_artifacts),
        actual_artifacts=tuple(actual_artifacts),
        artifact_digests=digests,
        classifications=classifications,
        warnings=tuple(warnings or ()),
        limitations=tuple(limitations or ()),
    )


def run_scenario_a_minimal(
    repo: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
    contract: InitializationContract | None = None,
) -> ScenarioResult:
    active = contract or default_contract()
    create_minimal_repository(repo)
    assert ensure_no_codestrata_config(repo)
    before = snapshot_workspace(repo)
    pre_existing = set(before.digests)
    commands: list[dict[str, Any]] = []

    doctor_pre = _run_cli(codestrata, ["doctor", "--config", "codestrata.toml"], cwd=repo, env=env)
    pre_cls = classify_output(doctor_pre.stdout, doctor_pre.stderr, exit_code=doctor_pre.exit_code)
    commands.append(
        command_record(
            "doctor_pre_init",
            ["doctor"],
            exit_code=doctor_pre.exit_code,
            classifications=pre_cls,
            detail="expected failure without config",
        )
    )
    if doctor_pre.exit_code == 0:
        return _fail("A_minimal_supported_repository", "doctor unexpectedly passed before init", commands=commands)

    init = _run_cli(codestrata, ["init"], cwd=repo, env=env)
    init_cls = classify_output(init.stdout, init.stderr, exit_code=init.exit_code)
    commands.append(
        command_record(
            "init",
            ["init"],
            exit_code=init.exit_code,
            classifications=init_cls,
            detail="init scaffold",
        )
    )
    if init.exit_code != 0 or init_cls.get("init") != "success":
        return _fail("A_minimal_supported_repository", "init failed", commands=commands, failures=["init_failed"])
    if init_cls.get("safety") == "traceback_present":
        return _fail("A_minimal_supported_repository", "traceback on init", commands=commands)

    cfg = repo / "codestrata.toml"
    ok_cfg, cfg_failures, _evidence = validate_generated_config(cfg, contract=active)
    if not ok_cfg:
        return _fail(
            "A_minimal_supported_repository",
            "config validation failed",
            commands=commands,
            failures=cfg_failures,
        )

    after = snapshot_workspace(repo)
    integrity_ok, integrity_failures = compare_snapshots(
        before, after, allowed_new={"codestrata.toml"}
    )
    if not integrity_ok:
        return _fail(
            "A_minimal_supported_repository",
            "source integrity failed",
            commands=commands,
            failures=integrity_failures,
        )

    doctor_post = _run_cli(
        codestrata,
        ["doctor", "--config", "codestrata.toml", "--output", "reports"],
        cwd=repo,
        env=env,
    )
    post_cls = classify_output(doctor_post.stdout, doctor_post.stderr, exit_code=doctor_post.exit_code)
    commands.append(
        command_record(
            "doctor_post_init",
            ["doctor"],
            exit_code=doctor_post.exit_code,
            classifications=post_cls,
            detail="doctor after init",
        )
    )
    if doctor_post.exit_code != 0:
        return _fail(
            "A_minimal_supported_repository",
            "doctor failed after init",
            commands=commands,
            failures=["doctor_post_failed"],
        )

    classifications = classify_artifacts(repo, pre_existing=pre_existing, contract=active)
    if forbidden_present(classifications):
        return _fail(
            "A_minimal_supported_repository",
            "forbidden artifacts",
            commands=commands,
            failures=forbidden_present(classifications),
        )
    missing = required_missing(classifications)
    if missing:
        return _fail(
            "A_minimal_supported_repository",
            "required artifacts missing",
            commands=commands,
            failures=missing,
        )

    return _success(
        "A_minimal_supported_repository",
        "minimal repository initialized",
        commands=commands,
        expected_artifacts=list(active.required_artifacts),
        actual_artifacts=list_relative_files(repo),
        digests={"codestrata.toml": file_digest(cfg)},
        classifications=classifications,
        limitations=[
            "Init writes cwd-relative codestrata.toml; no repository-root discovery.",
            "Doctor may create an optional reports/ directory for write probes.",
            "Generated profile key currently nests under [repository] via TOML table rules.",
        ],
    )


def run_scenario_b_empty(
    repo: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
) -> ScenarioResult:
    create_empty_repository(repo)
    before = snapshot_workspace(repo)
    commands: list[dict[str, Any]] = []
    init = _run_cli(codestrata, ["init"], cwd=repo, env=env)
    cls = classify_output(init.stdout, init.stderr, exit_code=init.exit_code)
    commands.append(
        command_record("init", ["init"], exit_code=init.exit_code, classifications=cls, detail="empty repo")
    )
    if init.exit_code != 0:
        return _fail("B_empty_repository", "init failed on empty repo", commands=commands)
    # Must not fabricate source files.
    after = snapshot_workspace(repo)
    ok, failures = compare_snapshots(before, after, allowed_new={"codestrata.toml"})
    if not ok:
        return _fail("B_empty_repository", "fabricated or modified files", commands=commands, failures=failures)
    return _success(
        "B_empty_repository",
        "empty repository accepts init without fabricating sources",
        commands=commands,
        expected_artifacts=["codestrata.toml"],
        actual_artifacts=list_relative_files(repo),
        digests={"codestrata.toml": file_digest(repo / "codestrata.toml")},
        classifications=classify_artifacts(repo, pre_existing=set()),
    )


def run_scenario_c_existing_valid(
    repo: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
) -> ScenarioResult:
    create_minimal_repository(repo)
    first = _run_cli(codestrata, ["init"], cwd=repo, env=env)
    if first.exit_code != 0:
        return _fail("C_existing_valid_configuration", "initial init failed")
    original = (repo / "codestrata.toml").read_bytes()
    second = _run_cli(codestrata, ["init"], cwd=repo, env=env)
    cls = classify_output(second.stdout, second.stderr, exit_code=second.exit_code)
    commands = [
        command_record("init_first", ["init"], exit_code=first.exit_code, classifications={"init": "success"}, detail="first"),
        command_record("init_second", ["init"], exit_code=second.exit_code, classifications=cls, detail="existing"),
    ]
    if second.exit_code == 0:
        return _fail("C_existing_valid_configuration", "silent overwrite", commands=commands)
    if cls.get("init") != "existing_config_refused":
        return _fail("C_existing_valid_configuration", "unexpected message class", commands=commands)
    if (repo / "codestrata.toml").read_bytes() != original:
        return _fail("C_existing_valid_configuration", "config bytes changed", commands=commands)
    if cls.get("safety") == "traceback_present":
        return _fail("C_existing_valid_configuration", "traceback", commands=commands)
    return _success(
        "C_existing_valid_configuration",
        "existing valid config refused without --force",
        commands=commands,
        expected_artifacts=["codestrata.toml"],
        actual_artifacts=list_relative_files(repo),
        digests={"codestrata.toml": file_digest(repo / "codestrata.toml")},
        classifications={"codestrata.toml": "required"},
    )


def run_scenario_d_malformed(
    repo: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
) -> ScenarioResult:
    create_minimal_repository(repo)
    cfg = repo / "codestrata.toml"
    bad = b"[[[not-valid-toml\n"
    cfg.write_bytes(bad)
    result = _run_cli(codestrata, ["init"], cwd=repo, env=env)
    cls = classify_output(result.stdout, result.stderr, exit_code=result.exit_code)
    commands = [
        command_record("init", ["init"], exit_code=result.exit_code, classifications=cls, detail="malformed")
    ]
    if result.exit_code == 0:
        return _fail("D_malformed_existing_configuration", "overwrote malformed config", commands=commands)
    if cfg.read_bytes() != bad:
        return _fail("D_malformed_existing_configuration", "malformed bytes not preserved", commands=commands)
    if cls.get("safety") == "traceback_present":
        return _fail("D_malformed_existing_configuration", "traceback", commands=commands)
    return _success(
        "D_malformed_existing_configuration",
        "malformed config preserved; init refused",
        commands=commands,
        expected_artifacts=["codestrata.toml"],
        actual_artifacts=list_relative_files(repo),
        digests={"codestrata.toml": file_digest(cfg)},
        classifications={"codestrata.toml": "pre_existing"},
    )


def run_scenario_e_unwritable(
    repo: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
) -> ScenarioResult:
    create_minimal_repository(repo)
    if os.name == "nt":
        return ScenarioResult(
            scenario_id="E_unwritable_repository",
            ok=True,
            detail="skipped on Windows (chmod semantics differ)",
            limitations=("Unwritable-directory simulation skipped on Windows.",),
        )
    make_unwritable(repo)
    try:
        result = _run_cli(codestrata, ["init"], cwd=repo, env=env)
    finally:
        restore_writable(repo)
    cls = classify_output(result.stdout, result.stderr, exit_code=result.exit_code)
    commands = [
        command_record("init", ["init"], exit_code=result.exit_code, classifications=cls, detail="unwritable")
    ]
    if result.exit_code == 0:
        return _fail("E_unwritable_repository", "init succeeded on unwritable repo", commands=commands)
    if (repo / "codestrata.toml").exists():
        return _fail("E_unwritable_repository", "partial config created", commands=commands)
    if cls.get("safety") == "traceback_present":
        return _fail("E_unwritable_repository", "traceback", commands=commands)
    return _success(
        "E_unwritable_repository",
        "unwritable repository fails safely",
        commands=commands,
        expected_artifacts=[],
        actual_artifacts=list_relative_files(repo),
        digests={},
        classifications={},
    )


def run_scenario_f_nested(
    repo: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
    contract: InitializationContract | None = None,
) -> ScenarioResult:
    active = contract or default_contract()
    root, nested = create_nested_repository(repo)
    result = _run_cli(codestrata, ["init"], cwd=nested, env=env)
    cls = classify_output(result.stdout, result.stderr, exit_code=result.exit_code)
    commands = [
        command_record("init", ["init"], exit_code=result.exit_code, classifications=cls, detail="nested cwd")
    ]
    if result.exit_code != 0:
        return _fail("F_nested_working_directory", "init failed in nested cwd", commands=commands)
    # Current contract: no root discovery — config appears in nested cwd, not root.
    nested_cfg = nested / "codestrata.toml"
    root_cfg = root / "codestrata.toml"
    if active.discovers_repository_root:
        if not root_cfg.exists() or nested_cfg.exists():
            return _fail("F_nested_working_directory", "root discovery contract mismatch", commands=commands)
    else:
        if not nested_cfg.exists():
            return _fail("F_nested_working_directory", "config not written to nested cwd", commands=commands)
        if root_cfg.exists():
            return _fail("F_nested_working_directory", "config incorrectly written to repo root", commands=commands)
    return _success(
        "F_nested_working_directory",
        "nested cwd writes local config (no upward root discovery)",
        commands=commands,
        expected_artifacts=["pkg/deep/codestrata.toml"],
        actual_artifacts=list_relative_files(root),
        digests={"pkg/deep/codestrata.toml": file_digest(nested_cfg)},
        classifications={"pkg/deep/codestrata.toml": "required"},
        limitations=("Current product does not discover repository root for init.",),
    )


def run_scenario_g_spaces(
    parent: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
) -> ScenarioResult:
    repo = create_space_path_repository(parent)
    result = _run_cli(codestrata, ["init"], cwd=repo, env=env)
    cls = classify_output(result.stdout, result.stderr, exit_code=result.exit_code)
    commands = [
        command_record("init", ["init"], exit_code=result.exit_code, classifications=cls, detail="spaces")
    ]
    if result.exit_code != 0:
        return _fail("G_path_containing_spaces", "init failed with spaces in path", commands=commands)
    if not (repo / "codestrata.toml").is_file():
        return _fail("G_path_containing_spaces", "config missing", commands=commands)
    return _success(
        "G_path_containing_spaces",
        "path with spaces supported",
        commands=commands,
        expected_artifacts=["codestrata.toml"],
        actual_artifacts=list_relative_files(repo),
        digests={"codestrata.toml": file_digest(repo / "codestrata.toml")},
        classifications={"codestrata.toml": "required"},
    )


def run_scenario_h_noninteractive(
    repo: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
) -> ScenarioResult:
    create_minimal_repository(repo)
    isolated = dict(env)
    isolated["CI"] = "1"
    isolated["TERM"] = "dumb"
    isolated.pop("CODESTRATA_PROFILE", None)
    result = _run_cli(codestrata, ["init"], cwd=repo, env=isolated)
    cls = classify_output(result.stdout, result.stderr, exit_code=result.exit_code)
    commands = [
        command_record("init", ["init"], exit_code=result.exit_code, classifications=cls, detail="noninteractive")
    ]
    combined = (result.stdout + result.stderr).lower()
    if result.exit_code != 0:
        return _fail("H_non_interactive_environment", "init blocked", commands=commands)
    for needle in ("password", "consent", "y/n", "continue?", "telemetry upload"):
        if needle in combined:
            return _fail("H_non_interactive_environment", f"prompt-like output: {needle}", commands=commands)
    ok_cfg, failures, evidence = validate_generated_config(repo / "codestrata.toml")
    if not ok_cfg:
        return _fail("H_non_interactive_environment", "config invalid", commands=commands, failures=failures)
    if evidence.get("telemetry_section_present"):
        return _fail("H_non_interactive_environment", "telemetry section unexpectedly present", commands=commands)
    return _success(
        "H_non_interactive_environment",
        "non-interactive init without prompts or silent AI/telemetry enablement",
        commands=commands,
        expected_artifacts=["codestrata.toml"],
        actual_artifacts=list_relative_files(repo),
        digests={"codestrata.toml": file_digest(repo / "codestrata.toml")},
        classifications={"codestrata.toml": "required"},
        limitations=("AI provider key may appear in config; assess still requires --with-ai.",),
    )


def run_scenario_i_unsupported(
    repo: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
) -> ScenarioResult:
    create_unsupported_shape_repository(repo)
    result = _run_cli(codestrata, ["init"], cwd=repo, env=env)
    cls = classify_output(result.stdout, result.stderr, exit_code=result.exit_code)
    commands = [
        command_record("init", ["init"], exit_code=result.exit_code, classifications=cls, detail="unsupported shape")
    ]
    # Current product: init does not inspect repository shape; scaffolding succeeds.
    if result.exit_code != 0:
        return _fail("I_unsupported_repository_shape", "init failed unexpectedly", commands=commands)
    return _success(
        "I_unsupported_repository_shape",
        "init scaffolds regardless of unsupported binary-only shape",
        commands=commands,
        expected_artifacts=["codestrata.toml"],
        actual_artifacts=list_relative_files(repo),
        digests={"codestrata.toml": file_digest(repo / "codestrata.toml")},
        classifications=classify_artifacts(repo, pre_existing={"blob.bin"}),
        limitations=("Init does not claim language support; it only writes configuration.",),
        warnings=("Unsupported shape still receives a Community config scaffold.",),
    )


def run_scenario_j_unrelated(
    repo: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
) -> ScenarioResult:
    create_unrelated_files_repository(repo)
    before = snapshot_workspace(repo)
    result = _run_cli(codestrata, ["init"], cwd=repo, env=env)
    cls = classify_output(result.stdout, result.stderr, exit_code=result.exit_code)
    commands = [
        command_record("init", ["init"], exit_code=result.exit_code, classifications=cls, detail="unrelated")
    ]
    if result.exit_code != 0:
        return _fail("J_existing_unrelated_files", "init failed", commands=commands)
    after = snapshot_workspace(repo)
    ok, failures = compare_snapshots(before, after, allowed_new={"codestrata.toml"})
    if not ok:
        return _fail("J_existing_unrelated_files", "unrelated files changed", commands=commands, failures=failures)
    return _success(
        "J_existing_unrelated_files",
        "unrelated files preserved",
        commands=commands,
        expected_artifacts=["codestrata.toml"],
        actual_artifacts=list_relative_files(repo),
        digests={"codestrata.toml": file_digest(repo / "codestrata.toml")},
        classifications=classify_artifacts(
            repo, pre_existing=set(before.digests)
        ),
    )


def run_scenario_k_determinism(
    first_repo: Path,
    second_repo: Path,
    *,
    codestrata: Path,
    env: dict[str, str],
) -> ScenarioResult:
    create_minimal_repository(first_repo)
    create_minimal_repository(second_repo)
    a = _run_cli(codestrata, ["init"], cwd=first_repo, env=env)
    b = _run_cli(codestrata, ["init"], cwd=second_repo, env=env)
    commands = [
        command_record("init_a", ["init"], exit_code=a.exit_code, classifications=classify_output(a.stdout, a.stderr, exit_code=a.exit_code), detail="first"),
        command_record("init_b", ["init"], exit_code=b.exit_code, classifications=classify_output(b.stdout, b.stderr, exit_code=b.exit_code), detail="second"),
    ]
    if a.exit_code != 0 or b.exit_code != 0:
        return _fail("K_determinism_pair", "init failed in determinism pair", commands=commands)
    if not configs_byte_identical(first_repo / "codestrata.toml", second_repo / "codestrata.toml"):
        return _fail("K_determinism_pair", "generated configs differ", commands=commands)
    cls_a = classify_output(a.stdout, a.stderr, exit_code=a.exit_code)
    cls_b = classify_output(b.stdout, b.stderr, exit_code=b.exit_code)
    # Exclude volatile path-bearing stdout; compare semantic classifications.
    if {k: v for k, v in cls_a.items() if k != "paths"} != {
        k: v for k, v in cls_b.items() if k != "paths"
    }:
        return _fail("K_determinism_pair", "semantic classifications differ", commands=commands)
    return _success(
        "K_determinism_pair",
        "deterministic configuration across clean repositories",
        commands=commands,
        expected_artifacts=["codestrata.toml"],
        actual_artifacts=["codestrata.toml"],
        digests={"codestrata.toml": file_digest(first_repo / "codestrata.toml")},
        classifications={"codestrata.toml": "required"},
        limitations=("CLI stdout may include absolute Wrote paths; excluded from config digests.",),
    )
