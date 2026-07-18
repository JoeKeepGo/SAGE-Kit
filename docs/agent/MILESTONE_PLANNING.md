# Milestone Planning

Milestone Planning prevents broad milestones from turning into vague,
hard-to-execute work.

The goal is not to create more paperwork. The goal is to expose missing
contracts, missing verification, cross-file conflicts, and approval gates before
implementation starts.

## Milestone Ready Rule

A milestone is ready for implementation only when it can be decomposed into
reviewable phases with clear contracts, file boundaries, tests, runtime checks,
and stop conditions, its planning review is `ACCEPTABLE` or
`ACCEPTABLE_WITH_CONCERNS`, and Project Manager or project owner records
acceptance of the executable package.

If the milestone cannot be decomposed, it is still planning work.

Broad, non-technical, or coarse-roadmap projects must pass through a capability map before
their milestone candidates become an executable roadmap.

Project Owner Entry outputs are planning inputs. They are not executable
roadmaps.

## Granularity Rules

Each milestone should have one primary capability.

Before accepting a roadmap, compare milestone candidates against
`docs/CAPABILITY_MAP.md`. If the roadmap has far fewer milestones than the
capability map has primary capabilities, audit for epic-sized milestones before
implementation starts.

Each phase should have:

- one observable result;
- one primary owner or integration boundary;
- one public contract or clearly documented no-contract reason;
- a bounded file list;
- a focused test plan;
- a runtime smoke plan or explicit non-applicability reason;
- clear non-goals.

Avoid phases named only by broad activity, such as:

- implement backend;
- build UI;
- integrate everything;
- add tests;
- fix bugs;
- polish;
- refactor core.

Avoid milestones named only by broad areas, such as:

- backend complete;
- frontend complete;
- agent integration;
- admin console;
- data layer;
- production readiness;
- all tests;
- final polish.

Replace broad phases with capability slices:

- define contract;
- implement model or state;
- implement API or service boundary;
- implement user-facing surface;
- connect integration path;
- validate runtime behavior;
- review and harden.

## Decomposition Ladder

Use this ladder before accepting a milestone plan:

1. Capability map: which primary capability does this milestone prove?
2. Product outcome: what user or operator capability changes?
3. Contract surface: what API, event, UI, CLI, data, or runtime contract is affected?
4. Ownership boundary: which component owns the behavior?
5. Durable state: what state changes, if any?
6. Execution path: what runtime path proves it works?
7. Failure path: what errors, retries, denials, or blocked states must appear?
8. Verification path: what tests and smoke prove each claim?
9. Approval gates: what human approval is required?
10. Parallel lanes: which work can be split safely?
11. Capability routing: which specialist skills, plugins, connectors, MCP
    tools, CI, or reviewers should execute or verify domain work under
    `docs/SAGE_CORE.md#external-capability-boundary`?
12. Governance Level: is this control scope Light, Standard, or Heavy?
13. Permission Mode: is this role read-only, write-authorized,
    corrective-authorized, environment-write-authorized, or submit-authorized?
14. Integration gate: what must remain serial?

## Execution Shape Analysis

Before choosing an execution shape, record a dependency DAG for the milestone.
The analysis must list parallel candidates, serial barriers, and any
phase-internal lanes that can use disjoint ownership. Shared serial ownership
does not justify milestone-wide serial execution.

Assign shared files to a named serial integration owner, then continue checking
whether work on mutually exclusive files can run in parallel around that
barrier. A `SERIAL` decision must identify the concrete phase or lane
dependency, file conflict, approval gate, or runtime ownership constraint that
prevents a safe wave. A broad label such as migration, integration, backend, or
frontend is not sufficient by itself.

Do not repartition a phase that is already active unless its authority
explicitly permits it. Apply a safer parallel plan from the next safe
barrier or wave.

## Milestone Entry Gate Checklist

Before implementation starts, the entry gate must answer the required core
questions. Conditional controls should be recorded only when enabled, proposed,
or required by the active risk; otherwise write `Not enabled: <reason>`.

Required core gate:

- What is the one milestone objective?
- Which primary capability from the capability map does it prove, or why is no
  capability map enabled?
- What is explicitly out of scope?
- What are the phases?
- What dependency DAG connects the phases, and which nodes are parallel
  candidates or serial barriers?
- Which phases contain phase-internal lanes with disjoint writable ownership?
- What contract does each phase own?
- What files or modules are likely to change?
- Which files are shared, and which named controller or integration owner owns
  them? Workers may propose patches but cannot own shared files.
- What governance level applies to the milestone controller, and what level
  should each worker or lane use?
- What permission mode applies to the milestone controller, and what mode
  should each worker, lane, review, integration repair, or corrective round use?
- Which gates remain closed?
- Which runtime checks prove the milestone?
- What Final Review, corrective convergence, owner decision, and closeout path
  closes the milestone?
- What closeout summary will future work need after the milestone closes?

Conditional optional controls:

- Wave Execution: if waves are proposed, which phases can use them and what
  Wave Readiness evidence proves safe parallel lanes? Otherwise:
  `Not enabled: <reason>`.
- Session Orchestration: if repeated manual handoff across phases justifies it,
  name Project Manager, Coder, Final Review, packet paths, structural gate, and
  corrective convergence budget. Otherwise: `Not enabled: <reason>`.
- Worktree Isolation: if isolation is authorized, name modes by scope, maximum
  count, branch/worktree naming, review-worktree creator, and post-verdict
  submit/cleanup owner.
  Otherwise: `Not enabled: <reason>`.
