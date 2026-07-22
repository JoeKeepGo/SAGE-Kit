# SAGE-Kit Execution

Execution economy, change classes, Bounded Corrective Authority, evidence
invalidation, one primary review topology, shared-file serialization, and local
limits are canonical in `docs/agent/EXECUTION_ECONOMY.md`. Use
`docs/agent/CONTINUITY_PROTOCOL.md` when a local limit requires
`HANDOFF_READY`. These rules prevent older generic execution guidance from
causing broader repeated work; explicit project approval and safety gates still
control.

Use this reference for implementation, debugging, refactoring, subagent work,
Strict Mode, Wave Execution, Session Orchestration, or Worktree Isolation.

## Thin Packet Compilation

For an explicitly adopted `thin-v1` milestone, validate `SAGE_PROJECT.json`,
`MILESTONE_MANIFEST.json`, and the selected phase manifest before execution.
Resolve the selected current source under
`docs/agent/SPEC_SOURCE_CONTRACT.md#sage-ctx-001`.
Resolve explicit project approval/gates before project overrides, pinned
contract/profile policy, and runtime defaults. Unknown profiles, invalid
overrides, conflicting authority, and missing digests must not fall back.

Build the temporary execution packet through the harness packet builder. The
packet binds the project lock, milestone, phase, resolved policy, and source
digests. Compact output is suitable only when the runtime can load the exact
pinned profile. A standalone compiled packet includes the resolved generic
rules. Both forms retain exact project scope, verification, and stop conditions;
neither changes source manifests, `ACTIVE_CONTEXT`, or `DOC_ROUTING`.

## Pre-Edit Gate

Before editing files:

1. Read the routed specification docs.
2. Inspect current code or docs with narrow searches.
3. Select the governance level for the current control scope.
4. State governance level and permission mode.
5. State allowed files, read-only files, forbidden files, and shared files.
6. Identify quality gates, approval gates, tests, smoke, and stop conditions.
7. Stop if the required change falls outside the phase boundary.

## Execution Loop

1. Implement the narrowest change.
2. Keep contracts explicit.
3. Avoid unrelated refactors.
4. Add or update focused tests when behavior changes.
5. Run focused checks.
6. Run runtime smoke when runtime behavior is claimed.
7. Record evidence in the completion report, phase doc, or ledger.

## Strict Mode

Use the project model assurance policy to decide whether Strict Mode is
required.

In Strict Mode:

- execute only the task card;
- read only listed files;
- modify only allowed files;
- run exact commands;
- stop on ambiguity, failed required commands, missing contracts, or approval
  gates;
- return memory update proposals when startup docs are not allowed files.

Strict Mode `DONE` means the task card is complete, not necessarily the phase.

## Subagents And Lanes

Use subagents only for bounded tasks with clear ownership. For each lane, define:

- role;
- objective;
- governance level;
- allowed files;
- forbidden files;
- applicable skills, plugins, connectors, or tools;
- commands;
- expected evidence;
- return format.

Before delegating, inspect available capability metadata when the runtime
exposes it. Select specialist capabilities from metadata first, then load only
the selected capability instructions needed for the worker.

SAGE-Kit governs scope, gates, files, and evidence. Specialist capabilities do
the domain work.

## External Capability Integration

Use external skills, plugins, connectors, and tools only when they are relevant
to the approved SAGE-Kit phase, lane, task, or corrective boundary.

External capabilities may supply execution methods. They must not redefine
scope, create new file authority, bypass locks, open approval gates, downgrade
required evidence, or mark SAGE-Kit gates complete.

Superpowers is a reference integration, not a hard dependency. If it is
available, route only to the named skills that fit the current need. If it is
unavailable, continue with SAGE-Kit phase, gate, packet, and evidence
templates.

### Codex GPT-5.6 Runtime Override

