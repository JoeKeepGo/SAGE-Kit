# SAGE-Kit Adoption

Use this reference when a project is being evaluated for SAGE-Kit or when
SAGE-Kit docs need to be bootstrapped.

## Fit Check

SAGE-Kit is useful when the project needs durable planning, explicit contracts,
AI agent execution boundaries, quality gates, and repeatable handoff.

Do not force SAGE-Kit onto a project when the user wants a small one-off script,
throwaway prototype, or informal exploration without retained governance.

## Bootstrap Order

1. Confirm the active project boundary.
2. If the project starts from a broad or non-technical idea, create:
   - `docs/PROJECT_OWNER_INTAKE.md`
   - `docs/CAPABILITY_MAP.md`
   These are planning inputs, not implementation authorization.
3. Copy the reusable core rules:
   - `docs/SAGE_CORE.md`
4. Create or adapt the Light baseline:
   - `docs/PROJECT_PROFILE.md`
   - `docs/QUALITY_GATES.md`
   - `docs/ACTIVE_CONTEXT.md`
   - `docs/DOC_ROUTING.md`
5. Add `docs/TECHNICAL_DESIGN.md`, `docs/ENGINEERING_SYSTEM.md`, and
   `docs/APPROVAL_GATES.md` when Standard/Heavy adoption is selected or project
   risk requires them.
6. Run Milestone Granularity Gate on milestone candidates. For projects that do
   not use a capability map, record why roadmap granularity is already clear.
7. Create `docs/MILESTONE_ROADMAP.md` only by promoting accepted candidates into
   `docs/MILESTONE_ROADMAP.md`.
8. Copy `docs/agent/` when AI agents will execute or review work.
9. Use `docs/agent/CAPABILITY_ADAPTERS.md` when the project expects optional
   external skills, plugins, MCP tools, CLIs, CI, reviewers, frontend tools,
   OpenSpec, GitNexus, browser QA, or database tools.
10. Copy profile templates only when the project matches that profile.
11. Create the first milestone:
   - `docs/M<ID>/00-entry-gate.md`
   - `docs/M<ID>/MILESTONE_LEDGER.md`
   - one phase doc per reviewable slice
12. Do not create `MILESTONE_CLOSEOUT.md` until milestone closure.

## Minimum Viable Specification

For a new project, the minimum useful SAGE-Kit setup is:

- project profile;
- SAGE Core rules;
- capability map for broad, non-technical, or coarse-roadmap projects;
- technical design or architecture boundary;
- quality and approval gates;
- active context;
- document routing;
- first milestone entry gate;
- milestone ledger;
- at least one phase doc.

## Adoption Stop Conditions

Stop and ask for direction when:

- the project goal is unclear;
- a broad idea is being turned directly into an executable roadmap without a
  capability map;
- the architecture boundary cannot be stated;
- approval gates are unknown;
- the user wants low-process work that conflicts with SAGE-Kit;
- adopting SAGE-Kit would require changing unrelated project files.

## Output

When bootstrapping, summarize:

- files created or updated;
- unresolved project decisions;
- first milestone and phase boundary;
- capability map and any candidate milestones not promoted;
- optional capability adapters and fallbacks;
- required verification and approval gates;
- next action.
