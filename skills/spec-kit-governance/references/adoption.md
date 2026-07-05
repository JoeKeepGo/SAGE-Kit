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
2. Create or adapt:
   - `docs/PROJECT_PROFILE.md`
   - `docs/TECHNICAL_DESIGN.md`
   - `docs/ENGINEERING_SYSTEM.md`
   - `docs/QUALITY_GATES.md`
   - `docs/APPROVAL_GATES.md`
   - `docs/ACTIVE_CONTEXT.md`
   - `docs/DOC_ROUTING.md`
   - `docs/MILESTONE_ROADMAP.md`
3. Copy `docs/agent/` when AI agents will execute or review work.
4. Copy profile templates only when the project matches that profile.
5. Create the first milestone:
   - `docs/M<ID>/00-entry-gate.md`
   - `docs/M<ID>/MILESTONE_LEDGER.md`
   - one phase doc per reviewable slice
6. Do not create `MILESTONE_CLOSEOUT.md` until milestone closure.

## Minimum Viable SPEC

For a new project, the minimum useful SPEC-Kit setup is:

- project profile;
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
- the architecture boundary cannot be stated;
- approval gates are unknown;
- the user wants low-process work that conflicts with SPEC-Kit;
- adopting SPEC-Kit would require changing unrelated project files.

## Output

When bootstrapping, summarize:

- files created or updated;
- unresolved project decisions;
- first milestone and phase boundary;
- required verification and approval gates;
- next action.
