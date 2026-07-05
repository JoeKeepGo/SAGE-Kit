# Agent Harness

The Agent Harness defines how AI agents work inside a SPEC-Kit project.

The harness does not replace the project spec. It tells agents how to execute
against the spec without losing context, widening scope, or hiding risk.

## Operating Rules

- Read the smallest safe context first.
- Identify the active phase before editing.
- Name allowed files, read-only files, and forbidden files before writable work.
- Use Wave Execution for safe parallel work inside a phase.
- Keep one task tied to one phase unless a batch execution plan explicitly
  defines phase order, gates, and stop conditions.
- Do not invent missing contracts.
- Do not use placeholder success for failed runtime behavior.
- Do not touch closed approval gates.
- Update durable docs before handoff.

## Strict Mode Trigger

Use `docs/agent/MODEL_ASSURANCE_POLICY.md` to decide whether the executor must
use Strict Mode.

Strict Mode reduces judgment requirements by turning a phase into a narrow task
card with explicit reads, allowed files, forbidden files, exact commands,
completion evidence, and stop conditions.

When in doubt, use Strict Mode.

## Agent Startup Checklist

1. Read `docs/ACTIVE_CONTEXT.md`.
2. Read `docs/DOC_ROUTING.md`.
3. Read active milestone ledger and phase doc when applicable.
4. Check change-control state, such as branch, changelist, revision, and dirty
   files when applicable.
5. Identify likely files and required verification.
6. Report blockers before editing.

## Batch Execution

Batch execution across phases is opt-in.

Before batch execution starts, the controller must record:

- phase order;
- gate status required between phases;
- stop conditions;
- ledger update points;
- approval gates that remain closed;
- final integration owner.

A batch run must stop when any phase has a blocking `FAIL`, `BLOCKED`, or
unapproved `WAIVED` gate.

## File Ownership

Before writable work starts, record:

| Lane | Role | Allowed Files | Forbidden Files | Integration Owner |
|---|---|---|---|---|
| `<lane>` | `<read-only / writable / validation / serial>` | `<files>` | `<files>` | `<owner>` |

Parallel writable lanes must have exclusive allowed files. If two lanes need
the same file, they are not parallel lanes; merge them, make one read-only, or
assign the shared file to a serial controller lane.

For parallel work, use `docs/agent/WAVE_EXECUTION.md` and return lane results
with `docs/templates/LANE_PACKET_TEMPLATE.md`.

## Handoff Packet

Use `docs/agent/HANDOFF_TEMPLATE.md` for phase/session handoff and
`docs/templates/LANE_PACKET_TEMPLATE.md` for lane handoff.

## Completion Rule

The agent may claim `DONE` only after verification evidence is fresh and no
blocking gate is skipped, failed, or unresolved.

Use `BLOCKED` when a required gate cannot produce evidence.

Use `HANDOFF` when work is intentionally paused for review, approval, or
controller integration.

See `docs/agent/STRICT_MODE.md` for the stricter execution contract.
