---
name: sage-kit
description: "Use when SAGE-Kit is explicit: the user invokes $sage-kit, asks to adopt/bootstrap SAGE-Kit, or references SAGE-Kit-owned docs or constructs such as docs/ACTIVE_CONTEXT.md, docs/DOC_ROUTING.md, docs/agent/AGENT_HARNESS.md, SAGE-Kit Governance Levels, Authority Matrix, Strict Mode, Wave Execution, Session Orchestration, Worktree Isolation, Task Dispatch Profile, or Capability Adapters. Do not use for generic milestones, gates, phase docs, planning, review, or debugging unless tied to SAGE-Kit."
---

# SAGE-Kit

Use this skill to keep AI work aligned with SAGE-Kit without loading the whole
framework into context.

SAGE-Kit is governance, not a skill library. It controls scope,
authorization, file boundaries, gates, evidence, locks, memory, and completion
status. External skills, plugins, connectors, and tools provide execution
methods inside those approved boundaries.

Task Dispatch is an internal optional SAGE-Kit profile. Superpowers and other
skills, plugins, MCP tools, CLIs, CI systems, reviewers, frontend builders,
OpenSpec, GitNexus, browser tools, and database tools are optional capability
adapters unless a project explicitly defines a narrower policy.

This skill does not replace the project's own specification documents. The project
remains responsible for maintaining its `docs/` profile, design, gates, active
context, routing, milestones, phase docs, ledgers, completion reports, and
closeouts.

## Core Rule

Do not read every SAGE-Kit document by default. Start from the active project
context and let `docs/DOC_ROUTING.md` decide the narrow read set.

Historical ledgers, phase docs, completion reports, and closeouts are not
startup context.

Context budget is a guardrail, not a correctness cap. Expand the read set when
correctness, safety, provenance, full milestone review, or final acceptance
requires it, but state why the extra context is needed and what decision it
supports.

## Detect The Situation

1. Identify the active repository boundary and change-control state.
2. Check for SAGE-Kit project markers:
   - `docs/ACTIVE_CONTEXT.md`
   - `docs/DOC_ROUTING.md`
   - `docs/PROJECT_PROFILE.md`
   - `docs/agent/AGENT_HARNESS.md`
3. If project docs are missing but the user wants to adopt or bootstrap
   SAGE-Kit, read `references/adoption.md`.
4. If this is the SAGE-Kit source repository, edit kit templates or skills only
   when requested; do not expect instantiated project docs to exist.
5. If the repo is not SAGE-Kit governed and the user did not ask to adopt it,
   do not impose SAGE-Kit.

## Default Startup

For a SAGE-Kit governed project:

1. Read `docs/ACTIVE_CONTEXT.md`.
2. Read `docs/DOC_ROUTING.md`.
3. Read only the active milestone ledger, phase doc, contract docs, or gates
   named by routing and task scope.
4. Select the governance level and permission mode for the current control
   scope using `docs/agent/GOVERNANCE_LEVELS.md` when the task is non-trivial,
   delegated, controller-level, review, corrective, environment-writing, or
   submit-related.
5. When external capabilities are relevant, read
   `docs/agent/CAPABILITY_ADAPTERS.md` or the project routing entry that
   defines the adapter boundary.
6. Before writable work, name allowed files, read-only files, forbidden files,
   gates, verification commands, and stop conditions.

If required startup docs are missing or contradictory, stop and report the gap
before editing.

## Task Routing

- Adoption or bootstrap: read `references/adoption.md`.
- Milestone, roadmap, or phase planning: read `references/planning.md`.
- Implementation, debugging, refactor, or subagent execution: read only the
  relevant core sections of `references/execution.md`. Load its Advanced
  Execution Economy section only under the Heavy, corrective, or
  final-verification rule below.
- Review, handoff, completion, or closeout: read
  `references/review-completion.md`.
- Execution economy, change classes, corrective authority, evidence reuse,
  review topology, or deterministic limits: read
  `docs/agent/EXECUTION_ECONOMY.md`.
