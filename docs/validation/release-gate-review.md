# Engine release-gate review (E15.3)

**Decision:** `PASS`  
**Candidate SHA:** `60b748f6edb304b438c8a1dc10215b04bef0aa00`  
**Dirty inventory:** M engine/verification/validation/corpus/results/deno.json
 M engine/verification/validation/corpus/results/summary.json

## Cumulative harness

- E15.1 corpus manifest: **PASS**
- E15.2 regression harness: **PASS**
- M15 promotion blocked: **False**
- Remote tiers enabled: **False** (env `CODESTRATA_RUN_REMOTE_VALIDATION`)
- Three tiers fully executed: **True**
- External pin count: **50** (bar >= 50 identity pins)
- Engine source digest bound to records: `e660d3315c7c7cd87a64c20791b195a68a299ded813000dcce5657d5bfb7f2ff`

## Checkpoint gates

| Gate | Ledger | Decision | Detail |
|---|---|---|---|
| G00 | engine\docs\implementation\gates\G00.md | PASS | ledger present |
| G10 | engine\docs\implementation\gates\G10.md | PASS | ledger present |
| G20 | engine\docs\implementation\gates\G20.md | PASS | ledger present |
| G30 | engine\docs\implementation\gates\G30.md | PASS | ledger present |
| G40 | engine\docs\implementation\gates\G40.md | PASS | ledger present |

## Story prerequisites (P49 chain)

| Story | Ledger | Status | Detail |
|---|---|---|---|
| E05.3 | engine\docs\implementation\gates\E05.3.md | PASS | **Integrated** at merge `8853bf1c` (PR #9) |
| E06.3 | engine\docs\implementation\gates\E06.3.md | PASS | **Integrated** at merge `eb7fd0fc` (PR #16) |
| E07.3 | engine\docs\implementation\gates\E07.3.md | PASS | **Integrated** at merge `b9006faa` (PR #46) |
| E08.3 | engine\docs\implementation\gates\E08.3.md | PASS | **Integrated** at merge `eda6509b` (PR #24) |
| E10.3 | engine\docs\implementation\gates\E10.3.md | PASS | **Integrated** at merge `f138ff9f` (PR #51) |
| E11.3 | engine\docs\implementation\gates\E11.3.md | PASS | **Integrated** at merge `ce40ac9a` (PR #63) |
| E12.3 | engine\docs\implementation\gates\E12.3.md | PASS | **Integrated** at merge `78e71deb` (PR #65) |
| E13.3 | engine\docs\implementation\gates\E13.3.md | PASS | **Integrated** at merge `1a031462` (PR #27) |
| E14.3 | engine\docs\implementation\gates\E14.3.md | PASS | **Integrated** at merge `b06a7ad6` (PR #60) |
| E14.4 | engine\docs\implementation\gates\E14.4.md | PASS | **Integrated** at merge `ed110798` (PR #61) |
| E15.2 | engine\docs\implementation\gates\E15.2.md | PASS | Integrated. This ledger was missing at the G30 audit (G30-D006). G30-D005 later changed repeat and parity to live executions. |

## M33 resource envelope (published, measured)

- Host CPUs: 16 (4vCPU)
- <=10k eligible files: 10min/2GiB
- <=100k eligible files: 30min/8GiB
- Budgets published: True
- Corpus YAML digest: `f79c785aa939a52d325a3a3d0b42e0bd5ea648879941ab6b8ef907d6f71a73ee`

## M15 confusion (published split)

| Group | TP | FP | FN | TN | UNKNOWN |
|---|---:|---:|---:|---:|---:|
| dependency.hygiene | 22 | 0 | 0 | 22 | 0 |
| security.configuration | 22 | 0 | 0 | 22 | 0 |
| security.known_vulnerability | 22 | 0 | 0 | 22 | 0 |
| security.license | 22 | 0 | 0 | 22 | 0 |
| security.secrets | 22 | 0 | 0 | 22 | 0 |

## Per-repository / label results (sample)

- `codestrata-engine` (dogfood): **PASS** — assess exit 0; le_10k_files; artifacts present; tree unchanged
- `doris` (external_large): **PASS** — assess exit 0; artifacts present; tree unchanged
- `spring-framework` (external_large): **PASS** — assess exit 0; artifacts present; tree unchanged
- `spring-boot` (external_large): **PASS** — assess exit 0; artifacts present; tree unchanged
- `kafka` (external_large): **PASS** — assess exit 0; artifacts present; tree unchanged
- `elasticsearch` (external_large): **PASS** — assess exit 0; artifacts present; tree unchanged
- `flink` (external_large): **PASS** — assess exit 0; artifacts present; tree unchanged
- `cassandra` (external_large): **PASS** — assess exit 0; artifacts present; tree unchanged
- … and 59 more rows in JSON output

## Independently reviewed exceptions

- `platform-r05` (out_of_engine_release_gate): pending review — Remaining Platform/R05 work is explicitly out of this gate, not a waiver for missing Engine behavior.

## Notes

- Pin identity is not execution; each dogfood/external pin needs a fresh assessment record under verification/validation/corpus/results/.
- Records are bound to Engine source digest e660d3315c7c7cd8; a source or pin change makes them stale.
- M33 budgets are published measured limits.
- Five smoke repositories do not replace the 50-large tier.
- Platform/R05 remains out of scope; see reviewed-exception-list.yaml.
- Failed or unrun required checks are never PASS.
