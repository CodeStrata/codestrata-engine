# Incremental assessment

Public product name: **CodeStrata**. Internal package/CLI/config remain `codestrata`.

## Purpose

Make incremental assessment **operationally trustworthy and inspectable** while
keeping full assessment as the default.

```text
Incremental plan
      │
      ▼
Incremental executor
      │
      ▼
Complete assessment result
      │
      ▼
Validation + equivalence + metrics + explanations
      │
      ▼
Incremental execution record
      │
      ├─ CLI (`codestrata incremental`)
      └─ MCP (additive tools)
```

## Core correctness rule

For every supported incremental scenario, the deterministic incremental result
must be **semantically equivalent** to a clean full assessment of the same
repository state.

- Validation is deterministic (no LLM)
- Equivalence and explainability use no AI
- Fallback is expected safe behavior
- No partial result is trusted or persisted as a complete incremental result
- `codestrata assess` remains a full rebuild
- AI artifact reuse remains disabled

## Rollout modes

```toml
[incremental]
rollout_mode = "off"   # default
```

| Mode | Planning | Incremental execution |
| ---- | -------- | --------------------- |
| `off` | blocked | blocked |
| `plan_only` | allowed | blocked |
| `opt_in` | allowed | explicit CLI/MCP/API only |
| `default_with_fallback` | modeled/tested | **not** activated as the product default |

Legacy `enabled` / `execution_enabled` map safely when `rollout_mode` is omitted.
Conflicting combinations are rejected. Hard safety fallbacks cannot be disabled.

## Configuration

```toml
[incremental]
rollout_mode = "off"
enabled = false
execution_enabled = false
validate_after_execution = true
persist_execution_records = true
enable_equivalence_check = false
max_explanations = 500
max_equivalence_differences = 100
allow_ai_reuse = false
fallback_on_validation_failure = true
fallback_on_metric_inconsistency = true
```

## CLI (explicit opt-in)

```bash
codestrata incremental plan <repository> [--previous-run-id ...] [--json]
codestrata incremental assess <repository> [--previous-run-id ...] [--with-ai] [--equivalence-check] [--json]
codestrata incremental explain <execution-id> [--kind ...] [--subject-id ...] [--limit N] [--json]
```

- Exit `0`: trusted completion (including successful full fallback)
- Exit `1`: blocked / untrusted validation
- Exit `2`: configuration or execution failure

`codestrata assess` is unchanged.

## MCP (additive)

Four new tools (existing 20 granular + 5 agent tools unchanged):

1. `create_incremental_assessment_plan`
2. `execute_incremental_assessment`
3. `get_incremental_execution`
4. `explain_incremental_execution`

## Validation, metrics, explainability

After an incremental execution, the Engine:

- validates plan/execution integrity and optional semantic equivalence
- computes reuse/recompute metrics (fallback counts as zero reuse)
- emits deterministic explainability reason codes (no speculative language)
- persists an execution record for CLI/MCP inspection under
  `{knowledge}/incremental_executions/`

## Supported scenarios

- Explicit opt-in via `codestrata incremental assess`, MCP execute tool, or
  `assess_incrementally_if_safe(...)` with rollout `opt_in`
- Eligible no-change / metadata-only / incremental-candidate plans
- Successful full-rebuild fallback (structured success)
- Post-execution validation + metrics + explanations + provenance

## Unsupported / fallback scenarios

- `codestrata assess` (always full)
- `rollout_mode = off` (default)
- `plan_only` for execution
- engine / schema / fingerprint incompatibility
- truncated / unknown impact
- AI reuse (always disabled)
- any case where safety cannot be proven → full rebuild

## Shared rules and incremental reuse

Each shared `RuleMetadata` may declare `incremental_behaviors`.
`rule_invalidation_fingerprint` combines rule ID, version, config, and context.

Incremental rule reuse is **conservative** today: plans recompute
(`reuse_claimed=false`, `actual_reuse_count=0`). Selective reuse requires proven
compatibility, provenance, equivalence, and telemetry before it is enabled.

## Security

No caller-defined steps, fingerprints, SQL, blob access, report reads, shell/Git
commands, path traversal, unbounded explanations, or disabling hard fallbacks.
Execution records never expose absolute paths, credentials, or source code.

## Related

Contributors can use
`tests/application/incremental/equivalence_helpers.py` to compare incremental
vs clean full assessment artifacts without reading report files.

Advanced organizational knowledge capabilities are available in CodeStrata
Platform. See [community-vs-platform.md](community-vs-platform.md).
