# Quality Gates Template

This document defines the evidence required before project work can be called
complete.

## Gate Levels

| Level | Use When | Evidence Examples |
|---|---|---|
| Unit | Pure behavior in one module. | Focused test cases. |
| Contract | API, event, CLI, worker, UI, or config boundary. | Schema tests, fixture tests, consumer tests. |
| Integration | Multiple components interact. | Service-to-worker, API-to-database, backend-to-external adapter checks. |
| Runtime | Behavior depends on a running process. | Curl, CLI invocation, process health, logs. |
| UI | User-visible behavior changes, if the project has a UI. | Browser or component smoke with visible states. |
| Security | Secrets, auth, permissions, sensitive data. | Redaction checks, deny-path tests, scans. |
| Release | Build, package, deploy, or publish. | Artifact checks, rollback notes, release smoke. |

## Gate Status Values

Every phase completion report must classify applicable gates with these values.

| Status | Meaning |
|---|---|
| `PASS` | Required evidence exists and was checked. |
| `FAIL` | Evidence was produced and shows the gate failed. |
| `BLOCKED` | Evidence cannot be produced without a blocker, missing input, or approval. |
| `WAIVED` | Project owner explicitly accepted the risk for this phase. |
| `N/A` | Gate does not apply, with a concrete reason. |

Blocking gates marked `FAIL`, `BLOCKED`, or missing cannot be accepted.
Blocking gates marked `WAIVED` require owner, reason, and scope.

## Universal Required Gates

| Gate | Required Evidence |
|---|---|
| Read gate | Completion report names authority and context read, files, and verification plan. |
| Project owner entry gate | Broad, non-technical, or coarse-roadmap projects produce intake and a capability map before executable roadmap planning. |
| Active execution authority gate | Non-trivial work uses retained active SPEC, phase, or task authority in the project's selected representation; Markdown is not required. |
| Milestone granularity gate | Milestone candidate maps to one primary capability and has reviewable phases with contracts, file boundaries, tests, and smoke plans. |
| Contract gate | Request, response, event, config, UI, CLI, or data contract is named before implementation. |
| Test gate | Focused tests exist and run, or a manual-only exception is justified. |
| Runtime gate | Runtime claims are proven by live evidence. |
| UI visibility gate | UI claims are proven by visible state checks when UI is in scope. |
| Wave safety gate | When Wave Execution is used, parallel lanes have exclusive file ownership and controller integration evidence. |
| Wave readiness gate | Wave or parallel phase execution names independent lanes, exclusive writable files, serial shared files, frozen contracts, runtime ownership, validation lanes, integration owner, and conflict stop conditions. |
| Coder separation gate | In Session Orchestration, Coder Controller self-execution is absent or explicitly allowed, narrow, recorded, and independently reviewed. |
| Authority gate | Every active packet names both governance level and permission mode; write, corrective, environment-write, and submit authority are explicit. |
| Corrective closure gate | When review returns required corrections, it provides a corrective packet, Project Manager decision request, blocker, or waiver path. |
| Correction re-review gate | Corrective rounds have independent re-review evidence before Final Review closes the verdict, except exact `MECHANICAL_STATUS` corrections closed by a reviewer-authored Deterministic Closure predicate and receipt. |
| Deterministic closure gate | A no-re-review closure names the prior reviewer predicate, precommitted final verdict, authoritative value/source, exact allowed diff, closure commands, out-of-scope hashes, State Truth result, a Closure Receipt Owner separate from the fixer, receipt ref/destination, `AUTO_CLOSED_BY_PREDICATE`, and `VERDICT_FINALIZED_FROM_RECEIPT`; any mismatch falls back to re-review. |
| Security gate | Secrets and sensitive data are not exposed or staged. |
| No fallback gate | No guessed fields, hidden success, speculative aliases, unauthorized fallback behavior, or silent downgrade paths. |
| Completion report gate | Final report lists files, tests, smoke, skipped checks, and remaining gaps. |
| Capability adapter gate | External capability use records adapter name, authorization level, boundary served, evidence produced, and required or safe-fallback behavior. |
| Structured dispatch gate | When Task Dispatch Profile is active, task and evidence records exist, required L0-L4 levels are present, resource locks and leases are recorded, and the validator passes in gate-ready mode before acceptance. |
| State Truth Reconciliation gate | When Task Dispatch is active, record reconciliation under `docs/profiles/task-dispatch/DISPATCH_PROFILE.md`; mismatches block acceptance. |

