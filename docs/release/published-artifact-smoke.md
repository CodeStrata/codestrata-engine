# Published-artifact smoke (E16.3 / G52)

Package revision `ENGINE-2026-09-15-R1`.

**This procedure verifies independently downloaded PyPI bytes.** A wheel built from
the monorepo checkout cannot replace it. G52 PASS requires the **candidate** semver
(`0.2.2` today) after E16.2 publish and a recorded wheel digest in
`verification/published_smoke/targets.yaml` (from `release-owner-approval-record.md`).

## Prerequisites

| Requirement | Status |
|---|---|
| G50 PASS | Required |
| E16.2 PASS (candidate on PyPI, approval digests) | **BLOCKED** as of 2026-09-30 — PyPI still `0.2.1` only |
| Clean host | Fresh venv; `PYTHONPATH` unset; not the Engine working tree |
| Five representatives | E15.1 pins in `verification/validation/corpus/representatives.yaml` |

## Five pinned representative repositories

Selected in E15.1 (not invented here):

| Role | ID | GitHub | Pin SHA |
|---|---|---|---|
| supported_java | doris | apache/doris | see `external-large.yaml` |
| supported_js_ts | typescript | microsoft/TypeScript | see corpus |
| mixed_build_monorepo | vscode | microsoft/vscode | see corpus |
| retained_lower_depth | django | django/django | see corpus |
| partial_unsupported | rust | rust-lang/rust | see corpus |

Run `python -m verification.published_smoke --json` for the resolved table.

## Maintainer steps (clean host)

1. Readiness (no install):

   ```bash
   cd engine
   python -m verification.published_smoke --json
   ```

   Exit `0` only when the candidate is on PyPI **and** `candidate_wheel_sha256` in
   `targets.yaml` matches the downloaded wheel.

2. Install candidate with hash verification (after updating `targets.yaml`):

   ```python
   from pathlib import Path
   from verification.published_smoke.install import install_published_semver
   from verification.published_smoke.plan import load_targets

   t = load_targets()
   install_published_semver(
       project=t.pypi_project,
       semver=t.candidate_semver,
       expected_wheel_sha256=t.candidate_wheel_sha256,
       outside_root=Path("/tmp/codestrata-smoke"),
   )
   ```

3. For **each** representative: shallow clone at the pinned SHA (read-only), run
   `codestrata init` / `codestrata assess --repo . --no-ai`, and retain
   `canonical-report.{html,json,sarif.json}` digests in the gate log under
   `engine/.quality-runs/<id>/`.

4. Exercise **no-consent** defaults: `codestrata telemetry status --json` (disabled
   by default; no outbound collection without opt-in).

5. Exercise **MCP** surface: `codestrata mcp --help` and a read-only tool invocation
   against local assessment artifacts (requires `[mcp]` extra if tools are invoked).

6. Run one **known comparison** using pinned `AnalysisResult` fixtures or a controlled
   base/head pair (see `engine/docs/contracts/E11.3-installed-journeys.md`).

7. Record wheel SHA-256, commands, exit codes, and skip reasons in
   `engine/docs/implementation/gates/G52.md`.

## Rollback rehearsal (live stable)

Rollback identity is PyPI **`0.2.1`**, digest
`a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18`.
See `baseline.md` and `release-candidate-freeze.md`. Automated guard:
`tests/verification/published_smoke/test_published_smoke.py` (digest check always;
full install journey when `CODESTRATA_RUN_PUBLISHED_SMOKE=1`).

## Blocking regressions

A blocking regression (secret leak, untrusted artifact labeled verified, canonical
nondeterminism, failed clean install, material compatibility break) **stops new
recommendation** and follows the rollback/yank policy in `team-transition-observation.md`
without overwriting immutable PyPI versions.

Platform assessment integration (R04) remains **closed** until this smoke passes on
the **candidate** semver — not on rollback rehearsal alone.
