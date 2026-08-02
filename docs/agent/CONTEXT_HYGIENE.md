# Context Hygiene

Context hygiene keeps long-running AI work reliable.

## Rules

- Start with indexes, headings, symbols, and small ranges.
- Read large files only after explaining why they are needed.
- Summarize command output into decisions, errors, changed files, and next
  actions.
- Do not paste long logs into durable docs.
- Do not rely on previous chat memory when a ledger or active context should
  hold the state.
- Use document routing to avoid reading historical archives by default.
- Maintain active context by replacement, not append-only accumulation.
- Keep document routing stable unless the documentation topology or routing
  policy changes.
- Name one Startup Context Controller for each run. That controller is the only
  writer for the configured `ACTIVE_CONTEXT` path (legacy default
  `docs/ACTIVE_CONTEXT.md`) and `docs/DOC_ROUTING.md`. Workers and
  integration lanes return proposals; they never edit or race those files.

## Minimum Read Declaration

Before broad exploration, state:

- files needed;
- why each file is needed;
- expected symbol, heading, or section;
- decision the read should support.

## Durable Memory Locations

| Memory Type | Location |
|---|---|
| Current repository state | Configured `ACTIVE_CONTEXT` path; legacy default `docs/ACTIVE_CONTEXT.md` |
| Milestone progress | `docs/M<ID>/MILESTONE_LEDGER.md` |
| Milestone outcome | `docs/M<ID>/MILESTONE_CLOSEOUT.md` |
| Phase scope and evidence | `docs/M<ID>/<phase>.md` |
| Review decision | Review report or phase completion report |
| Next action | Milestone ledger and final handoff |

Historical closeouts are compressed indexes. They are not startup context. Read
them before opening historical ledgers or phase docs when prior milestone
outcomes are relevant.

## End-Of-Run Memory Maintenance

Every non-trivial agent run must close with memory maintenance before handoff,
commit, or completion. Direct edits to startup context files require both
permission mode and named Startup Context Controller ownership. If either is
missing, the agent must return a memory update proposal or explicit no-change
note for the serial controller.

For the configured `ACTIVE_CONTEXT` path:

- update current repository, branch, milestone, phase, objective, next action,
  and blocker fields when they changed;
- replace stale facts instead of appending corrections below them;
- delete closed blockers, completed objectives, and expired assumptions;
- keep evidence and historical detail in ledgers, phase docs, completion
  reports, closeouts, or handoffs.

For `docs/DOC_ROUTING.md`:

- update only when document locations, task routing, ownership boundaries, or
  archive policy changed;
- do not add session notes, progress summaries, command output, or review
  observations.

If neither file needs an edit, the Startup Context Controller records, and
workers propose, this completion note:

```text
Memory Maintenance: ACTIVE_CONTEXT no change; DOC_ROUTING no change.
```

If either file exceeds its target size budget, context growth is a compaction
duty, not an automatic completion gate. The owning controller must compact or
record an explicit compaction handoff before the context changes can be claimed
as current; this handoff is not itself `BLOCKED` and should continue once the
owning controller resolves it.
