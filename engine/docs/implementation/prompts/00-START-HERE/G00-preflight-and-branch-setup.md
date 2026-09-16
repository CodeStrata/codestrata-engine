# G00 — Preflight and branch setup (do this before P01)

**Package revision `ENGINE-2026-09-15-R1`.** This is setup, not a 53rd
implementation story, and not permission to change root files. C
coordinates; A and B review the parts relevant to them. Full detail is in
`CodeStrata-Engine-Team-Execution-and-Quality-Gates.md` and
`CodeStrata-Engine-Kickoff-Steps.md` — this file covers branch setup and git
identity specifically. **Package revision/manifest verification (matching
`ENGINE-2026-09-15-R1` across all documents and prompts, SHA-256 digests,
byte-identical standalone/ZIP copies) is Kickoff Steps Phase 2 — do that
before this file's steps, not after.**

## 1. Record the actual starting point

```bash
cd codestrata-platform
git fetch origin
git log -1 --format="%H %cI" origin/main
git status --porcelain          # record any dirty/untracked state, do not reset it
```

Compare the resulting SHA against the planning baseline
(`3f32ce4b82a06162062babf7e8c77451f5761e6a`). If it has moved, that's expected
— record the real SHA in the gate ledger and treat file/path assumptions in
the prompts as something to verify, not trust blindly. Do not reset or
discard unrelated in-progress work.

## 2. Create the isolated integration branch — before any story work

```bash
git checkout -b release/engine-next origin/main
git push -u origin release/engine-next
```

Then each engineer branches per story off `release/engine-next`, not off
`main` and not off each other's branches:

```bash
# example for P19 / E06.1, run by whichever engineer owns that story
git checkout release/engine-next
git pull
git checkout -b engine/E06.1-secret-config-rules
```

One branch per story keeps review scoped and makes "a different engineer
reviews before integration" (required for every story, not just some)
straightforward — the reviewer looks at one story's diff, not a pile of
concurrent work.

**Before any push:** inspect the repository's actual publisher/workflow
triggers (`.github/workflows/`, branch protection rules) to confirm pushing
`release/engine-next` or a story branch cannot itself fire a publish, tag
move, or mirror update. If that isn't verifiable yet, keep branch setup
local-only and continue with read-only preparation until it is. Normal story
work must never be able to publish or move a stable tag/mirror as a side
effect of an ordinary push.

## 3. Git identity — make sure Cursor's identity never shows up on GitHub

This matters for every commit, on every branch, for the whole project. Set it
per-engineer, once, before the first commit:

```bash
git config user.name  "Your actual name"
git config user.email "your-actual-work-email@company"
```

Then, specifically:

- **Do not use Cursor's built-in GitHub/"Create PR" integration** for this
  repository if it authenticates as a separate Cursor-owned GitHub App or bot
  identity. Push with your own authenticated `git` remote (SSH key or your
  own `gh auth login` session) and open the PR yourself, so the commit
  author, the committer, and the PR opener are all the human engineer — not
  a bot account, and not Cursor.
- **Check commit trailers before pushing.** Some AI coding tools
  automatically append a line like `Co-authored-by: Cursor <...>` to commit
  messages. Strip this before committing:
  ```bash
  git commit --amend  # edit the message, remove any AI co-author trailer
  ```
  A simple habit: write your own commit message rather than accepting a
  tool-generated one verbatim, and check `git log -1` before every push.
- **Verify after your first commit of the session:**
  ```bash
  git log -1 --format="%an <%ae> / committer: %cn <%ce>"
  ```
  Both should show the human engineer — specifically, the engineer
  **implementing and committing** the change, not a reviewer's identity and
  not Cursor's. If either shows anything else, fix `git config` (and, if
  already committed, `git commit --amend --reset-author`) before pushing.
  Never rewrite another engineer's commits to change attribution.
- If Cursor is configured with its own GitHub account/token for repository
  access, treat that as read access for the agent session only — the actual
  push and PR creation should go through the engineer's own credentials, not
  that integration.

### Verify the identity-check hooks are actually active — not just present

