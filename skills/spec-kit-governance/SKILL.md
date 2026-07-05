---
name: spec-kit-governance
description: SPEC-Kit governance workflow for AI-assisted projects. Use when working in or adopting a SPEC-Kit governed repository; when the user mentions SPEC-Kit, SPEC, Agent Harness, ACTIVE_CONTEXT, DOC_ROUTING, milestones, phases, ledgers, closeouts, Strict Mode, Wave Execution, quality gates, approval gates, handoff, or completion reports; or when Codex must plan, implement, review, or finish work without drifting from the project's SPEC framework.
---

# SPEC-Kit Governance

Use this skill to keep AI work aligned with SPEC-Kit without loading the whole
framework into context.

## Core Rule

Do not read every SPEC-Kit document by default. Start from the active project
context and let `docs/DOC_ROUTING.md` decide the narrow read set.

Historical ledgers, phase docs, completion reports, and closeouts are not
startup context.

## Detect The Situation

1. Identify the active repository boundary and change-control state.
2. Check for SPEC-Kit project markers:
   - `docs/ACTIVE_CONTEXT.md`
   - `docs/DOC_ROUTING.md`
   - `docs/PROJECT_PROFILE.md`
   - `docs/agent/AGENT_HARNESS.md`
3. If project docs are missing but the user wants to adopt or bootstrap
   SPEC-Kit, read `references/adoption.md`.
4. If this is the SPEC-Kit source repository, edit kit templates or skills only
   when requested; do not expect instantiated project docs to exist.
5. If the repo is not SPEC-Kit governed and the user did not ask to adopt it,
   do not impose SPEC-Kit.

## Default Startup

For a SPEC-Kit governed project:

1. Read `docs/ACTIVE_CONTEXT.md`.
2. Read `docs/DOC_ROUTING.md`.
3. Read only the active milestone ledger, phase doc, contract docs, or gates
   named by routing and task scope.
4. Before writable work, name allowed files, read-only files, forbidden files,
   gates, verification commands, and stop conditions.

If required startup docs are missing or contradictory, stop and report the gap
before editing.

## Task Routing

- Adoption or bootstrap: read `references/adoption.md`.
- Milestone, roadmap, or phase planning: read `references/planning.md`.
- Implementation, debugging, refactor, or subagent execution: read
  `references/execution.md`.
- Review, handoff, completion, or closeout: read
  `references/review-completion.md`.

Read only the reference files needed for the current task.

## Guardrails

- Keep one task tied to one approved phase unless a batch plan defines order,
  gates, and stop conditions.
- Do not invent missing contracts, fallback behavior, or success evidence.
- Do not edit outside the approved file boundary.
- Do not open approval gates without explicit user approval.
- Do not treat historical closeouts as startup context.
- Do not claim `DONE` unless required verification and memory maintenance are
  complete.
- Use Strict Mode according to `docs/agent/MODEL_ASSURANCE_POLICY.md`; do not
  guess the policy from memory.
- Use Wave Execution only when file ownership is disjoint and serial gates stay
  serial.

## End Of Run

Before final handoff, commit, or completion:

1. Run the required checks or state why they cannot run.
2. Maintain `docs/ACTIVE_CONTEXT.md` by replacement, not append-only history,
   or return a memory update proposal when the task does not own that file.
3. Update `docs/DOC_ROUTING.md` only when routing or document topology changed,
   or record that no routing change is needed.
4. Update the completion report and milestone ledger with memory maintenance
   status when the task owns them.
5. Write or update `MILESTONE_CLOSEOUT.md` only when closing a milestone.
6. Report skipped checks, blockers, remaining gaps, and next action.