## State Truth Reconciliation Gate

Record:

- applicability and inactive-profile reason when `N/A`;
- profile reference;
- owners and mutation authority checked;
- mismatches or corrective/handoff reference;
- result: `PASS`, `BLOCKED`, or `N/A`.

State Truth conflicts block closure until the responsible surface owners
reconcile them under matching write/corrective authority. Ledger, task,
evidence, status, and implementation surfaces remain writable only by their
named owners. A Closure Receipt Owner verifies the reconciled state and records
the receipt only in its own review packet/output; that review-output write does
not grant authority over any corrected surface.

## Finding Severity Acceptance Rule

Final Review severity decides whether Project Manager acceptance is blocked.

| Severity | Acceptance Rule |
|---|---|
| `P0` | Blocks acceptance while open. It may close only after the issue is fixed or explicitly reclassified with evidence by the required authority. |
| `P1` | Blocks acceptance while open. It may close only after the issue is fixed or explicitly reclassified with evidence by the required authority. |
| `P2` | Blocks acceptance only when it affects authority, false-green risk, approval gates, security boundaries, validator/gate-ready requirements, source authority, or evidence integrity. Ordinary documentation consistency P2 findings may be accepted with concerns or auto-corrected. |
| `P3` | Does not block acceptance. Record as concern, follow-up, or cleanup. |

## Corrective Convergence Rule

Corrective work should continue automatically only inside an authorized
corrective packet or boundary, and only while all are true:

- open finding count or severity is decreasing;
- the approved scope is not expanding;
- no blocking approval gate is bypassed;
- no new authority, false-green, approval-gate, security,
  validator/gate-ready, source-authority, or evidence-integrity risk appears;
- the same root cause has not stalled for two consecutive corrective rounds.

Do not mark work `BLOCKED` merely because a fixed round count was reached. Use
`BLOCKED` when no authorized path is making progress, required evidence or
authority is missing, scope would need to expand, or the same root cause has
made no material progress for two consecutive corrective rounds.

The no-re-review `MECHANICAL_STATUS` exception must satisfy the complete
Deterministic Closure contract and reject/fallback table in
`docs/agent/SESSION_ORCHESTRATION.md`. Only Final Review may record
`VERDICT_FINALIZED_FROM_RECEIPT`; Project Manager acceptance remains pending.
All ineligible or failed cases use the targeted or full re-review selected by
that contract.

Mechanical verification noise is not a blocking finding when the verification
command exits successfully. For example, `git diff --check` line-ending notices
such as LF-to-CRLF conversion warnings are non-blocking warnings when exit code
is `0`. Ordinary EOF/trailing-whitespace findings use the pre-freeze
`AUTO_NORMALIZATION_CORRECTIVE` contract in
`docs/agent/EXECUTION_ECONOMY.md`; they do not directly become an artificial
human blocker. Conflict markers, malformed patches, protected-byte findings,
or any remaining non-zero verification exit still fail closed.

### Preauthorized Convergence Window Gate

The Preauthorized Convergence Window is opt-in. If inactive, one approved
corrective batch still creates at most a single automatic successor. If active,
record its authority id and digest, execution scope, root-cause family,
component-aware allowed paths, invariant, `implementation-preserving-only`
policy, targeted-review state, stop conditions, and approval source.

Continue across multiple candidates only for semantic-preserving corrective
implementation while findings or severity converge, or when targeted-reviewed
evidence shows the next deterministic layer in the same family. Do not hand off
because of a fixed generation count. Each candidate still gets independent
final-verification counters and may start final verification only once.

