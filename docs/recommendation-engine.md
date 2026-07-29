# Recommendation engine

Deterministic recommendations mapped from assessment findings.

```text
findings.json
        ↓
Recommendation Engine (finding → action mappings)
        ↓
recommendations.json
```

## Guarantees

* Consumes findings and read-only graph context
* Never mutates Repository Graph, Assessment Graph, bindings, or findings
* Never calls AI
* Domain `Recommendation` records are distinct from optional AI enrichment
  narratives

## Artifact

`recommendations.json` in the run directory.

## Relationship to AI

Deterministic recommendations are the source of truth. Optional
[AI enrichment](ai-enrichment.md) may narrate them but must not create, delete,
or rewrite this artifact.

## Related

- [rule-engine.md](rule-engine.md)
- [report-generation.md](report-generation.md)
- [modernization-roadmap.md](modernization-roadmap.md)
