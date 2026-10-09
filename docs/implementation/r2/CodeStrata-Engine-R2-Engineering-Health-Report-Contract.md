# CodeStrata Engine R2 Engineering Health Report Contract

**Revision:** `ENGINE-R2-2026-10-03-R1`

## 1. Goal

Engine HTML and future Platform repository Engineering Health must use the same mental model. Platform may add persistence, organization/workspace context, governance and long-term history; it must not require a different health taxonomy.

The Engine produces two primary local reports:

1. **Baseline report** — current repository source state.
2. **Five-commit trend report** — committed HEAD plus four first-parent predecessors.

Reference targets:
- `reference/baseline-report.html`
- `reference/five-commit-trend-report.html`
- `reference/implementation-guide.html`

The reference samples are visual/data-contract guidance. Production output must use real canonical Engine values and states.

## 2. Baseline command and semantics

```bash
codestrata assess --repo .
```

- assesses current files on disk;
- dirty state is allowed and visible;
- current Git history may be used for M22/M25/M26 context;
- no comparison/trend is inferred;
- no LLM required;
- JSON/HTML/SARIF/canonical artifacts remain deterministic from pinned inputs.

## 3. Baseline primary report hierarchy

### 3.1 Leadership / attention-first summary

Show only facts already supported by canonical outcomes/findings/actions/coverage.

Must answer:
- What needs attention now?
- Which outcome(s) drive that attention?
- What are the top grounded Priority Actions?
- What important evidence is unavailable?

Do not invent business impact or effort.

### 3.2 Four Engineering Health outcomes

Exactly:
- Architecture
- Security
- Quality
- Maintainability & Technical Debt

Each outcome shows:
- display status derived from canonical truth;
- coverage/trust state;
- primary qualifying drivers;
- key findings;
- linked evidence;
- no trend/movement on first baseline.

Allowed display labels may include:
- Needs attention
- No material issues observed
- Insufficient evidence
- Not applicable

These are presentation mappings, not new canonical enums.

### 3.3 Architecture Map

Visualize existing graph JSON/canonical graph.

Required:
- component/module nodes when canonical membership exists;
- canonical dependency edges;
- click/drill-down to canonical node/file/finding/evidence;
- overlays for existing findings/hotspot/ownership context are allowed;
- renderer computes layout only;
- no invented edges, architecture layers, centrality, risk or impact;
- unavailable graph/component identity is explicit.

### 3.4 Engineering Hotspots — M22

Show supplied canonical hotspot records:
- canonical rank;
- complexity contributor;
- churn contributor;
- rank value/formula/version when present;
- history window/coverage;
- context-only ownership/centrality/finding references;
- evidence.

A scatter/visual map may use churn and complexity values. Marker size/color must not imply an additional hidden ranking unless the canonical record explicitly supplies it.

### 3.5 Ownership concentration — M25

Show repository/component/file scope as supported:
- numerator;
- denominator;
- ratio;
- history window;
- coverage/limitations;
- evidence.

### 3.6 Temporal co-change — M26

Show:
- pair;
- scope;
- support;
- union denominator;
- supplied Jaccard value;
- incomplete-window/unavailable reason;
- evidence.

### 3.7 Priority Actions

Keep the existing recommendation-backed Priority Action universe.

Each action may show:
- why;
- affected outcome/component/file/path where supported;
- supporting finding(s);
- deterministic priority/horizon if canonically supplied;
- evidence;
- effort only if supplied with a supported basis/evidence.

Hotspot rank must not silently become Priority Action order.

### 3.8 Coverage & Trust

Make visible:
- Engine version;
- rule package/version/digest;
- config/profile digest;
- source revision / dirty state / working-state digest;
- Git-history coverage/freshness;
- vulnerability-feed provider/version/digest/freshness;
- capability execution/coverage reasons;
- canonical/result digest/signature state when available;
- material limitations.

Do not dump dozens of limitations in the leadership surface. Summarize material limitations and provide full technical detail in appendix.

### 3.9 Supporting evidence / appendix

Include:
- inventory;
- dependency detail;
- Git detail;
- raw findings;
- rule IDs;
- evidence records;
- graph technical detail;
- legacy Cloud/AI/Modernization pack output only as appendix/supporting material if still produced; never as headline health outcomes.

