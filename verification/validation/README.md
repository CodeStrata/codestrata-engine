"""E15.1 corpus pins and E15.2 regression harness.

Maintainer-only. Default tests **do not** clone or assess the 50 remotes.
Three-tier remote execution is E15.3 / G50.

```bash
cd engine
python -m verification.validation --json --write-docs
python -m verification.validation.regression --json --write-docs
python -m verification.validation.release_gate --json --write-docs
python -m pytest tests/verification/validation --import-mode=importlib -q
```

Set `CODESTRATA_RUN_REMOTE_VALIDATION=1` only on an authorized maintainer host to
attempt full remote tier assesses; default tests keep pin identity and ledgers.
