# Context Hygiene

Context hygiene keeps long-running AI work reliable.

## Rules

- Start with indexes, headings, symbols, and small ranges.
- Read large files only after explaining why they are needed.
- Summarize command output into decisions, errors, changed files, and next
  actions.
- Do not paste long logs into durable docs.
- Do not rely on previous chat memory when active context should hold current
  state or a ledger should index immutable history/evidence.
- Use document routing to avoid reading historical archives by default.
- Maintain active context by replacement, not append-only accumulation.
- Keep document routing stable unless the documentation topology or routing
  policy changes.
- Name one Startup Context Controller when the run can change durable current
  truth. That controller is the only writer for the project-selected
  current-truth authority path and project routing authority. Workers and
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
| Current repository state | Project-selected current-truth authority path |
| Current objective/status/findings/blockers/next action | Project-selected current-truth authority path |
| Immutable milestone history/evidence index | `docs/M<ID>/MILESTONE_LEDGER.md` when selected |
| Milestone outcome | `docs/M<ID>/MILESTONE_CLOSEOUT.md` |
| Phase scope and evidence | `docs/M<ID>/<phase>.md` |
| Review decision | Review report or phase completion report |
| Bounded transfer view | Final handoff, referencing `ACTIVE_CONTEXT` |

Historical closeouts are compressed indexes. They are not startup context. Read
them before opening historical ledgers or phase docs when prior milestone
outcomes are relevant.

## End-Of-Run Memory Maintenance

Update durable memory only when current truth, routing, or handoff ownership
changed. Direct edits to startup context files require both permission mode and
named Startup Context Controller ownership; otherwise return a bounded update
proposal when a durable fact actually changed.

For the project-selected current-truth authority path:

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

Do not record no-change memory or routing notes.

If either file exceeds its target size budget, context growth is a compaction
duty, not an automatic completion gate. The owning controller must compact or
record an explicit compaction handoff before the context changes can be claimed
as current; this handoff is not itself `BLOCKED` and should continue once the
owning controller resolves it.
