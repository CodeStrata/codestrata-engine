"""Architecture: the adapter's imports, its credential boundary, and no network in tests."""

from __future__ import annotations

import ast
from pathlib import Path

import codestrata.ai.provider_adapters.openai as openai_adapter_package

# The adapter is a leaf: it may reach the contracts, the OpenAI SDK, the
# settings types, and the two narrow legacy helpers it must stay compatible
# with — nothing else inside codestrata.
_ALLOWED_CODESTRATA_PREFIXES: tuple[str, ...] = (
    "codestrata.ai.provider_adapters",
    "codestrata.ai.provider_contracts",
    "codestrata.ai.prompts.models",
    "codestrata.ai.providers.exceptions",
    "codestrata.ai.providers.models",
    "codestrata.ai.providers.parsing",
    "codestrata.config.settings",
)

_FORBIDDEN_MODULE_PREFIXES: tuple[str, ...] = (
    "boto3",
    "botocore",
    "codestrata.analytics",
    "codestrata.application",
    "codestrata.cli",
    "codestrata.datalake",
    "codestrata.platform",
    "codestrata.reporting",
    "codestrata.telemetry",
    "cursor",
    "vscode",
)

# Only the credential boundary may import the SDK or read the environment.
_CREDENTIAL_BOUNDARY_MODULE = "client.py"


def _package_dir() -> Path:
    return Path(openai_adapter_package.__file__).resolve().parent


def _modules() -> list[Path]:
    return sorted(_package_dir().glob("*.py"))


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_expected_modules_are_present() -> None:
    assert {path.name for path in _modules()} == {
        "__init__.py",
        "adapter.py",
        "capabilities.py",
        "client.py",
        "configuration.py",
        "diagnostics.py",
        "error_mapping.py",
        "factory.py",
        "legacy_bridge.py",
        "request_mapping.py",
        "response_mapping.py",
        "usage_mapping.py",
    }


def test_no_module_imports_a_forbidden_layer() -> None:
    offenders: dict[str, set[str]] = {}
    for path in _modules():
        hits = {
            name
            for name in _imported_module_names(path)
            if any(
                name == prefix or name.startswith(prefix + ".")
                for prefix in _FORBIDDEN_MODULE_PREFIXES
            )
        }
        if hits:
            offenders[path.name] = hits
    assert offenders == {}, f"forbidden imports found: {offenders}"


def test_internal_codestrata_imports_stay_inside_the_allowed_set() -> None:
    offenders: dict[str, set[str]] = {}
    for path in _modules():
        hits = {
            name
            for name in _imported_module_names(path)
            if name.startswith("codestrata.")
            and not name.startswith(_ALLOWED_CODESTRATA_PREFIXES)
        }
        if hits:
            offenders[path.name] = hits
    assert offenders == {}, f"unexpected codestrata dependencies: {offenders}"


def test_only_the_client_module_imports_the_openai_sdk() -> None:
    importers = {
        path.name
        for path in _modules()
        if any(
            name == "openai" or name.startswith("openai.")
            for name in _imported_module_names(path)
        )
    }

    assert importers == {_CREDENTIAL_BOUNDARY_MODULE}


def test_only_the_client_module_imports_os() -> None:
    importers = {
        path.name for path in _modules() if "os" in _imported_module_names(path)
    }

    assert importers == {_CREDENTIAL_BOUNDARY_MODULE}


def _attribute_accesses(path: Path) -> set[str]:
    """Return ``module.attribute`` pairs actually accessed in code, ignoring prose."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    accesses: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            accesses.add(f"{node.value.id}.{node.attr}")
        elif isinstance(node, ast.Name):
            accesses.add(node.id)
    return accesses


def test_no_module_reads_the_environment_outside_the_credential_boundary() -> None:
    offenders = {
        path.name
        for path in _modules()
        if path.name != _CREDENTIAL_BOUNDARY_MODULE
        and {"os.environ", "os.getenv", "getenv"} & _attribute_accesses(path)
    }

    assert offenders == set()


def test_no_module_performs_network_or_subprocess_work() -> None:
    forbidden = {
        "requests",
        "httpx",
        "urllib",
        "subprocess",
        "socket",
    }
    offenders: dict[str, set[str]] = {}
    for path in _modules():
        hits = forbidden & {name.split(".")[0] for name in _imported_module_names(path)}
        if hits:
            offenders[path.name] = hits

    assert offenders == {}


def test_no_module_sleeps() -> None:
    offenders = {
        path.name for path in _modules() if "time.sleep" in _attribute_accesses(path)
    }

    assert offenders == set()


def test_no_openrouter_reference_anywhere_in_the_adapter() -> None:
    offenders = {
        path.name
        for path in _modules()
        if "openrouter" in path.read_text(encoding="utf-8").lower()
    }

    assert offenders == set()


def test_importing_the_package_does_not_import_the_openai_sdk() -> None:
    """A cold import of the adapter must not pull in the optional extra."""

    import subprocess
    import sys

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "import codestrata.ai.provider_adapters.openai.factory as factory\n"
            "factory.build_openai_provider()\n"
            "print('openai' in sys.modules)\n",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[4],
        env={"PYTHONPATH": "src:.", "PATH": "/usr/bin:/bin"},
    )

    assert completed.stdout.strip().endswith("False")
