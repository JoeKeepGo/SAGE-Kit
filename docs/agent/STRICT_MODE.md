# Strict Mode

Strict Mode is the conservative execution mode for lower-assurance or unknown
AI models.

Use `docs/agent/MODEL_ASSURANCE_POLICY.md` to decide whether Strict Mode is
required.

## Purpose

Strict Mode lets agents execute SAGE-Kit work without relying on broad
architectural judgment. It narrows the task into a task card, explicit file
ownership, fixed commands, mechanical checks, and hard stop conditions.

## Controller Rule

The controller or human must prepare the task card before a
Strict Mode agent begins writable work.

The Strict Mode agent should not design the phase, widen scope, choose new
architecture, invent contracts, or decide that an approval gate can be opened.

A Strict Mode agent must not convert a phase into its own task card.

Strict Mode agents perform memory maintenance only when the task card lists the
startup docs under `Allowed to modify`. Otherwise, a complete `Memory Update
Proposal` satisfies the Strict Mode agent's memory responsibility for its task,
and the controller applies or compacts startup docs serially before the phase
can be marked `DONE`.

## Required Task Card

```markdown
Task:

Goal:

Read these files only:

Allowed to modify:

Forbidden files:

Exact steps:

Exact commands:

Completion requires:

Memory maintenance responsibility:

Stop if:

Return format:
```

## Execution Rules

- Read only the files listed in the task card.
- Modify only files listed under `Allowed to modify`.
- Do not edit shared files unless the task card names them.
- Do not infer missing requirements.
- Do not add fallback behavior.
- Do not open approval gates.
- Do not continue after a failed required command.
- Do not claim completion without the required evidence.
- Do not edit `docs/ACTIVE_CONTEXT.md` or `docs/DOC_ROUTING.md` unless the task
  card explicitly allows it.

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

Files Read:

Files Changed:

Commands Run:

Evidence:

Memory Update Proposal:

Stopped Because:

Remaining Gaps:
```

`DONE` in Strict Mode means the assigned task card is complete. It does not mean
the phase is complete when controller-owned memory maintenance, review,
integration, approval, or change-control work remains.
