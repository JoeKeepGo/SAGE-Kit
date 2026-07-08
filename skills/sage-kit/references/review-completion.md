# SAGE-Kit Review And Completion

Use this reference for reviews, handoff, completion reports, milestone ledgers,
memory maintenance, closeout, commit, or push.

## Review Stance

Review for:

- spec compliance;
- milestone granularity and primary capability alignment;
- file boundary drift;
- missing tests or smoke;
- unproven runtime claims;
- approval gate violations;
- hidden fallback behavior;
- stale active context;
- ledger or closeout gaps;
- ignored specialist capabilities when the runtime exposed relevant skills,
  plugins, connectors, or tools;
- external capability output treated as gate completion instead of evidence;
- adapter authorization, fallback, or evidence mapping missing when an external
  capability was selected;
- external plans that were not mapped into tracked SAGE-Kit docs;
- unauthorized or unsafe worktree isolation;
- incomplete task-dispatch records or failed validator results when Task
  Dispatch Profile is active;
- session orchestration packet completeness when used.
- Coder Controller self-executed broad milestone work instead of staying within
  the execution packet's self-execution policy;
- Wave Execution was claimed without lane independence, exclusive writable
  files, runtime ownership, integration owner, or serial gate protection.
- governance level was recorded without a matching permission mode;
- read-only review was treated as closure after required corrections were
  found;
- `Corrective Packet Required: yes` appeared without a corrective packet,
  Project Manager decision request, blocker, or waiver path.

Lead with blocking findings before summaries.

## Completion Report Must Name

- scope implemented;
- governance level;
- permission mode;
- controls enabled, and controls not enabled when the control was considered or
  relevant;
- upgrade triggers when relevant, or a `none` note when the governance decision
  needs an explicit record;
- stopped worker or controller decision status when applicable;
- Coder execution mode and self-execution policy status when Session
  Orchestration is used;
- wave readiness decision when Wave Execution or parallel phases are used;
- corrective closure status when a review finds required corrections;
- files changed;
- contract evidence;
- specialist capabilities used when relevant;
- capability adapters selected, authorization level, fallback, and evidence
  mapping when an adapter was selected, considered, unavailable, or produced
  evidence;
- superpowers skills used when available and relevant;
- external capability boundary and evidence produced when external capability
  output was used;
- external planning output destination when external planning was used;
- tests run;
- runtime smoke or non-applicability reason;
- approval gates;
- task-dispatch validator result when the profile is active for the current
  task, phase, or gate;
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

Direct edits to `ACTIVE_CONTEXT.md` or `DOC_ROUTING.md` require permission mode
and ownership. If either is missing, return a `Memory Update Proposal` or record
an explicit no-change note.

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
- Final Review records its permission mode and preserves write, corrective,
  submit, and cleanup authority boundaries.
- Final Review checks whether Coder self review and capability routing were
  performed.
- Final Review checks whether selected superpowers skills, if available and
  relevant, stayed inside SAGE-Kit scope, locks, gates, and evidence
  requirements.
- Final Review treats external skill, plugin, connector, or tool completion as
  evidence to verify, not as SAGE-Kit acceptance.
- Final Review checks whether Worktree Isolation was authorized, mapped,
  integrated, and safe when used.
- Final Review reassesses whether the milestone execution shape was safe:
  serial, waves inside phases, or parallel phases.
- Final Review checks whether Coder self-execution was allowed, narrow, and
  independently verified. Broad self-executed milestone implementation is a
  review risk and may require correction or Project Manager decision.
- Final Review cannot accept the milestone directly.
- Final Review classifies each required correction as `AUTO_CORRECTIVE`,
  `PM_DECISION`, `BLOCKED`, or `DEFER`.
- If Final Review is read-only, it must return a packet-only corrective handoff,
  Project Manager decision request, blocker, or waiver path instead of editing.
- If corrective execution is authorized, Final Review may open a bounded
  corrective round and must require verification and re-review.
- Corrective re-review must produce independent evidence before Final Review
  closes the verdict.
- Rerun affected review workers, review subagents, or validation lanes when the
  original review used them, the fix touches behavior, contracts, runtime,
  shared files, gates, or the regression surface is unclear.
- Corrective packets must name findings, classification, files, commands,
  permission mode, and stop conditions.
- After the corrective round limit, return `HANDOFF` or `BLOCKED`.

## Submit Gate

Before commit, push, PR, or final handoff:

1. Check change-control state.
2. Review changed and staged files.
3. Scan for secrets or local data when applicable.
4. Run required verification.
5. Confirm completion report, ledger, and memory maintenance are current.
6. Confirm worktree submit and cleanup authority when worktrees were used.
7. Confirm Task Dispatch validator success when the profile is active and the
   gate requires it.
8. Commit or hand off only intended scope.