For every Codex GPT-5.6 family session, Superpowers is
`DISABLED_BY_RUNTIME_POLICY`. The controller and its descendants must not read,
invoke, or delegate to Superpowers, including `using-superpowers` and composite
Superpowers workflows. `using-superpowers` is explicitly disabled even when its
skill metadata describes invocation as mandatory. All descendants inherit this
override and must not re-enable the adapter through delegation.

Every subagent launch packet must explicitly repeat
`DISABLED_BY_RUNTIME_POLICY` and the `using-superpowers` prohibition. Every
descendant authorized to delegate must copy both into each child launch packet.
Preserve the policy across context compaction, handoff, resume, and replacement
workers; do not rely on a one-time follow-up message to an already running
worker.

Use model-native brainstorming, planning, test-driven implementation,
systematic debugging, subagent orchestration, review, and verification instead.
These are required native behaviors, not similarly named skill invocations. The
override changes the method provider, not the required engineering discipline
or SAGE-Kit evidence contract.

Record the adapter as disabled. Capability routing must not treat disabled
Superpowers as a capability gap, fallback trigger, blocker, or stop reason. If
an existing packet selected a Superpowers workflow, use the equivalent
model-native workflow inside the same approved boundary without reopening scope
or gates.

Precedence is `Codex GPT-5.6 Runtime Override > generic capability routing >
Superpowers availability`. Claude, Kimi, OpenCode, and non-GPT-5.6 runtime
mappings remain unchanged.

Apply `docs/agent/CAPABILITY_ADAPTERS.md` for external capabilities. Use
metadata-only or read-only behavior by default. Do not install capabilities,
write MCP config, add hooks, generate global skills, or mutate environment
configuration unless the active SAGE-Kit boundary or user approval explicitly
allows it.

For approved install candidates such as `ui-ux-pro-max`, `OpenSpec`, or
`GitNexus`, do not rely on remembered commands. Read current capability
documentation, package metadata, or installed-tool help first; then request
approval with exact command, write list, runtime requirements, rollback path,
and fallback. If docs are unclear or conflict, return `HANDOFF`.

For `ui-ux-pro-max`, prefer a single Codex-targeted install path when approved.
Do not use `--ai all`, global install, or multi-assistant generation unless the
user explicitly approves the wider environment write. `design-system/` outputs
require allowed-file coverage and remain design evidence, not SAGE-Kit source
of truth.

Recommended routing:

| Need | superpowers Skill |
|---|---|
| Clarify broad intent before planning | `superpowers:brainstorming` |
| Convert an approved phase into an execution plan | `superpowers:writing-plans` |
| Implement a feature or bug fix | `superpowers:test-driven-development` |
| Diagnose failures or unexpected behavior | `superpowers:systematic-debugging` |
| Run bounded worker tasks | `superpowers:subagent-driven-development` or `superpowers:dispatching-parallel-agents` |
| Request implementation review | `superpowers:requesting-code-review` |
| Prove work before completion claims | `superpowers:verification-before-completion` |
| Finish branch work after submit authority exists | `superpowers:finishing-a-development-branch` |

Frontend work should detect and select an available frontend or browser-testing
adapter when UI, styling, responsive layout, design-system components,
accessibility, or visual QA is in scope and the adapter is useful. If no
adapter is available, authorized, or useful, record the fallback and continue
through the SAGE-Kit-native path when safe. Selected adapters must return
runtime, screenshot, console, network, responsive, or accessibility evidence as
applicable, but SAGE-Kit still decides the gate.

SAGE-Kit remains authoritative for scope, file ownership, governance level,
resource locks, quality gates, approval gates, memory maintenance, milestone
state, and final acceptance.

Do not copy full external workflows into SAGE-Kit docs. Record the selected
capability name, the boundary it served, and concise evidence produced.

External planning outputs must be written into, or explicitly mapped to, the
active milestone ledger, phase doc, execution packet, or result packet. Do not
leave an untracked second source of truth.

External capability completion is execution evidence. It is not acceptance,
gate completion, milestone closure, or authorization to continue past a closed
SAGE-Kit gate.

