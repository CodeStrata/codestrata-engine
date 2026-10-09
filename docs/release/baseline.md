# Live Engine artifact and release route (E00.1)

This file records **inspected live registry and workflow evidence**.
It is not a release authorization. Package revision `ENGINE-2026-09-15-R1`.

Inspected: `2026-09-17T12:11:47Z`. R01 and PyPI identity rechecked for E16.2 on
**2026-09-30** (workflows unchanged; PyPI still `0.2.1` only). See
`publication-plan-0.2.2.md` and `engine/docs/implementation/gates/E16.2.md`.

Local `engine/pyproject.toml` version `0.2.1` was
**not** used as the live version. Git tags `v0.1.0`, `v0.2.0` were **not** used as the live
version.

## PyPI (`codestrata`)

| | |
|---|---|
| Live version | `0.2.1` |
| Yanked | `False` |
| Known published versions | `0.2.1` |
| Project | https://pypi.org/project/codestrata/0.2.1/ |

| File | Type | SHA-256 | Bytes |
|---|---|---|---|
| `codestrata-0.2.1-py3-none-any.whl` | `bdist_wheel` | `a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18` | 2286589 |
| `codestrata-0.2.1.tar.gz` | `sdist` | `acd8615186977d9a62f3661f8a8d71fe2be380c371c9ea29048f1bb2cd1212e6` | 1673543 |

Pinned install of the live wheel (isolated venv, never the working checkout):

```text
python -m pip install --no-deps --require-hashes -r pypi-live.hashes.txt
# hashes file body:
https://files.pythonhosted.org/packages/df/81/24e41d964e01f557bbb57e41ef88298f91aec776a59fe644570c41840ef5/codestrata-0.2.1-py3-none-any.whl --hash=sha256:a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18
```

## Git identities (stable vs next)

| Repository | Ref | SHA | Kind | Notes |
|---|---|---|---|---|
| `github.com/CodeStrata/codestrata-platform` | `origin/main` | `3f32ce4b82a06162062babf7e8c77451f5761e6a` | `mirror_commit` | Monorepo stable branch (planning baseline). Not a PyPI publisher. |
| `github.com/CodeStrata/codestrata-platform` | `origin/release/engine-next` | `3cb1096d8e3be528db14a4088db968aa582aa696` | `mirror_commit` | Isolated next-release integration branch. Ordinary push runs ci.yml only. |
| `github.com/CodeStrata/codestrata-engine` | `main` | `ca18a660f164f8c2bd9983a81faf1f82094a1abc` | `mirror_commit` | Public Community mirror default branch HEAD (GitHub API 2026-09-17). |
| `github.com/CodeStrata/codestrata-engine` | `refs/tags/v0.2.1` | `ca18a660f164f8c2bd9983a81faf1f82094a1abc` | `git_tag` | Tag matches live PyPI 0.2.1; other tags were not treated as live. |
| `github.com/CodeStrata/codestrata-engine` | `GitHub release v0.2.1` | `a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18` | `release_asset` | Attached wheel digest equals PyPI wheel SHA-256. |

## Container / OCI

No verified public Engine container digest. A 401 from GHCR is **unavailable**,
not proof of absence.

| Registry | Repository | Status | Digest | HTTP | Notes |
|---|---|---|---|---|---|
| `docker.io` | `codestrata (org listing)` | `NOT_FOUND` | `none` | 200 | hub.docker.com/v2/repositories/codestrata/ count=0 |
| `docker.io` | `codestrata/engine` | `NOT_FOUND` | `none` | 404 | No public Docker Hub Engine image at this name. |
| `ghcr.io` | `codestrata/codestrata-engine` | `UNAVAILABLE` | `none` | 401 | Anonymous GHCR list returned 401; not treated as proof of absence. |

## R01 — authorized publisher

**Status: PRESENT (local tree, pending merge and PyPI Trusted Publishing)**

As of **2026-09-30**, the monorepo includes `.github/workflows/engine-pypi-release.yml`
(`workflow_dispatch`, `id-token: write`, `pypa/gh-action-pypi-publish`, builds under
`engine/` only). `evaluate_r01(load_root_workflows(repo_root))` reports **PRESENT**
when that file is present.

**Still required before live E16.2 publish:** merge the workflow on the default release
branch, create GitHub environment `engine-pypi`, configure PyPI Trusted Publishing for
this workflow, and run only after release-owner approval (`release-owner-approval-record.md`).

Historical inventory (2026-09-17): ci.yml validation-only; AWS OIDC workflows not
publishers; Community export excludes `.github/workflows/**` from the public mirror.

Engine-only OIDC publisher workflow: `.github/workflows/engine-pypi-release.yml`.

Required outside-Engine change (not performed in E00.1):

An authorized Engine-only GitHub Actions workflow that requests id-token: write for PyPI Trusted Publishing (or equivalent OIDC-constrained signer), publishes only the Engine package/image, and is not excluded by the Community export workflow denylist. Root CI and AWS infrastructure OIDC cannot be relabeled as that publisher. That change is outside this story and must not be made here.


| Path | Name | Triggers | OIDC | AWS | PyPI | Engine-only |
|---|---|---|---|---|---|---|
| `.github/workflows/aws-identity-check.yml` | `aws-identity-check` | workflow_dispatch | yes | yes | no | no |
| `.github/workflows/ci.yml` | `ci` | pull_request, push | no | no | no | no |
| `.github/workflows/infrastructure-apply.yml` | `infrastructure-apply` | workflow_dispatch | yes | yes | no | no |
| `.github/workflows/infrastructure-plan.yml` | `infrastructure-plan` | pull_request, workflow_dispatch | yes | yes | no | no |

Ordinary push to `release/**` still runs validation-only `ci.yml`. This story
did not edit workflows, the export manifest, or remotes.

## Install / rollback of the live artifact

Status: **PASS**

| Step | Exit | Version | SHA-256 |
|---|---|---|---|
| install | 0 | `0.2.1` | `a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18` |
| uninstall | 0 | `None` | `None` |
| reinstall | 0 | `0.2.1` | `a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18` |

- Isolated venv engine/.tmp-assess/e00.1-live-wheel (not .venv-engine-next, not live install).
- Wheel bytes SHA-256 verified before pip install; --no-deps so only the Engine artifact was the subject.
- Installed the hashed live wheel, uninstalled it, and reinstalled the same digest in an isolated venv (not the story working tree).

## Notes

- PyPI simple index lists only 0.2.1; GitHub engine tags also include v0.1.0 and v0.2.0 which are not live PyPI versions.
- Monorepo tags v0.1.0 and v0.2.0 exist; there is no monorepo v0.2.1 tag.
- PyPI project owner login recorded as sknampally; that is not an OIDC workflow identity.
- No Engine Dockerfile in engine/; container rollback is NOT_FOUND / UNAVAILABLE, not PASS.
- G00 on this clone is not PASS (ZIP identity, GitHub branch protection, teammate git identity still open).
- This story did not edit workflows, public-export-manifest.yaml, remotes, tags, or published artifacts.
