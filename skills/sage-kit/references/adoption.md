# SAGE-Kit Adoption

Use this reference when a project is being evaluated for SAGE-Kit or when
SAGE-Kit docs need to be bootstrapped.

## Choose The Execution Document Model

Adoption must be explicit. Keep the established `legacy-markdown` path for an
existing project unless the project creates a valid `SAGE_PROJECT.json` that
pins `execution_document_model: thin-v1` and a versioned SAGE-Kit contract.

For `thin-v1`, create project-specific authority only:

- `SAGE_PROJECT.json` from `docs/templates/SAGE_PROJECT_TEMPLATE.json`;
- `docs/<M>/MILESTONE_MANIFEST.json`;
- `docs/<M>/phases/<P>.json`.

Do not copy generic governance prose into these manifests. It stays in the
pinned contract and profiles. Accepted historical legacy documents remain
immutable, adoption does not migrate them, and a thin artifact without valid
lock authority fails closed. Installed Skill is not project authority.

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
3. For `legacy-markdown`, copy the reusable core rules:
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
8. For `legacy-markdown`, copy `docs/agent/` when AI agents will execute or
   review work. Thin projects reference the pinned contract instead of copying
   generic agent governance into milestone and phase manifests.
9. Use `docs/agent/CAPABILITY_ADAPTERS.md` when the project expects optional
   external skills, plugins, MCP tools, CLIs, CI, reviewers, frontend tools,
   OpenSpec, GitNexus, browser QA, or database tools.
10. Copy profile templates only when the project matches that profile.
11. Create the first milestone using exactly one document model:
   - For `legacy-markdown`, create `docs/M<ID>/00-entry-gate.md`,
     `docs/M<ID>/MILESTONE_LEDGER.md`, and one Markdown phase document per
     reviewable slice.
   - For `thin-v1`, create `SAGE_PROJECT.json`,
     `docs/M<ID>/MILESTONE_MANIFEST.json`, and one
     `docs/M<ID>/phases/<P>.json` manifest per reviewable slice. Do not create
     legacy active milestone or phase documents in that container.
12. Do not create `MILESTONE_CLOSEOUT.md` until milestone closure.

## Minimum Viable Specification

For a new project, both models need project profile, architecture boundaries,
quality/approval gates, active context, and document routing. Then choose one
model-specific minimum:

- `legacy-markdown`: copied SAGE Core rules, the first milestone entry gate,
  milestone ledger, and at least one Markdown phase document.
- `thin-v1`: `SAGE_PROJECT.json`, one thin milestone manifest, and at least one
  thin phase manifest. Generic SAGE Core and agent policy stays in the pinned
  contract/profile rather than being copied into the active milestone.

Add a capability map for broad, non-technical, or coarse-roadmap projects.

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
