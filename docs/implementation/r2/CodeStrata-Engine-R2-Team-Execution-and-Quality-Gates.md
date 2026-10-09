# CodeStrata Engine R2 Team Execution and Quality Gates

**Revision:** `ENGINE-R2-2026-10-03-R1`

## 1. Operating rule

Each prompt is a bounded implementation unit. Do not add “nice to have” features while executing a prompt. If a gap is outside the current story but inside R2, record it for the appropriate later prompt. If outside R2, defer it.

Completion notes are not acceptance evidence.

## 2. Required evidence per prompt

Every story completion must record:
- starting SHA and final SHA;
- files changed;
- requirement-to-code mapping;
- tests added/changed;
- commands run;
- passing/failing/skipped tests;
- generated artifacts and digests where applicable;
- known limitations;
- reviewer name/identity when team process supports it;
- statement that no out-of-boundary feature was added.

## 3. R2-G1 — Baseline Engineering Health gate

**Unlocks:** P05-P09.

Must prove on generated installed-Engine artifacts:

### Product model
- primary report headline outcomes are exactly four;
- Quality is first-class;
- Inventory/Dependencies/Git are supporting;
- Cloud/AI/Modernization are not peer headline outcomes;
- no composite health score.

### Baseline canonical wiring
- M22/M25/M26 are sealed during assess rather than opportunistically re-observed by report rendering;
- capability coverage/freshness visible;
- source revision + dirty state correct;
- missing Git/feed yields UNKNOWN/partial states;
- no comparison/movement shown on first run.

### Architecture Map
- generated from real canonical graph JSON;
- canonical node/edge counts trace to source artifact;
- component grouping traceable;
- no invented edge/centrality/impact;
- unavailable graph case handled.

### Cases
At minimum:
1. complete supported repo with Git history;
2. no/insufficient Git history;
3. missing/stale vulnerability feed;
4. dirty working tree;
5. partial/unsupported capability;
6. installed wheel outside checkout.

Gate fails for contradictory status such as “Succeeded/Complete” when required evidence/rules are absent.

## 4. R2-G2 — Five-commit trend gate

**Unlocks:** P10.

Must prove:

### Snapshot isolation
- selection is committed HEAD + four first-parent predecessors;
- oldest→newest order stable;
- each snapshot file tree matches its SHA;
- worktree/index unchanged;
- dirty uncommitted changes excluded.

### No future-history leakage
Create an adversarial fixture where later commits add:
- a new hotspot file;
- a new co-change pair;
- ownership/churn changes;
- a graph node/edge;
- a finding.

Assert S1 cannot contain any later-only fact.

History for S_i must be explicitly bounded by S_i as the Git head. A hardcoded/current HEAD observer is a gate failure.

### Comparisons
- four adjacent + one span comparison produced where source states available;
- M27/M28/M29/M30/M31 values equal independent expectations;
- named deltas supplied by canonical comparison, not HTML math;
- failed/missing slot preserved and affected comparison marked unavailable;
- testing drivers project under Quality.

### Bundle
- five-slot artifacts live outside baseline `current/previous` rotation;
- evidence is source-state bound;
- deterministic rerun produces equal semantic/digest results subject to explicitly documented run-ID fields.

## 5. R2-G3 — R2 implementation acceptance

G3 does **not** replace the project's existing G50/G52 release gates.

Requirements:
- all P01-P10 acceptance complete;
- cumulative mandatory suite passes;
- real-repository baseline and trend generated and visually reviewed;
- installed wheel and sdist reproduce expected report semantics outside checkout;
- container included if required by current G50 contract;
- no unexplained skips;
- no boundary regression;
- no Platform import;
- Community custom-rule create/load/import remains unsupported;
- exact candidate SHA and artifact digests recorded.

A G3 PASS means: **R2 is eligible to enter a fresh exact-artifact G50.**

It does not mean:
- PyPI is published;
- G52 passed;
- public release completed.

## 6. Fresh G50 after R2-G3

Do not reuse the old stamped G50 evidence.

Fresh G50 must qualify the exact R2 candidate bytes according to the existing Engine release contract, including independent installed artifact checks and required wheel/sdist/container parity.

Any code/config/catalog change after G50 invalidates affected evidence.

## 7. Review discipline

At each gate:
1. freeze candidate SHA;
2. run read-only audit against acceptance, not ledgers;
3. record defects with expected/actual and reproducer;
4. repair only accepted gaps;
5. rerun affected + cumulative checks;
6. independent review;
7. PASS only when evidence is coherent.
