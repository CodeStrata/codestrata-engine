"""SV.4 scenario implementations."""

from __future__ import annotations

import os
from pathlib import Path

from verification.repository_assessment.artifacts import (
    enumerate_artifacts,
    find_latest_run_directory,
)
from verification.repository_assessment.catalog import CatalogView, select_smoke_repository
from verification.repository_assessment.clone import clone_qualified_repository
from verification.repository_assessment.commands import (
    assessment_environ,
    canonical_assess_argv,
    run_assess,
    run_doctor,
    run_init,
)
from verification.repository_assessment.contract import REQUIRED_ARTIFACT_NAMES
from verification.repository_assessment.models import ScenarioResult
from verification.repository_assessment.normalization import (
    aggregate_counts,
    compare_normalized,
    load_json,
)
from verification.repository_assessment.reporting import classify_assess_output
from verification.repository_assessment.validation import structural_summary
from verification.repository_assessment.workspace import (
    assert_outside_codestrata_tree,
    capture_inventory,
    compare_source_integrity,
    copy_fixture,
    create_empty_repository,
    create_minimal_python_repository,
    create_nested_layout,
    create_space_path_repository,
    create_unsupported_repository,
    make_unwritable,
    resolve_local_fixture,
)


def _golden_path(
    *,
    codestrata: Path,
    repo: Path,
    env: dict[str, str],
    output: str = "reports",
    run_doctor_first: bool = True,
) -> tuple[bool, list[str], dict]:
    failures: list[str] = []
    meta: dict = {
        "assessment_command": canonical_assess_argv(repo=".", output=output),
        "execution_mode": "deterministic_no_ai",
        "network_behavior": "offline",
        "telemetry_behavior": "disabled",
    }

    before = capture_inventory(repo)

    if run_doctor_first:
        doctor = run_doctor(codestrata, cwd=repo, env=env)
        meta["doctor_exit"] = doctor.exit_code
        if doctor.has_traceback:
            failures.append("doctor_traceback")

    init = run_init(codestrata, cwd=repo, env=env)
    meta["init_exit"] = init.exit_code
    if init.exit_code != 0:
        failures.append(f"init_failed:{init.exit_code}")
        if init.has_traceback:
            failures.append("init_traceback")
        return False, failures, meta
    if not (repo / "codestrata.toml").is_file():
        failures.append("init_missing_config")
        return False, failures, meta

    assess = run_assess(codestrata, cwd=repo, env=env, repo=".", output=output)
    meta["exit_code"] = assess.exit_code
    meta["duration_bucket"] = assess.duration_bucket
    meta["classifications"] = classify_assess_output(
        assess.stdout_sanitized, assess.stderr_sanitized, exit_code=assess.exit_code
    )
    if assess.has_traceback:
        failures.append("assess_traceback")
    if assess.exit_code != 0:
        failures.append(f"assess_failed:{assess.exit_code}")
        return False, failures, meta

    inventory = enumerate_artifacts(repo, output)
    meta["expected_artifacts"] = REQUIRED_ARTIFACT_NAMES
    meta["actual_artifacts"] = inventory.actual_names()
    meta["artifact_validation"] = inventory.validation_map()
    for name in REQUIRED_ARTIFACT_NAMES:
        record = inventory.by_name().get(name)
        if record is None or record.classification == "missing":
            failures.append(f"missing_artifact:{name}")
        elif record.classification == "malformed":
            failures.append(f"malformed_artifact:{name}")

    run_dir = find_latest_run_directory(repo / output)
    if run_dir is not None and (run_dir / "report.json").is_file():
        summary = structural_summary(run_dir / "report.json")
        meta["normalized_summary"] = {
            "structure_ok": summary.get("ok"),
            "schema": (summary.get("structure") or {}).get("schema_version"),
            "traceability": (summary.get("traceability") or {}).get("state"),
            "ai": summary.get("ai"),
            "counts": aggregate_counts(load_json(run_dir / "report.json")),
        }
        if not summary.get("ok"):
            failures.append("structural_validation_failed")
            if summary.get("forbidden_content"):
                failures.append("forbidden_content")
    else:
        failures.append("report_json_missing")

    after = capture_inventory(repo)
    ok_src, src_failures = compare_source_integrity(before, after)
    meta["source_integrity"] = "pass" if ok_src else "fail"
    if not ok_src:
        failures.extend(src_failures[:20])

    for banned in ("node_modules", ".venv", "venv", "target", "dist"):
        if (repo / banned).exists():
            failures.append(f"forbidden_dir_created:{banned}")

    return (not failures), failures, meta


