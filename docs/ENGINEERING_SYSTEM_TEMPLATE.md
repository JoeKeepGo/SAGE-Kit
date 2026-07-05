# Engineering System Template

This document defines the daily development workflow for humans and AI agents.

## Working Principles

- Keep modules cohesive and small.
- Prefer explicit contracts over implicit shared state.
- Define ownership before editing shared files.
- Do not add speculative aliases or guessed fallback behavior.
- Preserve a runnable baseline.
- Keep planning, implementation, review, and release gates distinct.
- Make runtime behavior visible through tests, logs, UI, API responses, or
  smoke checks.
- Keep local data and secrets out of commits and reports.

## Session Roles

| Role | Owns | Must Not Do |
|---|---|---|
| Planning | Specs, milestones, phase docs, acceptance criteria. | Implement unapproved code. |
| Implementation | One approved phase or task. | Expand scope without updating the phase doc. |
| Review | Findings, risks, missing evidence, go/no-go recommendation. | Edit files during review-only work. |
| Coordinator | Context routing, lane ownership, integration, ledger updates. | Hide unresolved conflicts or skipped verification. |

## Explore

Before editing:

- check change-control state, such as branch, changelist, revision, and dirty
  files when applicable;
- read active context and routing docs;
- read the active milestone and phase doc;
- inspect relevant files with narrow searches and small ranges;
- identify contracts, tests, runtime checks, allowed files, and forbidden files.

## Plan

For non-trivial work, as defined in `docs/SPEC_CORE.md`, create or update a
retained phase document before implementation.

The plan must include:

- one observable goal;
- requirement IDs;
- file boundary;
- module ownership;
- public contract;
- test plan;
- runtime smoke;
- non-goals;
- completion gate.

## Implement

- Stay within the approved file boundary.
- Keep public contracts stable unless the phase owns the migration.
- Add or update tests with behavior changes.
- Stop and return to planning if a shared file or external approval gate is
  needed but not listed.

## Verify

Use the narrowest relevant checks during development and the full gate before
completion.

Examples:

```bash
<test command>
<typecheck command>
<runtime smoke command>
```

Any runtime claim must be proven by a live process, API call, browser check,
worker invocation, database check, or other concrete evidence.

## Submit

Before handoff or commit:

- inspect changed files;
- check staged files if staging is used;
- scan for secrets or local data when applicable;
- update completion report;
- update milestone ledger;
- name skipped checks and remaining gaps.