- Preauthorized Convergence Window, multi-candidate deterministic corrective
  convergence, or successor stop rules: read
  `docs/agent/EXECUTION_ECONOMY.md` and `docs/agent/CONTINUITY_PROTOCOL.md`.
- Checkpoint or resume: read `docs/agent/CONTINUITY_PROTOCOL.md`, then run
  `sagekit resume` before loading broader context.
- Task Dispatch validation contract selection or historical compatibility:
  read `docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md`. For an existing
  project whose accepted history predates structured active-set authority,
  route the owner to the Validation Scope Manifest migration procedure. Require
  an explicit container path and frozen v0/v1 version selected from historical
  provenance; do not choose a version by trying validators, invent acceptance,
  downgrade current work, or rewrite historical documents. The CLI/validator,
  not this Skill, decides scope and contract selection.

Read only the reference files needed for the current task.

Load advanced execution-economy detail only for relevant Heavy, corrective,
or final-verification work. Ordinary Light or Standard tasks use the core
workflow and must not carry that advanced runtime context by default.

## Context Budget

Prefer narrow reads in this order:

1. active context and routing;
2. active milestone, phase, gate, or packet docs;
3. capability metadata before capability bodies;
4. closeouts before historical ledgers;
5. targeted searches or ranges before full archives.

Do not read every specification document, phase doc, ledger, closeout, skill body,
plugin body, or log by default. If a broad read is required, say why and
summarize the useful result into the ledger, closeout, completion report, or
handoff.

## Guardrails

- Treat C0 record-only maintenance as record ownership work. Run
  targeted record consistency verification only; do not rerun implementation tests or full
  review lanes when protected implementation evidence remains valid.
- Use Bounded Corrective Authority for C1 and aggregate uncovered paths into one
  `AUTHORITY_DELTA`. C2 requires affected semantic review. C3 requires a human
  decision.
- Treat a Preauthorized Convergence Window as explicit opt-in authority. Keep
  the default single automatic successor when it is absent. Inside the window,
  allow only semantic-preserving implementation correction with stable scope,
  family, allowed paths, invariant, evidence, and required targeted review.
  policy-changing semantics return `HANDOFF_READY`; two consecutive same-root
  no-progress rounds return `BLOCKED`. Never use the window as unlimited retry
  or to rerun deterministic failures speculatively.
- Choose one primary review topology for an execution unit. Do not stack
  per-task, per-worker, corrective, lane, and final reviewers without a
  recorded P0/P1, security, authority, cross-contract, or destructive reason.
- Reuse evidence according to its fingerprint and invalidate only affected
  paths, contracts, dependencies, platforms, packages, or authority versions.
- Validate closed legacy Task Dispatch history with the manifest-selected frozen
  v0/v1 contract. Require current metadata for active work; mixed or ambiguous
  records fail closed, and a selected-contract failure must never fall back to
  another contract.
- CLI/validator owns contract and milestone scope selection. Skill guidance,
  filenames, prose, or terminal record state alone cannot authorize legacy
  validation.
- Do not rewrite accepted historical documents to satisfy current phase format.
  The validator reports immutable accepted history through an auditable,
  aggregated compatibility finding.
- When a deterministic local limit is reached, create a checkpoint and return
  `HANDOFF_READY`; reserve `STOP` for immediate safety or destructive risk.
- Managed expensive verification is eligible only for a frozen candidate whose
  fingerprint matches current inputs. Before freeze, prohibit full suite,
  retained regression, wheel/install, outside-source/package smoke, and full
  integration re-review; a non-consuming legacy preliminary counter is not
  authority to run them.
- For one finding, run only the minimum reproduction and directly affected
  focused tests. At a lane gate, run only the affected-lane suite. After a
  corrective, run only targeted verification and targeted re-review. Reduce
  harness or teardown failures to a minimum reproduction before any broader
  rerun.
- Reuse evidence for the same fingerprint while its inputs remain unchanged.
  Workers and reviewers cannot expand expensive-verification authority; Lane
  Controllers own only affected-lane verification, and the Root or Final
  Controller exclusively owns final full-suite authority.
