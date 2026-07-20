# Active Context Template

This is a compact current-truth and handoff view. Its configured path may differ;
`docs/ACTIVE_CONTEXT.md` remains the legacy default. Harness runtime state and
full history do not belong here.

## Current Work

- Current milestone: `<milestone ID or none>`
- Current phase: `<phase ID or none>`
- Current status: `<planned, active, blocked, review, complete, or none>`
- Current authority: `<explicit source, configured source, current-work pointer, or legacy adapter>`
- Active SPEC source: `<project-relative path or none>`
- Current blockers: `<concise blockers or none>`
- Next action: `<single next action or none>`

## Key Decisions

- `<decision that current work must preserve>`
- `<decision or none>`

## Evidence And Closeout

- Evidence pointer: `<path or digest reference or none>`
- Closeout pointer: `<path or none>`

## Maintenance

Replace stale current facts; do not append a session diary. Put leases,
candidate counters, command logs, detailed evidence, and accepted history under
`.sagekit`, an evidence store, ledger, or closeout as appropriate.

Ordinary status, next-action, evidence-pointer, path-display, blank-line, and
wording synchronization is C0/C1 and needs targeted consistency verification
only. Authority, scope, approval, safety boundary, or source-of-truth changes
require semantic review. Check and compile never rewrite this file.