Return `HANDOFF_READY` for policy-changing semantics, scope/path/invariant or
family changes, new gates or permissions, consumer mutation, security or
evidence weakening, test/gate weakening, or missing/malformed authority. Return
`BLOCKED` after two consecutive no-progress rounds for the same root cause or
when required evidence cannot be produced. Security, authority, containment,
validator, package, and release-gate implementation correctives require the
targeted review named by the authority. This is not an unlimited retry rule:
transient rerun is distinct from code corrective, and deterministic failure
must not be retried speculatively.

## Universal Blockers

- behavior changed but no test or smoke path exists;
- implementation started without retained active SPEC, phase, or task authority;
- a broad, non-technical, or coarse-roadmap project generated an executable roadmap directly
  from intake without a capability map and granularity audit;
- milestone implementation started before phases were decomposed into
  reviewable slices;
- a milestone candidate spans multiple primary capabilities without being
  split;
- a phase mixes unrelated ownership domains without a wave plan and integration
  owner;
- parallel lanes edit the same file without controller-owned serialization;
- a runtime behavior was claimed from static checks only;
- UI behavior was claimed without opening or smoke-checking the UI surface;
- Wave Execution or parallel phases are used without Wave Readiness Gate
  evidence;
- Coder Controller self-executes broad milestone work without explicit
  self-execution policy and independent review;
- a packet or handoff names governance level but omits permission mode;
- a read-only review returns `NEEDS_CORRECTION`, `BLOCKED`, or
  `Corrective Packet Required: yes` without a corrective packet, Project
  Manager decision request, blocker, or waiver path;
- corrective work changes files, behavior, contracts, runtime behavior, gate
  state, shared ownership, or required evidence without either independent
  re-review evidence or the complete strict Deterministic Closure receipt and
  verdict-finalization transition;
- a corrective worker authors/broadens a deterministic predicate, records its
  own closure receipt, or mutates a ledger, task, evidence, status, or
  implementation surface it does not own;
- write, corrective, environment-write, submit, merge, publish, release, or
  cleanup work occurs without the matching permission mode;
- a hidden success, unauthorized fallback, or silent downgrade path masks
  failure as success;
- an external capability writes files, installs tools, changes environment
  configuration, or claims completion without adapter authorization and
  evidence mapping;
- a shared contract changed without updating both owner and consumer evidence;
- secrets, credentials, tokens, private keys, account data, or production data
  are staged or committed.
- a blocking gate is skipped without an explicit `WAIVED` status from the
  project owner.
- Task Dispatch Profile is active and a task, phase, or milestone is accepted
  without a passing gate-ready dispatch validator result.
- Task Dispatch Profile is active and a task or evidence record is orphaned;
- two tasks claim overlapping `ACTIVE` or `HELD` exclusive locks;
- State Truth Reconciliation is `BLOCKED` under the active profile.

## Required Gate Status Table

Every phase completion report must include:

| Gate | Status | Evidence | Blocking | Owner | Notes |
|---|---|---|---|---|---|
| `<gate>` | `PASS`, `FAIL`, `BLOCKED`, `WAIVED`, or `N/A` | `<evidence>` | `<yes/no>` | `<owner>` | `<notes>` |

## Baseline Commands

Replace with project-specific commands:

```bash
<unit test command>
<typecheck command>
<build command>
<runtime smoke command>
```

## Completion Language Rule

Allowed:

```text
Unit tests passed. Runtime smoke was not applicable because this phase changed
only static documentation.
```

Not allowed:

```text
This should work.
```

Evidence beats confidence.

## Optional Structured Evidence Levels

Use these levels when a project adopts the Task Dispatch Profile:

| Level | Meaning |
|---|---|
| `L0` | Static and structural evidence. |
| `L1` | Focused behavior evidence. |
| `L2` | Contract or integration evidence. |
| `L3` | Runtime evidence. |
| `L4` | Release or production-path evidence. |

These levels complement the gate table above. They do not replace normal
quality gates, owner waivers, or Final Review judgment.
