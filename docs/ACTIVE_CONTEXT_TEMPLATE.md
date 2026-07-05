# Active Context Template

This file is the short startup context for the active repository.

It should be concise enough to read at the start of every future session.

## Active Repository Boundary

- Active local repository: `<absolute path>`
- Active remote: `<remote URL or n/a>`
- Active branch or baseline: `<branch, commit, changelist, release, or n/a>`
- Current milestone: `<milestone ID or none>`
- Current phase: `<phase path or none>`

## Current Accepted State

- `<accepted fact>`
- `<accepted fact>`

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

## Non-Goals For This Context Layer

- No broad historical summary.
- No raw logs.
- No secrets.
- No implementation instructions that belong in phase docs.
