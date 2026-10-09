# E15.2 — Deterministic and adversarial regression harness

Maintainer-only. Planted artifacts only in default tests.

```bash
cd engine
python -m verification.validation.regression --json --write-docs
python -m pytest tests/verification/validation --import-mode=importlib -q
```
