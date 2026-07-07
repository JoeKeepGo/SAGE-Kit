# SPEC-Kit Adoption

Use this reference when a project is being evaluated for SPEC-Kit or when
SPEC-Kit docs need to be bootstrapped.

## Fit Check

SPEC-Kit is useful when the project needs durable planning, explicit contracts,
AI agent execution boundaries, quality gates, and repeatable handoff.

Do not force SPEC-Kit onto a project when the user wants a small one-off script,
throwaway prototype, or informal exploration without retained governance.

## Bootstrap Order

1. Confirm the active project boundary.
2. If the project starts from a broad or non-technical idea, create:
   - `docs/PROJECT_OWNER_INTAKE.md`
   - `docs/CAPABILITY_MAP.md`
   These are planning inputs, not implementation authorization.
3. Create or adapt:
   - `docs/PROJECT_PROFILE.md`
   - `docs/TECHNICAL_DESIGN.md`
   - `docs/ENGINEERING_SYSTEM.md`
   - `docs/QUALITY_GATES.md`
   - `docs/APPROVAL_GATES.md`
   - `docs/ACTIVE_CONTEXT.md`
   - `docs/DOC_ROUTING.md`
4. Run Milestone Granularity Gate on milestone candidates. For projects that do
   not use a capability map, record why roadmap granularity is already clear.
5. Create `docs/MILESTONE_ROADMAP.md` only by promoting accepted candidates into
   `docs/MILESTONE_ROADMAP.md`.
6. Copy `docs/agent/` when AI agents will execute or review work.
7. Copy profile templates only when the project matches that profile.
8. Create the first milestone:
   - `docs/M<ID>/00-entry-gate.md`
   - `docs/M<ID>/MILESTONE_LEDGER.md`
   - one phase doc per reviewable slice
9. Do not create `MILESTONE_CLOSEOUT.md` until milestone closure.

## Minimum Viable SPEC

For a new project, the minimum useful SPEC-Kit setup is:

- project profile;
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
- the user wants low-process work that conflicts with SPEC-Kit;
- adopting SPEC-Kit would require changing unrelated project files.

## Output

When bootstrapping, summarize:

- files created or updated;
- unresolved project decisions;
- first milestone and phase boundary;
- capability map and any candidate milestones not promoted;
- required verification and approval gates;
- next action.
