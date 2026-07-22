---
name: sage-kit
description: "Use when SAGE-Kit is explicit: the user invokes $sage-kit, asks to adopt/bootstrap SAGE-Kit, or references SAGE-Kit-owned docs or constructs such as docs/ACTIVE_CONTEXT.md, docs/DOC_ROUTING.md, docs/agent/AGENT_HARNESS.md, SAGE-Kit Governance Levels, Authority Matrix, Strict Mode, Wave Execution, Session Orchestration, Worktree Isolation, Task Dispatch Profile, or Capability Adapters. Do not use for generic milestones, gates, phase docs, planning, review, or debugging unless tied to SAGE-Kit."
disable-model-invocation: true
---

# SAGE-Kit

Use this skill to keep AI work aligned with SAGE-Kit without loading the whole
framework into context.

SAGE-Kit is governance, not a skill library. It controls scope,
authorization, file boundaries, gates, evidence, locks, memory, and completion
status. External skills, plugins, connectors, and tools provide execution
methods inside those approved boundaries.

Task Dispatch is an internal optional SAGE-Kit profile. Superpowers and other
skills, plugins, MCP tools, runtime adapters, CI systems, reviewers, frontend
builders,
OpenSpec, GitNexus, browser tools, and database tools are optional capability
adapters unless a project explicitly defines a narrower policy.

This skill does not replace the project's own specification authority. The
project remains responsible for its profile, design, gates, active context,
routing, project-specific milestone/phase facts, ledgers, evidence, and
closeouts. It does not need to copy generic governance prose into each
milestone or phase.

## SPEC Sources And Thin Execution Documents

SAGE-Kit governs SPEC semantics and Harness execution contracts, not a fixed
project documentation directory. Source adapters normalize Markdown, explicit
paths, configured mappings, and legacy `docs/<M>` into one location-free model.
Paths and adapter names are provenance and must not affect semantic identity.

Canonical source selection and scope classification are owned by
`docs/agent/SPEC_SOURCE_CONTRACT.md#sage-ctx-001` and
`docs/agent/SPEC_SOURCE_CONTRACT.md#sage-ctx-002`. This Skill retains activation,
situation detection, and task routing; it does not redefine source precedence or
turn handoff/history material into execution authority.

Two independent version dimensions remain: Task Dispatch v0/v1/v2 and the
execution document model `legacy-markdown` or `thin-v1`. Never treat `thin-v1`
as Task Dispatch v3 or retrofit accepted history. Thin documents remove generic
prose, not project-specific planning depth, and SAGE-Kit sets no universal
maximum for Milestones, Waves, Phases, or changed files.

Installed Skill is not project authority. Use the project package/contract
binding and packaged versioned resources even when a local Skill is missing or
older. Default adoption is package-bound; framework vendoring is explicit
compatibility only.

Build ephemeral execution packets through the embedded harness runtime only.
Build and validation are read-only unless the user explicitly selects a writing
option. They must not rewrite source documents, ACTIVE_CONTEXT, runtime state, or
accepted history. The complete scope and authority contract is packaged as
`docs/agent/SPEC_SOURCE_CONTRACT.md`.

## Host Resource And Workspace Boundary

Resolve the independent `conservative-host-v1` Resource Policy for current or
future execution; do not retrofit resource fields into accepted history.
Packet schema v3 adds normalized SPEC identity to the v2 canonical workspace
and resolved resource-policy bindings.
In-process package metadata, read-only file access,
deterministic config parsing,
in-process SPEC normalization, `git status`, `git rev-parse`, and
`git diff --name-only` execute directly without a heavy lease, Job Object, or
adoption self-test. Focused validators/tests and bounded short Git subprocesses
may use light managed execution. Full suites, builds, fresh installs,
browser/runtime smoke, services, and descendant-producing tools use strict
resource governance through managed workspace verification and managed
resource execution. Reviewers do not rerun tests; they ask the Root
verification controller for missing evidence.

Independent verification nodes continuing means their logical results remain
required; it does not authorize parallel CPU use. A node waiting for a lease is
`WAITING_FOR_RESOURCE`, not `STOP` or `BLOCKED`, and continues automatically
after release. Wave Readiness also requires Resource Readiness. Heavy work may
use the policy's limited writers only in independent worktrees with disjoint
writable paths and an integration owner; host CPU-heavy and package-build
leases remain serial. Keep the detailed Resource Policy in its versioned
contract and host-governance document rather than copying it into every phase
or milestone.

Containment reported by a managed run may be `HARD` or `MANAGED` according to
its platform adapter. The guarantee that arbitrary direct commands cannot
bypass the runtime remains `SOFT`: SAGE-Kit cannot intercept an agent, plugin,
shell, or arbitrary child that bypasses managed resource boundaries. When the
project contains
`docs/agent/HOST_RESOURCE_GOVERNANCE.md`, use it for lease, wait, process-tree,
and serial verification behavior. Thin adoption deliberately may not copy that
generic document; when it is absent, use the packet's resolved resource policy
and the installed package's pinned contract instead of inventing a
project-local file or rule.