def _result(
    sid: str,
    ok: bool,
    *,
    detail: str = "",
    failures: list[str] | tuple[str, ...] = (),
    warnings: list[str] | tuple[str, ...] = (),
    limitations: list[str] | tuple[str, ...] = (),
    meta: dict | None = None,
    **kwargs,
) -> ScenarioResult:
    meta = meta or {}
    return ScenarioResult(
        scenario_id=sid,
        ok=ok,
        detail=detail,
        assessment_command=tuple(meta.get("assessment_command") or ()),
        execution_mode=str(meta.get("execution_mode") or "deterministic_no_ai"),
        exit_code=meta.get("exit_code"),
        duration_bucket=meta.get("duration_bucket"),
        expected_artifacts=tuple(meta.get("expected_artifacts") or ()),
        actual_artifacts=tuple(meta.get("actual_artifacts") or ()),
        artifact_validation=dict(meta.get("artifact_validation") or {}),
        normalized_summary=dict(meta.get("normalized_summary") or {}),
        source_integrity=str(meta.get("source_integrity") or "not_run"),
        network_behavior=str(meta.get("network_behavior") or "offline"),
        telemetry_behavior=str(meta.get("telemetry_behavior") or "disabled"),
        failures=tuple(failures),
        warnings=tuple(warnings),
        limitations=tuple(limitations),
        **kwargs,
    )


def scenario_a_catalog(
    *,
    codestrata: Path,
    catalog: CatalogView,
    work_root: Path,
    codestrata_root: Path,
    env: dict[str, str],
    allow_network: bool,
) -> ScenarioResult:
    sid = "A_qualified_catalog_repository"
    entry, reason = select_smoke_repository(catalog)
    if entry is None or entry.qualified_revision is None:
        return _result(
            sid,
            False,
            detail="catalog qualification gap",
            catalog_id=catalog.catalog_id,
            failures=["catalog_qualification_gap"],
            limitations=[
                "no catalog entry has qualified_revision (commit|tag); "
                "remote end-to-end assessment not executed",
                reason,
            ],
            meta={"network_behavior": "not_attempted", "source_integrity": "not_run"},
        )

    if not allow_network:
        return _result(
            sid,
            False,
            detail="network disabled; catalog clone skipped",
            catalog_id=catalog.catalog_id,
            repository_id=entry.id,
            project_name=entry.project_name,
            github_repository=entry.github_repository,
            qualified_revision_type=entry.qualified_revision.revision_type,
            qualified_revision_value=entry.qualified_revision.value,
            failures=["network_disabled"],
            limitations=["enable catalog network to clone qualified repositories"],
            meta={"network_behavior": "skipped"},
        )

    dest = work_root / "catalog-clone" / entry.id
    assert_outside_codestrata_tree(dest, codestrata_root)
    clone = clone_qualified_repository(entry, dest)
    if not clone.ok:
        return _result(
            sid,
            False,
            detail=clone.detail,
            catalog_id=catalog.catalog_id,
            repository_id=entry.id,
            project_name=entry.project_name,
            github_repository=entry.github_repository,
            qualified_revision_type=entry.qualified_revision.revision_type,
            qualified_revision_value=entry.qualified_revision.value,
            failures=[f"clone_failed:{clone.detail}"],
            meta={"network_behavior": "clone_only"},
        )

    offline_env = assessment_environ(env, offline=True)
    ok, failures, meta = _golden_path(codestrata=codestrata, repo=dest, env=offline_env)
    meta["network_behavior"] = "clone_then_offline"
    return _result(
        sid,
        ok,
        detail=entry.selection_reason or reason,
        catalog_id=catalog.catalog_id,
        repository_id=entry.id,
        project_name=entry.project_name,
        github_repository=entry.github_repository,
        qualified_revision_type=clone.revision_type,
        qualified_revision_value=clone.revision_value,
        checked_out_sha=clone.checked_out_sha,
        failures=failures,
        meta=meta,
    )


