# M<ID> Milestone: <Name>

Use this template when starting a new milestone.

## Required Files

Create:

- `docs/M<ID>/00-entry-gate.md`
- `docs/M<ID>/MILESTONE_LEDGER.md`
- one phase file per independently reviewable work slice

Create when closing the milestone:

- `docs/M<ID>/MILESTONE_CLOSEOUT.md`

Reference (resolve configured paths through `SAGEKIT_CONFIG.json`; fixed paths
below are legacy defaults):

- `docs/ACTIVE_CONTEXT.md`
- `docs/DOC_ROUTING.md`
- `docs/QUALITY_GATES.md`
- `docs/agent/MILESTONE_PLANNING.md`
- `docs/agent/SESSION_ORCHESTRATION.md` when milestone-level controller
  handoff is used
- `docs/agent/WORKTREE_ISOLATION.md` when isolated workspaces are allowed
- `docs/agent/CAPABILITY_ADAPTERS.md` when optional external providers are
  expected or selected
- `docs/profiles/task-dispatch/DISPATCH_PROFILE.md` when structured task
  dispatch is adopted
- `docs/templates/PHASE_TEMPLATE.md`
- `docs/templates/MILESTONE_EXECUTION_PACKET_TEMPLATE.md` when Session
  Orchestration is used
- `docs/templates/MILESTONE_RESULT_PACKET_TEMPLATE.md` when Session
  Orchestration is used
- `docs/templates/STRUCTURAL_GATE_TEMPLATE.md` when Session Orchestration is
  used
- `docs/templates/FINAL_REVIEW_PACKET_TEMPLATE.md` when Session Orchestration
  is used
- `docs/templates/CORRECTIVE_PACKET_TEMPLATE.md` when Session Orchestration is
  used
- `docs/templates/MILESTONE_CLOSEOUT_TEMPLATE.md`

## Entry Gate Requirements

The entry gate must include:

- milestone objective;
- primary capability from `docs/CAPABILITY_MAP.md` when a capability map exists;
- governance level for the milestone controller and delegated workers;
- accepted inputs;
- product constraints and non-goals;
- phase sequence;
- file boundary;
- module ownership;
- named controller/integration ownership for every shared file;
- public contract;
- worktree isolation policy when isolated execution is allowed;
- task-dispatch policy when structured task/evidence records are required;
- test and smoke expectations;
- capability routing expectations;
- capability adapter authorization, evidence, and fallback policy when optional
  providers are expected;
- Coder Controller integration edit policy when Session Orchestration is used;
- wave readiness decision when Wave Execution or parallel phases are proposed;
- approval gates;
- completion gate.

## Milestone Granularity Gate

Before implementation starts, the milestone must be decomposed into reviewable
phases.

Each phase must have:

- one governance level selected for its local scope;
- one permission mode selected for its current authority;
- one observable result;
- one primary ownership boundary;
- one public contract or clear no-contract reason;
- bounded allowed files;
- explicit read-only and forbidden files;
- focused tests;
- runtime smoke or a clear non-applicability reason;
- non-goals;
- stop conditions.

Planning is blocked when a phase is too broad to assign exclusive file
ownership, test independently, or review without reading unrelated history.

Planning is also blocked when the milestone spans multiple primary capabilities
from `docs/CAPABILITY_MAP.md` and has not been split.

Use `docs/agent/MILESTONE_PLANNING.md` for the decomposition checklist.

When Session Orchestration is used, Coder Controller orchestrates workers and
performs controller-level synthesis and preliminary integration review. It does
not edit worker-owned implementation files. Any direct edit is limited to a
named controller-owned integration or packet file. Corrective workers are
reserved for Final Review corrective rounds on `AUTO_CORRECTIVE` findings.

## Phase Decomposition Matrix

Every milestone entry gate must include this matrix.

