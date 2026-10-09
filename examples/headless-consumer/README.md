# Headless consumer example (E14.3)

This folder documents the Engine-owned headless interop flow. Run from `engine/`:

```bash
python -m pytest tests/application/release/test_headless_interop.py -q
python -m verification.headless_interop
```

Use prepared package directories containing `EffectiveRuleSet.json` (see
`tests/contracts/fixtures/e04.3/expected-customer-production.json` for an
independent expected production fixture).

Sign results in a separate process; do not export signer PEM into the analysis
environment.
