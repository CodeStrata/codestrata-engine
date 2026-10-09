---
title: "CodeStrata Engine"
subtitle: "Kickoff Steps — Branch, Docs, and First Prompt"
---

::: {.doc-meta}
<div><b>Document type:</b> Step-by-step kickoff checklist, not a new planning document</div>
<div><b>Date:</b> 15 September 2026</div>
<div><b>Companions:</b> CodeStrata-Engine-MVP-Backlog.md, CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md, CodeStrata-Engine-Team-Execution-and-Quality-Gates.md, CodeStrata-Engine-Cursor-Execution.zip</div>
<div><b>Use:</b> Run once at project start (Phases 0-4), then per-engineer and per-group ongoing (Phases 5-7)</div>
:::

## Revision note — 15 September 2026

**Package revision: `ENGINE-2026-09-15-R1`.** Targeted launch amendment: first-class Engineering Hotspots; scoped repository-local ownership concentration; explicit boundary-spread and blast-radius summaries; report-facing capability coverage/freshness; visible HTML comparison and evidence views; installed-artifact report acceptance; and package revision verification. E08.3 is now a hard prerequisite of E10.2, bringing the plan to 99 hard story links. The 17 epics, 52 stories, 33 measurement groups, five analyzer families and four public outcomes are preserved. Engine remains database-free, Platform-independent and deterministic with YAML-only rule execution. No new score, analyzer family, public outcome, CodeGraph/RAG or customer-rule authoring scope is added.

This revision updates these five Markdown specifications. The master prompt book, all 52 split prompts and execution ZIP must be reconciled against this revision and reviewed before copying or G00 PASS; this delivery does not certify those older artifacts as updated. Existing numeric compatibility behavior is governed by the unchanged no-opaque-score contract; it is not a new launch score.

Branch first, MD docs and prompts into a folder on that branch, engineers pick up their own chunk. This is the complete sequence, in order.

## Phase 0 — Founding team reads first (no repo work yet)

- Read the five approved revised Markdown specifications (Boundary, Measurement Contract, Backlog, Team Execution and Quality Gates, and this Kickoff checklist). Older PDFs are historical reference unless regenerated from this revision.
- Confirm with Vinay: who is A, B, C by actual name, and who's the release owner for R01 (the publish-route decision).

## Phase 1 — Create the branch (one person, e.g. whoever coordinates — "C" in the plan)

- Fetch and record the actual current commit:
  ```bash
  git fetch origin
  git log -1 --format="%H %cI" origin/main
  ```
- Compare that SHA against the planning baseline (`3f32ce4b82a06162062babf7e8c77451f5761e6a`). If it's moved on, that's fine — just note the real one, don't treat the old plan's file assumptions as guaranteed still accurate.
- **Before pushing anything**, check `.github/workflows/` and branch protection rules to confirm creating/pushing this branch can't itself trigger a publish or move a stable tag/mirror.
- Create and push the one shared integration branch:
  ```bash
  git checkout -b release/engine-next origin/main
  git push -u origin release/engine-next
  ```
- This is the **only** long-lived shared branch. Engineers don't commit to it directly — they branch off it per story (Phase 5) and merge back in via review.

## Phase 2 — Put the MD docs and prompts on that branch, in a folder

- Extract `CodeStrata-Engine-Cursor-Execution.zip` outside the repository. Run the commands below from the **monorepo root**, with `release/engine-next` checked out. Set this variable to the actual extracted package folder containing `engine-docs-implementation/`, `by-engineer/`, `quality-gates/` and `00-START-HERE/`:
  ```bash
  pkg="/absolute/path/to/CodeStrata-Engine-Cursor-Execution"
  ```