def scenario_b_local_fixture(
    *,
    codestrata: Path,
    monorepo_root: Path,
    work_root: Path,
    fixture_relative: str,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "B_controlled_local_fixture"
    source = resolve_local_fixture(monorepo_root, fixture_relative)
    dest = work_root / "local-fixture"
    copy_fixture(source, dest)
    ok, failures, meta = _golden_path(codestrata=codestrata, repo=dest, env=env)
    return _result(
        sid,
        ok,
        detail=f"fixture={fixture_relative}",
        project_name="sample-js-app",
        failures=failures,
        meta=meta,
        limitations=["local fixture is not a substitute for catalog-backed pinned revision"],
    )


def scenario_c_spaces(
    *,
    codestrata: Path,
    monorepo_root: Path,
    work_root: Path,
    fixture_relative: str,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "C_path_with_spaces"
    source = resolve_local_fixture(monorepo_root, fixture_relative)
    dest = create_space_path_repository(work_root / "spaces", source)
    ok, failures, meta = _golden_path(codestrata=codestrata, repo=dest, env=env)
    return _result(sid, ok, detail="path contains spaces", failures=failures, meta=meta)


def scenario_d_nested(
    *,
    codestrata: Path,
    work_root: Path,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "D_nested_invocation"
    repo, nested = create_nested_layout(work_root / "nested-repo")
    # Init/assess must target repo root via --repo; cwd nested must not write
    # unintended outputs under an alternate tree without documentation.
    before = capture_inventory(repo)
    doctor = run_doctor(codestrata, cwd=nested, env=env)
    init = run_init(codestrata, cwd=nested, env=env)
    failures: list[str] = []
    # Actual contract (SV.3): init writes codestrata.toml into cwd, not repo root discovery.
    nested_config = nested / "codestrata.toml"
    root_config = repo / "codestrata.toml"
    if init.exit_code != 0:
        failures.append(f"init_failed:{init.exit_code}")
    # Document actual behavior: config lands in cwd (nested), not auto-discovered root.
    # Pass repo-relative path for --repo to avoid absolute paths in verification records.
    repo_from_nested = Path(os.path.relpath(repo, nested))
    if nested_config.is_file() and not root_config.is_file():
        assess = run_assess(
            codestrata,
            cwd=nested,
            env=env,
            repo=str(repo_from_nested),
            output=str(repo_from_nested / "reports"),
        )
    elif root_config.is_file():
        assess = run_assess(codestrata, cwd=repo, env=env)
    else:
        failures.append("no_config_written")
        return _result(sid, False, detail="nested init produced no config", failures=failures)

    if assess.exit_code != 0:
        failures.append(f"assess_failed:{assess.exit_code}")
    if assess.has_traceback or doctor.has_traceback or init.has_traceback:
        failures.append("traceback")

    # Ensure reports did not land unexpectedly under nested cwd only.
    if (nested / "reports").exists() and not (repo / "reports").exists():
        failures.append("output_written_only_under_nested_cwd")

    after = capture_inventory(repo)
    # Allow nested codestrata.toml and reports under repo.
    ok_src, src_fail = compare_source_integrity(before, after)
    # Nested config path is under repo — classify: if init wrote into nested, it's a new file.
    # compare_source_integrity will flag nested codestrata.toml as unexpected unless approved.
    # Approved paths only cover repo-root codestrata.toml; nested config is actual contract.
    unexpected = [f for f in src_fail if f.startswith("unexpected_new:") and "codestrata.toml" not in f and "reports/" not in f]
    if unexpected:
        failures.extend(unexpected[:10])

    meta = {
        "assessment_command": assess.argv,
        "exit_code": assess.exit_code,
        "duration_bucket": assess.duration_bucket,
        "source_integrity": "pass" if not unexpected else "fail",
        "execution_mode": "deterministic_no_ai",
        "normalized_summary": {
            "init_cwd_writes_config": nested_config.is_file(),
            "root_config": root_config.is_file(),
            "contract": "no_repository_root_discovery; config written to cwd",
        },
    }
    return _result(
        sid,
        not failures,
        detail="nested cwd; explicit --repo for assessment root",
        failures=failures,
        limitations=["init does not discover repository root; writes codestrata.toml to cwd"],
        meta=meta,
    )


def scenario_e_empty(
    *,
    codestrata: Path,
    work_root: Path,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "E_empty_repository"
    repo = create_empty_repository(work_root / "empty-repo")
    run_init(codestrata, cwd=repo, env=env)
    before = capture_inventory(repo)
    assess = run_assess(codestrata, cwd=repo, env=env)
    failures: list[str] = []
    if assess.has_traceback:
        failures.append("traceback")
    # Safe outcome: non-zero OR zero with honest empty/limited assessment — not fabricated success with fake findings.
    run_dir = find_latest_run_directory(repo / "reports")
    if assess.exit_code == 0 and run_dir and (run_dir / "report.json").is_file():
        doc = load_json(run_dir / "report.json")
        assessment = doc.get("assessment") if isinstance(doc.get("assessment"), dict) else doc
        findings = assessment.get("findings") or []
        # Empty repo should not invent large fabricated finding sets; allow zero/few hygiene findings.
        if isinstance(findings, list) and len(findings) > 50:
            failures.append("suspected_fabricated_analysis")
    after = capture_inventory(repo)
    ok_src, src_fail = compare_source_integrity(before, after)
    if not ok_src:
        failures.extend(src_fail[:10])
    meta = {
        "exit_code": assess.exit_code,
        "duration_bucket": assess.duration_bucket,
        "assessment_command": assess.argv,
        "source_integrity": "pass" if ok_src else "fail",
        "normalized_summary": {"safe_empty_outcome": not failures},
    }
    return _result(sid, not failures, detail="empty repository safe outcome", failures=failures, meta=meta)


def scenario_f_unsupported(
    *,
    codestrata: Path,
    work_root: Path,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "F_unsupported_repository"
    repo = create_unsupported_repository(work_root / "unsupported-repo")
    run_init(codestrata, cwd=repo, env=env)
    assess = run_assess(codestrata, cwd=repo, env=env)
    failures: list[str] = []
    if assess.has_traceback:
        failures.append("traceback")
    # Must not claim false rich success; allow completed deterministic scan with skipped packs.
    if assess.exit_code == 0:
        run_dir = find_latest_run_directory(repo / "reports")
        if run_dir and (run_dir / "report.json").is_file():
            summary = structural_summary(run_dir / "report.json")
            if summary.get("ai", {}).get("executed"):
                failures.append("ai_executed_unexpectedly")
        # False success would be exit 0 with no report — flag that.
        elif not run_dir:
            failures.append("false_success_no_artifacts")
    meta = {
        "exit_code": assess.exit_code,
        "duration_bucket": assess.duration_bucket,
        "assessment_command": assess.argv,
        "normalized_summary": {"unsupported_handled": not failures},
    }
    return _result(sid, not failures, detail="unsupported/plain-text repository", failures=failures, meta=meta)


def scenario_g_malformed_config(
    *,
    codestrata: Path,
    work_root: Path,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "G_malformed_configuration"
    repo = create_minimal_python_repository(work_root / "malformed-config")
    config = repo / "codestrata.toml"
    original = "this is not valid toml [[[\n"
    config.write_text(original, encoding="utf-8")
    before = capture_inventory(repo)
    assess = run_assess(codestrata, cwd=repo, env=env)
    failures: list[str] = []
    if assess.exit_code == 0:
        failures.append("expected_nonzero_exit")
    if assess.has_traceback:
        failures.append("traceback")
    if config.read_text(encoding="utf-8") != original:
        failures.append("config_mutated")
    # No partial successful report artifacts claiming success.
    run_dir = find_latest_run_directory(repo / "reports")
    if run_dir is not None and assess.exit_code != 0:
        # Partial files may exist; must not treat as verified success — we already fail on exit 0.
        pass
    after = capture_inventory(repo)
    ok_src, src_fail = compare_source_integrity(before, after)
    # reports/ creation on failure is acceptable if not claiming success.
    filtered = [f for f in src_fail if not f.startswith("unexpected_new:reports/")]
    if filtered:
        failures.extend(filtered[:10])
    meta = {
        "exit_code": assess.exit_code,
        "assessment_command": assess.argv,
        "source_integrity": "pass" if not filtered else "fail",
        "normalized_summary": {"config_preserved": config.read_text(encoding="utf-8") == original},
    }
    return _result(sid, not failures, detail="malformed config fails before assessment", failures=failures, meta=meta)


def scenario_h_missing_config(
    *,
    codestrata: Path,
    work_root: Path,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "H_missing_configuration"
    repo = create_minimal_python_repository(work_root / "missing-config")
    assess = run_assess(codestrata, cwd=repo, env=env)
    failures: list[str] = []
    if assess.has_traceback:
        failures.append("traceback")
    # Document actual behavior: assess may work with --repo without prior init.
    implicit_init = (repo / "codestrata.toml").is_file()
    meta = {
        "exit_code": assess.exit_code,
        "assessment_command": assess.argv,
        "normalized_summary": {
            "implicit_init": implicit_init,
            "contract": (
                "assess accepts --repo without codestrata.toml; "
                "init is recommended but not always required"
            ),
        },
    }
    # Pass if behavior is deterministic (no traceback) — either fails clearly or succeeds without silent init.
    if implicit_init:
        failures.append("undocumented_implicit_init")
    return _result(
        sid,
        not failures,
        detail="missing config behavior documented",
        failures=failures,
        limitations=["init recommended; assess --repo may proceed without codestrata.toml"],
        meta=meta,
    )


def scenario_i_invalid_output(
    *,
    codestrata: Path,
    work_root: Path,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "I_invalid_output_directory"
    repo = create_minimal_python_repository(work_root / "bad-output")
    run_init(codestrata, cwd=repo, env=env)
    blocked = work_root / "unwritable-out"
    make_unwritable(blocked)
    before = capture_inventory(repo)
    try:
        assess = run_assess(
            codestrata,
            cwd=repo,
            env=env,
            output=str(blocked / "nested"),
        )
    finally:
        # Restore permissions for cleanup.
        blocked.chmod(0o755)

    failures: list[str] = []
    if assess.exit_code == 0:
        # Some platforms may still write; if success, verify no source mutation.
        pass
    if assess.has_traceback:
        failures.append("traceback")
    after = capture_inventory(repo)
    ok_src, src_fail = compare_source_integrity(before, after)
    if not ok_src:
        failures.extend(src_fail[:10])
    # Prefer non-zero on unwritable; if zero, mark warning via limitations.
    limitations: list[str] = []
    if assess.exit_code == 0:
        limitations.append("assess exited 0 against unwritable output on this platform")
    meta = {
        "exit_code": assess.exit_code,
        "assessment_command": assess.argv,
        "source_integrity": "pass" if ok_src else "fail",
    }
    return _result(
        sid,
        not failures,
        detail="invalid/unwritable output directory",
        failures=failures,
        limitations=limitations,
        meta=meta,
    )


def scenario_j_existing_artifacts(
    *,
    codestrata: Path,
    monorepo_root: Path,
    work_root: Path,
    fixture_relative: str,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "J_existing_output_artifacts"
    source = resolve_local_fixture(monorepo_root, fixture_relative)
    dest = work_root / "reuse-output"
    copy_fixture(source, dest)
    run_init(codestrata, cwd=dest, env=env)
    first = run_assess(codestrata, cwd=dest, env=env)
    run1 = find_latest_run_directory(dest / "reports")
    second = run_assess(codestrata, cwd=dest, env=env)
    run2 = find_latest_run_directory(dest / "reports")
    failures: list[str] = []
    if first.exit_code != 0 or second.exit_code != 0:
        failures.append("assess_failed")
    if first.has_traceback or second.has_traceback:
        failures.append("traceback")
    # Timestamped run dirs should not silently overwrite prior run in place.
    if run1 and run2 and run1 == run2:
        # Same directory reuse — document; verify report still valid.
        limitations = ["same run directory reused across consecutive assesses"]
    else:
        limitations = ["timestamped run directories isolate consecutive assessments"]
    if run2 and (run2 / "report.json").is_file():
        summary = structural_summary(run2 / "report.json")
        if not summary.get("ok"):
            failures.append("second_run_malformed")
    meta = {
        "exit_code": second.exit_code,
        "assessment_command": second.argv,
        "normalized_summary": {
            "run1": run1.name if run1 else None,
            "run2": run2.name if run2 else None,
            "isolated": bool(run1 and run2 and run1 != run2),
        },
    }
    return _result(sid, not failures, detail="existing output reuse", failures=failures, limitations=limitations, meta=meta)


def scenario_k_failed_assessment(
    *,
    codestrata: Path,
    work_root: Path,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "K_failed_assessment_safety"
    repo = create_minimal_python_repository(work_root / "fail-assess")
    run_init(codestrata, cwd=repo, env=env)
    # Simulate bounded failure: point --repo at a non-existent path.
    assess = run_assess(codestrata, cwd=repo, env=env, repo=str(repo / "does-not-exist"))
    failures: list[str] = []
    if assess.exit_code == 0:
        failures.append("expected_failure_exit")
    if assess.has_traceback:
        failures.append("traceback")
    run_dir = find_latest_run_directory(repo / "reports")
    if run_dir and (run_dir / "report.json").is_file():
        # If artifacts exist after failure, they must not be treated as success — exit already non-zero.
        pass
    meta = {
        "exit_code": assess.exit_code,
        "assessment_command": assess.argv,
        "normalized_summary": {"failed_safely": assess.exit_code != 0 and not assess.has_traceback},
    }
    return _result(sid, not failures, detail="bounded assessment failure", failures=failures, meta=meta)


def scenario_l_noninteractive(
    *,
    codestrata: Path,
    monorepo_root: Path,
    work_root: Path,
    fixture_relative: str,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "L_non_interactive"
    source = resolve_local_fixture(monorepo_root, fixture_relative)
    dest = work_root / "noninteractive"
    copy_fixture(source, dest)
    # Close stdin simulation via env already CI=1; also pass empty input.
    ok, failures, meta = _golden_path(codestrata=codestrata, repo=dest, env=env)
    if "classifications" in meta and meta["classifications"].get("safety") == "traceback_present":
        failures.append("traceback")
    return _result(sid, ok, detail="CI/non-interactive completion", failures=failures, meta=meta)


def scenario_m_offline(
    *,
    codestrata: Path,
    monorepo_root: Path,
    work_root: Path,
    fixture_relative: str,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "M_offline_deterministic"
    source = resolve_local_fixture(monorepo_root, fixture_relative)
    dest = work_root / "offline"
    copy_fixture(source, dest)
    offline = assessment_environ(env, offline=True)
    offline["http_proxy"] = "http://127.0.0.1:9"
    offline["https_proxy"] = "http://127.0.0.1:9"
    offline["HTTP_PROXY"] = "http://127.0.0.1:9"
    offline["HTTPS_PROXY"] = "http://127.0.0.1:9"
    offline["NO_PROXY"] = ""
    offline["no_proxy"] = ""
    ok, failures, meta = _golden_path(codestrata=codestrata, repo=dest, env=offline)
    meta["network_behavior"] = "proxies_point_to_blackhole"
    if ok:
        ai = (meta.get("normalized_summary") or {}).get("ai") or {}
        if ai.get("executed") or ai.get("provider_invoked"):
            failures.append("ai_network_activity")
            ok = False
    return _result(sid, ok and not failures, detail="offline deterministic mode", failures=failures, meta=meta)


def scenario_n_determinism(
    *,
    codestrata: Path,
    monorepo_root: Path,
    work_root: Path,
    fixture_relative: str,
    env: dict[str, str],
) -> ScenarioResult:
    sid = "N_repeat_run_determinism"
    source = resolve_local_fixture(monorepo_root, fixture_relative)
    # Identical project directory names — folder name can feed inventory/IDs.
    dest_a = work_root / "run-a" / "sample-js-app"
    dest_b = work_root / "run-b" / "sample-js-app"
    copy_fixture(source, dest_a)
    copy_fixture(source, dest_b)
    ok_a, fail_a, meta_a = _golden_path(codestrata=codestrata, repo=dest_a, env=env)
    ok_b, fail_b, meta_b = _golden_path(codestrata=codestrata, repo=dest_b, env=env)
    failures = list(fail_a) + [f"b:{f}" for f in fail_b]
    if not ok_a or not ok_b:
        return _result(sid, False, detail="one or both runs failed", failures=failures, meta=meta_a)

    run_a = find_latest_run_directory(dest_a / "reports")
    run_b = find_latest_run_directory(dest_b / "reports")
    if not run_a or not run_b:
        return _result(sid, False, detail="missing run dirs", failures=["missing_run_dir"], meta=meta_a)

    left = load_json(run_a / "report.json")
    right = load_json(run_b / "report.json")
    same, diffs = compare_normalized(left, right)
    meta = {
        "exit_code": meta_a.get("exit_code"),
        "duration_bucket": meta_a.get("duration_bucket"),
        "assessment_command": meta_a.get("assessment_command"),
        "source_integrity": meta_a.get("source_integrity"),
        "normalized_summary": {
            "determinism_ok": same,
            "diff_categories": diffs,
            "counts_a": aggregate_counts(left),
            "counts_b": aggregate_counts(right),
        },
    }
    if not same:
        failures.extend(diffs)
    return _result(
        sid,
        same and not failures,
        detail="normalized repeat-run comparison",
        failures=failures,
        meta=meta,
        determinism="pass" if same else "fail",
    )
