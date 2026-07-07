# SPEC-Kit Planning

Use this reference for roadmap, milestone, entry gate, phase, wave, and session
orchestration planning.

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

## Entry Gate Checklist

Before implementation starts, the entry gate must answer:

- What is the milestone objective?
- What is out of scope?
- What are the phases?
- What contract does each phase own?
- What files or modules are likely to change?
- Which files are shared and need serial ownership?
- Which phases can use Wave Execution?
- Does this milestone need Session Orchestration to avoid repeated manual
  handoff between Project Manager, Coder, and Final Review controllers?
- Which specialist skills, plugins, connectors, or tools should controllers
  route to for implementation, validation, review, or runtime smoke?
- Which gates remain closed?
- Which tests and runtime checks prove the milestone?
- What review, handoff, or closeout closes the milestone?

## Phase Boundary Checklist

Before a phase can be executed:

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
- capability discovery and specialist routing;
- milestone execution packet;
- milestone result packet;
- structural gate owner;
- final review packet;
- corrective round limit.

Do not use Session Orchestration for small single-phase work.

## Milestone Closure Order

1. Required phases are `accepted` or explicitly `superseded`.
2. The milestone ledger is current.
3. `MILESTONE_CLOSEOUT.md` is written or updated.
4. The milestone is marked closed or accepted.