Continuous execution may proceed only inside the approved phase, task, lane, or
corrective boundary. Stop for controller or user decision on closed approval
gates, scope expansion, shared-file conflicts, resource lock conflicts, failed
required evidence, or unapproved runtime, destructive, submit, merge, push, or
cleanup operations.

Parallel writable lanes must not share files. Parallel lanes must not edit
`ACTIVE_CONTEXT.md` or `DOC_ROUTING.md`; they return proposals for controller
integration.

Direct memory-file edits require both permission mode and ownership. Without
both, return a `Memory Update Proposal` or explicit no-change note.

Do not inherit Heavy governance globally. A Heavy milestone controller may
delegate Light or Standard workers when their scope is narrow and risk is
bounded. Workers that discover Heavy triggers must stop for controller
decision.

## Worktree Isolation

Use Worktree Isolation only when the Project Manager execution packet allows
it.

Coder Controller may decide which authorized phases or lanes receive worktrees.
It must record the worktree map, branch names, owners, integration status, and
cleanup recommendation in the milestone result packet.

Keep work serial or stop for Project Manager when shared files, migrations,
lockfiles, generated artifacts, runtime ownership, approval gates, branch base,
maximum worktree count, submit authority, or cleanup policy are unclear.

Workers must not push, merge, or delete worktrees unless the packet explicitly
assigns that authority.

## Task Dispatch

Use Task Dispatch Profile only when the active milestone or execution packet
adopts it.

When active:

- read the active `task.yaml` and `evidence.yaml` named by routing;
- keep task status, runs, attempts, resource locks, leases, blockers, and next
  action current;
- run State Truth Reconciliation whenever a task moves between planning,
  waiting, authorized, in-progress, pending-review, verified, blocked, or
  released states;
- record L0-L4 evidence in `evidence.yaml` instead of copying long logs into
  startup docs;
- run the active Task Dispatch validator check before returning a task,
  phase, or milestone as gate-ready when the packet requires validator
  closeout;
- return `HANDOFF` or `BLOCKED` when validator failure reflects missing scope,
  missing evidence, unsafe fallback, or a Project Manager decision.

Do not create task-dispatch records for ordinary small tasks unless Project
Manager adopted the profile.

### State Truth Reconciliation

Run this gate before starting a task, after creating or renewing a run/lease,
before leaving a task, and before moving to the next task or phase.

All active state surfaces must agree:

- `task.yaml`: status, runs, attempts, locks, leases, blockers, closure note,
  and next action;
- `evidence.yaml`: status, L0-L4 reasons, next action, artifacts,
  files-changed, commands, skipped checks, and review result;
- milestone ledger and dispatch board: current status, historical decisions,
  accepted authority, blockers, and next action;
- completion or result packet when it exists.

Reconciliation is inspect-only by default. Use the owner recorded by project
routing or the active packet. In the absence of a narrower project rule:

- Project Manager owns the dispatch board, milestone ledger, and current
  decision state;
- the assigned execution controller owns `task.yaml` lifecycle and run/lease
  coordination;
- the evidence producer owns evidence facts, while the assigned reviewer owns
  review result and acceptance fields;
- the packet author owns its result, review, or corrective packet.

Mutate a surface only when both ownership and the required write or corrective
authority are present. Otherwise return a precise update proposal, corrective
packet, or `HANDOFF`; do not make multiple files agree by overwriting a more
authoritative source.

If authority, branch, baseline, run, lease, or gate state changed, remove stale
planning/future/waiting wording from active fields. Historical STOP or waiting
decisions may remain only when marked historical, superseded, or unlocked by a
named accepted authority.

Do not advance to the next task or phase when structured task/evidence fields
contradict the ledger, board, active run, or lease. Treat that as false-green
or stale-authority risk, not ordinary documentation cleanup.

## Session Orchestration

When Session Orchestration is active:

- Project Manager creates the milestone execution packet.
- Coder Controller orchestrates phase and lane workers by default.
- Coder Controller may self-execute only when the execution packet explicitly
  allows a narrow phase, integration glue step, or integration repair before
  Final Review; it must record why worker dispatch was skipped.
