# Complexity signals fixture (validation only)

Purpose-built **Technical Debt / complexity** precision fixture for CodeStrata. Static Python sources only; nothing in this tree is meant to be executed as an application.

This fixture is **not** part of the six-repository `ACTIVE_VALIDATION_SET`. Use overlay config `engine/validation/configs/local-complexity-signals.toml` when assessing this tree.

## Default rule thresholds (strictly greater than)

Findings are emitted only when a **production** (`SOURCE`) subject’s measured metric is **greater than** the threshold (equal values do **not** match).

| Rule ID | Metric | Default threshold | Operator |
|---------|--------|-------------------|----------|
| `technical_debt.large-callable` | `physical_line_count` (callable span) | 50 | GT |
| `technical_debt.excessive-branching` | `branch_point_count` | 10 | GT |
| `technical_debt.deep-nesting` | `max_nesting_depth` | 4 | GT |
| `technical_debt.excessive-parameters` | `parameter_count` | 5 | GT |
| `technical_debt.oversized-type` | `physical_line_count` (type/module span) | 300 | GT |

Test-classified paths (`tests/`) are excluded from production Technical Debt findings even when metrics exceed thresholds.

## Production symbols (`src/production/`)

### Below threshold (expect **no** finding)

| Symbol | File | Intended measurement |
|--------|------|----------------------|
| `large_below` | `below_threshold.py` | ~45 physical lines |
| `branch_below` | `below_threshold.py` | 8 separate `if` branch points |
| `nest_below` | `below_threshold.py` | `max_nesting_depth` 3 |
| `params_below` | `below_threshold.py` | 4 parameters |

### Equal to threshold (expect **no** finding — GT semantics)

| Symbol | File | Intended measurement |
|--------|------|----------------------|
| `large_equal` | `equal_threshold.py` | 50 physical lines |
| `branch_equal` | `equal_threshold.py` | 10 branch points |
| `nest_equal` | `equal_threshold.py` | `max_nesting_depth` 4 |
| `params_equal` | `equal_threshold.py` | 5 parameters |

### Above threshold (expect **finding**)

| Symbol | File | Intended measurement |
|--------|------|----------------------|
| `large_above` | `above_threshold.py` | 60 physical lines |
| `branch_above` | `above_threshold.py` | 12 branch points |
| `nest_above` | `above_threshold.py` | `max_nesting_depth` 6 |
| `params_above` | `above_threshold.py` | 8 parameters |

### Oversized types

| Symbol | File | Role |
|--------|------|------|
| `OversizedType` | `oversized_type.py` | ~350 physical lines (class span) — **positive** control for `oversized-type` |
| `CompactType` | `oversized_type.py` | ~20 physical lines — **negative** control |

Because `oversized-type` applies to module records as well, the module `production.oversized_type` (full file span) may also exceed 300 lines when the oversized class is present. Treat `OversizedType` as the primary class-level signal; module-level match is an expected secondary signal for this file layout.

## Test-only symbol (`tests/`)

| Symbol | File | Role |
|--------|------|------|
| `test_large_ignored` | `tests/test_complex_fixture.py` | 80 physical lines, `TEST` classification — must **not** appear in production `large-callable` (or other production TD) findings |

## Probe (local verification)

From `engine/` with project venv and `PYTHONPATH=src`:

1. Collect evidence: `ComplexityEvidenceService` over this fixture root.
2. Evaluate Technical Debt complexity rules with default thresholds (50 / 10 / 4 / 5 / 300).

Expected production matches: `large_above`, `branch_above`, `nest_above`, `params_above`, `OversizedType` (and optionally module `production.oversized_type`). No matches for below/equal symbols or `test_large_ignored`.
