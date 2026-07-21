# Governance Levels

Governance Levels keep SAGE-Kit proportional. Use the lightest control level
that preserves scope, evidence, memory, and approval boundaries.

Governance level is selected per control scope, not inherited globally. A Heavy
milestone controller may delegate Light or Standard worker tasks when their
scope is narrow and risk is bounded.

Formal reviews that verify gates, milestone readiness, durable state, or
verdict evidence are Standard or Heavy by controller scope. Final acceptance is
a Project Manager decision, not a read-only review action.

Governance level and permission mode are separate decisions. The governance
level decides how much structure is required. The permission mode decides what
the role may do in the repository, runtime, environment, or project state.
Every packet should name both.

## Authority Matrix

Select the governance level first, then select the permission mode for the
current role and control scope.

| Permission Mode | Allows | Does Not Allow |
|---|---|---|
| `READ_ONLY_REVIEW` | Inspect, analyze, verify, classify findings, and recommend next action. | Editing files, running corrective work, opening approval gates, submitting, or treating review as closure when findings require action. |
| `WRITE_AUTHORIZED` | Edit only the allowed files or runtime surfaces named by the packet, then provide evidence. | Scope expansion, approval-gate changes, submit/merge/publish, or corrective work outside the approved boundary. |
| `CORRECTIVE_AUTHORIZED` | A corrective worker may fix findings named in a corrective packet, run required checks, and return evidence for re-review or fix according to a pre-authored Deterministic Closure predicate and return evidence. | Granting the read-only Final Review Controller file-write authority, authoring or broadening a closure predicate, recording a closure receipt, redesign, unassigned fixes, new product decisions, approval-gate changes, or accepting the milestone. |
| `ENVIRONMENT_WRITE_AUTHORIZED` | Install, initialize, index, configure, or mutate environment-local tools only within the named adapter boundary. | Silent installs, global configuration, hooks, credentials, destructive changes, or treating tool setup as project completion. |
| `SUBMIT_AUTHORIZED` | Commit, push, merge, publish, release, or clean up worktrees under a distinct post-verdict grant issued after the required review and Project Manager decision. | Initial Coder execution, submitting unreviewed scope, bypassing approval gates, or accepting technical risk without a recorded owner decision. |

`PM_DECISION_AUTHORIZED` is a Project Manager decision record, not a worker
permission mode. It allows the Project Manager to record accept, accept with
concerns, waive, defer, block, or hand off after the required evidence and Final
Review verdict. It does not grant Final Review authority to accept a milestone,
and it does not grant file, environment, submit, or cleanup writes.

`READ_ONLY_REVIEW` is a permission mode, not a completion state. If a read-only
review returns `NEEDS_CORRECTION`, `BLOCKED`, or gate-affecting concerns, it
must produce a corrective packet, a Project Manager decision request, or an
explicit blocker. "Corrective required: yes" without one of those outputs is an
incomplete review.

Orchestration authority and worker write authority are separate. A Final Review
Controller remains `READ_ONLY_REVIEW`; Project Manager may separately authorize
it to dispatch review workers and bounded corrective workers. Each corrective
worker needs its own `CORRECTIVE_AUTHORIZED` packet. The controller never edits
implementation or corrective files.

Waivers also require separate authority. Each ordinary quality finding names a
Finding Owner and Waiver Authority. The Finding Owner may waive only when also
named as Waiver Authority. Project Manager may record a waiver only with an
explicit decision reference from the Waiver Authority or a documented
delegation reference granting that authority. A closed human-only approval gate
can be opened, waived, or reclassified only by its named human authority;
Project Manager cannot waive it alone.

Common combinations:

| Combination | Normal Use | Required Closure |
|---|---|---|
| `Light + READ_ONLY_REVIEW` | Informational-only scan or narrow review slice. | Finding summary or no-change note. It cannot decide gates or milestone acceptance. |
| `Light + WRITE_AUTHORIZED` | Tiny docs, formatting, or low-risk local correction. | Focused evidence and memory no-change/update note. |
| `Standard + READ_ONLY_REVIEW` | Formal bounded review within one phase or ownership area. | Verdict plus corrective packet, handoff, blocker, or no-correction rationale. |
| `Standard + WRITE_AUTHORIZED` | Bounded implementation in one module, phase, or ownership area. | Tests or smoke evidence and completion report. |
| `Standard + CORRECTIVE_AUTHORIZED` | Fix named findings inside an existing boundary. | Required checks and evidence, then a re-review request or evidence return for an eligible mechanical-status finding; the corrective worker must not record the closure receipt. |
| `Heavy + READ_ONLY_REVIEW` | Milestone, multi-phase, multi-agent, release, approval, or high-risk review. | Final Review packet plus corrective packet, PM decision request, blocker, or recommended waiver path for Project Manager decision. |
| `Heavy + CORRECTIVE_AUTHORIZED` | High-risk corrective worker scope for milestone-blocking findings. | Corrective packet, bounded executor, verification, re-review, and PM final decision. |
| `Heavy + SUBMIT_AUTHORIZED` | Post-review submit, release, merge, publish, or cleanup. | Recorded Final Review verdict and explicit Project Manager submit authority. |

