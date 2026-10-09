# E11.3 assessment journey (offline)

Portable first-assessment and compare checks using only paths inside the
installed Engine package and a copied fixture repository.

1. Build the candidate wheel (E14.2 flow): from the Engine root run
   `python -m verification.release_build --output /tmp/codestrata-build`.
2. Create a clean virtualenv **outside** the Engine checkout, install the wheel,
   and leave `PYTHONPATH` unset.
3. Copy `tests/fixtures/e11_3/java-minimal` to a writable directory.
4. Run:

```bash
codestrata init --config ./codestrata.toml
codestrata assess --repo . --no-ai --output ./.codestrata-artifacts/assessments
```

5. Open `./.codestrata-artifacts/assessments/*/current/canonical-report.html`
   locally (no CDN). The first run must say **no baseline** and must not invent
   trends or HTML-calculated scores.

Automated expectations live in
`tests/fixtures/e11_3/expected/first_assessment_expectations.json`.
Pytest coverage: `tests/cli/test_e11_3_assessment_journeys.py`.
