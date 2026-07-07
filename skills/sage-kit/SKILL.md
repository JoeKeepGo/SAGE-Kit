---
name: sage-kit
description: "Use when SAGE-Kit is explicit: the user invokes $sage-kit, asks to adopt or bootstrap SAGE-Kit, or references SAGE-Kit docs or constructs such as ACTIVE_CONTEXT, DOC_ROUTING, Governance Levels, Authority Matrix, Agent Harness, milestones, phase docs, ledgers, closeouts, gates, Strict Mode, Wave Execution, Session Orchestration, Worktree Isolation, Task Dispatch, or Capability Adapters. Do not use for ordinary coding, planning, review, or debugging unless SAGE-Kit is explicit."
---

# SAGE-Kit

Use this skill to keep AI work aligned with SAGE-Kit without loading the whole
framework into context.

SAGE-Kit is governance, not a skill library. It controls scope,
authorization, file boundaries, gates, evidence, locks, memory, and completion
status. External skills, plugins, connectors, and tools provide execution
methods inside those approved boundaries.

Task Dispatch is an internal optional SAGE-Kit profile. Superpowers and other
skills, plugins, MCP tools, CLIs, CI systems, reviewers, frontend builders,
OpenSpec, GitNexus, browser tools, and database tools are optional capability
adapters unless a project explicitly defines a narrower policy.

This skill does not replace the project's own specification documents. The project
remains responsible for maintaining its `docs/` profile, design, gates, active
context, routing, milestones, phase docs, ledgers, completion reports, and
closeouts.

## Core Rule

Do not read every SAGE-Kit document by default. Start from the active project
context and let `docs/DOC_ROUTING.md` decide the narrow read set.

Historical ledgers, phase docs, completion reports, and closeouts are not
startup context.

Context budget is a guardrail, not a correctness cap. Expand the read set when
correctness, safety, provenance, full milestone review, or final acceptance
requires it, but state why the extra context is needed and what decision it
supports.

## Detect The Situation

1. Identify the active repository boundary and change-control state.
2. Check for SAGE-Kit project markers:
   - `docs/ACTIVE_CONTEXT.md`
   - `docs/DOC_ROUTING.md`
   - `docs/PROJECT_PROFILE.md`
   - `docs/agent/AGENT_HARNESS.md`
3. If project docs are missing but the user wants to adopt or bootstrap
   SAGE-Kit, read `references/adoption.md`.
4. If this is the SAGE-Kit source repository, edit kit templates or skills only
   when requested; do not expect instantiated project docs to exist.
5. If the repo is not SAGE-Kit governed and the user did not ask to adopt it,
   do not impose SAGE-Kit.

## Default Startup

For a SAGE-Kit governed project:

1. Read `docs/ACTIVE_CONTEXT.md`.
2. Read `docs/DOC_ROUTING.md`.
3. Read only the active milestone ledger, phase doc, contract docs, or gates
   named by routing and task scope.
4. Select the governance level and permission mode for the current control
   scope using `docs/agent/GOVERNANCE_LEVELS.md` when the task is non-trivial,
   delegated, controller-level, review, corrective, environment-writing, or
   submit-related.
5. When external capabilities are relevant, read
   `docs/agent/CAPABILITY_ADAPTERS.md` or the project routing entry that
   defines the adapter boundary.
6. Before writable work, name allowed files, read-only files, forbidden files,
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

## Context Budget

Prefer narrow reads in this order:

1. active context and routing;
2. active milestone, phase, gate, or packet docs;
3. capability metadata before capability bodies;
4. closeouts before historical ledgers;
5. targeted searches or ranges before full archives.

Do not read every specification document, phase doc, ledger, closeout, skill body,
plugin body, or log by default. If a broad read is required, say why and
summarize the useful result into the ledger, closeout, completion report, or
handoff.

## Guardrails

- Keep one task tied to one approved phase unless a batch plan defines order,
  gates, and stop conditions.
- Do not invent missing contracts, fallback behavior, or success evidence.
- Do not edit outside the approved file boundary.
- Do not open approval gates without explicit user approval.
- Do not treat historical closeouts as startup context.
- Do not claim `DONE` unless required verification and memory maintenance are
  complete.
- Use `docs/agent/GOVERNANCE_LEVELS.md` to choose the lightest governance level
  that safely preserves scope, evidence, memory, and approval boundaries, and
  choose the matching permission mode for read-only, write, corrective,
  environment-write, or submit authority. Heavy controller work may delegate
  Light or Standard workers.
- Do not treat `READ_ONLY_REVIEW` as closure when findings require correction,
  Project Manager decision, blocker handling, or waiver. A read-only review
  that returns `NEEDS_CORRECTION` must include a corrective packet, handoff, or
  blocker.
- Do not let parallel workers or subagents edit `docs/ACTIVE_CONTEXT.md` or
  `docs/DOC_ROUTING.md` directly. They must return memory update proposals for
  controller integration.
- Do not let SAGE-Kit displace specialist skills, plugins, connectors, or
  tools. Use available capability metadata to select the right specialist
  capability before delegating or executing domain work.
- Use Capability Adapters for optional external skills, plugins, MCP tools,
  CLIs, CI systems, reviewers, frontend skills, OpenSpec, GitNexus, browser
  QA, and database tools. Detect, authorize, bound, invoke, capture, map, and
  fall back without making them core dependencies.
- Do not silently install external skills, plugins, CLIs, MCP servers, hooks,
  generated skills, or global configuration. Recommend or request installation
  only when the source, writes, fallback, and approval path are explicit.
- Treat superpowers as a reference integration, not a dependency. When
  available and relevant, selected superpowers skills may guide execution
  inside an approved SAGE-Kit boundary. If unavailable, continue with SAGE-Kit
  phase, gate, packet, and evidence templates.
- Do not treat external capability completion as SAGE-Kit gate completion.
  Record it as execution evidence and keep gate decisions in SAGE-Kit docs.
- Use Strict Mode according to `docs/agent/MODEL_ASSURANCE_POLICY.md`; do not
  guess the policy from memory.
- Use Wave Execution only when file ownership is disjoint and serial gates stay
  serial.
- Use Session Orchestration only for large milestones where Project Manager,
  Coder, and Final Review controller packets reduce handoff overhead without
  weakening gates.
- In Session Orchestration, Coder Controller orchestrates workers by default.
  It may self-execute only when the execution packet explicitly allows a narrow
  phase, glue step, or corrective fix, and it must record why worker dispatch
  was skipped.
- Final Review must classify required corrections as `AUTO_CORRECTIVE`,
  `PM_DECISION`, `BLOCKED`, or `DEFER`. If corrective execution is authorized,
  it may open a bounded corrective round; if review is read-only, it must return
  a packet-only corrective handoff or blocker.
- Do not claim Wave Execution or parallel phases unless Wave Readiness is
  proven with independent lanes, exclusive writable files, serial shared files,
  frozen contracts, runtime ownership, validation lanes, and integration owner.
- Use Worktree Isolation only when Project Manager authorization names the
  allowed mode, maximum count, naming, integration owner, submit authority, and
  cleanup policy.
- Use Task Dispatch Profile only when project routing, the milestone entry
  gate, or the execution packet adopts structured task/evidence records and
  validator closeout.
- Use Project Owner Entry for broad or non-technical ideas, but do not promote
  its draft outputs into an executable roadmap until a capability map and
  Milestone Granularity Gate pass.

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
6. Update task/evidence records and run the dispatch validator only when Task
   Dispatch Profile is active for the current task or gate.
7. Report skipped checks, blockers, remaining gaps, and next action.
