# SPEC-Kit

[English](README.md) | [中文](README.zh-CN.md)

SPEC-Kit is a reusable project specification system and AI agent execution
harness.

It helps teams define what a project is, how it should evolve, and how AI
agents should safely perform work inside it. The kit separates durable project
specification from execution governance so that product, architecture, tests,
and agent workflows can stay aligned over many sessions.

## What SPEC-Kit Provides

- A core project specification model.
- Templates for project profiles, milestones, phases, ledgers, closeouts,
  quality gates, approval gates, and completion reports.
- Project Owner Entry for turning a non-technical idea into a lightweight
  intake, project profile draft, capability map, and candidate milestones
  before executable planning starts.
- An AI agent harness for context control, file ownership, verification,
  handoff, and review.
- Wave Execution for safe parallel development inside a phase.
- Session Orchestration for milestone-level Project Manager, Coder, and Final
  Review controller workflows.
- Worktree Isolation for controlled phase, lane, or review workspaces when the
  Project Manager authorizes isolated execution.
- Task Dispatch Profile for structured task records, evidence records,
  resource locks, Run/Attempt/Lease tracking, and validator-backed gate
  closeout when a milestone needs stronger dispatch control.
- Capability routing so controllers can delegate to relevant skills, plugins,
  connectors, or tools instead of letting governance instructions displace
  specialist capabilities.
- Milestone planning rules that force capability maps, reviewable milestones,
  and testable phase slices before implementation.
- Strict Mode for lower-assurance or unknown model families.
- Optional profile packs for common project shapes, such as state-machine
  systems and control-plane plus execution-agent systems.
- A default model assurance policy that projects may make stricter.

## Core Idea

SPEC defines the project contract.

Harness defines how AI agents execute against that contract.

Project profiles adapt the shared rules to a specific architecture without
polluting the reusable core.

## Kit Contents

```text
docs/
  SPEC_CORE.md
  *_TEMPLATE.md
  agent/
    AGENT_HARNESS.md
    MODEL_ASSURANCE_POLICY.md
    STRICT_MODE.md
    PROJECT_OWNER_ENTRY.md
    WAVE_EXECUTION.md
    SESSION_ORCHESTRATION.md
    WORKTREE_ISOLATION.md
    MILESTONE_PLANNING.md
  profiles/
    state-machine/
    control-plane-agent/
    task-dispatch/
  templates/
    PROJECT_OWNER_INTAKE_TEMPLATE.md
    CAPABILITY_MAP_TEMPLATE.md
    *_TEMPLATE.md
scripts/
  validate_task_dispatch.py
skills/
  spec-kit-governance/
```

## Bundled Skill

SPEC-Kit includes `skills/spec-kit-governance`, a Codex skill that helps agents
stay aligned with the framework during adoption, planning, implementation,
review, handoff, and milestone closeout.

The skill is intentionally a governance entrypoint, not a copy of every
SPEC-Kit document. It tells agents to read `ACTIVE_CONTEXT.md` and
`DOC_ROUTING.md` first, then load only the milestone, phase, gate, or historical
closeout files required by the task.

To use it in another environment, copy `skills/spec-kit-governance` into the
Codex skills directory and invoke:

```text
Use $spec-kit-governance to plan and execute this task under SPEC-Kit.
```

The skill is designed for explicit invocation so it does not displace more
specific coding, frontend, document, GitHub, or review skills during ordinary
work.

The skill can help bootstrap SPEC-Kit in a new project, but the project still
needs to adopt the relevant templates and maintain its own SPEC documents.

## Recommended Project Layout

```text
docs/
  ACTIVE_CONTEXT.md
  DOC_ROUTING.md
  PROJECT_PROFILE.md
  TECHNICAL_DESIGN.md
  ENGINEERING_SYSTEM.md
  QUALITY_GATES.md
  APPROVAL_GATES.md
  CAPABILITY_MAP.md       # conditional for broad, non-technical, or coarse-roadmap projects
  MILESTONE_ROADMAP.md
  agent/
    AGENT_HARNESS.md
    MODEL_ASSURANCE_POLICY.md
    STRICT_MODE.md
    PROJECT_OWNER_ENTRY.md
    WAVE_EXECUTION.md
    SESSION_ORCHESTRATION.md
    WORKTREE_ISOLATION.md
    MILESTONE_PLANNING.md
  templates/
    PROJECT_OWNER_INTAKE_TEMPLATE.md
    CAPABILITY_MAP_TEMPLATE.md
    PHASE_TEMPLATE.md
    MILESTONE_LEDGER_TEMPLATE.md
    MILESTONE_CLOSEOUT_TEMPLATE.md
    MILESTONE_EXECUTION_PACKET_TEMPLATE.md
    MILESTONE_RESULT_PACKET_TEMPLATE.md
    STRUCTURAL_GATE_TEMPLATE.md
    FINAL_REVIEW_PACKET_TEMPLATE.md
    CORRECTIVE_PACKET_TEMPLATE.md
    COMPLETION_REPORT_TEMPLATE.md
    LANE_PACKET_TEMPLATE.md
  M<ID>/
    00-entry-gate.md
    MILESTONE_LEDGER.md
    MILESTONE_CLOSEOUT.md  # created at milestone closure
    01-phase-name.md
    dispatch/              # optional task-dispatch profile records
      DISPATCH_BOARD.md
      TASK-001/
        task.yaml
        evidence.yaml
```

