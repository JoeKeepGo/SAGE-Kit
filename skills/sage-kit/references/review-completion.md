# Review And Completion

Review the active diff against current authority, acceptance criteria, affected
contracts, tests, security boundaries, and evidence. Return one bounded finding
set.

- P0/P1 block.
- P2 blocks only for authority conflict, false-green, approval gate, security
  boundary, or failed required verification.
- Ordinary documentation consistency P2 may be accepted with concerns or
  corrected directly.
- P3 does not block.

Correct only the affected boundary and perform targeted re-review. Repeat full
review only after semantic, permission, source-authority, or cross-boundary
contract change.

Implementation completion, review verdict, submit authorization, and human
acceptance remain separate. Closeout records the accepted outcome; it never
creates acceptance. A handoff reports authority, changed surfaces, checks,
review evidence, concerns, skipped work, blockers, next action, and next owner.