## 4. Five-commit trend command and semantics

```bash
codestrata trend --repo .
```

Fixed R2 selection:

```text
committed HEAD + four first-parent predecessors
```

Display oldest → newest.

Trend does not include uncommitted working-tree changes. If the user's worktree is dirty, report that trend used committed HEAD and the worktree was left untouched.

All five assessments must use one pinned profile:
- Engine version;
- bundled rule set/version;
- configuration;
- vulnerability-feed snapshot;
- evaluation time;
- analyzer versions.

## 5. Five-commit report hierarchy

### 5.1 Current HEAD Engineering Health

Reuse the baseline report model for current committed HEAD.

### 5.2 Five-state health trend

Show five ordered source-state observations. Do not create a composite health score.

Visualize named metrics/outcome states only when compatible. Gaps remain gaps.

### 5.3 Outcome movement — M30

For each adjacent comparison and S1→HEAD span:
- Architecture;
- Security;
- Quality;
- Maintainability & Technical Debt.

Allowed Engine movement states are projected as supplied, including Insufficient/Mixed/Deteriorated/Improved/Stable where applicable.

Testing-specific drivers roll up under public Quality.

### 5.4 Finding lifecycle — M28

Show supplied lifecycle identities:
- new;
- resolved;
- persisting;
- unverified/unknown as supported.

Equal finding counts must not be interpreted as Stable when identities changed.

### 5.5 Change summary — M27

For each selected comparison show supplied:
- changed files;
- changed components;
- changed tests;
- architecture-boundary spread;
- crossed-boundary data where supplied;
- coverage/limitations.

### 5.6 Static impact / blast radius — M29

Show supplied candidate-side bounded impact:
- changed seeds;
- additional affected components;
- affected components;
- affected tests;
- direction;
- edge kinds;
- max depth/nodes/edges;
- visited counts;
- cutoff/lower-bound/UNKNOWN semantics;
- boundary spread / crossed-boundary pairs;
- unresolved mapping/test-association coverage.

Never describe static bounded reach as runtime certainty.

### 5.7 Before / After / Delta

Project named compatible MetricDelta records. HTML must not calculate subtraction or compatibility.

Each row/card includes:
- metric ID/label;
- before;
- after;
- supplied delta;
- unit;
- compatibility;
- cause/reason;
- evidence.

### 5.8 Cause attribution — M31

Show supplied attribution and bound source/feed/config/engine digests. Do not infer intent or causality outside Engine semantics.

### 5.9 Evidence binding

Every snapshot has:
- slot/source-state identity;
- full commit SHA;
- source digest;
- assessment/result digest;
- evidence tied to that snapshot.

Comparison evidence identifies base and candidate revisions.

## 6. Dedicated trend artifact layout

Recommended R2 layout (exact implementation may adjust names but must preserve semantics):

```text
.codestrata-artifacts/
  trends/
    <repository-id>/
      <series-id>/
        five-commit-trend.html
        trend-index.json
        snapshots/
          s1/<assessment artifacts>
          s2/<assessment artifacts>
          s3/<assessment artifacts>
          s4/<assessment artifacts>
          s5/<assessment artifacts>
        comparisons/
          s1-s2/
          s2-s3/
          s3-s4/
          s4-s5/
          s1-s5/
```

Do not reuse the two-slot `current/previous` retention model.

## 7. Offline / token-efficient execution

Both report journeys are deterministic and local by default. Report rendering does not require an LLM and does not consume repository tokens.

Token efficiency story remains:
- Engine reads and analyzes code deterministically;
- reusable structured evidence is produced once;
- optional AI/Platform receives only relevant structured evidence/context rather than repeatedly sending the repository to an LLM.

## 8. Report acceptance invariants

- HTML works locally without CDN/server.
- HTML escapes source/evidence/messages.
- HTML does not compute health, rank, lifecycle, deltas, movement or graph topology.
- no synthetic zero/healthy state for missing evidence.
- first baseline visibly has no trend/movement.
- fewer than five commits are represented honestly.
- links resolve to exact findings/evidence/source state.
- Architecture Map uses canonical graph only.
- downloadable JSON preserves canonical IDs.
- print/export is presentation only and does not create new semantics.
