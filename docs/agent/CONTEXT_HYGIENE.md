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
| Phase scope and evidence | `docs/M<ID>/<phase>.md` |
| Review decision | Review report or phase completion report |
| Next action | Milestone ledger and final handoff |

