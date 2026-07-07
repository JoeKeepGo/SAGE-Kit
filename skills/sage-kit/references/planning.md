# SAGE-Kit Planning

Use this reference for roadmap, milestone, entry gate, phase, wave, session
orchestration, and worktree isolation planning.

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

Before implementation starts, the entry gate must answer:

- What governance level applies to this control scope: `Light`, `Standard`, or
  `Heavy`?
- What permission mode applies to this role or packet:
  `READ_ONLY_REVIEW`, `WRITE_AUTHORIZED`, `CORRECTIVE_AUTHORIZED`,
  `ENVIRONMENT_WRITE_AUTHORIZED`, or `SUBMIT_AUTHORIZED`?
- If this is Heavy controller work, which worker or lane scopes can remain
  Light or Standard?
- If this is read-only review, what packet, decision request, blocker, or
  waiver path closes the run when correction is required?
- What is the milestone objective?
- Which primary capability from the capability map does it prove?
- What is out of scope?
- What are the phases?
- What contract does each phase own?
- What files or modules are likely to change?
- Which files are shared and need serial ownership?
- Which phases can use Wave Execution?
- Does this milestone need Session Orchestration to avoid repeated manual
  handoff between Project Manager, Coder, and Final Review controllers?
- If Session Orchestration is used, may Coder Controller self-execute any work?
  If yes, what exact narrow phase, glue step, or corrective fix is allowed?
- If Wave Execution or parallel phases are proposed, do lanes pass Wave
  Readiness Gate with exclusive writable files, frozen contracts, runtime
  ownership, validation lanes, and integration owner?
- Does Project Manager allow Worktree Isolation, and if yes what mode, maximum
  count, naming, submit authority, and cleanup policy apply?
- Does this milestone need Task Dispatch Profile for structured task/evidence
  records, resource locks, Run/Attempt/Lease tracking, or validator-backed
  gate closeout?
- Which specialist skills, plugins, connectors, or tools should controllers
  route to for implementation, validation, review, or runtime smoke?
- Which Capability Adapters apply, and what authorization level, fallback, and
  evidence mapping does each one use?
- If superpowers is available, which specific skills should be used as
  execution discipline, and inside which SAGE-Kit boundary? If it is not
  available, what SAGE-Kit-native packet, phase, gate, and evidence path will
  be used instead?
- Where will external planning outputs be written or mapped so the milestone
  ledger, phase docs, and packets remain the source of truth?
- Which gates remain closed?
- Which tests and runtime checks prove the milestone?
- What review, handoff, or closeout closes the milestone?

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
  corrective work;
- wave readiness decision, with serial fallback when lane independence is not
  proven;
- worktree isolation authorization, if allowed;
- capability discovery and specialist routing;
- milestone execution packet;
- milestone result packet;
- structural gate owner;
- final review packet;
- corrective round limit.

Do not use Session Orchestration for small single-phase work.

## External Planning Outputs

External planning skills or tools may help shape execution, but their outputs
must be summarized into the active SAGE-Kit artifact that controls the work:
entry gate, milestone ledger, phase doc, execution packet, or result packet.

Do not keep a separate untracked plan as the authoritative source. If an
external plan changes scope, files, gates, sequencing, locks, tests, runtime
requirements, or acceptance criteria, stop until the relevant SAGE-Kit artifact
is updated and approved.

## Capability Adapter Planning

Use `docs/agent/CAPABILITY_ADAPTERS.md` when a phase, milestone, or controller
expects an external skill, plugin, MCP tool, CLI, CI system, reviewer, frontend
tool, OpenSpec, GitNexus, browser QA, or database tool.

Plan:

- adapter name and provider type;
- default authorization level;
- current provider documentation, package metadata, or installed-tool help that
  must be read before install or init;
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
- validator command;
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