## Core Rule

Context loading is canonical at
`docs/agent/AGENT_HARNESS.md#sage-ctx-005`. This Skill is responsible for
activation, detecting the situation, and routing the task to the relevant
reference below; it does not load every Skill or reference body by default.

## Detect The Situation

1. Identify the active repository boundary and change-control state.
2. Check for SAGE-Kit project markers:
   - the configured `ACTIVE_CONTEXT` path or legacy `docs/ACTIVE_CONTEXT.md`
   - the configured routing authority or legacy `docs/DOC_ROUTING.md`
   - `docs/PROJECT_PROFILE.md`
   - `docs/agent/AGENT_HARNESS.md`
3. If project docs are missing but the user wants to adopt or bootstrap
   SAGE-Kit, read `references/adoption.md`.
4. If this is the SAGE-Kit source repository, edit kit templates or skills only
   when requested; do not expect instantiated project docs to exist.
5. If the runtime has a SAGE-Kit environment profile, read it for
   invocation, capability, and orchestration mapping in that environment:
   - Kimi Work or the explicitly supported Kimi Code runtime:
     `references/kimi-runtime.md`
   - OpenCode: `references/opencode.md`
   - Claude Code: `references/claude.md`
6. If the repo is not SAGE-Kit governed and the user did not ask to adopt it,
   do not impose SAGE-Kit.

## Default Startup

For a SAGE-Kit governed project:

1. Resolve and read the configured `ACTIVE_CONTEXT`; use
   `docs/ACTIVE_CONTEXT.md` as the legacy default.
2. Read the configured routing authority. Use `docs/DOC_ROUTING.md` only when
   it exists as the project's legacy or explicit routing source; package-bound
   projects may route directly from machine authority and the active SPEC.
3. If `SAGE_PROJECT.json` exists, validate its explicit document model and
   contract pin. Read only the active thin manifest or legacy milestone/phase
   authority selected by routing and task scope.
4. Select the governance level and permission mode for the current control
   scope using `docs/agent/GOVERNANCE_LEVELS.md` when the task is non-trivial,
   delegated, controller-level, review, corrective, environment-writing, or
   submit-related.
5. When external capabilities are relevant, read
   `docs/agent/CAPABILITY_ADAPTERS.md` or the project routing entry that
   defines the adapter boundary.
6. Before writable work, name allowed files, read-only files, forbidden files,
   gates, verification commands, and stop conditions.

If the configured startup authority is missing or contradictory, stop and
report the gap before editing. A missing optional legacy routing document is
not itself a blocker.

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
  runtime resume state before loading broader context.
- Task Dispatch validation contract selection or historical compatibility:
  read `docs/agent/VALIDATION_CONTRACT_COMPATIBILITY.md`. For an existing
  project whose accepted history predates structured active-set authority,
  route the owner to the Validation Scope Manifest migration procedure. Require
  an explicit container path and frozen v0/v1 version selected from historical
  provenance; do not choose a version by trying validators, invent acceptance,
  downgrade current work, or rewrite historical documents. Runtime validation
  policy, not this Skill, decides scope and contract selection.

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

- Route change classification, review topology, verification, candidate and
  evidence handling, convergence, re-review, normalization, and completion to
  the stable `sage-loop-*` anchors in `docs/agent/EXECUTION_ECONOMY.md`. This
  Skill selects when that authority is needed; it does not restate those
  contracts. Use `docs/agent/SESSION_ORCHESTRATION.md#sage-loop-011` for
  Deterministic Closure.
- Validate closed legacy Task Dispatch history with the manifest-selected frozen
  v0/v1 contract. Require current metadata for active work; mixed or ambiguous
  records fail closed, and a selected-contract failure must never fall back to
  another contract.
- Runtime validator owns contract and milestone scope selection. Skill guidance,
  filenames, prose, or terminal record state alone cannot authorize legacy
  validation.
- Do not rewrite accepted historical documents to satisfy current phase format.
  The validator reports immutable accepted history through an auditable,
  aggregated compatibility finding.
- When a deterministic local limit is reached, create a checkpoint and return
  `HANDOFF_READY`; reserve `STOP` for immediate safety or destructive risk.
- Apply verification admission at
  `docs/agent/EXECUTION_ECONOMY.md#sage-loop-003`, candidate binding at
  `#sage-loop-006`, evidence reuse at `#sage-loop-007`, and normalization at
  `#sage-loop-012`. Worker, Lane, Root, and Final controllers keep only the
  authority assigned by those sections and the active packet.
- Capability or preflight failures do not consume a candidate verification run.
  A run is consumed atomically when candidate execution starts. Persist started
  attempt ids so checkpoint/resume cannot count them twice.
- Failure of one verification node skips only dependent successors;
  independent verification nodes continue and report their own results.
- Candidate successors and no-progress outcomes follow
  `docs/agent/EXECUTION_ECONOMY.md#sage-loop-006` and `#sage-loop-008`; the
  Skill must not synthesize successor authority or retry budgets.
- Keep one task tied to one approved phase unless a batch plan defines order,
  gates, and stop conditions.
