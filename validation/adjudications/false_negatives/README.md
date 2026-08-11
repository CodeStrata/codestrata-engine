# False-negative adjudications

Committed, reviewable adjudication files for Epic 5 Slice 5.10.

Each file is named `fn_<sha24>.json` and maps to `false_negative_id = fn:<sha24>`.

Generated validation records under `validation/results/` must never overwrite
these files.

Schema fields:

- `false_negative_id`
- `classification` (`suspected` | `confirmed` | `rejected` | `ambiguous` |
  `expectation_error` | `unsupported_capability` | `insufficient_evidence`)
- `status`
- `root_cause` (optional; required for confirmed→fixed)
- `resolution` (optional; required for fixed)
- `rationale` (optional)
- `source_evidence_note` (optional; bounded descriptive text, not source)
- `supported_scope_note` (optional)
- `regression_test_refs` (required for confirmed product fixes)
- `limitations` (optional)

Do not store secrets, absolute paths, raw snippets, or personal reviewer identities.