- Coder performs integration self review, runs bounded integration repair
  workers when allowed, and returns a milestone result packet.
- Project Manager runs only the structural gate.
- Final Review Controller orchestrates review workers or validation lanes,
  verifies independently, and returns a verdict.
- Final Review classifies required corrections and either opens an authorized
  corrective round or returns a packet-only handoff, Project Manager decision
  request, or blocker.
- Corrective orchestration authority does not grant Final Review write
  authority. Final Review delegates fixes to separately authorized corrective
  workers and remains independent for re-review.
- Corrective workers fix only findings named in corrective packets.
- After corrective work, Final Review follows the Deterministic Closure or
  re-review selection contract in `docs/agent/SESSION_ORCHESTRATION.md`. Only
  the separated review authority may record a receipt and precommitted
  `VERDICT_FINALIZED_FROM_RECEIPT`; Project Manager acceptance remains pending.
- If Task Dispatch Profile is active, Coder updates task/evidence records and
  Final Review treats them as an evidence index to verify, not as proof by
  themselves.

Corrective convergence budgets may be configured by the execution or Final
Review packet, but they are control signals, not unconditional blockers.

### Compact Controller Launch Envelope

When local project authority is readable, launch a controller with role and
objective, authority references, baseline or entry condition, permission mode,
PM authority deltas, terminal state, and only necessary prohibitions or stop
conditions. The envelope must not duplicate the execution packet. A 40-80 line
target is a guideline, not a correctness gate.

Every PM authority delta retains its authority ID, source, priority, and
reconciliation destination. Classify it and handle authority gaps under
`docs/agent/AGENT_HARNESS.md#sage-auth-010`; this reference retains execution-
specific worker launch and packet-loading guidance.

Worker prompts remain explicit. Workers and external agents that cannot read
the referenced authority still receive exact allowed, read-only, and forbidden
files, tests, evidence, runtime ownership, and stop conditions.

### Advanced Execution Economy

Apply this lifecycle only when managed expensive verification is relevant to
Heavy, corrective, or final-verification work. Ordinary Light or Standard work,
including affected-lane focused verification, stays in the basic workflow above
and does not load or apply these advanced runtime details by default.

Managed expensive verification is eligible only for a frozen candidate whose
fingerprint matches current inputs. Before freeze, full suite, retained
regression, wheel/install, outside-source/package smoke, and full integration
re-review are prohibited; legacy preliminary counters do not authorize them.
Any legacy pre-freeze result remains only a historical development signal and
cannot serve as final acceptance evidence.

For one finding, use the minimum reproduction and directly affected focused
tests. At a lane gate, use only the affected-lane suite. After a corrective,
use targeted verification and targeted re-review. Reduce harness or teardown
failures to a minimum reproduction instead of rerunning the complete suite.
Ordinary record or status correction uses targeted consistency verification
and does not reopen a product full suite while implementation inputs remain
unchanged.

Reuse matching-fingerprint evidence while its inputs remain unchanged. A new
diff invalidates only the affected checks, paths, contracts, dependencies,
platforms, or packages; independent evidence remains reusable. Workers and
reviewers cannot expand expensive-verification authority. A Lane Controller
owns only affected-lane verification, and the Root or Final Controller
exclusively owns final full-suite authority.

Capability or preflight failure for an eligible candidate does not consume a
final run. Each admitted attempt keeps one stable identity, records `STARTED`
once and its terminal completion, and resumes from checkpoints under that same
identity without recounting. When one verification-graph node fails, skip only
successors that depend on it; continue and report independent nodes.

After the single corrective batch closes, freeze a
HEAD/diff/contract/dependency fingerprint and allow one final run per matching
candidate. Final verification and acceptance bind only to that exact frozen
candidate. A candidate change retains the old result as history but forbids
reusing it as current final evidence.

