# Engine integration, hotfix and prerelease isolation (E00.3)

Package revision `ENGINE-2026-09-15-R1`. This file is the Engine-owned
lane and candidate-namespace contract. It is not a release authorization
and it does not edit root workflows.

Inspection status: **PASS**.

## Lanes

| Lane | Ref | Purpose |
|---|---|---|
| Integration | `release/engine-next` | Isolated next-release merge target |
| Short story/epic | `engine/E<id>-<slug>` | One short-lived branch per story; PR into next |
| Stable maintenance | `main` | The one live hotfix lane in this monorepo |
| Hotfix | `hotfix/<id>` | Lands on maintenance, then a recorded backport into next |

Do not stack long-lived epic trains. Community mirror `codestrata-engine`
is a published snapshot of a reviewed Engine tree, not a second
maintenance lane for this backlog.

## CI push coverage

- Workflow: `.github/workflows/ci.yml`
- Push globs: `main, develop, release/**`
- Required glob present: `release/**` → True
- `release/engine-next` matches: True
- Sample story branch matches push filter: False
- Status: **PASS** — push.branches includes release/**

Existing CI already uses `release/**`. This story does not change that pattern.

## Ordinary merges do not publish or move tags

- Workflows considered: .github/workflows/ci.yml, .github/workflows/infrastructure-plan.yml
- Status: **PASS**
- ordinary push/PR workflows do not publish or move stable tags

workflow_dispatch AWS identity/plan/apply remains out of the ordinary
push/PR path. Closing R01 is still an outside-Engine publisher change.

## Candidate namespaces

| Use | Path |
|---|---|
| Candidate venv | `.venv-engine-next` |
| Candidate output | `engine/.tmp-assess/engine-next-candidate/` |
| Versioned candidate output | `engine/.tmp-assess/candidates/{label}/` |
| Quality logs | `engine/.quality-runs/` |
| Live-artifact rollback venv (not a candidate) | `engine/.tmp-assess/e00.1-live-wheel` |

Candidate installs use the candidate venv and a local output directory.
They must not upgrade a live install, reuse `.venv`/`venv`, write
`.codestrata/` snapshots, or rewrite an occupied versioned directory.

## Rollback artifact

- File: `codestrata-0.2.1-py3-none-any.whl`
- Version: `0.2.1`
- SHA-256: `a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18`
- Exact live wheel digest from E00.1. Candidate work must not rewrite this file or treat pyproject/tags as a substitute rollback identity.

## Hotfix flow

1. Land the live fix on `main` (or a `hotfix/` branch merged there).
2. Preserve the exact rollback wheel digest above.
3. Backport into `release/engine-next` with an explicit recorded cherry-pick
   or merge. Automatic promotion of next onto main is forbidden.
4. Do not move stable tags as a side effect of that merge.

## Notes

- This inspection does not publish, tag, deploy or notify.
- R01 publisher identity remains E00.1 BLOCKED; isolation does not close it.
