# Engineering System Template

This document defines the daily development workflow for humans and AI agents.

## Working Principles

- Keep modules cohesive and small.
- Prefer explicit contracts over implicit shared state.
- Define ownership before editing shared files.
- Do not add speculative aliases or guessed fallback behavior.
- Preserve a runnable baseline.
- Keep planning, implementation, review, and release gates distinct.
- Use the lightest governance level that safely preserves scope, evidence,
  memory, and approval boundaries.
- Make runtime behavior visible through tests, logs, UI, API responses, or
  smoke checks.
- Route execution to available specialist skills, plugins, connectors, tools,
  CI, or reviewers under `docs/SAGE_CORE.md#external-capability-boundary`.
- Use `docs/agent/CAPABILITY_ADAPTERS.md` for optional providers so external
  capability use has authorization, evidence mapping, and fallback.
- Keep local data and secrets out of commits and reports.

## Session Roles

| Role | Owns | Must Not Do |
|---|---|---|
| Planning | Specs, milestones, phase docs, acceptance criteria. | Implement unapproved code. |
| Implementation | One approved phase or task. | Expand scope without updating the phase doc. |
| Review | Findings, risks, missing evidence, go/no-go recommendation. | Edit files during review-only work. |
| Coordinator | Context routing, lane ownership, integration, ledger updates. | Hide unresolved conflicts or skipped verification. |
| Project Manager Controller | Milestone direction, authority matrix, execution packet, structural gate, final decision. | Perform full technical review. |
| Coder Controller | Phase and lane worker orchestration for one milestone. | Redefine milestone scope or accept the milestone. |
| Final Review Controller | Independent review orchestration, corrective classification, and verdict. | Trust Coder self-report, accept the milestone directly, or fix code unless corrective-authorized. |
| Submit Controller | Authorized commit, push, merge, release, or worktree cleanup. | Submit unverified scope or bypass Project Manager approval. |

## Explore

Before editing:

- check change-control state, such as branch, changelist, revision, and dirty
  files when applicable;
- read active context and routing docs;
- read the active milestone and phase doc;
- inspect relevant files with narrow searches and small ranges;
- identify contracts, tests, runtime checks, allowed files, and forbidden files.

## Plan

For non-trivial work, as defined in `docs/SAGE_CORE.md`, create or update a
retained phase document before implementation.

For broad or non-technical project starts, use
`docs/agent/PROJECT_OWNER_ENTRY.md` and create a capability map before
promoting milestone candidates into an executable roadmap.

The plan must include:

- governance level: `Light`, `Standard`, or `Heavy`;
- permission mode: read-only, write-authorized, corrective-authorized,
  environment-write-authorized, or submit-authorized;
- one observable goal;
- requirement IDs;
- file boundary;
- module ownership;
- public contract;
- test plan;
- runtime smoke;
- selected capability adapters, authorization levels, and fallback paths when
  relevant;
- non-goals;
- completion gate.

External planning outputs must be written into or mapped to the retained
milestone, phase, or packet documents. Do not maintain a second planning source
of truth.

For large milestones with many phases or high handoff overhead, use
`docs/agent/SESSION_ORCHESTRATION.md` and create a milestone execution packet
instead of manually forwarding each phase between sessions.

Use `docs/agent/WORKTREE_ISOLATION.md` only when Project Manager authorizes
isolated milestone, phase, lane, or review workspaces and names submit and
cleanup authority.

Use `docs/profiles/task-dispatch/DISPATCH_PROFILE.md` only when Project Manager
adopts structured task/evidence records, resource locks, leases, and validator
closeout for the milestone.

## Implement

- Stay within the approved file boundary.
- Keep public contracts stable unless the phase owns the migration.
- Add or update tests with behavior changes.
- Stop and return to planning if a shared file or external approval gate is
  needed but not listed.
- Stop if an external capability reaches a closed approval gate, expands scope,
  conflicts on shared files or resource locks, fails required evidence, or needs
  unapproved runtime, destructive, submit, merge, push, or cleanup operations.
- Do not silently install skills, plugins, CLIs, MCP servers, hooks, generated
  skills, or global configuration.

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
- confirm submit and cleanup authority when worktrees were used;
- confirm Task Dispatch validator status when the profile is active and the
  gate requires it;
- maintain `docs/ACTIVE_CONTEXT.md` as a compact current-state snapshot;
- update `docs/DOC_ROUTING.md` only when routing or document topology changed;
- update completion report with memory maintenance status;
- record capability adapter use, authorization, evidence, and fallback when
  relevant;
- update milestone ledger;
- name skipped checks and remaining gaps.