Kickoff Steps Phase 2 copies and activates these hooks as part of setting up
`engine/docs/implementation/`. **This section is a verification checkpoint,
not a separate setup step** — an earlier version of this file had engineers
run `git config core.hooksPath` against a path that only existed inside the
extracted ZIP, never inside the actual repository, so the hooks looked
configured but never fired. Confirm that didn't happen to you:

```bash
git config --local --get core.hooksPath
# must print exactly: engine/docs/implementation/git-hooks
ls -l engine/docs/implementation/git-hooks/
# both pre-commit and commit-msg must be present and executable (-rwxr-xr-x)
```

If `core.hooksPath` is empty, points somewhere else, or the files aren't
executable, go back to Kickoff Steps Phase 2's hook-copy step before
continuing — do not just run `git config` by itself here without the copy
and `chmod` having actually happened first.

Then prove it actually works, don't just trust that it's configured:

```bash
git config user.name "Cursor Test"; git config user.email "test@cursor.sh"
git commit --allow-empty -m "hook activation test"
# must be BLOCKED — if this commit succeeds, the hooks are not active
```

Restore your real identity immediately after this test:

```bash
git config user.name  "Your actual name"
git config user.email "your-actual-work-email@company"
```

What the hooks actually do once active: `pre-commit` blocks a commit if
`git config user.name`/`user.email` is empty or matches a known AI-tool
pattern; `commit-msg` blocks a commit message containing an AI co-author
trailer. Both were tested against real commits before shipping, including
two false positives that got caught and fixed — a human named "Talbot" or
"Claude" is not blocked; a "Cursor Agent" identity or a `Co-authored-by:
Cursor` trailer is. No pattern-matching heuristic is perfect: if a genuine
false positive comes up, the hook's own error message explains the
`git commit --no-verify` bypass — use it, but confirm with your reviewer
that the resulting commit author is actually you before pushing.

This is a local control only. It cannot catch a commit made outside this
clone, and nothing in this repository can enforce it server-side without
touching root `.github/workflows/`, which is outside this backlog's
`engine/`-only boundary.

## 4. Environment isolation

```bash
python3.12 -m venv .venv-engine-next
source .venv-engine-next/bin/activate
pip install -e "./[dev,mcp]"
```

Use a separate output/cache directory for candidate runs — do not point at
the live installation's stable output/cache paths, and do not mutate any
existing source snapshot.

## 5. Record the quality-command baseline

From `engine/`, in the isolated environment:

```bash
python -m pip check
python -m ruff check .
python -m mypy --config-file pyproject.toml
python -m pytest tests --import-mode=importlib --cov=codestrata --cov-branch --cov-report=term-missing --cov-fail-under=80 -q
```

Record the exact exit code of each command, even if some fail — a failing
baseline is recorded as a failure, not silently waived. These failures (if
any) must be repaired within allowed Engine scope before G10 can pass. A
failure whose cause lives outside `engine/` is recorded separately and
stays BLOCKED rather than being fixed here.

## 6. Confirm the team is ready

- [x] Package manifest verified — every document and prompt declares `ENGINE-2026-09-15-R1`, SHA-256 digests recorded, standalone/ZIP copies byte-identical, all 99 prerequisite links checked (Kickoff Steps Phase 2)
- [x] `core.hooksPath` set to `engine/docs/implementation/git-hooks`; confirmed a deliberately-bad test commit is actually rejected before doing real work
- [x] Actual checkout SHA recorded and compared to the planning baseline
- [x] `release/engine-next` created and pushed; publisher triggers checked before that push
- [x] Each engineer's `git config user.name`/`user.email` verified as their own identity, not Cursor's
- [x] Isolated venv and output directory in place, live installation untouched
- [x] Baseline lint/type/test/coverage results recorded (pass or fail — either is fine, silence is not)
- [x] Evidence ledger location confirmed: `engine/docs/implementation/gates/`
- [x] A, B, C assigned by name; reviewer-differs-from-author agreed for every story
- [x] Group counter at zero; G10 through G52 all `NOT_RUN`

Once all of this is true, **G00 PASS** — P01 can start. Nothing above claims
any implementation or quality gate has passed; it only means it's now safe
to begin.
