# Installed Engine journeys

These folders are ordinary repositories. They do not point at a monorepo
checkout, a platform package, or a source-tree `PYTHONPATH`.

From a clean directory, after `codestrata init`:

```text
codestrata doctor
codestrata assess --repo . --no-ai
```

`codestrata compare` needs both `--baseline` and `--candidate`. A first
assessment has no baseline. Missing git history, a missing or stale
`codestrata/osv-snapshot.json`, an unknown author, a missing test, and an
impact cutoff stay UNKNOWN. They are not zeros, healthy badges, or a trend.

Pinned evaluation time for the bundled feed snapshots is
`2026-09-27T00:00:00Z`. The fresh snapshot is one day older. The stale
snapshot is dated `2020-01-01`.
