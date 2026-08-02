# Review And Completion

Review the active diff against current authority, acceptance criteria, affected
contracts, tests, security boundaries, and evidence. Return one bounded finding
set.

- P0/P1 block.
- P2 blocks only for authority conflict, false-green, approval gate, safety
  boundary, or validator/required project-check failure.
- Ordinary P2 may be accepted with concerns or corrected directly.
- P3 does not block.

Mechanical wording, status, and EOF fixes close with a focused check. Semantic
correctives receive one targeted re-review of the affected boundary. Repeat a
full review only after permission, source-authority, or broad cross-boundary
scope changes.

Continue while findings decrease inside the same authorized corrective scope,
without asking for new approval each round. Two consecutive no-progress rounds
for the same root cause return `BLOCKED`.

Implementation completion, review verdict, submit authorization, and human
acceptance remain separate. Closeout records the accepted outcome; it never
creates acceptance. A handoff reports authority, changed surfaces, checks,
review evidence, concerns, skipped work, blockers, next action, and next owner.
