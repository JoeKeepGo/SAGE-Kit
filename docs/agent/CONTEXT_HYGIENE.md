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
- Treat `docs/ACTIVE_CONTEXT.md` and `docs/DOC_ROUTING.md` as single-writer
  files during parallel or subagent work. Workers return memory update
  proposals; the controller applies or rejects them serially.

## Minimum Read Declaration

Before broad exploration, state:

- files needed;
- why each file is needed;
- expected symbol, heading, or section;
- decision the read should support.

## Durable Memory Locations

| Memory Type | Location |
|---|---|
| Current repository state | `docs/ACTIVE_CONTEXT.md` |
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
commit, or completion. If the running agent does not own the startup context
files, it must return a memory update proposal for the serial controller.

For `docs/ACTIVE_CONTEXT.md`:

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

If neither file needs an edit, the completion report or handoff must say:

```text
Memory Maintenance: ACTIVE_CONTEXT no change; DOC_ROUTING no change.
```

If either file exceeds its target size budget, the agent or controller that owns
the startup context files must compact it before claiming phase `DONE`. If the
current agent does not own those files, it must return a memory update proposal;
the controller must finish compaction before the phase can be `DONE`, or return
`HANDOFF` with the compaction gap named.
