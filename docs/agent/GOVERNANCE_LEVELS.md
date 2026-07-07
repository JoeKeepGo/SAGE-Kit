# Governance Levels

Governance Levels keep SPEC-Kit proportional. Use the lightest control level
that preserves scope, evidence, memory, and approval boundaries.

Governance level is selected per control scope, not inherited globally. A Heavy
milestone controller may delegate Light or Standard worker tasks when their
scope is narrow and risk is bounded.

Formal reviews that decide or unblock gates, milestone acceptance, durable
state, or verdicts are Standard or Heavy by controller scope.

## Levels

| Level | Use For | Required Controls |
|---|---|---|
| `Light` | Trivial docs, formatting, informational narrow read-only review or scan, or narrow corrective work with no behavior, contract, runtime, security, gate, verdict, or milestone-state change. | Narrow routed reads, explicit file boundary, focused evidence, memory update proposal or no-change note. |
| `Standard` | Non-trivial phase or task that changes behavior, contracts, tests, docs with durable meaning, runtime-visible behavior, or a formal gate-affecting review within one bounded ownership area. | Retained phase or task doc, quality gates, tests or smoke plan, completion report, milestone ledger update when milestone state changes. |
| `Heavy` | Milestone controller work, multi-phase execution, multi-agent orchestration, parallel phases, shared files, public contracts, state machines, cross-component integration, release, production data, approval gates, or high false-completion risk. | Entry gate, controller packets, serial gates, explicit worker governance levels, integration owner, evidence aggregation, final review, memory maintenance, and optional controls only when triggered. |

## Selection Rule

Start at `Light`.

Upgrade to `Standard` when any condition is true:

- the task is non-trivial under `docs/SPEC_CORE.md`;
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
  Worktree Isolation, Session Orchestration, or corrective round control;
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
Isolation, Session Orchestration, or corrective round control does not upgrade a
worker unless the worker scope manages, enables, or owns that control.

Controllers must assign each delegated worker its own level:

| Worker Scope | Typical Level |
|---|---|
| Informational read-only risk scan or review slice | `Light` |
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

Heavy does not automatically enable every control.

- Use Session Orchestration for milestone-level multi-controller handoff.
- Use Wave Execution for safe parallel lanes inside a phase.
- Use Worktree Isolation only when Project Manager authorization names mode,
  count, naming, integration owner, submit authority, and cleanup policy.
- Use Task Dispatch Profile only when structured task/evidence records,
  resource locks, leases, or validator-backed closeout are worth the extra
  ceremony.
- Use Strict Mode according to `docs/agent/MODEL_ASSURANCE_POLICY.md`, not
  merely because the project is large.
- Use external skills, plugins, tools, CI, or reviewers only under
  `docs/SPEC_CORE.md#external-capability-boundary`. Superpowers is a reference
  integration for execution discipline when available, but it does not change
  the selected governance level or override SPEC-Kit authority.

## Packet Requirement

Milestone execution, result, final review, lane, and corrective packets should
name:

- controller governance level;
- worker or lane governance levels;
- controls enabled and controls explicitly not enabled;
- upgrade triggers found during execution;
- any stopped worker that needs controller decision.
