# SAGE-Kit Planning

Use this reference for roadmap, milestone, entry gate, phase, wave, session
orchestration, and worktree isolation planning.

## Execution Document Routing

Before planning an executable milestone, select its document model and SPEC
sources from project authority under
`docs/agent/SPEC_SOURCE_CONTRACT.md#sage-ctx-001`. `legacy-markdown` continues to use the retained
Markdown entry gate and phase documents. `thin-v1` requires
`SAGE_PROJECT.json` plus explicit or configured milestone and phase sources. The
legacy adapter keeps `docs/<M>/MILESTONE_MANIFEST.json` and
`docs/<M>/phases/<P>.json` as compatible defaults; paths are provenance, not
authority.

The thin milestone manifest retains the objective, capability outcome,
authority references, dependency DAG, approval gates, phase IDs, acceptance,
milestone-specific invariants, state, and evidence references. The thin phase
manifest retains its objective, dependencies, profile, permission, owner, path
boundaries, acceptance, focused verification, evidence, phase-specific stop
conditions, handoff target, and state. Generic governance is inherited from the
pinned profiles rather than repeated.

An active milestone must not mix the two models. Missing or conflicting
`execution_document_model` authority fails closed and must not fall back.

## Project Owner Entry

For broad or non-technical ideas, use Project Owner Entry before roadmap
planning:

- collect the five-question intake;
- draft a simple project profile;
- create a capability map;
- generate candidate milestones only after the capability map exists;
- do not treat candidates as executable until Milestone Granularity Gate passes.

## Milestone Granularity

A milestone should prove one primary capability. It is ready only when it can be
decomposed into reviewable phases with:

- one observable result;
- one primary owner or integration boundary;
- a public contract or documented no-contract reason;
- bounded allowed files;
- read-only and forbidden files;
- focused tests;
- runtime smoke or a non-applicability reason;
- non-goals and stop conditions.

Split broad phases such as "build backend", "add UI", "integrate everything",
"add tests", "polish", or "refactor core".

Split broad milestones such as "backend complete", "frontend complete",
"agent integration", "admin console", "data layer", "production readiness", or
"final polish".

For broad, non-technical, or coarse-roadmap projects, compare the roadmap against
`docs/CAPABILITY_MAP.md`. If a milestone spans multiple primary capabilities,
it remains a candidate and must be split before execution.

## Entry Gate Checklist

Before implementation starts, answer the required core gate. Optional controls
are conditional: record their details only when enabled, proposed, or needed by
the active risk. Otherwise write `Not enabled: <reason>` instead of filling the
whole optional checklist.

Required core gate:

- What governance level applies to this control scope: `Light`, `Standard`, or
  `Heavy`?
- What permission mode applies to this role or packet:
  `READ_ONLY_REVIEW`, `WRITE_AUTHORIZED`, `CORRECTIVE_AUTHORIZED`,
  `ENVIRONMENT_WRITE_AUTHORIZED`, or `SUBMIT_AUTHORIZED`?
- What is the milestone objective?
- Which primary capability from the capability map does it prove, or why is no
  capability map enabled?
- What is out of scope?
- What are the phases?
- What contract does each phase own?
- What files or modules are likely to change?
- Which files are shared and need serial ownership?
- Which gates remain closed?
- Which tests and runtime checks prove the milestone?
- What review, handoff, or closeout closes the milestone?

Conditional optional controls:

- Heavy controller decomposition: if this is Heavy controller work, which
  worker or lane scopes can remain Light or Standard? Otherwise:
  `Not enabled: <reason>`.
- Read-only review closure: if this is read-only review, what packet, decision
  request, blocker, or waiver path closes the run when correction is required?
  Otherwise: `Not enabled: <reason>`.
- Wave Execution: if waves or parallel phases are proposed, which phases can
  use them and do lanes pass Wave Readiness Gate with exclusive writable files,
  frozen contracts, runtime ownership, validation lanes, and integration owner?
  Otherwise: `Not enabled: <reason>`.
