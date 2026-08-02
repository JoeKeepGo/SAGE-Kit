# M<ID> Milestone Closeout: <Name>

Use this file when closing a milestone.

Closeout order, terminal status eligibility, and the startup-context boundary
are canonical at `docs/templates/MILESTONE_TEMPLATE.md#sage-lif-011`. This
template records the resulting historical outcome and does not decide whether
the milestone may close.

Waiver meaning is canonical at
`docs/agent/GOVERNANCE_LEVELS.md#sage-auth-008`. This closeout retains the
project-instance Finding Owner, Waiver Authority, decision/delegation, and
human-authority evidence fields.

This file is a historical outcome index, not startup context. Keep it concise
enough to answer what happened, what shipped, what remains, and where to find
evidence without rereading every phase document.

Completed closeout target size: 80-150 lines. Link to ledgers, phase docs,
completion reports, and change refs instead of copying raw evidence tables or
command output.

## Outcome

- Status: `DONE`, `DONE_WITH_CONCERNS`, `CLOSED_BLOCKED`, `DEFERRED`,
  `ABANDONED`, or `SUPERSEDED`
- Closed on: `<date or change ref>`
- Owner: `<owner>`
- Final Review verdict/ref:
- Corrective convergence status/ref:
- Project Manager/project-owner decision/ref:
- Change refs: `<commit, PR, changelist, release, or n/a>`

Record no `HANDOFF` closeout. Use `CLOSED_BLOCKED`, `DEFERRED`, or `ABANDONED`
only after the canonical closeout sequence produces that authorized decision.

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

| Gate | Final Status | Evidence | Finding Owner | Waiver Authority | Decision Or Delegation Ref | Notes |
|---|---|---|---|---|---|---|
| `<gate>` | `PASS`, `WAIVED`, `BLOCKED`, or `N/A` | `<source>` | `<owner or n/a>` | `<authority or n/a>` | `<explicit decision/delegation ref or n/a>` | `<notes>` |

Complete these local fields under
`docs/agent/GOVERNANCE_LEVELS.md#sage-auth-008`.

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
