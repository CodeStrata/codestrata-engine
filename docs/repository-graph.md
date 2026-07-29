# Repository graph

CodeStrata builds a deterministic structural view of the assessed repository.

## Pipeline

```text
Repository (scan)
     ↓
Repository Inventory (manifest + fingerprints)
     ↓
Repository Graph (nodes + relationships)
     ↓
Dependency extraction (Maven / package.json and related manifests)
```

## What it contains

* Repository, module, and file structure
* Dependency nodes with versions where known (version is a property, not part of
  the dependency identity)
* Highlights such as Java language level, Spring Boot version, and Node engine
  when detectable from manifests

## What it excludes

* Full source file bodies
* Secrets and absolute host paths in customer-facing reports
* Lockfile-only resolution (manifest-declared versions are used)

## Artifacts

Under `reports/<repo>/<run>/graphs/`:

* `repository-manifest.json`
* `repository-graph.json`
* `graph-summary.json` (plus knowledge/assessment siblings)

## Boundaries

* Scanner and analyzer DTOs remain separate from the graph model.
* The Repository Graph is adapted from inventory; it is not collapsed into
  scanner DTOs.
* Graph construction never calls AI.

## Related

- [runtime.md](runtime.md)
- [assessment-graph.md](assessment-graph.md)
- [rule-engine.md](rule-engine.md)