- Capability or preflight failures do not consume a candidate verification run.
  A run is consumed atomically when candidate execution starts. Persist started
  attempt ids so checkpoint/resume cannot count them twice.
- Failure of one verification node skips only dependent successors;
  independent verification nodes continue and report their own results.
- Freeze the candidate only after review and the bounded corrective batch
  close. One approved corrective batch may create one automatic successor
  without human budget relaxation; another successor from that batch or any
  post-final code change first returns `HANDOFF_READY`. A human-approved
  handoff corrective may create the next generation only with a persisted
  authority anchor, root-cause id, and finding count. Do not impose a numeric
  generation ceiling: block only after two approved rounds for the same root
  cause make no progress, and reset that count when findings decrease.
- Keep one task tied to one approved phase unless a batch plan defines order,
  gates, and stop conditions.
- Do not invent missing contracts, fallback behavior, or success evidence.
- Do not edit outside the approved file boundary.
- Do not open approval gates without explicit user approval.
- Do not treat historical closeouts as startup context.
- Do not claim `DONE` unless required verification and memory maintenance are
  complete.
- Use `docs/agent/GOVERNANCE_LEVELS.md` to choose the lightest governance level
  that safely preserves scope, evidence, memory, and approval boundaries, and
  choose the matching permission mode for read-only, write, corrective,
  environment-write, or submit authority. Heavy controller work may delegate
  Light or Standard workers.
- Do not treat `READ_ONLY_REVIEW` as closure when findings require correction,
  Project Manager decision, blocker handling, or waiver. A read-only review
  that returns `NEEDS_CORRECTION` must include a corrective packet, handoff, or
  blocker.
- Do not let parallel workers or subagents edit `docs/ACTIVE_CONTEXT.md` or
  `docs/DOC_ROUTING.md` directly. They must return memory update proposals for
  controller integration.
- Direct edits to `docs/ACTIVE_CONTEXT.md` or `docs/DOC_ROUTING.md` require
  both permission mode and ownership. If either is missing, return a memory
  update proposal or no-change note.
- Do not let SAGE-Kit displace specialist skills, plugins, connectors, or
  tools. Use available capability metadata to select the right specialist
  capability before delegating or executing domain work.
- Use Capability Adapters for optional external skills, plugins, MCP tools,
  CLIs, CI systems, reviewers, frontend skills, OpenSpec, GitNexus, browser
  QA, and database tools. Detect, authorize, bound, invoke, capture, map, and
  fall back without making them core dependencies.
- Do not silently install external skills, plugins, CLIs, MCP servers, hooks,
  generated skills, or global configuration. Recommend or request installation
  only when the source, writes, fallback, and approval path are explicit.
- Treat superpowers as a reference integration, not a dependency. When
  available and relevant, selected superpowers skills may guide execution
  inside an approved SAGE-Kit boundary. If unavailable, continue with SAGE-Kit
  phase, gate, packet, and evidence templates.
- Do not treat external capability completion as SAGE-Kit gate completion.
  Record it as execution evidence and keep gate decisions in SAGE-Kit docs.
- Use Strict Mode according to `docs/agent/MODEL_ASSURANCE_POLICY.md`; do not
  guess the policy from memory.
- Use Wave Execution only when file ownership is disjoint and serial gates stay
  serial.
- Use Session Orchestration only for large milestones where Project Manager,
  Coder, and Final Review controller packets reduce handoff overhead without
  weakening gates.
- In Session Orchestration, Coder Controller orchestrates workers by default.
  It may self-execute only when the execution packet explicitly allows a narrow
  phase, glue step, or integration repair before Final Review, and it must
  record why worker dispatch was skipped.
- Final Review must classify required corrections as `AUTO_CORRECTIVE`,
  `PM_DECISION`, `BLOCKED`, or `DEFER`. If corrective execution is authorized,
  it may orchestrate a bounded corrective round through separately authorized
  workers; it must not edit implementation or corrective files itself. If
  review is read-only, it must return a packet-only corrective handoff or
  blocker.