- Task Dispatch Profile: if structured task/evidence records, locks,
  Run/Attempt/Lease tracking, or validator-backed closeout are active, define
  records, lock ownership, and gate-ready validator requirement. Otherwise:
  `Not enabled: <reason>`.
- Specialist capabilities and adapters: when skills, plugins, connectors, MCP
  tools, CI, reviewers, or adapters are useful and available, name routing,
  authorization, fallback, and evidence mapping. Otherwise:
  `Not enabled: <reason>`.
- External planning workflows: when used, name where outputs are written into or
  mapped to milestone, phase, or packet docs. Otherwise:
  `Not enabled: <reason>`.

## Planning Package Flow

Use this optional flow when the work is planning-only and the main cost is
manual handoff between planning, planning review, closeout or status updates,
and submit.

The model should select this flow automatically when all are true:

- the requested work creates or updates planning artifacts such as roadmap,
  capability map, milestone plan, entry gate, phase docs, ledger, review packet,
  evidence or status records, or closeout;
- no product code, runtime behavior, schema, migration, test implementation,
  release artifact, credentials, production data, or approval-gate state is in
  scope;
- submit or push is explicitly authorized, or will be handled by a separately
  authorized Submit Controller;
- role separation can be preserved inside one root session.

Planning Review returns one of:

- `ACCEPTABLE`: eligible for Project Manager/project-owner acceptance;
- `ACCEPTABLE_WITH_CONCERNS`: eligible only with recorded concerns and owner
  acceptance;
- `NEEDS_CORRECTION`: Targeted Fix, then Closure Verification chooses strict
  Deterministic Closure when every pre-authored `MECHANICAL_STATUS` condition
  in `docs/agent/SESSION_ORCHESTRATION.md` passes; otherwise Targeted Re-Review;
- `BLOCKED`: stop until an owner records resolve, defer, abandon, or
  close-blocked.

An executable planning package requires an accepted Planning Review verdict and
a Project Manager/project-owner acceptance record. Submitting its documents is
not acceptance.

Recommended root-session orchestration:

1. Planning Author prepares or repairs the planning package.
2. Planning Review checks granularity, authority, evidence, gates, and status.
3. Targeted Fix applies only Planning Review findings inside the planning
   artifact boundary.
4. Closure Verification selects strict Deterministic Closure or Targeted
   Re-Review under the rule above.
5. The Closure Receipt Owner records the receipt and the original review
   authority performs Verdict Finalization, or Targeted Re-Review verifies the
   changed items.
6. Project Manager or project owner records package acceptance only after an
   accepted review verdict.
7. Closeout/Status updates compact history, ledger state, and next action.
8. Submit Controller stages, commits, pushes, or hands off only after submit
   authority, changed-file review, verification, and hygiene checks pass.

Role separation still applies even when one session orchestrates every step:

- Planning Author must not be the Planning Reviewer.
- Planning Reviewer must not submit or accept the milestone.
- Targeted Fix must not expand the planning package scope.
- Closure Receipt Owner must be the original Planning Review controller or
  named review packet author and must be separate from Targeted Fix.
- Verdict Finalization belongs to that review authority; it does not re-review
  files or perform Project Manager acceptance.
- Targeted Re-Review, when selected, must remain independent from Targeted Fix.
- Submit Controller must not reinterpret planning acceptance.
- Submitting planning documents records delivery only. It is not planning
  package acceptance or milestone acceptance.
- If planning changes semantics, permission boundaries, source authority,
  information architecture, public contracts, approval gates, validator meaning,
  or implementation scope, stop the planning package flow and run full affected
  review lanes before submit.

## Planning Blockers

Treat these as blockers:

- no capability map exists for a broad, non-technical, or coarse roadmap;
- project owner intake was promoted directly into an executable roadmap;
- a roadmap milestone spans multiple primary capabilities without a split;
- milestone has no phase sequence;
- milestone controller governance level is not named;
- permission mode is not named for the controller or active worker/lane;
- Heavy milestone governance was inherited by every worker without checking
  worker-specific scope and risk;
- a phase has no file boundary;
- a phase has no test or smoke plan;
- a phase mixes unrelated ownership domains;
- a phase requires approval but does not name the gate;
- a phase depends on an unspecified contract;
- a phase says integration is complete without naming the runtime path;
- shared files are assigned to workers or edited by multiple phases without a
  named controller/integration owner;
- validation is saved only for the end when early contract tests are possible.

## Recommended Milestone Shape

Not every milestone needs every phase, but this shape is a good default:

| Phase Type | Purpose |
|---|---|
| Entry gate | Objective, inputs, non-goals, gates, phase sequence. |
| Contract phase | Public contract, fixtures, schema, or protocol. |
| Foundation phase | Models, state, adapters, or core behavior. |
| Surface phase | API, UI, CLI, worker, or user-facing path. |
| Integration phase | Cross-component path and runtime smoke. |
| Review phase | Independent review, hardening, and handoff. |

## Output

A well-planned milestone produces:

- capability-map link for broad, non-technical, or coarse-roadmap work;
- `00-entry-gate.md`;
- `MILESTONE_LEDGER.md`;
- one phase file per reviewable slice;
- wave plan for phases that can run in parallel;
- governance level selector result for the controller and delegated workers;
- session orchestration packet plan when Project Manager, Coder, and Final
  Review controllers are used;
- capability routing plan for specialist skills, plugins, connectors, MCP
  tools, CI, or reviewers;
- approval gates and stop conditions;
- final review, corrective convergence, owner-decision, and closeout criteria;
- `MILESTONE_CLOSEOUT.md` after the milestone closes.