## Copy Map

Use this map when adopting SPEC-Kit into a project.

| SPEC-Kit Source | Project Destination |
|---|---|
| `docs/PROJECT_PROFILE_TEMPLATE.md` | `docs/PROJECT_PROFILE.md` |
| `docs/TECHNICAL_DESIGN_TEMPLATE.md` | `docs/TECHNICAL_DESIGN.md` |
| `docs/ENGINEERING_SYSTEM_TEMPLATE.md` | `docs/ENGINEERING_SYSTEM.md` |
| `docs/QUALITY_GATES_TEMPLATE.md` | `docs/QUALITY_GATES.md` |
| `docs/APPROVAL_GATES_TEMPLATE.md` | `docs/APPROVAL_GATES.md` |
| `docs/ACTIVE_CONTEXT_TEMPLATE.md` | `docs/ACTIVE_CONTEXT.md` |
| `docs/DOC_ROUTING_TEMPLATE.md` | `docs/DOC_ROUTING.md` |
| `docs/templates/PROJECT_OWNER_INTAKE_TEMPLATE.md` | Optional `docs/PROJECT_OWNER_INTAKE.md` |
| `docs/templates/CAPABILITY_MAP_TEMPLATE.md` | `docs/CAPABILITY_MAP.md` for broad, non-technical, or coarse-roadmap projects |
| `docs/templates/MILESTONE_ROADMAP_TEMPLATE.md` | `docs/MILESTONE_ROADMAP.md` |
| `docs/templates/ENTRY_GATE_TEMPLATE.md` | `docs/M<ID>/00-entry-gate.md` |
| `docs/templates/MILESTONE_LEDGER_TEMPLATE.md` | `docs/M<ID>/MILESTONE_LEDGER.md` |
| `docs/templates/MILESTONE_CLOSEOUT_TEMPLATE.md` | `docs/M<ID>/MILESTONE_CLOSEOUT.md` at milestone closure |
| `docs/templates/PHASE_TEMPLATE.md` | `docs/M<ID>/<NN>-<phase-name>.md` |
| `docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md` | Milestone-level Project Manager to Coder packet |
| `docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md` | Milestone-level Coder result packet |
| `docs/templates/STRUCTURAL_GATE_TEMPLATE.md` | Project Manager structural gate checklist |
| `docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md` | Final Review verdict packet |
| `docs/templates/CORRECTIVE_PACKET_TEMPLATE.md` | Bounded corrective work packet |
| `docs/agent/PROJECT_OWNER_ENTRY.md` | Optional lightweight project owner entry policy |
| `docs/agent/WORKTREE_ISOLATION.md` | Optional worktree isolation policy |
| `docs/profiles/task-dispatch/` | Optional structured task dispatch profile |
| `scripts/validate_task_dispatch.py` | Optional task dispatch validator |

Copy `docs/agent/` when AI agents will execute or review work. Copy the
relevant `docs/profiles/<profile>/` templates only when the project uses that
profile.

## Adoption Flow

1. If the project starts from a broad or non-technical idea, use Project Owner
   Entry to create intake notes, a project profile draft, and a capability map.
2. Fill or refine `PROJECT_PROFILE.md`.
3. Write or adapt `TECHNICAL_DESIGN.md`.
4. Define `QUALITY_GATES.md` and `APPROVAL_GATES.md`.
5. Add `ACTIVE_CONTEXT.md` and `DOC_ROUTING.md`.
6. Create `CAPABILITY_MAP.md` for broad, non-technical, or coarse-roadmap
   projects.
7. Create draft milestone candidates from `CAPABILITY_MAP.md` when it is used.
8. Promote only candidates that pass Milestone Granularity Gate into the
   executable roadmap.
9. Create the first milestone with `00-entry-gate.md`.
10. Decompose the milestone into reviewable phases with explicit contracts,
   file boundaries, tests, and runtime checks.
11. Execute each phase through retained phase docs and completion reports.
12. Use Wave Execution when safe parallel lanes can speed up the phase.
13. Use Session Orchestration for large milestones that need Project Manager,
   Coder, and Final Review controller handoff.
14. Use Worktree Isolation only when Project Manager authorizes isolated
    phase, lane, or review workspaces.
15. Use the Task Dispatch Profile only when a milestone needs structured
    task/evidence records, resource locks, lease tracking, or validator-backed
    dispatch closeout.
16. Keep milestone state in `MILESTONE_LEDGER.md`.
17. When a milestone closes, write `MILESTONE_CLOSEOUT.md` as a compact
    historical outcome index.

Historical closeouts are not default startup context. Read them only through
`DOC_ROUTING.md` when a task needs prior milestone outcomes, decisions, gaps, or
provenance.

## Applicability

SPEC-Kit is not a fit for every project. Review the kit before adopting it to
confirm that its planning depth, documentation structure, and AI agent workflow
match the project you want to run.

## Non-Goals

- SPEC-Kit is not a project management application.
- SPEC-Kit is not a replacement for tests, reviews, or runtime verification.
- SPEC-Kit does not prescribe one programming language, framework, hosting
  model, database, or agent provider.