- Session Orchestration: if repeated manual handoff justifies it, define Project
  Manager, Coder, Final Review, and Coder self-execution policy. Otherwise:
  `Not enabled: <reason>`.
- Worktree Isolation: if Project Manager allows it, name mode, maximum count,
  naming, submit authority, and cleanup policy. Otherwise:
  `Not enabled: <reason>`.
- Task Dispatch Profile: if structured task/evidence records, resource locks,
  Run/Attempt/Lease tracking, or validator-backed gate closeout are needed,
  define the profile use. Otherwise: `Not enabled: <reason>`.
- Specialist capabilities: when implementation, validation, review, or runtime
  smoke benefits from available skills, plugins, connectors, or tools, name the
  routing. Otherwise: `Not enabled: <reason>`.
- Capability Adapters: when an external capability is selected, unavailable
  but relevant, or needs fallback, name authorization level, fallback, and
  evidence mapping. Otherwise: `Not enabled: <reason>`.
- Superpowers: when available and relevant, name the specific skills and
  SAGE-Kit boundary. If unavailable or irrelevant, record
  `Not enabled: <reason>`.
- External planning outputs: when used, name where outputs are written or
  mapped so the milestone ledger, phase docs, and packets remain the source of
  truth. Otherwise: `Not enabled: <reason>`.

## Phase Boundary Checklist

Before a phase can be executed:

- governance level is selected for this phase or task;
- goal is observable;
- requirement IDs are named;
- inputs and outputs are concrete;
- file boundary is explicit;
- shared files have one owner;
- contracts are frozen or migration is in scope;
- tests and smoke are named;
- approval gates are closed unless explicitly opened;
- stop conditions are clear.

## Wave Planning

Use waves when parallel work is safe. Keep these serial:

- contract freeze;
- shared file changes;
- real runtime smoke;
- approval gates;
- final integration;
- active context and routing maintenance;
- milestone ledger update;
- closeout;
- git operations when used.

Parallel lanes must have disjoint writable files. If a lane needs a shared
startup context file, it returns a proposal and the controller applies it
serially.

Admit Graph planning under `docs/SAGE_CORE.md#sage-grf-001`. Record the
project-specific dependency DAG, parallel candidates, serial barriers, and
phase-internal lanes in the plan, and apply the canonical shape,
affected-serialization, and active-change rules at
`docs/agent/WAVE_EXECUTION.md#sage-grf-002`,
`docs/agent/WAVE_EXECUTION.md#sage-grf-005`, and
`docs/agent/WAVE_EXECUTION.md#sage-grf-006`.

## Session Orchestration Planning

Use Session Orchestration for large milestones with many phases, repeated
handoff, or separate Coder and Final Review controllers.

Plan:

- Project Manager Controller;
- Coder Controller;
- Final Review Controller;
- controller governance level, normally `Heavy`;
- controller and worker permission modes;
- worker and lane governance levels, selected per scope;
- Coder self-execution policy, normally `not allowed` except narrow glue or
  integration repair before Final Review;
- wave readiness decision, with affected-node serial fallback when lane
  independence is not proven;
- worktree isolation authorization, if allowed;
- capability discovery and specialist routing;
- milestone execution packet;
- milestone result packet;
- structural gate owner;
- final review packet;
- corrective convergence budget.

Do not use Session Orchestration for small single-phase work.

## External Planning Outputs

External planning skills or tools may help shape execution, but their outputs
must be summarized into the active SAGE-Kit artifact that controls the work:
entry gate, milestone ledger, phase doc, execution packet, or result packet.

Do not keep a separate untracked plan as the authoritative source. If an
external plan changes scope, files, gates, sequencing, locks, tests, runtime
requirements, or acceptance criteria, stop until the relevant SAGE-Kit artifact
is updated and approved.

## Planning Package Closeout Flow