- Severity gates acceptance: open P0/P1 always block; P2 blocks only for
  authority, false-green, approval gate, security, validator/gate-ready, source
  authority, or evidence-integrity issues; ordinary documentation-consistency
  P2 may close as concerns or be auto-corrected; P3 does not block.
- After corrective work, follow the Deterministic Closure eligibility,
  separation, receipt, and reject/fallback contract in
  `docs/agent/SESSION_ORCHESTRATION.md`; only Final Review may record a
  precommitted `VERDICT_FINALIZED_FROM_RECEIPT`, not milestone acceptance.
- Do not mark `BLOCKED` merely because a fixed corrective round count was
  reached. Continue only inside an authorized corrective packet or boundary
  while findings or severity decrease, scope does not expand, no blocking
  approval gate is bypassed, and no new authority, false-green, approval-gate,
  security, validator/gate-ready, source-authority, or evidence-integrity risk
  appears. Mark `BLOCKED` when the same root cause makes no material progress
  for two consecutive corrective rounds, required evidence or authority is
  missing, or the fix would exceed the approved boundary. When Project Manager
  judgment is needed, return `NEEDS_CORRECTION` with `PM_DECISION_REQUIRED`
  closure/status rather than `BLOCKED`.
- Do not claim Wave Execution or parallel phases unless Wave Readiness is
  proven with independent lanes, exclusive writable files, serial shared files,
  frozen contracts, runtime ownership, validation lanes, and integration owner.
- Use Worktree Isolation only when Project Manager authorization names the
  allowed mode, maximum count, naming, integration owner, submit authority, and
  cleanup policy.
- Use Task Dispatch Profile only when project routing, the milestone entry
  gate, or the execution packet adopts structured task/evidence records and
  validator closeout.
- When Task Dispatch state changes, run State Truth Reconciliation before
  moving on: task status, runs, leases, blockers, closure notes, evidence
  reasons, artifacts, commands, ledger decisions, board status, and next action
  must describe the same current truth. Do not leave planning/future/waiting or
  superseded STOP text active after authority, branch, run, or lease state has
  changed. Reconciliation is inspect-only by default; mutate each surface only
  with its named ownership and write/corrective authority, otherwise return an
  update proposal, corrective packet, or `HANDOFF`.
- Use Project Owner Entry for broad or non-technical ideas, but do not promote
  its draft outputs into an executable roadmap until a capability map and
  Milestone Granularity Gate pass.
- Automatically select Planning Package Closeout Flow when the work is
  planning-only, manual handoff is the main cost, submit or push is explicitly
  authorized or separately assigned to a Submit Controller, role separation can
  be preserved, and the work is limited to roadmap, capability map, milestone,
  phase, ledger,
  evidence/status, review packet, closeout, or submit handoff artifacts.
  Preserve separate Planning Author, Planning Review, Targeted Fix, Closure
  Verification (`strict Deterministic Closure` or `Targeted Re-Review`),
  Closeout/Status, and Submit Controller authority. Stop and run full
  affected review lanes if semantics, permissions, source authority,
  information architecture, contracts, approval gates, validator meaning,
  implementation scope, or runtime behavior changes.

## End Of Run

Before final handoff, commit, or completion:

1. Run the required checks or state why they cannot run.
2. Maintain `docs/ACTIVE_CONTEXT.md` by replacement, not append-only history,
   only when permission mode and ownership allow direct writes; otherwise
   return a memory update proposal or no-change note.
3. Update `docs/DOC_ROUTING.md` only when routing or document topology changed
   and permission mode plus ownership allow direct writes; otherwise record a
   memory update proposal or no-change note.
4. Update the completion report and milestone ledger with memory maintenance
   status when the task owns them.
5. Write or update `MILESTONE_CLOSEOUT.md` only when closing a milestone.
6. Update task/evidence records and run the dispatch validator only when Task
   Dispatch Profile is active for the current task or gate.
7. Run State Truth Reconciliation when task, evidence, lease, authority, board,
   ledger, or next-action state changed.
8. Report skipped checks, blockers, remaining gaps, and next action.
