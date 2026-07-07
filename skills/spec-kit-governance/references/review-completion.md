# SPEC-Kit Review And Completion

Use this reference for reviews, handoff, completion reports, milestone ledgers,
memory maintenance, closeout, commit, or push.

## Review Stance

Review for:

- spec compliance;
- file boundary drift;
- missing tests or smoke;
- unproven runtime claims;
- approval gate violations;
- hidden fallback behavior;
- stale active context;
- ledger or closeout gaps;
- ignored specialist capabilities when the runtime exposed relevant skills,
  plugins, connectors, or tools;
- unauthorized or unsafe worktree isolation;
- session orchestration packet completeness when used.

Lead with blocking findings before summaries.

## Completion Report Must Name

- scope implemented;
- files changed;
- contract evidence;
- tests run;
- runtime smoke or non-applicability reason;
- approval gates;
- security or data hygiene checks;
- memory maintenance;
- skipped checks;
- remaining gaps;
- handoff or next action.

Skipped blocking gates make the work `BLOCKED` or `HANDOFF`, not `DONE`.

## Memory Maintenance

Maintain `ACTIVE_CONTEXT.md` as a current-state snapshot:

- update current milestone, phase, objective, blocker, and next action;
- replace stale facts;
- delete completed or irrelevant facts;
- move evidence and historical detail to ledger, phase doc, completion report,
  closeout, or handoff.

Update `DOC_ROUTING.md` only when routing policy, document paths, ownership
boundaries, or archive policy changed.

If neither file needs an edit, record:

```text
Memory Maintenance: ACTIVE_CONTEXT no change; DOC_ROUTING no change.
```

## Milestone Closeout

Write or update `MILESTONE_CLOSEOUT.md` only when closing a milestone.

The closeout is a compact historical outcome index. It records:

- outcome;
- source documents;
- what shipped;
- what changed;
- key decisions;
- verification summary;
- approval gates;
- known gaps;
- follow-up milestones;
- superseded assumptions.

Do not copy raw logs, full evidence tables, or full phase reports into the
closeout. Link to evidence.

## Session Orchestration Review

When Session Orchestration is used:

- Project Manager structural gate checks packet completeness only.
- Final Review verifies independently and returns a verdict.
- Final Review checks whether Coder self review and capability routing were
  performed.
- Final Review checks whether Worktree Isolation was authorized, mapped,
  integrated, and safe when used.
- Final Review reassesses whether the milestone execution shape was safe:
  serial, waves inside phases, or parallel phases.
- Final Review cannot accept the milestone directly.
- Corrective packets must name findings, files, commands, and stop conditions.
- After the corrective round limit, return `HANDOFF` or `BLOCKED`.

## Submit Gate

Before commit, push, PR, or final handoff:

1. Check change-control state.
2. Review changed and staged files.
3. Scan for secrets or local data when applicable.
4. Run required verification.
5. Confirm completion report, ledger, and memory maintenance are current.
6. Confirm worktree submit and cleanup authority when worktrees were used.
7. Commit or hand off only intended scope.
