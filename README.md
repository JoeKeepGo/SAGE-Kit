# SPEC-Kit

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
- An AI agent harness for context control, file ownership, verification,
  handoff, and review.
- Wave Execution for safe parallel development inside a phase.
- Milestone planning rules that force reviewable, testable phase slices.
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
    WAVE_EXECUTION.md
    MILESTONE_PLANNING.md
  profiles/
    state-machine/
    control-plane-agent/
  templates/
    *_TEMPLATE.md
```

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
  MILESTONE_ROADMAP.md
  agent/
    AGENT_HARNESS.md
    MODEL_ASSURANCE_POLICY.md
    STRICT_MODE.md
    WAVE_EXECUTION.md
    MILESTONE_PLANNING.md
  templates/
    PHASE_TEMPLATE.md
    MILESTONE_LEDGER_TEMPLATE.md
    MILESTONE_CLOSEOUT_TEMPLATE.md
    COMPLETION_REPORT_TEMPLATE.md
    LANE_PACKET_TEMPLATE.md
  M<ID>/
    00-entry-gate.md
    MILESTONE_LEDGER.md
    MILESTONE_CLOSEOUT.md  # created at milestone closure
    01-phase-name.md
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
| `docs/templates/MILESTONE_ROADMAP_TEMPLATE.md` | `docs/MILESTONE_ROADMAP.md` |
| `docs/templates/ENTRY_GATE_TEMPLATE.md` | `docs/M<ID>/00-entry-gate.md` |
| `docs/templates/MILESTONE_LEDGER_TEMPLATE.md` | `docs/M<ID>/MILESTONE_LEDGER.md` |
| `docs/templates/MILESTONE_CLOSEOUT_TEMPLATE.md` | `docs/M<ID>/MILESTONE_CLOSEOUT.md` at milestone closure |
| `docs/templates/PHASE_TEMPLATE.md` | `docs/M<ID>/<NN>-<phase-name>.md` |

Copy `docs/agent/` when AI agents will execute or review work. Copy the
relevant `docs/profiles/<profile>/` templates only when the project uses that
profile.

## Adoption Flow

1. Fill in `PROJECT_PROFILE.md`.
2. Write or adapt `TECHNICAL_DESIGN.md`.
3. Define `QUALITY_GATES.md` and `APPROVAL_GATES.md`.
4. Add `ACTIVE_CONTEXT.md` and `DOC_ROUTING.md`.
5. Create the first milestone with `00-entry-gate.md`.
6. Decompose the milestone into reviewable phases with explicit contracts,
   file boundaries, tests, and runtime checks.
7. Execute each phase through retained phase docs and completion reports.
8. Use Wave Execution when safe parallel lanes can speed up the phase.
9. Keep milestone state in `MILESTONE_LEDGER.md`.
10. When a milestone closes, write `MILESTONE_CLOSEOUT.md` as a compact
    historical outcome index.

Historical closeouts are not default startup context. Read them only through
`DOC_ROUTING.md` when a task needs prior milestone outcomes, decisions, gaps, or
provenance.

## Non-Goals

- SPEC-Kit is not a project management application.
- SPEC-Kit is not a replacement for tests, reviews, or runtime verification.
- SPEC-Kit does not prescribe one programming language, framework, hosting
  model, database, or agent provider.
- SPEC-Kit should not contain project-specific product names, internal paths,
  credentials, account data, or deployment secrets.
