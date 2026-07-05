# Active Context Template

This file is the short startup context for the active repository.

It should be concise enough to read at the start of every future session.

Maintain this file as a current-state snapshot, not an execution log. At the
end of any agent run that changes durable state, replace stale facts, remove
closed or irrelevant items, and keep only information needed to restart work
safely.

## Active Repository Boundary

- Active local repository: `<absolute path>`
- Active remote: `<remote URL or n/a>`
- Active branch or baseline: `<branch, commit, changelist, release, or n/a>`
- Current milestone: `<milestone ID or none>`
- Current phase: `<phase path or none>`

## Current Accepted State

- `<accepted fact>`
- `<accepted fact>`

## Current Work Pointer

- Active objective: `<objective or none>`
- Next action: `<single next action or none>`
- Current blocker: `<blocker or none>`

## Current Source Of Truth

| Role | File |
|---|---|
| Product profile | `docs/PROJECT_PROFILE.md` |
| Technical design | `docs/TECHNICAL_DESIGN.md` |
| Quality gates | `docs/QUALITY_GATES.md` |
| Roadmap | `docs/MILESTONE_ROADMAP.md` |
| Active milestone ledger | `<path>` |

## Closed Gates

These gates remain closed unless the user explicitly opens one with scope,
inputs, and objective:

- production credentials;
- production data access;
- destructive actions;
- release or publish;
- merge to protected branches;
- protected branch or release-target changes, when change control uses them;
- external service mutation;
- billing or payment operations.

## Startup Read Shortcut

For most future work:

1. Read this file.
2. Read `docs/DOC_ROUTING.md`.
3. Read the active milestone ledger and phase doc only when relevant.
4. Read exact contract docs only for touched surfaces.

## End-Of-Run Maintenance

Before handoff, commit, or completion:

1. Update repository, branch, milestone, phase, objective, next action, and
   blocker fields when they changed.
2. Replace obsolete accepted facts with the current fact.
3. Delete facts that are no longer needed for startup.
4. Move evidence, command output, review notes, and historical detail to the
   milestone ledger, phase doc, completion report, or milestone closeout for
   closed milestones.
5. Record `No active context change needed` in the handoff or completion report
   when this file does not require an edit.

Target size: keep this file under 120 lines unless the project profile
explicitly raises the startup-context budget.

## Non-Goals For This Context Layer

- No broad historical summary.
- No raw logs.
- No secrets.
- No implementation instructions that belong in phase docs.
- No completed milestone diary.
- No evidence tables that belong in ledgers or completion reports.
