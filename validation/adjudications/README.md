# Validation adjudications

Committed, reviewable adjudication files for Epic 5 quality tracking.

## False positives (Slice 5.9)

Each file is named `fp_<sha24>.json` and maps to `false_positive_id = fp:<sha24>`.

## False negatives (Slice 5.10)

See [`false_negatives/`](./false_negatives/). Each file is named
`fn_<sha24>.json` and maps to `false_negative_id = fn:<sha24>`.

Generated validation records under `validation/results/` must never overwrite
these files.

Do not store secrets, absolute paths, raw snippets, or personal reviewer identities.