## Levels

| Level | Use For | Required Controls |
|---|---|---|
| `Light` | Trivial docs, formatting, informational-only narrow read-only review or scan, or narrow corrective work with no behavior, contract, runtime, security, gate, verdict, or milestone-state change. | Narrow routed reads, explicit file boundary, focused evidence, memory update proposal or no-change note. |
| `Standard` | Non-trivial phase or task that changes behavior, contracts, tests, docs with durable meaning, runtime-visible behavior, or a formal gate-affecting review within one bounded ownership area. | Retained phase or task doc, quality gates, tests or smoke plan, completion report, milestone ledger update when milestone state changes. |
| `Heavy` | Milestone controller work, multi-phase execution, multi-agent orchestration, parallel phases, shared files, public contracts, state machines, cross-component integration, release, production data, approval gates, or high false-completion risk. | Entry gate, controller packets, serial gates, explicit worker governance levels, integration owner, evidence aggregation, final review, memory maintenance, and optional controls only when triggered. |

## Selection Rule

Start at `Light`.

Upgrade to `Standard` when any condition is true:

- the task is non-trivial under `docs/SAGE_CORE.md`;
- behavior, contract, tests, runtime-visible output, or durable documentation
  changes;
- a retained phase/task document or milestone ledger evidence is needed;
- a read-only review or scan decides or unblocks a gate, milestone acceptance,
  durable state, or formal verdict within one bounded ownership area;
- a worker is implementing one bounded phase or ownership area.

Upgrade to `Heavy` when any condition is true:

- the current role controls a whole milestone, multiple phases, or multiple
  workers;
- the current control scope plans or owns parallel phases, wave execution, or
  lane orchestration;
- shared files, public contracts, state machines, migrations, generated
  artifacts, lockfiles, runtime ownership, or integration gates are involved;
- approval gates, release, production data, credentials, destructive actions,
  external service mutation, or security-sensitive work are in scope;
- the current control scope manages, enables, or owns Task Dispatch Profile,
  Worktree Isolation, Session Orchestration, Capability Adapter installation or
  environment-write policy, or corrective round control;
- the risk of verbal green-lighting or hidden fallback is high.

Stay `Light` only when all are true:

- no behavior, contract, runtime, release, security, approval, or durable state
  changes;
- no milestone status changes;
- no shared writable files;
- any read-only review is informational and does not decide or unblock gates,
  milestone acceptance, durable state, or formal verdicts;
- focused evidence can prove the claim without retained phase machinery.

## Scope Rule

Large projects often use Heavy governance at the Project Manager or milestone
controller layer. That does not make every worker Heavy.

Parent milestone use of Wave Execution, Task Dispatch Profile, Worktree
Isolation, Session Orchestration, Capability Adapters, or corrective round
control does not upgrade a worker unless the worker scope manages, enables, or
owns that control.

Controllers must assign each delegated worker its own level:

| Worker Scope | Typical Level |
|---|---|
| Informational-only read-only risk scan or review slice | `Light` |
| Small documentation or formatting correction | `Light` |
| Bounded implementation in one module or phase | `Standard` |
| Runtime validation lane with named smoke | `Standard` |
| Cross-component integration, shared contract, migration, or release lane | `Heavy` |
| Corrective worker for one named finding | `Light` or `Standard` |

When a lower-level worker discovers a Heavy trigger, it must stop and return
`HANDOFF` with the controller decision needed. When a controller discovers that
the execution shape itself must change, it returns `STOP_FOR_PM` rather than
silently upgrading the run.

## Optional Controls

Heavy does not automatically enable every control. Controls are optional unless
the active packet, owner authorization, or explicit SPEC entry marks them required.

- Use Session Orchestration for milestone-level multi-controller handoff.
- Use Wave Execution for safe parallel lanes inside a phase.
- Use Worktree Isolation only when Project Manager authorization names mode,
  count, naming, integration owner, and the post-verdict submit and cleanup
  owner. The initial execution packet does not grant submit authority.
- Use Task Dispatch Profile only when structured task/evidence records,
  resource locks, leases, or validator-backed closeout are worth the extra
  ceremony.
- Use Strict Mode according to `docs/agent/MODEL_ASSURANCE_POLICY.md`, not
  merely because the project is large.
- Use external skills, plugins, tools, CI, or reviewers only under
  `docs/SAGE_CORE.md#external-capability-boundary` and
  `docs/agent/CAPABILITY_ADAPTERS.md`. Superpowers is a reference integration
  for execution discipline when runtime policy allows, but it does not change the
  governance level or override SAGE-Kit authority.

## Packet Requirement

Milestone execution, result, final review, lane, and corrective packets should
name:

- controller governance level;
- worker or lane governance levels;
- permission mode for the current role and worker/lane modes when delegated;
- orchestration authority separately from each delegated worker's write
  authority;
- whether Final Review corrective orchestration is authorized or requires a
  Project Manager decision;
- controls enabled and controls explicitly not enabled;
- upgrade triggers found during execution;
- selected capability adapters, authorization levels, and fallbacks when
  relevant;
- any stopped worker that needs controller decision.
