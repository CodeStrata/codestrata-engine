"""Maintainer runner: assess every pinned corpus repository with the installed Engine.

    cd engine
    CODESTRATA_RUN_REMOTE_VALIDATION=1 \
        python -m verification.validation.release_gate.tier_execute --all

Per repository this clones the pinned SHA outside the checkout, runs
``codestrata init`` then ``codestrata assess --repo . --output reports --no-ai``
from a clean non-editable install, measures wall time and peak RSS, verifies the
assessed tree was not modified, and writes one record under
``verification/validation/corpus/results/``. The release gate reads those
records. Nothing here publishes, tags, or touches the assessed project's build.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import venv
from dataclasses import dataclass
from pathlib import Path

from verification.cli_installation.environment import (
    scrub_environ,
    venv_codestrata,
    venv_python,
    with_venv_path,
)
from verification.repository_assessment.catalog import CatalogEntry, QualifiedRevision
from verification.repository_assessment.clone import clone_qualified_repository
from verification.repository_assessment.commands import assessment_environ
from verification.repository_assessment.workspace import assert_outside_codestrata_tree
from verification.validation.loader import load_bundle
from verification.validation.models import CheckStatus, CorpusTier, RepositoryPin
from verification.validation.release_gate.policy import load_policy
from verification.validation.release_gate.tier_records import (
    BUCKET_GT_100K,
    BUCKET_LE_10K,
    BUCKET_LE_100K,
    RECORD_SCHEMA,
    SUMMARY_SCHEMA,
    TierRecord,
    bucket_for_files,
    default_results_dir,
    load_records,
    measured_budgets,
    source_tree_digest,
    write_record,
    write_summary,
)

# Hang ceilings, not published budgets. A finished run is recorded with its real
# wall time; the published budget is that measured maximum. The <=100k ceiling
# is 6 hours because a 42k-file repository was still assessing at 60 minutes.
ASSESS_TIMEOUT_S = {
    BUCKET_LE_10K: 20 * 60,
    BUCKET_LE_100K: 6 * 60 * 60,
    BUCKET_GT_100K: 12 * 60 * 60,
    "unknown": 6 * 60 * 60,
}
INIT_TIMEOUT_S = 120
CLONE_TIMEOUT_S = 30 * 60
CLONE_TIMEOUT_LARGE_S = 60 * 60
LARGE_REPO_KIB = 2 * 1024 * 1024
APPROVED_MUTATION_PREFIXES = (
    "codestrata.toml",
    "reports/",
    ".codestrata/",
    ".codestrata-artifacts/",
)
_IGNORED_TREE_DIRS = frozenset({".git"})


@dataclass(frozen=True, slots=True)
class InstalledEngine:
    codestrata: Path
    python: Path
    venv_dir: Path
    wheel_path: Path
    wheel_sha256: str
    engine_git_sha: str
    engine_tree_dirty: bool
    source_digest: str


def _cli_argv(installed: InstalledEngine, *args: str) -> list[str]:
    """Invoke the installed CLI inside its interpreter.

    The Windows ``codestrata.exe`` launcher is a few megabytes and spawns Python.
    Measuring that launcher reports the launcher, not the assessment.
    """

    return [str(installed.python), "-c", "from codestrata.cli import app; app()", *args]


class RemoteValidationDisabled(RuntimeError):
    """Raised when the maintainer opt-in variable is not set."""


def require_remote_opt_in(env_name: str) -> None:
    value = os.environ.get(env_name, "").strip().lower()
    if value not in {"1", "true", "yes", "on"}:
        raise RemoteValidationDisabled(
            f"{env_name} is not set; corpus tiers clone public repositories and run only on a "
            "maintainer host"
        )


def _git(engine_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(engine_root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_engine(engine_root: Path, workspace: Path) -> InstalledEngine:
    """Build one wheel from ``engine_root`` and install it into a venv outside the checkout."""

    assert_outside_codestrata_tree(workspace, engine_root)
    dist = workspace / "dist"
    if dist.exists():
        shutil.rmtree(dist, ignore_errors=True)
    dist.mkdir(parents=True, exist_ok=True)
    for stale in dist.glob("*.whl"):
        stale.unlink()
    wheel_cmd = [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist)]
    build = subprocess.run(
        [*wheel_cmd, "--no-build-isolation", str(engine_root)],
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if build.returncode != 0:
        # Fall back to an isolated build when the host interpreter lacks setuptools.
        build = subprocess.run(
            [*wheel_cmd, str(engine_root)],
            check=False,
            capture_output=True,
            text=True,
            timeout=900,
        )
    if build.returncode != 0:
        raise RuntimeError(f"wheel build failed: {(build.stderr or build.stdout)[-600:]}")
    wheels = sorted(dist.glob("codestrata-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one codestrata wheel, found {len(wheels)}")
    wheel = wheels[0]

    venv_dir = _fresh_venv_dir(workspace)
    venv.create(venv_dir, with_pip=True, clear=True)
    python = venv_python(venv_dir)
    env = with_venv_path(scrub_environ(), venv_dir)
    install = subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", str(wheel)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=1200,
    )
    if install.returncode != 0:
        raise RuntimeError(f"wheel install failed: {(install.stderr or install.stdout)[-600:]}")
    codestrata = venv_codestrata(venv_dir)
    if not codestrata.is_file():
        raise RuntimeError("codestrata executable missing after install")
    porcelain = _git(engine_root, "status", "--porcelain", "--", ".")
    return InstalledEngine(
        codestrata=codestrata,
        python=python,
        venv_dir=venv_dir,
        wheel_path=wheel,
        wheel_sha256=_sha256(wheel),
        engine_git_sha=_git(engine_root, "rev-parse", "HEAD"),
        engine_tree_dirty=bool(porcelain),
        source_digest=source_tree_digest(engine_root),
    )


def count_eligible_files(root: Path) -> int:
    total = 0
    for _current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _IGNORED_TREE_DIRS]
        total += len(files)
    return total


def _windows_job_limits():  # type: ignore[no-untyped-def]
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", Basic),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    return Extended


def _assign_windows_job(proc: subprocess.Popen[str]) -> int | None:
    """Put ``proc`` in a job and return the job handle, so child processes count."""

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    extended = _windows_job_limits()
    info = extended()
    info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
    handle = getattr(proc, "_handle", None)
    assigned = handle is not None and kernel32.AssignProcessToJobObject(
        job, wintypes.HANDLE(int(handle))
    )
    if not assigned:
        kernel32.CloseHandle(job)
        return None
    return int(job)


def _job_peak_rss_bytes(job: int) -> int | None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    info = _windows_job_limits()()
    ok = kernel32.QueryInformationJobObject(
        wintypes.HANDLE(job), 9, ctypes.byref(info), ctypes.sizeof(info), None
    )
    kernel32.CloseHandle(wintypes.HANDLE(job))
    if not ok:
        return None
    return int(info.PeakJobMemoryUsed) or None


def _peak_rss_bytes(proc: subprocess.Popen[str]) -> int | None:
    """Peak resident memory of the direct child. Windows: PeakWorkingSetSize."""

    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        handle = getattr(proc, "_handle", None)
        if handle is None:
            return None
        counters = _Counters()
        counters.cb = ctypes.sizeof(_Counters)
        try:
            psapi = ctypes.WinDLL("psapi")
            ok = psapi.GetProcessMemoryInfo(
                wintypes.HANDLE(int(handle)), ctypes.byref(counters), counters.cb
            )
        except OSError:
            return None
        return int(counters.PeakWorkingSetSize) if ok else None
    try:
        import resource
    except ImportError:
        return None
    usage = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return int(usage) if sys.platform == "darwin" else int(usage) * 1024


def _windows_tree_working_set(root_pid: int) -> int | None:
    """Current working set of ``root_pid`` and its descendants.

    The Windows ``python.exe`` in a venv is a launcher. Peak memory of that
    process is a few megabytes; the interpreter it starts holds the assessment.
    """

    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snap = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return None
    entry = Entry()
    entry.dwSize = ctypes.sizeof(Entry)
    children: dict[int, list[int]] = {}
    found = kernel32.Process32FirstW(snap, ctypes.byref(entry))
    while found:
        children.setdefault(int(entry.th32ParentProcessID), []).append(int(entry.th32ProcessID))
        found = kernel32.Process32NextW(snap, ctypes.byref(entry))
    kernel32.CloseHandle(snap)

    pending = [root_pid]
    pids: list[int] = []
    while pending:
        pid = pending.pop()
        pids.append(pid)
        pending.extend(children.get(pid, []))

    psapi = ctypes.WinDLL("psapi")
    total = 0
    seen = False
    access = 0x0400 | 0x0010  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
    for pid in pids:
        handle = kernel32.OpenProcess(access, False, pid)
        if not handle:
            continue
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            total += int(counters.WorkingSetSize)
            seen = True
        kernel32.CloseHandle(handle)
    return total if seen else None


def _sample_peak(proc: subprocess.Popen[str], stop: threading.Event, holder: list[int]) -> None:
    while not stop.is_set():
        if sys.platform == "win32":
            current = _windows_tree_working_set(proc.pid)
            if current is not None and current > holder[0]:
                holder[0] = current
        stop.wait(0.5)


def _kill_tree(proc: subprocess.Popen[str]) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            check=False,
            capture_output=True,
            timeout=60,
        )
    else:
        proc.kill()
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        pass


@dataclass(frozen=True, slots=True)
class CommandRun:
    exit_code: int
    wall_seconds: float
    peak_rss_bytes: int | None
    timed_out: bool
    stderr_tail: str
    has_traceback: bool


def run_measured(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_s: float,
) -> CommandRun:
    started = time.perf_counter()
    proc = subprocess.Popen(
        argv,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    job = _assign_windows_job(proc) if sys.platform == "win32" else None
    sampled = [0]
    stop = threading.Event()
    sampler = threading.Thread(target=_sample_peak, args=(proc, stop, sampled), daemon=True)
    sampler.start()
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        stdout, stderr = proc.communicate()
    stop.set()
    sampler.join(timeout=2)
    elapsed = time.perf_counter() - started
    peak = _peak_rss_bytes(proc)
    if sampled[0] > (peak or 0):
        peak = sampled[0]
    if job is not None:
        job_peak = _job_peak_rss_bytes(job)
        if job_peak is not None and (peak is None or job_peak > peak):
            peak = job_peak
    combined = f"{stdout}\n{stderr}".lower()
    tail = (stderr or stdout or "")[-1200:].replace(str(cwd), "<repo>")
    return CommandRun(
        exit_code=124 if timed_out else proc.returncode,
        wall_seconds=elapsed,
        peak_rss_bytes=peak,
        timed_out=timed_out,
        stderr_tail=tail,
        has_traceback="traceback (most recent call last)" in combined,
    )


def unapproved_mutations(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        return ["git status failed"]
    bad: list[str] = []
    for line in proc.stdout.splitlines():
        rel = line[3:].strip().strip('"').replace("\\", "/")
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1]
        if rel.startswith(APPROVED_MUTATION_PREFIXES) or "/.codestrata/" in f"/{rel}":
            continue
        bad.append(rel)
    return bad


def find_current_assessment(output_root: Path) -> Path | None:
    candidates = [
        path.parent
        for path in output_root.rglob("canonical-report.html")
        if path.parent.name == "current"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _catalog_entry(pin: RepositoryPin) -> CatalogEntry:
    return CatalogEntry(
        id=pin.id,
        project_name=pin.id,
        github_repository=pin.github_repository,
        github_url=pin.github_url,
        language_group=pin.language_group,
        candidate_category=pin.project_shape,
        license=pin.license,
        qualified_revision=QualifiedRevision("commit", pin.sha.lower()),
        enabled_for_smoke=True,
        selection_reason="M33 corpus pin",
    )


def _now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def _record(
    pin: RepositoryPin,
    installed: InstalledEngine,
    *,
    status: CheckStatus,
    detail: str,
    stage: str,
    checked_out_sha: str | None = None,
    exit_code: int | None = None,
    wall_seconds: float | None = None,
    peak_rss_bytes: int | None = None,
    eligible_files: int | None = None,
    canonical_sha256: str | None = None,
    findings_sha256: str | None = None,
) -> TierRecord:
    return TierRecord(
        schema=RECORD_SCHEMA,
        repository_id=pin.id,
        tier=pin.tier.value,
        pin_sha=pin.sha,
        checked_out_sha=checked_out_sha,
        status=status.value,
        detail=detail[:400],
        stage=stage,
        exit_code=exit_code,
        wall_seconds=None if wall_seconds is None else round(wall_seconds, 3),
        peak_rss_bytes=peak_rss_bytes,
        eligible_files=eligible_files,
        bucket=bucket_for_files(eligible_files),
        depth_class=pin.depth_class,
        source_tree_digest=installed.source_digest,
        engine_git_sha=installed.engine_git_sha,
        engine_tree_dirty=installed.engine_tree_dirty,
        wheel_sha256=installed.wheel_sha256,
        canonical_sha256=canonical_sha256,
        findings_sha256=findings_sha256,
        host=f"{platform.system()} {platform.release()} cpu={os.cpu_count()}",
        python=platform.python_version(),
        recorded_at=_now(),
    )


def assess_pin(
    pin: RepositoryPin,
    installed: InstalledEngine,
    *,
    workspace: Path,
    log_dir: Path | None,
) -> TierRecord:
    repo = workspace / "repos" / pin.id
    home = workspace / "homes" / pin.id
    _remove_tree(repo)
    _remove_tree(home)
    home.mkdir(parents=True)
    clone_timeout = CLONE_TIMEOUT_LARGE_S if pin.size_kib >= LARGE_REPO_KIB else CLONE_TIMEOUT_S
    try:
        clone = clone_qualified_repository(_catalog_entry(pin), repo, timeout_s=clone_timeout)
        if not clone.ok:
            return _record(
                pin,
                installed,
                status=CheckStatus.BLOCKED,
                detail=f"clone: {clone.detail}",
                stage="clone",
                checked_out_sha=clone.checked_out_sha,
            )
        eligible = count_eligible_files(repo)
        bucket = bucket_for_files(eligible)
        env = assessment_environ(scrub_environ(), offline=True)
        env = with_venv_path(env, installed.venv_dir)
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
        env["XDG_CONFIG_HOME"] = str(home / ".config")
        env["XDG_CACHE_HOME"] = str(home / ".cache")
        env["CODESTRATA_KNOWLEDGE_DIRECTORY"] = str(home / "knowledge")
        env.pop("CODESTRATA_RUN_REMOTE_VALIDATION", None)

        # A repository that ships its own codestrata.toml (the dogfood pin) is
        # assessed with that configuration; ``init`` refuses to overwrite it.
        if (repo / "codestrata.toml").is_file():
            init = CommandRun(
                exit_code=0,
                wall_seconds=0.0,
                peak_rss_bytes=None,
                timed_out=False,
                stderr_tail="",
                has_traceback=False,
            )
        else:
            init = run_measured(
                _cli_argv(installed, "init"),
                cwd=repo,
                env=env,
                timeout_s=INIT_TIMEOUT_S,
            )
        if init.exit_code != 0 or init.has_traceback:
            _write_log(log_dir, pin.id, "init", init.stderr_tail)
            return _record(
                pin,
                installed,
                status=CheckStatus.FAIL,
                detail=f"init exit {init.exit_code}",
                stage="init",
                checked_out_sha=clone.checked_out_sha,
                exit_code=init.exit_code,
                eligible_files=eligible,
            )

        assess = run_measured(
            _cli_argv(installed, "assess", "--repo", ".", "--output", "reports", "--no-ai"),
            cwd=repo,
            env=env,
            timeout_s=ASSESS_TIMEOUT_S[bucket],
        )
        _write_log(log_dir, pin.id, "assess", assess.stderr_tail)
        common = {
            "checked_out_sha": clone.checked_out_sha,
            "exit_code": assess.exit_code,
            "wall_seconds": assess.wall_seconds,
            "peak_rss_bytes": assess.peak_rss_bytes,
            "eligible_files": eligible,
        }
        if assess.timed_out:
            cap = ASSESS_TIMEOUT_S[bucket]
            return _record(
                pin,
                installed,
                status=CheckStatus.FAIL,
                detail=f"budget_exceeded: assess did not finish in {cap}s ({bucket})",
                stage="assess",
                **common,
            )
        mutations = unapproved_mutations(repo)
        if mutations:
            return _record(
                pin,
                installed,
                status=CheckStatus.FAIL,
                detail=f"assessed tree modified: {', '.join(mutations[:5])}",
                stage="integrity",
                **common,
            )
        if assess.exit_code != 0 or assess.has_traceback:
            return _record(
                pin,
                installed,
                status=CheckStatus.FAIL,
                detail=f"assess exit {assess.exit_code}"
                + ("; traceback" if assess.has_traceback else ""),
                stage="assess",
                **common,
            )
        current = find_current_assessment(repo / "reports")
        if current is None:
            return _record(
                pin,
                installed,
                status=CheckStatus.FAIL,
                detail="assess exit 0 but no current/canonical-report.html",
                stage="artifacts",
                **common,
            )
        findings = current / "findings.json"
        canonical_digest = _sha256(current / "canonical-report.html")
        findings_digest = _sha256(findings) if findings.is_file() else None
        if pin.depth_class == "partial_unsupported":
            status = CheckStatus.UNSUPPORTED
            detail = "crash-free with explicit unsupported/partial depth; not analytical success"
        else:
            status = CheckStatus.PASS
            detail = f"assess exit 0; {bucket}; artifacts present; tree unchanged"
        return _record(
            pin,
            installed,
            status=status,
            detail=detail,
            stage="complete",
            canonical_sha256=canonical_digest,
            findings_sha256=findings_digest,
            **common,
        )
    finally:
        _remove_tree(repo)
        _remove_tree(home)


def _fresh_venv_dir(workspace: Path) -> Path:
    """Pick a venv directory. A previous run can leave a Windows DLL locked."""

    for name in ("venv", *(f"venv-{index}" for index in range(2, 20))):
        candidate = workspace / name
        _remove_tree(candidate)
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate a venv under {workspace}")


def _remove_tree(path: Path) -> None:
    """Delete a clone; git leaves read-only objects that plain rmtree cannot remove on Windows."""

    if not path.exists():
        return

    def _make_writable(func, target, _exc_info) -> None:  # type: ignore[no-untyped-def]
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
            func(target)
        except OSError:
            pass

    for attempt in range(3):
        try:
            shutil.rmtree(path, onexc=_make_writable)
        except OSError:
            pass
        if not path.exists():
            return
        time.sleep(1 + attempt)
    if path.exists():
        print(f"warning: could not fully remove {path}", file=sys.stderr)


def _write_log(log_dir: Path | None, repo_id: str, stage: str, text: str) -> None:
    if log_dir is None or not text:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{repo_id}.{stage}.log").write_text(text, encoding="utf-8")


def _pins(selected_tiers: set[str], repositories: set[str] | None) -> list[RepositoryPin]:
    bundle = load_bundle()
    pins: list[RepositoryPin] = []
    if CorpusTier.DOGFOOD.value in selected_tiers:
        pins.extend(bundle.dogfood)
    if CorpusTier.EXTERNAL_LARGE.value in selected_tiers:
        pins.extend(bundle.external_large)
    if repositories:
        pins = [pin for pin in pins if pin.id in repositories]
    return pins


def write_run_summary(results_dir: Path, installed: InstalledEngine | None) -> Path:
    records = load_records(results_dir)
    counts: dict[str, int] = {}
    for record in records.values():
        counts[record.status] = counts.get(record.status, 0) + 1
    payload = {
        "schema": SUMMARY_SCHEMA,
        "record_count": len(records),
        "status_counts": dict(sorted(counts.items())),
        "measured_budgets": measured_budgets(records),
        "source_tree_digest": installed.source_digest if installed else None,
        "wheel_sha256": installed.wheel_sha256 if installed else None,
        "engine_git_sha": installed.engine_git_sha if installed else None,
        "engine_tree_dirty": installed.engine_tree_dirty if installed else None,
        "host": f"{platform.system()} {platform.release()} cpu={os.cpu_count()}",
        "python": platform.python_version(),
        "written_at": _now(),
        "note": (
            "peak_rss_bytes is the direct codestrata process; helper subprocesses are "
            "not included. Budget publication is a separate reviewed edit of policy.yaml."
        ),
    }
    return write_summary(results_dir, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assess pinned corpus tiers (E15.3 / M33).")
    parser.add_argument("--engine-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument("--tier", action="append", choices=[t.value for t in CorpusTier])
    parser.add_argument("--all", action="store_true", help="dogfood and external_large tiers")
    parser.add_argument("--repository", action="append", dest="repositories")
    parser.add_argument("--force", action="store_true", help="re-run pins with a fresh record")
    parser.add_argument("--log-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    engine_root = args.engine_root.resolve()
    policy = load_policy()
    try:
        require_remote_opt_in(policy.remote_tier_env)
    except RemoteValidationDisabled as error:
        print(f"BLOCKED: {error}")
        return 2
    tiers = set(args.tier or [])
    if args.all or not tiers:
        tiers = {CorpusTier.DOGFOOD.value, CorpusTier.EXTERNAL_LARGE.value}
    pins = _pins(tiers, set(args.repositories or []) or None)
    if not pins:
        print("no pins selected")
        return 2
    workspace = (args.workspace or Path(tempfile.gettempdir()) / "codestrata-m33-tiers").resolve()
    assert_outside_codestrata_tree(workspace, engine_root)
    workspace.mkdir(parents=True, exist_ok=True)
    results_dir = (args.results_dir or default_results_dir(engine_root)).resolve()
    default_log_dir = engine_root / ".quality-runs" / "m33-tiers"
    log_dir = args.log_dir.resolve() if args.log_dir else default_log_dir

    print(f"installing engine from {engine_root} into {workspace}")
    installed = install_engine(engine_root, workspace)
    print(
        f"wheel {installed.wheel_path.name} sha256={installed.wheel_sha256} "
        f"git={installed.engine_git_sha[:12]} dirty={installed.engine_tree_dirty} "
        f"source_digest={installed.source_digest[:16]}"
    )
    existing = load_records(results_dir)
    failures = 0
    for index, pin in enumerate(pins, start=1):
        previous = existing.get(pin.id)
        if (
            previous is not None
            and not args.force
            and previous.source_tree_digest == installed.source_digest
            and previous.pin_sha == pin.sha
            and previous.check_status in {CheckStatus.PASS, CheckStatus.UNSUPPORTED}
        ):
            print(f"[{index}/{len(pins)}] {pin.id}: kept existing {previous.status}")
            continue
        size_mib = pin.size_kib // 1024
        print(f"[{index}/{len(pins)}] {pin.id}: cloning {pin.sha[:12]} ({size_mib} MiB)")
        started = time.perf_counter()
        record = assess_pin(pin, installed, workspace=workspace, log_dir=log_dir)
        target = write_record(results_dir, record)
        elapsed = time.perf_counter() - started
        if record.check_status in {CheckStatus.FAIL, CheckStatus.ERROR, CheckStatus.BLOCKED}:
            failures += 1
        print(
            f"[{index}/{len(pins)}] {pin.id}: {record.status} in {elapsed:.0f}s "
            f"(assess {record.wall_seconds}s, files {record.eligible_files}, "
            f"rss {record.peak_rss_bytes}) -> {target.name}; {record.detail}"
        )
        write_run_summary(results_dir, installed)
    summary = write_run_summary(results_dir, installed)
    print(f"summary -> {summary}")
    print(f"records not PASS/UNSUPPORTED this run: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