- Before copying or starting, verify the approved boundary, measurement contract, backlog, quality gates, kickoff checklist, master prompt book and every split prompt declare `ENGINE-2026-09-15-R1`. Record an approved package manifest with each relative path, revision and SHA-256 digest; different files have different digests. Require byte-identical standalone/ZIP document copies and compare all 52 split prompt bodies with their master sections (excluding only documented wrapper metadata). Check exactly one P01-P52/story mapping, group assignments and all 99 prerequisite links. Reconcile P02/P05, P24/P28, P34/P35/P36 and P46 plus G00/G40/G50/audit templates against these amendments; other prompt bodies may remain unchanged but must be included in the reviewed revision manifest. A revision label alone does not prove content agreement. Missing/mixed/stale package content blocks copying and G00 PASS until corrected. Record manifest digest, reviewer and approved setup commit in the G00 ledger.
- The reconciled package must place all five revised specifications and `CodeStrata-Engine-Cursor-Prompts.md` in `engine-docs-implementation/`, and include its approved revision manifest. Copy only after the checks above pass. Copy the six Markdown documents and retain the manifest with them:
  ```bash
  mkdir -p engine/docs/implementation
  cp "$pkg"/engine-docs-implementation/*.md engine/docs/implementation/
  ```
- **Copy and activate the git identity-check hooks — the `*.md` glob above does not include them, and skipping this step leaves the hooks present in the package but never actually running:**
  ```bash
  cp -R "$pkg/engine-docs-implementation/git-hooks" engine/docs/implementation/
  chmod +x engine/docs/implementation/git-hooks/pre-commit \
           engine/docs/implementation/git-hooks/commit-msg
  ```
  Check for an existing hook configuration before replacing it — overwriting a
  `core.hooksPath` someone already relies on for something else would silently
  disable it:
  ```bash
  target="engine/docs/implementation/git-hooks"
  cur="$(git config --local --get core.hooksPath || true)"
  if [ -n "$cur" ] && [ "$cur" != "$target" ]; then
    echo "core.hooksPath is already set to '$cur'."
    echo "Confirm before overwriting — it may be doing something else."
    # resolve this by hand before continuing; do not overwrite blindly
  else
    git config --local core.hooksPath "$target"
  fi
  ```
  Verify activation actually rejects a bad commit before trusting it — see
  G00 section 3 for the exact test. A hook that's present but never
  activated protects nobody.
- Copy the engineer prompts, audit/repair templates and preflight instructions together. These commands are for the initial setup, before those destination folders exist:
  ```bash
  mkdir -p engine/docs/implementation/prompts
  cp -R "$pkg/by-engineer" "$pkg/quality-gates" "$pkg/00-START-HERE" \
        engine/docs/implementation/prompts/
  ```
- The committed locations are now:
  - Story prompts: `engine/docs/implementation/prompts/by-engineer/`
  - Audit, repair and gate templates: `engine/docs/implementation/prompts/quality-gates/`
  - Preflight: `engine/docs/implementation/prompts/00-START-HERE/G00-preflight-and-branch-setup.md`
  - Git identity-check hooks: `engine/docs/implementation/git-hooks/` (activated via `core.hooksPath` above)
  - Gate records created during execution: `engine/docs/implementation/gates/`
- References to `quality-gates/` or `00-START-HERE/` in the copied package refer to the folders under `engine/docs/implementation/prompts/`. All copied files stay inside the sanctioned Engine path.
- Verify copied file digests against the approved package manifest before the setup commit; retain the manifest under `engine/docs/implementation/`.
- Before the setup commit, the coordinator must verify their own Git identity using Phase 3's identity instructions. The setup commit belongs to the coordinator making it, not its reviewer.
- Commit and push this as one setup commit:
  ```bash
  git add engine/docs/implementation
  git commit -m "Add Engine implementation planning docs and prompts"
  git push
  ```
- This means every engineer works from the same committed copy — nobody's pasting slightly different prompt text into their own session.

## Phase 3 — Each engineer sets up their own environment (once, before their first prompt)

- Set the identity of the **engineer implementing and committing the change**, not the reviewer and not a Cursor default:
  ```bash
  git config user.name  "Your Name"
  git config user.email "you@company"
  ```
- The ZIP prompt reminder's phrase “actual reviewing engineer” means the **implementing/committing engineer** for Git identity. Do not configure the reviewer's name or email as the author's identity. Review attribution remains separate in the PR and gate record.
- After your own first commit, verify its author and committer:
  ```bash
  git log -1 --format="%an <%ae> / committer: %cn <%ce>"
  ```
  Both should identify the human who made that commit. Do not rewrite another engineer's commits to change attribution.
