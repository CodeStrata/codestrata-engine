# Assess runtime

How `codestrata assess` produces graphs, findings, recommendations, optional AI
enrichment, and reports in the Community Edition.

```text
CLI / Config
     ↓
Analysis (detect + analyzers + optional PMD)
     ↓
Repository Inventory
     ↓
Repository Graph (+ dependency extraction)
     ↓
Knowledge Pipeline ← Engineering Knowledge Graph (builtin catalog)
     ↓
Assessment Graph
     ↓
Rule Engine → findings.json
     ↓
Recommendation Engine → recommendations.json
     ↓
optional AI Enrichment (exactly one provider call) → advisor.json
     ↓
HTML Report v2 (report.html) + report.json
     (+ optional advisor-execution.json)
```

## Modes

| Mode | AI calls | Notes |
| ---- | -------- | ----- |
| Deterministic (`--no-ai`, default) | 0 | Graphs, findings, recommendations, HTML/JSON |
| AI (`--with-ai`) | 1 | Same deterministic artifacts + enrichment on success |

## Failure behavior

* Graph / rule / recommendation failures abort the assessment with a clear stage error.
* AI enrichment failures warn and keep deterministic artifacts; CLI exits 0.
* HTML/JSON write failures surface as report-stage errors without deleting prior
  graph/findings/recommendation/enrichment files already written for the run.

## Performance controls

Assessment keeps deterministic semantics while bounding I/O, memory, and
concurrency for large repositories. These controls apply to onboarding,
analysis, and report generation. They are separate from optional Performance
Intelligence analysis packs.

### Goals

* Avoid repeated source-file reads across architecture and technical-debt packs
* Bound concurrent disk reads without changing finding or scoring output
* Emit stage-level timing and skip/truncate telemetry
* Keep secure default limits for source-file volume and per-file size

### Settings (`analysis.runtime`)

| Setting | Default | Purpose |
| ------- | ------- | ------- |
| `shared_source_text_cache` | `true` | Load eligible source texts once and reuse |
| `max_read_workers` | `4` | Bounded thread pool for independent file reads |
| `max_source_files` | `2000` | Cap on shared source-text map size |
| `max_source_chars` | `100000` | Per-file truncation for shared loads |
| `capture_peak_rss` | `true` | Record process RSS heuristic in timing |

Example `codestrata.toml`:

```toml
[analysis.runtime]
shared_source_text_cache = true
max_read_workers = 4
max_source_files = 2000
max_source_chars = 100000
capture_peak_rss = true
```

### Timing fields

`assessment.timing` in `report.json` may include:

* `graph_ms`, `rules_ms`, `evidence_ms`, `knowledge_ms`
* `files_loaded`, `files_skipped`
* `cache_hits`, `cache_misses`
* `peak_rss_mb`
* `report_ms`, `total_ms` (measured after a single HTML render)

JSON is built once and patched; HTML is not rendered twice for timing.

### Recommended limits

* Keep the defaults unless repositories routinely exceed 2k source files **and**
  host memory headroom is confirmed.
* Prefer `max_read_workers` of 2–4 on shared CI; up to 8 on dedicated runners.
* Do not disable `shared_source_text_cache` in production; baseline mode exists
  only for A/B measurement.

Contributors can exercise the deterministic harness via
`scripts/bench_runtime_performance.py` (baseline / compare modes).

## Related docs

* [repository-graph.md](repository-graph.md)
* [assessment-graph.md](assessment-graph.md)
* [rule-engine.md](rule-engine.md)
* [recommendation-engine.md](recommendation-engine.md)
* [ai-enrichment.md](ai-enrichment.md)
* [report-generation.md](report-generation.md)
* [incremental-assessment.md](incremental-assessment.md)
