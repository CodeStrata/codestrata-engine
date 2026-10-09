# Release candidate freeze (E16.1)

Package revision `ENGINE-2026-09-15-R1`.

**Status: FROZEN**

Freeze performed on `ae08622dd28c08c12351e3fe51229aacf85047e8`. E15.3 release gate
evaluated to PASS (`decision: PASS`, exit 0). Artifacts generated via
`verification.release_build`.

## Qualified source

| Field | Value |
|---|---|
| Git SHA | `ae08622dd28c08c12351e3fe51229aacf85047e8` |
| Integration branch | `engine/G50-tier-validation-and-freeze` |
| Independent reviewer | Abhinav Bussa |
| Freeze date (UTC) | 2026-09-30 |

## Version identity

| | |
|---|---|
| Live PyPI (rollback target) | `0.2.1` — rechecked 2026-09-29; see `baseline.md` |
| Candidate semver | `0.2.2` |
| `RULESET_VERSION` | `1.2.0` |

Live files (PyPI JSON, 2026-09-29):

| File | SHA-256 | Bytes |
|---|---|---|
| `codestrata-0.2.1-py3-none-any.whl` | `a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18` | 2286589 |
| `codestrata-0.2.1.tar.gz` | `acd8615186977d9a62f3661f8a8d71fe2be380c371c9ea29048f1bb2cd1212e6` | 1673543 |

## Artifact digests (E14.2 verifier)

Produced on qualified SHA `ae08622d`:

```text
cd engine
python -m verification.release_build --output .quality-runs/candidate-freeze/release-build
```

Recorded from `provenance.json`:

| Artifact | SHA-256 | Bytes |
|---|---|---|
| Wheel | `159ae99d41c0c5e4ad339d757b6e869e7fe503306ffbb19f0cbd5731de856f5a` | 2968123 |
| sdist | `c8cc2e52c25131bacc50942d9133bac5e9da14c928b2c808c67fe6c766f51e9d` | 2194853 |
| Runtime SBOM digest | `7baaddca4596196567327291b53b6148dadfa872a0deb19346ff13a675b33dff` | 1117 |
| Runtime lock digest | `d8196f3c031f37a85d5bbe1903cf6217a0a25147b896348794aab86a3f1453dd` | 0 |
| Headless operational limits digest | `fe26e39a8e3089ed2c98529632f85c87172abd7a7899d74b057748c2318658f8` | — |

Container image digest: Recorded as UNAVAILABLE in E00.1 baseline; wheel/sdist qualification complete.

## Catalog and packaged policy digests

At freeze, record packaged resource digests bound in provenance (rule YAML
inventory, verification profiles, export policy versions). Do not substitute
hand-copied paths for `verification.release_build` output.

## Compatibility map

- Outside-Engine import inventory: `consumer-import-inventory.md` (regenerate at
  qualification if the module surface changed).
- Supported Python: `requires-python = ">=3.12"` in `pyproject.toml` today.
  Re-read it at the freeze SHA.
- Community vs Enterprise execution profiles: local no-consent default stays
  in force; confirm E13.1 / E02.3 on the qualified SHA.
- VS Code extension, Platform, Webapp, and AWS deployment are **out of scope**
  for this Engine freeze.

## Verified rollback (live stable)

Rollback identity is the **published** PyPI wheel, not the monorepo tag or
`pyproject.toml` alone. Digests below match the 2026-09-29 PyPI JSON response
and `baseline.md`.

| Step | Detail |
|---|---|
| Artifact | `codestrata-0.2.1-py3-none-any.whl` |
| SHA-256 | `a079344c4e3cc4824a1f37b594004085314df00eb5712f0de2b84718932b0c18` |
| Install | Isolated venv; `pip install` with hash pinning per `baseline.md` |
| Uninstall | `pip uninstall codestrata` in that venv |
| Verify | `codestrata version` reports `0.2.1` |

Candidate work must not overwrite `engine/.tmp-assess/e00.1-live-wheel` or
relabeled live bytes. See `isolation.md`.

## Release notes

Not written. `CHANGELOG.md` stays on published `[0.2.1]`. When a semver is
chosen on a qualified SHA, add that section from the integrated stories on
that commit. Do not imply PyPI publication; E16.2 still needs R01 and
release-owner authorization. G50 must verify the frozen candidate before P51.

## Review record

| | |
|---|---|
| Author | _pending the freeze commit_ |
| Independent reviewer | _required before merge of a freeze_ |
| G50 | Must verify this exact candidate before P51 (E16.2) |