Automatically select this flow when the task is planning-only, manual handoff is
the main cost, submit or push is explicitly authorized or separately assigned to
a Submit Controller, role separation can be preserved, and the likely outputs
are roadmap, capability map, milestone plan, entry gate, phase docs, ledger,
evidence/status records, review packet, closeout, or submit handoff.

Do not select it when product code, runtime behavior, schema, migrations, test
implementation, release artifacts, credentials, production data, approval-gate
state, source authority, information architecture, public contracts, or
validator meaning will change.

If Planning Review returns `NEEDS_CORRECTION`, run Targeted Fix, then choose
strict Deterministic Closure when every pre-authored `MECHANICAL_STATUS`
condition in `docs/agent/SESSION_ORCHESTRATION.md` passes; otherwise run
Targeted Re-Review.

One root session may orchestrate the lifecycle, but role authority stays
separate:

1. Planning Author prepares or repairs the planning package.
2. Planning Review checks granularity, authority, evidence, gates, and status.
3. Targeted Fix resolves only Planning Review findings inside the planning
   artifact boundary.
4. Closure Verification selects strict Deterministic Closure or Targeted
   Re-Review.
5. Closure Receipt Owner and Verdict Finalization close the strict path, or
   Targeted Re-Review checks the changed planning items.
6. Closeout/Status records compact history, ledger state, and next action.
7. Submit Controller commits, pushes, or hands off only after explicit submit
   authority, changed-file review, verification, and hygiene checks.

Planning Author and Planning Review remain separate. Targeted Fix must be
separate from the Closure Receipt Owner and any Targeted Re-Review. The receipt
owner is the original reviewer or named packet author; Verdict Finalization is
review-owned, while Project Manager acceptance remains pending.

If any planning change alters semantics, permissions, source authority,
information architecture, public contracts, approval gates, validator meaning,
or implementation scope, stop this flow and run full affected review lanes
before submit.

## Capability Adapter Planning

Use `docs/agent/CAPABILITY_ADAPTERS.md` when a phase, milestone, or controller
expects an external skill, plugin, MCP tool, runtime adapter, CI system,
reviewer, frontend tool, OpenSpec, GitNexus, browser QA, or database tool.

Plan:

- adapter name and provider type;
- default authorization level;
- current provider documentation, package metadata, or installed-tool help that
  must be read before install or setup;
- whether installation or environment writes are forbidden, allowed, or gated;
- SAGE-Kit boundary the adapter serves;
- allowed files and forbidden files;
- evidence required from the adapter;
- fallback path when unavailable or inconclusive;
- where adapter output is mapped into SAGE-Kit docs.

Do not make optional adapters startup or completion dependencies. Missing
adapter support should degrade to the SAGE-Kit-native path unless the active
gate requires that capability and has no safe fallback.

Approved install candidates may be requested after explicit approval, not
installed silently. Current approved candidates are `ui-ux-pro-max`, `OpenSpec`,
and `GitNexus`. Before requesting installation, read the current provider docs
and state exact commands, write targets, runtime requirements, uninstall or
rollback path, and fallback.

For `ui-ux-pro-max`, plan the narrowest assistant target. In Codex work, prefer
a single Codex-targeted route and treat `--ai all`, global install, or
multi-assistant generation as separate environment-write approval. Plan
`design-system/` writes only when the phase or packet includes that directory
in allowed files.

## Task Dispatch Planning

Use Task Dispatch Profile only when structured task tracking is worth the
extra ceremony.

Plan:

- dispatch board path;
- task and evidence record roots;
- required L0-L4 levels by task class;
- resource lock and lease policy;
- validator requirement;
- which gate requires validator success;
- who updates task records;
- who updates evidence records.

Keep full task/evidence records out of startup context unless routing points to
the active task or gate.

## Milestone Closure Order

1. Required phases are `accepted` or explicitly `superseded`.
2. The milestone ledger is current.
3. `MILESTONE_CLOSEOUT.md` is written or updated.
4. The milestone is marked closed or accepted.
