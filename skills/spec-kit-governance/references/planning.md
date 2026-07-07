# SPEC-Kit Planning

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
- Does Project Manager allow Worktree Isolation, and if yes what mode, maximum
  count, naming, submit authority, and cleanup policy apply?
- Does this milestone need Task Dispatch Profile for structured task/evidence
  records, resource locks, Run/Attempt/Lease tracking, or validator-backed
  gate closeout?
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
- worktree isolation authorization, if allowed;
- capability discovery and specialist routing;
- milestone execution packet;
- milestone result packet;
- structural gate owner;
- final review packet;
- corrective round limit.

Do not use Session Orchestration for small single-phase work.

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
