# M<ID> Milestone Closeout: <Name>

Use this file when closing a milestone.

This file is a historical outcome index, not startup context. Keep it concise
enough to answer what happened, what shipped, what remains, and where to find
evidence without rereading every phase document.

Completed closeout target size: 80-150 lines. Link to ledgers, phase docs,
completion reports, and change refs instead of copying raw evidence tables or
command output.

## Outcome

- Status: `DONE`, `DONE_WITH_CONCERNS`, `HANDOFF`, `BLOCKED`, or `SUPERSEDED`
- Closed on: `<date or change ref>`
- Owner: `<owner>`
- Change refs: `<commit, PR, changelist, release, or n/a>`

## Source Documents

- Entry gate: `docs/M<ID>/00-entry-gate.md`
- Ledger: `docs/M<ID>/MILESTONE_LEDGER.md`
- Phase docs:
  - `<phase doc>`
- Completion reports:
  - `<phase or report path>`

## What Shipped

- `<capability, artifact, contract, workflow, or operational result>`

## What Changed

- `<product, architecture, API, UI, data, runtime, test, or process change>`

## Key Decisions

| Decision | Rationale | Source |
|---|---|---|
| `<decision>` | `<why>` | `<ledger, phase, commit, or report>` |

## Verification Summary

- Tests: `<summary and source link>`
- Runtime smoke: `<summary and source link or n/a reason>`
- Review: `<summary and source link>`
- Security or data hygiene: `<summary and source link>`

## Approval Gates

| Gate | Final Status | Evidence | Notes |
|---|---|---|---|
| `<gate>` | `PASS`, `WAIVED`, `BLOCKED`, or `N/A` | `<source>` | `<notes>` |

## Known Gaps

- `<gap, owner, follow-up, or none>`

## Follow-Up Milestones

- `<M<ID> or backlog item>`

## Superseded Assumptions

- `<assumption that is no longer valid or none>`

## Archive Notes

- Do not use this file as default startup context.
- Read this file before opening historical ledgers or phase docs.
- Open detailed evidence only when the closeout does not answer the current
  question or provenance must be verified.