Candidate freeze defaults to `clean-head`, which rejects staged, unstaged, and
untracked changes. When the active packet explicitly authorizes it, use
`working-tree` to bind the complete non-ignored uncommitted state without
granting commit or submit authority. Pass and bind the packet's non-empty
snapshot authority. Reassess that snapshot before and after
final verification. Any staged, unstaged, untracked, deletion, mode, or symlink
drift invalidates it. Dirty submodules and unrepresentable state fail closed;
there is no unbound allow-dirty option or automatic fallback to another mode.

One approved corrective batch may create one automatic successor without
budget approval; another successor from that batch or any change after final
verification returns `HANDOFF_READY`. A human-approved handoff corrective may
create the next generation only when it persists an authority anchor,
root-cause id, and finding count. Generation is not mechanically capped; the
same root cause with no progress for two approved rounds returns `BLOCKED`,
while reduced findings reset the no-progress count.

Within an explicit Preauthorized Convergence Window, each successor candidate
keeps a distinct fingerprint, checkpoint, finding trend, and final-verification
budget. A successor must identify its predecessor and state which findings it
closed and retained; it must not overwrite candidate identity or delete
historical records to manufacture convergence. Checkpoints remain traceable to
their input candidate and caller-supplied finding evidence. Final verification
must run against the final candidate, and acceptance binds only that verified
candidate rather than reusing an earlier success claim.

Stop or return `HANDOFF_READY` when a correction expands scope, changes
authority, weakens an invariant, gate, security boundary, or test, or crosses
the protected-path boundary.

This reference does not itself authorize querying, polling, or operating
remote CI. Only an explicitly authorized Capability Adapter may do so;
otherwise the caller supplies CI and finding evidence, and SAGE-Kit binds that
evidence to candidate continuity, checkpoints, and consistency verification.

Do not infer a governance result from user token budgets, platform quotas, or
similar service limits. Record the concrete capability or evidence constraint
and use the applicable handoff, checkpoint, or stop rule instead.
Continue automatic correction only inside an authorized corrective packet or
boundary while findings or severity decrease, scope does not expand, no
blocking approval gate is bypassed, and no new authority, false-green,
approval-gate, security, validator/gate-ready, source-authority, or
evidence-integrity risk appears. Stop as `BLOCKED` when the same root cause has
no material progress for two consecutive rounds, required evidence or authority
is missing, or the fix would exceed the approved boundary. When Project Manager
judgment is needed, return `NEEDS_CORRECTION` with `PM_DECISION_REQUIRED`
closure/status rather than `BLOCKED`.

Coder and Final Review controllers must reassess whether the milestone should
run serially, with waves inside phases, or with parallel phases. Heavy mode
does not imply wave readiness. Stop for Project Manager when a sequencing
change affects scope, approval gates, public contracts, shared ownership, or
final decision authority.

Apply Graph admission from `docs/SAGE_CORE.md#sage-grf-001` and execution-shape
and active-change semantics from `docs/agent/WAVE_EXECUTION.md#sage-grf-002` and
`docs/agent/WAVE_EXECUTION.md#sage-grf-006`. This reference remains responsible
for executing the selected shape and returning a controller decision when its
packet boundary would change.

## Runtime And Integration Claims

Do not claim UI, API, service, worker, database, device, or external integration
success from static inspection alone. Use live runtime evidence when that
surface is in scope, or record why smoke is not applicable.

## Stop Conditions

Stop or return to planning when:

- required files are outside the phase boundary;
- a closed approval gate is needed;
- an external capability suggests scope, file, runtime, or gate changes outside
  the approved boundary;
- an external planning output has not been mapped into tracked SAGE-Kit docs;
- a shared-file conflict or resource lock conflict appears;
- required evidence fails or cannot be produced;
- unapproved runtime, destructive, submit, merge, push, or cleanup operations
  are needed;
- contract owner and consumer disagree;
- runtime verification contradicts assumptions;
- local data hygiene is at risk;
- the task combines unrelated milestones.