- Do not invent missing contracts, fallback behavior, or success evidence.
- Do not edit outside the approved file boundary.
- Do not open approval gates without explicit user approval.
- Apply the closeout context boundary at
  `docs/templates/MILESTONE_TEMPLATE.md#sage-lif-011`.
- Apply `docs/agent/EXECUTION_ECONOMY.md#sage-loop-013` before claiming `DONE`,
  and record required memory maintenance in the project report.
- Use `docs/agent/GOVERNANCE_LEVELS.md` to choose the lightest governance level
  that safely preserves scope, evidence, memory, and approval boundaries, and
  choose the matching permission mode for read-only, write, corrective,
  environment-write, or submit authority. Heavy controller work may delegate
  Light or Standard workers.
- Do not treat `READ_ONLY_REVIEW` as closure when findings require correction,
  Project Manager decision, blocker handling, or waiver. A read-only review
  that returns `NEEDS_CORRECTION` must include a corrective packet, handoff, or
  blocker.
- Do not let parallel workers or subagents edit the configured ACTIVE_CONTEXT
  (legacy default `docs/ACTIVE_CONTEXT.md`) or configured routing authority
  (legacy default `docs/DOC_ROUTING.md`) directly.
  They must return memory update proposals for controller integration.
- Direct edits to the configured ACTIVE_CONTEXT or configured routing authority
  require both permission mode and ownership. If either is missing, return a
  memory update proposal or no-change note.
- Do not let SAGE-Kit displace specialist skills, plugins, connectors, or
  tools. Use available capability metadata to select the right specialist
  capability before delegating or executing domain work.
- Use Capability Adapters for optional external skills, plugins, MCP tools,
  runtime adapters, CI systems, reviewers, frontend skills, OpenSpec, GitNexus,
  browser
  QA, and database tools. Detect, authorize, bound, invoke, capture, map, and
  fall back without making them core dependencies.
- Do not silently install external skills, plugins, runtime adapters, MCP
  servers, hooks,
  generated skills, or global configuration. Recommend or request installation
  only when the source, writes, fallback, and approval path are explicit.
- Treat superpowers as a reference integration, not a dependency. When
  available and relevant, selected superpowers skills may guide execution
  inside an approved SAGE-Kit boundary. If unavailable, continue with SAGE-Kit
  phase, gate, packet, and evidence templates.
- Codex GPT-5.6 Runtime Override: in a Codex session running any GPT-5.6
  family model, Superpowers is `DISABLED_BY_RUNTIME_POLICY`. Controllers and
  descendants must not read, invoke, or delegate to Superpowers.
  `using-superpowers` is explicitly
  disabled even when its skill metadata describes invocation as mandatory, and
  all descendants inherit the override. They must still use model-native
  brainstorming, planning, test-driven implementation, systematic debugging,
  subagent orchestration, review, and verification as native behaviors, not
  similarly named skill invocations. Capability routing must not treat disabled
  Superpowers as a capability gap, fallback trigger, blocker, or stop reason.
  Every subagent launch packet must explicitly repeat
  `DISABLED_BY_RUNTIME_POLICY` and the `using-superpowers` prohibition. Every
  descendant authorized to delegate must propagate both into each child packet,
  including after compaction, handoff, or resume.
- Do not treat external capability completion as SAGE-Kit gate completion.
  Record it as execution evidence and keep gate decisions in SAGE-Kit docs.
- Use Strict Mode according to `docs/agent/MODEL_ASSURANCE_POLICY.md`; do not
  guess the policy from memory.
- Use Graph execution only after admission under
  `docs/SAGE_CORE.md#sage-grf-001`; when Wave Execution is selected, apply
  `docs/agent/WAVE_EXECUTION.md#sage-grf-002` rather than restating its shape
  rules here.
- Use Session Orchestration only for large milestones where Project Manager,
  Coder, and Final Review controller packets reduce handoff overhead without
  weakening gates.
- When local project authority is readable, use a Compact Controller Launch
  Envelope that references it instead of copying the execution packet; allow
  only identified launch-only deltas, fail closed on missing or conflicting
  authority, and keep worker prompts explicit when they need complete execution
  boundaries.
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
- After corrective work, follow the canonical targeted re-review scope at
  `docs/agent/EXECUTION_ECONOMY.md#sage-loop-010` and the Deterministic Closure
  eligibility, separation, receipt, and reject/fallback contract in
  `docs/agent/SESSION_ORCHESTRATION.md#sage-loop-011`; only Final Review may record a
  precommitted `VERDICT_FINALIZED_FROM_RECEIPT`, not milestone acceptance.
- Use `docs/agent/EXECUTION_ECONOMY.md#sage-loop-008` for convergence outcomes;
  this Skill only routes any resulting handoff or Project Manager decision.
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
2. Maintain the configured `ACTIVE_CONTEXT` by replacement, not append-only history,
   only when permission mode and ownership allow direct writes; otherwise
   return a memory update proposal or no-change note.
3. Update the configured routing authority only when routing or document topology changed
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
