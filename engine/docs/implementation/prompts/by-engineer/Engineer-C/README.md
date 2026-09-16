# Engineer C — story sequence

Your stories, in order, grouped exactly like the team-wide checkpoints. 
**A group's gate is team-wide** — even if you finish your own stories in a group early, 
do not start the next group until that group's cumulative audit records PASS in 
`engine/docs/implementation/gates/`. Help review a teammate's story or pick up an 
independent fixture/defect task instead of running ahead.


## Group 1 / G00

- `P01-E00.2.md` — E00.2 - Create Engine-only scope and compatibility guards (prereqs: None)
- `P04-E00.1.md` — E00.1 - Record the live artifact and release route (prereqs: None)
- `P06-E02.1.md` — E02.1 - Trace active SQLite, hosted and portfolio call paths (prereqs: E00.2)
- `P09-E00.3.md` — E00.3 - Establish integration, hotfix and prerelease isolation (prereqs: E00.1, E00.2)
- `P10-E15.1.md` — E15.1 - Pin corpus manifests and independent labeled fixtures (prereqs: E00.2, E01.1) — **C (coordination); A/B own their defects**

## Group 2 / G10

- `P11-E02.2.md` — E02.2 - Implement bounded file artifact storage and queries (prereqs: E01.2, E02.1)
- `P14-E02.3.md` — E02.3 - Narrow Engine surfaces and preserve supported compatibility (prereqs: E02.2)

## Group 3 / G20

- `P21-E09.1.md` — E09.1 - Pin working, staged, range and patch input states (prereqs: E01.3, E02.2)
- `P24-E09.2.md` — E09.2 - Create bounded history index and temporal metrics (prereqs: E09.1)
- `P28-E09.3.md` — E09.3 - Publish reusable change facts and equivalence fixtures (prereqs: E09.2, E03.3, E05.2)
- `P30-E15.2.md` — E15.2 - Automate deterministic and adversarial regression checks (prereqs: E15.1, E03.3, E02.3) — **C (coordination); A/B own their defects**

## Group 4 / G30

- `P32-E10.1.md` — E10.1 - Match finding lifecycle and compatible metric deltas (prereqs: E09.3, E01.3)
- `P35-E10.2.md` — E10.2 - Calculate graph delta, impact and change verdicts (prereqs: E10.1, E07.2, E08.2, E08.3)
- `P38-E10.3.md` — E10.3 - Separate source, feed and configuration causes (prereqs: E10.2, E06.3, E08.3)
- `P40-E12.1.md` — E12.1 - Serve bounded local evidence queries from artifacts (prereqs: E02.3, E11.2)

## Group 5 / G40

- `P42-E12.2.md` — E12.2 - Retain one optional local/BYO explanation path (prereqs: E12.1)
- `P44-E12.3.md` — E12.3 - Prove AI-on/off and local MCP equivalence (prereqs: E12.2, E10.3)
- `P49-E15.3.md` — E15.3 - Review candidate against every Engine release gate (prereqs: E05.3, E06.3, E07.3, E08.3, E10.3, E11.3, E12.3, E13.3, E14.3, E14.4, E15.2) — **C (coordination); A/B own their defects**
- `P50-E16.1.md` — E16.1 - Freeze and sign off the exact release candidate (prereqs: E15.3)

## Group 6 / G50

- `P51-E16.2.md` — E16.2 - Publish through the authorized Engine-only route (prereqs: E16.1)
- `P52-E16.3.md` — E16.3 - Smoke-test published artifacts and transition the team (prereqs: E16.2)
