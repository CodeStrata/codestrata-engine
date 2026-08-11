"""Expected CLI output markers for SV.2."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandResultView:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def combined(self) -> str:
        return f"{self.stdout}\n{self.stderr}"


def version_flag_ok(result: CommandResultView) -> tuple[bool, str]:
    if result.exit_code != 0:
        return False, f"--version exited {result.exit_code}"
    if "CodeStrata" not in result.stdout:
        return False, "--version missing CodeStrata marker"
    return True, "version flag ok"


def help_ok(result: CommandResultView) -> tuple[bool, str]:
    if result.exit_code != 0:
        return False, f"--help exited {result.exit_code}"
    text = result.stdout
    for marker in ("Primary workflow", "init", "doctor", "assess"):
        if marker not in text:
            return False, f"--help missing marker: {marker}"
    return True, "help ok"


def help_subcommand_absent(result: CommandResultView) -> tuple[bool, str]:
    """`codestrata help` is not a command; expect non-zero with guidance."""

    if result.exit_code == 0:
        return False, "`codestrata help` unexpectedly succeeded"
    combined = result.combined.lower()
    if "no such command" not in combined and "--help" not in combined:
        return False, "`codestrata help` failure message unexpected"
    return True, "help subcommand correctly absent"


def init_ok(result: CommandResultView) -> tuple[bool, str]:
    if result.exit_code != 0:
        return False, f"init exited {result.exit_code}"
    if "Wrote" not in result.stdout:
        return False, "init missing Wrote marker"
    if "Success: Configuration ready." not in result.stdout:
        return False, "init missing success marker"
    return True, "init ok"


def doctor_ok(result: CommandResultView) -> tuple[bool, str]:
    if result.exit_code != 0:
        return False, f"doctor exited {result.exit_code}"
    if "All doctor checks passed" not in result.stdout:
        return False, "doctor missing success marker"
    return True, "doctor ok"


def doctor_missing_config_fails(result: CommandResultView) -> tuple[bool, str]:
    if result.exit_code == 0:
        return False, "doctor unexpectedly passed without config"
    if "FAIL" not in result.stdout and "FAIL" not in result.stderr:
        return False, "doctor missing FAIL marker without config"
    if "init" not in result.combined.lower():
        return False, "doctor should suggest codestrata init"
    return True, "doctor correctly fails without config"


def init_existing_config_fails(result: CommandResultView) -> tuple[bool, str]:
    if result.exit_code == 0:
        return False, "init unexpectedly overwrote without --force"
    if "already exists" not in result.combined.lower():
        return False, "init missing already-exists message"
    return True, "init correctly refuses existing config"
