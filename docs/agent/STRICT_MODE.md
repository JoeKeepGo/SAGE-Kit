# Strict Mode

Strict Mode is an explicitly selected conservative mode for a project/human
policy or a concrete low-assurance, high-risk trigger. Unknown identity alone
does not enable it.

Use `docs/agent/MODEL_ASSURANCE_POLICY.md` to decide whether Strict Mode is
required.

## Purpose

Strict Mode lets agents execute SAGE-Kit work without relying on broad
architectural judgment. It narrows the task into a task card, explicit file
ownership, fixed commands, mechanical checks, and hard stop conditions.

## Controller Rule

The controller or human must prepare the task card before a
Strict Mode agent begins writable work.

The Strict Mode agent should not design the phase, widen scope, choose or change
architecture, invent contracts, or decide that an approval gate can be opened.

A Strict Mode agent must not convert a phase into its own task card.

Strict Mode agents update durable truth only when it changed and the task card
lists the startup doc under `Allowed to modify`. Otherwise they return a bounded
`Memory Update Proposal` only for an actual change; no-change notes are omitted.

## Required Task Card

```markdown
Task:

Goal:

Governance Level:

Permission Mode:

Read these files only:

Allowed to modify:

Forbidden files:

Exact steps:

Exact commands:

Completion requires:

Durable-truth update responsibility (only when changed):

Stop if:

Return format:
```

## Execution Rules

- Read only the files listed in the task card.
- Modify only files listed under `Allowed to modify`.
- Do not edit shared files unless the task card names them.
- Do not infer missing requirements.
- Do not add fallback behavior unless the task card or active SPEC explicitly
  authorizes it.
- Do not open approval gates.
- Do not continue after a failed required command.
- Do not claim completion without the required evidence.
- Do not edit the project-selected current-truth or routing authority paths
  unless the task card explicitly allows it.

## Hard Stop Conditions

Stop and report `BLOCKED` when:

- a required file is not listed in the task card;
- a needed edit is outside `Allowed to modify`;
- a test, build, or smoke command fails;
- a contract field is unclear;
- the task requires opening, using, or changing an approval gate that is not
  explicitly approved in the task card;
- a command asks for credentials, production data, destructive action, release,
  publish, or protected-branch merge;
- verification evidence cannot be produced.

## Return Format

```markdown
Status: DONE or BLOCKED

Governance Level:

Permission Mode:

Files Read:

Files Changed:

Commands Run:

Evidence:

Memory Update Proposal:

Stopped Because:

Remaining Gaps:
```

`DONE` in Strict Mode means the assigned task card is complete. It does not mean
the phase is complete when a required durable-truth update, review, integration,
approval, or change-control action remains.