| Phase | Governance Level | Permission Mode | Objective | Owner | Contract | Allowed Files | Read-Only Files | Forbidden Files | Tests | Runtime Smoke | Stop Conditions |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `<phase>` | `Light, Standard, or Heavy` | `<mode>` | `<objective>` | `<owner>` | `<contract or none>` | `<files>` | `<files>` | `<files>` | `<commands>` | `<smoke or n/a reason>` | `<stops>` |

## Wave Readiness

Use waves only when lane independence is proven.

Record:

- useful parallel lanes;
- exclusive writable files;
- shared files kept serial;
- contracts frozen before writable work;
- runtime ownership;
- validation lanes;
- integration owner;
- conflict stop conditions.

If readiness is not proven, keep execution serial.

Every shared file must have a named controller or integration owner. Workers
submit patch proposals for shared files to that owner.

## Auto-Advance Policy

Auto-advance is opt-in. A project may auto-advance from one accepted phase to
the next only when:

- the next phase is already inside the entry-gate scope;
- the ledger is current;
- verification evidence does not contradict the ledger;
- no approval gate, blocker, or review stop is required.

## Capability Routing

State which specialist skills, plugins, connectors, or tools should be used for
implementation, validation, review, runtime smoke, or artifact work when the
agent runtime exposes them.

If superpowers is available, name the specific skills that may be used as
execution discipline inside this milestone boundary.

For optional providers such as frontend skills, OpenSpec, GitNexus, browser QA,
database tools, CI, or reviewers, use `docs/agent/CAPABILITY_ADAPTERS.md` and
record authorization level, evidence required, and fallback behavior.

The controller must inspect capability metadata before delegating work and
record the selected capabilities in execution, result, review, or corrective
packets.

## Governance Levels And Authority

Use `docs/agent/GOVERNANCE_LEVELS.md`.

State:

- milestone controller governance level;
- worker, phase, lane, review, and corrective governance levels;
- milestone, worker, phase, lane, review, and corrective permission modes;
- whether Final Review corrective orchestration is separately authorized or
  requires Project Manager decision;
- controls enabled and explicitly not enabled;
- triggers that require stopping for Project Manager or controller decision.

## Worktree Isolation

State whether Project Manager allows Worktree Isolation.

If yes, name:

- allowed isolation mode;
- maximum worktree count;
- branch and worktree naming;
- base branch or commit;
- eligible phases or lanes;
- shared files that remain serial;
- runtime ownership;
- integration owner;
- review-worktree creator, when applicable;
- post-verdict submit and cleanup owner/policy.

## Task Dispatch

State whether Project Manager adopts Task Dispatch Profile for this milestone.

If yes, name:

- dispatch board path;
- task record root;
- evidence record root;
- required L0-L4 levels by task class;
- resource lock policy;
- Run/Attempt/Lease policy;
- validator command;
- gate where validator success is required;
- owner of task record updates;
- owner of evidence record updates.

## Session Orchestration

State whether this milestone uses Session Orchestration.

If yes, name:

- Project Manager Controller;
- Coder Controller;
- Final Review Controller;
- execution packet path;
- result packet path;
- structural gate owner;
- final review packet path;
- corrective convergence budget.

## Milestone Closeout

Close the milestone by writing `docs/M<ID>/MILESTONE_CLOSEOUT.md` after the
ledger is current.

Closure order:

1. Record the Final Review verdict.
2. Complete corrective convergence or record its explicit stop.
3. Record the Project Manager/project-owner accept, close-blocked, defer,
   abandon, or supersede decision.
4. Update `MILESTONE_LEDGER.md`, including required phase disposition.
5. Write or update `MILESTONE_CLOSEOUT.md`.

The closeout is a compact historical outcome index. It records what shipped,
what changed, key decisions, verification summary, known gaps, follow-up
milestones, and links to detailed evidence.

`HANDOFF` is not a closeout result. `BLOCKED` remains open until the authorized
owner explicitly chooses resume, close-blocked, defer, or abandon; resume does
not permit closeout.

Do not add the closeout to default startup context. Read it only when
the configured document-routing authority says historical milestone context is
needed.
