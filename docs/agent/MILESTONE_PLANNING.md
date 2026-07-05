# Milestone Planning

Milestone Planning prevents broad milestones from turning into vague,
hard-to-execute work.

The goal is not to create more paperwork. The goal is to expose missing
contracts, missing verification, cross-file conflicts, and approval gates before
implementation starts.

## Milestone Ready Rule

A milestone is ready for implementation only when it can be decomposed into
reviewable phases with clear contracts, file boundaries, tests, runtime checks,
and stop conditions.

If the milestone cannot be decomposed, it is still planning work.

## Granularity Rules

Each milestone should have one primary capability.

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

1. Product outcome: what user or operator capability changes?
2. Contract surface: what API, event, UI, CLI, data, or runtime contract is affected?
3. Ownership boundary: which component owns the behavior?
4. Durable state: what state changes, if any?
5. Execution path: what runtime path proves it works?
6. Failure path: what errors, retries, denials, or blocked states must appear?
7. Verification path: what tests and smoke prove each claim?
8. Approval gates: what human approval is required?
9. Parallel lanes: which work can be split safely?
10. Integration gate: what must remain serial?

## Milestone Entry Gate Checklist

Before implementation starts, the entry gate must answer:

- What is the one milestone objective?
- What is explicitly out of scope?
- What are the phases?
- What contract does each phase own?
- What files or modules are likely to change?
- Which files are shared and need exclusive ownership?
- Which phases can use waves?
- Which gates remain closed?
- Which runtime checks prove the milestone?
- What review or handoff phase closes the milestone?
- What closeout summary will future work need after the milestone closes?

## Planning Blockers

Treat these as blockers:

- milestone has no phase sequence;
- a phase has no file boundary;
- a phase has no test or smoke plan;
- a phase mixes unrelated ownership domains;
- a phase requires approval but does not name the gate;
- a phase depends on an unspecified contract;
- a phase says integration is complete without naming the runtime path;
- shared files are edited by multiple phases without an integration owner;
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

- `00-entry-gate.md`;
- `MILESTONE_LEDGER.md`;
- one phase file per reviewable slice;
- wave plan for phases that can run in parallel;
- approval gates and stop conditions;
- final review or handoff criteria;
- `MILESTONE_CLOSEOUT.md` after the milestone closes.