- Do **not** use Cursor's built-in GitHub/"Create PR" integration if it authenticates as its own app or bot — push and open PRs from your own `git`/`gh` session so commits and PRs show up as you, not Cursor.
- Create an isolated environment and install the engine in dev mode:
  ```bash
  python3.12 -m venv .venv-engine-next && source .venv-engine-next/bin/activate
  pip install -e "./engine[dev,mcp]"
  ```
- Run the baseline checks once and record the result (pass or fail — either is fine, silence isn't):
  ```bash
  cd engine
  python -m ruff check .
  python -m mypy --config-file pyproject.toml
  python -m pytest tests --import-mode=importlib --cov=codestrata \
    --cov-branch --cov-fail-under=80 -q
  ```

## Phase 4 — Confirm readiness (G00 sign-off)

- [ ] `release/engine-next` exists, pushed, publisher triggers checked
- [ ] `engine/docs/implementation/` committed with all five revised specifications, the master prompt book, approved revision manifest, all 52 split engineer prompts, quality-gate templates and preflight instructions
- [ ] Approved package revision `ENGINE-2026-09-15-R1`, content parity, 52 mappings, 99 dependency links and copied digests verified; reviewer and manifest digest recorded in G00
- [ ] A / B / C assigned by name; agreed that a different engineer reviews each story
- [ ] Each engineer's git identity verified as themselves, not Cursor
- [ ] Baseline check results recorded somewhere (even if some failed)
- [ ] Group counter at zero; G10-G52 marked `NOT_RUN`

Once this is all true — **G00 PASS**, start P01.

## Phase 5 — Each engineer runs their own prompts

- Go to your own folder: `engine/docs/implementation/prompts/by-engineer/Engineer-A/` (or B or C) — your `README.md` there lists your stories in order, grouped.
- For your next story, e.g. `Group-1-G00/P02-E01.1.md`:
  ```bash
  git checkout release/engine-next && git pull
  git checkout -b engine/E01.1-launch-measurements
  ```
- Open a **fresh** Cursor session with the repo open, paste in that file's full contents. Cursor must read the approved boundary, policy, relevant backlog story and measurement contract from `engine/docs/implementation/` as the prompt instructs.
- Let it run, review its own output against the acceptance criteria before you call it done, then push your branch and open a PR into `release/engine-next`.
- **A different engineer reviews and merges — never self-merge.**

## Phase 6 — After all 10 stories in a group are integrated (team-wide, not 10-per-person)

- Stop starting new stories. Freeze the checkpoint SHA.
- C coordinates the cumulative audit. In a fresh session, run `engine/docs/implementation/prompts/quality-gates/audit-prompt-template.md`, filled in. Assign review **per story or technical area** to a different engineer from its author.
- A, B and C can review one another's work; nobody must be uninvolved in the entire group, and no fourth engineer is required. Another engineer reviews C's own implementation and fixes. Record the author/reviewer mapping and review references in the gate record; a fresh Cursor session alone is not independent engineer sign-off.
- Any findings → `engine/docs/implementation/prompts/quality-gates/repair-prompt-template.md`, fix, re-audit.
- Record the outcome with `engine/docs/implementation/prompts/quality-gates/gate-record-template.md` under `engine/docs/implementation/gates/`.
- After repairs, rerun the affected checks and cumulative audit on the final integrated SHA. Each corrected area receives review by a different engineer from its author.
- **Only a recorded PASS unlocks the next group's stories.**

## Phase 7 — Repeat

- Groups are 10 / 10 / 10 / 10 / 10 / 2 stories (P01-P10, P11-P20, ... P51-P52) — six checkpoints total (G10, G20, G30, G40, G50, G52). Same cycle each time: run the group's stories, team-wide audit, repair if needed, gate record, then next group.

## One thing to confirm before Phase 1

Check with Vinay who actually has push access to create `release/engine-next` and who's the confirmed release owner for the R01 decision later — that's the one dependency in this whole sequence that isn't something an engineer can resolve alone.
