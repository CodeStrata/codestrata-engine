# Assessment graph

The Assessment Graph (AG) is a **projection/reference graph** for one assessment
run. It joins Repository Graph (RG) observations to Engineering Knowledge Graph
(EKG) concepts without mutating either source.

```text
Repository Graph  ──┐
                    ├── Knowledge bindings → Assessment Graph
Engineering KG    ──┘
```

## Why a separate graph

| Graph | Owns |
| ----- | ---- |
| Repository Graph | Repository facts (files, modules, dependencies) |
| Engineering Knowledge Graph | Reusable concepts, patterns, catalog rules |
| Assessment Graph | Per-run references + binding relationships |

## Properties

* Immutable projection; never mutates RG or EKG
* Deterministic `graph_id` and `source_fingerprint`
* Fail-closed validation against source fingerprints
* Evidence as references, not embedded source bodies

## Artifact

`graphs/assessment-graph.json` (plus `knowledge-bindings.json`,
`engineering-knowledge-graph.json`).

## Downstream

AG feeds the [Rule Engine](rule-engine.md) and
[Recommendation Engine](recommendation-engine.md). Rules and recommendations
never write back into AG.
