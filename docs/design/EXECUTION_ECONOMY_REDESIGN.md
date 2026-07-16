# Execution Economy, Continuity, and Validation Compatibility Design

Status: implementation design
Runtime floor: Python 3.10
Runtime dependencies: standard library only

## 1. Purpose

This design makes SAGE-Kit economical enough for long-running work without
weakening authority, evidence, or validation integrity. It replaces mechanical
stop/review behavior with explicit change classes, bounded corrective authority,
deterministic execution limits, evidence invalidation, convergent review, and a
local resumable checkpoint.

Validation compatibility is a separate subsystem. Closed legacy records remain
validated by a frozen legacy contract, active work uses the current contract,
and ambiguous or mixed records fail closed.

The design is project-neutral. It does not depend on any external repository,
product name, shell, hosted agent platform, token counter, or weekly quota.

## 2. Design Choice

Three approaches were considered:

1. **Modular policy/runtime with a thin CLI.** Small modules own classification,
   authority, evidence, limits, review, continuity, contract selection, and
   reporting. The CLI composes them. This is the selected approach because each
   policy can be tested and evolved independently.
2. **Extend the existing validators in place.** This would minimize new files,
   but both validators are already large and mix parsing, policy, reconciliation,
   and presentation. Adding continuity and execution state there would create an
   unreviewable orchestrator.
3. **Document-only policy plus a checkpoint command.** This would be cheap, but
   it could not enforce fail-closed compatibility, checkpoint integrity,
   deterministic counters, or bounded findings and would permit false-green
   behavior.

## 3. Goals and Non-Goals

### Goals

- distinguish record maintenance, bounded corrective work, contract changes,
  and external/destructive work;
- continue automatically inside explicit authority and aggregate missing file
  authority into one decision packet;
- reuse evidence until a defined change invalidates it;
- run focused, affected-lane, and final integration verification at distinct
  points;
- make review converge after one complete report and at most one corrective
  re-review for the same scope;
- choose one review topology per execution unit;
- serialize shared-file-dense work;
- checkpoint before a deterministic local limit forces a session handoff;
- resume only when repository, branch, HEAD, authority, and evidence still
  match;
- validate closed legacy and active records under different, auditable
  contracts without rewriting accepted history;
- bound human and JSON finding output while preserving exact total counts;
- keep runtime state ignored and untracked.

### Non-Goals

- executing arbitrary checkpoint `next_action` commands;
- cross-machine checkpoint export/import;
- rewriting closed historical records;
- scanning real external projects as part of this implementation;
- introducing a scheduler, daemon, hosted service, database, or non-stdlib
  runtime dependency;
- treating a capability adapter's completion signal as SAGE-Kit acceptance.

## 4. Runtime State Machine

The state machine has six terminal or actionable outcomes:

| State | Meaning | Required next behavior |
| --- | --- | --- |
| `CONTINUE` | Work is inside current authority and limits. | Continue with the next ladder step. |
| `AUTO_CORRECT` | A C0 change or C1 change inside a corrective envelope is allowed. | Apply the bounded change and run only its required focused verification. |
| `HANDOFF_READY` | State is complete enough for another session and no product decision is needed. | Write/refresh the checkpoint and end the current execution session. |
| `HUMAN_DECISION_REQUIRED` | Product scope, authority, security, or destructive behavior needs a decision. | Emit one aggregated decision packet. |
| `BLOCKED` | An external dependency is unavailable or the same root cause made no progress for two consecutive rounds. | Preserve the checkpoint and report the blocker. |
| `STOP` | Immediate safety or irreversible destructive risk exists. | Stop without mutation beyond safe checkpointing. |

Each decision event returns exactly one outcome:

```text
event
  +-- authorized ordinary work ------------> CONTINUE
  +-- authorized C0/C1 --------------------> AUTO_CORRECT
  +-- local execution limit reached -------> HANDOFF_READY
  +-- product/authority decision needed ---> HUMAN_DECISION_REQUIRED
  +-- unavailable dependency/no progress --> BLOCKED
  +-- immediate destructive risk ----------> STOP
```

A completed action creates a new event and a new decision. An event cannot move
backward merely to repeat review or verification. Counter exhaustion produces
`HANDOFF_READY`, not `STOP`.

## 5. Change Classification and Authority

### 5.1 Change classes

| Class | Scope | Default decision | Verification |
| --- | --- | --- | --- |
| `C0_RECORD_ONLY` | Status, evidence index, spelling, or current-truth synchronization without contract semantics. | `AUTO_CORRECT` when the record owner has write ownership. | Targeted record consistency only. |
| `C1_BOUNDED_CORRECTIVE` | Local reversible repair required by an already-approved acceptance criterion. | `AUTO_CORRECT` only inside the full corrective envelope. | Focused verification plus directly affected lane invalidation. |
| `C2_CONTRACT_AFFECTING` | API, schema, authority, source authority, permissions, state machine, information architecture, or acceptance semantics. | `CONTINUE` only with matching authority; otherwise `HUMAN_DECISION_REQUIRED`. | Relevant semantic lanes. |
| `C3_EXTERNAL_DESTRUCTIVE` | Deployment, migration, credentials, paid operations, external writes, or irreversible behavior. | `HUMAN_DECISION_REQUIRED`, or `STOP` for immediate risk. | Explicitly approved verification plan. |

Classification is an explicit structured input. File extensions alone never
prove a class. A classifier may suggest a class, but ambiguous input escalates
to C2 rather than silently choosing C0/C1.

### 5.2 Bounded Corrective Authority

A C1 request is automatically authorized only when all predicates are true:

- it serves an already-approved acceptance criterion;
- it adds no product feature;
- it changes no external API, security policy, or deployment target;
- every changed path is inside the predeclared corrective file scope;
- it is reversible;
- it names focused verification;
- it does not open a closed approval gate.

If all predicates except file coverage are true, the decision contains one
`AUTHORITY_DELTA` with every uncovered normalized path, each purpose, and a
recommended common scope. It never emits one stop per file. Previously valid
evidence remains reusable unless the eventual approved change intersects its
invalidation surface.

Any other failed predicate produces one aggregated
`HUMAN_DECISION_REQUIRED` packet. C3 never enters a corrective envelope.

### 5.3 Path safety

Repository paths are stored slash-normalized and relative to a canonical
repository root. Runtime checks resolve symlinks and Windows reparse
targets before containment checks. Windows comparisons use case-insensitive
normalization; POSIX comparisons remain case-sensitive. A path that resolves
outside the repository or an allowed scope is rejected even if its lexical path
appears inside.

## 6. Review Topology and Shared-File Density

Every execution unit selects exactly one primary topology:

| Topology | Use | Required checks |
| --- | --- | --- |
| `LIGHT` | Low-risk, local, reversible work. | Focused verification; no independent reviewer by default. |
| `STANDARD` | Bounded implementation or one affected contract/lane. | One implementation review plus affected-lane verification. |
| `HEAVY` | Security, authority, cross-contract, destructive, or multi-lane work. | Wave/lane review plus one final integration review. |

Per-task, per-worker, corrective, lane, and final reviewers are not stacked by
default. An additional reviewer requires a recorded P0/P1, security, authority,
cross-contract, or destructive rationale.

Shared-file density is true when two planned writes overlap, share a file, a
finding changes another task's assumptions, or workers would wait/replay
patches. Dense work selects one integration writer. Other agents may investigate
or review read-only; they may not write shared state.

External skills are optional adapters. SAGE-Kit selects a specific adapter when
useful, but adapter scope, completion, and workflow cannot expand authority,
bypass locks or gates, or redefine project completion.

## 7. Verification Ladder and Evidence

The only ladder is:

```text
focused verification
-> affected-lane verification
-> final integration verification
```

- a local change runs focused verification;
- a lane gate runs only its lane suite;
- full suite, wheel build/install, package discovery, and outside-source smoke
  run only for a stable candidate;
- a new session does not invalidate evidence;
- C0 record maintenance never reruns implementation tests;
- protected hashes are not recomputed unless their covered paths or authority
  changed.

### 7.1 Evidence fingerprint

Every reusable evidence record has this stable structure:

```yaml
evidence_id:
kind:
lane:
base_sha:
head_sha:
covered_paths:
covered_contracts:
command:
dependency_fingerprint:
toolchain_fingerprint:
platform:
authority_version:
result:
```

`kind` distinguishes record consistency, focused, semantic lane, build,
platform, package, and integration evidence. Fingerprints are immutable
observations. Reuse is a policy result; old evidence is never rewritten to
pretend it ran at a newer HEAD.

### 7.2 Invalidation

| Change | Invalidated evidence |
| --- | --- |
| C0 record-only | Record consistency evidence whose record path or direct authority reference changed. |
| C1 local implementation | Focused evidence covering an overlapping path and its directly affected lane. |
| C2 contract/authority/state machine | Evidence covering the changed contract or authority version and corresponding semantic lanes. |
| Build/dependency/package | Build, platform, package, and integration evidence that covers the changed surface. |
| Unrelated unchanged surface | None. Existing evidence remains reusable. |

Path overlap uses canonical containment, not substring matching. Contract overlap
uses exact normalized identifiers. Dependency, toolchain, platform, and
authority fingerprint drift invalidates only evidence that depends on that
dimension.

## 8. Deterministic Limits and Counters

The default execution limits are explicit data:

```yaml
implementation_workers: 1
read_only_review_agents: 2
parallel_agent_waves: 1
corrective_re_review_rounds: 1
full_suite_runs_after_baseline: 1
wheel_install_verification_runs: 1
reviewer_reports_per_scope: 1
repeated_root_cause_without_progress: 2
```

Counters record observable events, not model tokens or subscription usage.
Before an event would exceed a limit, the runtime returns `HANDOFF_READY` and
requires a checkpoint. A second full suite is allowed only when the caller names
the evidence invalidation reason; it is recorded as an exception event rather
than silently resetting the counter. Immediate safety risk still returns
`STOP`.

`reviewer_reports_per_scope` counts first-round reports. Corrective re-review is
counted separately by `corrective_re_review_rounds`, so one complete first report
and one targeted corrective re-review do not conflict.

## 9. Review Convergence Contract

A first review report must be complete for its declared scope and classify every
finding P0-P3. A scope accepts one first report. The one permitted corrective
re-review checks only:

- whether original findings closed;
- whether the fix caused a direct regression;
- whether a new P0/P1 appeared;
- whether a new P2 affects authority or creates false-green risk.

New ordinary P2/P3 findings outside direct regression go to the backlog. They do
not expand the current scope.

Blocking policy:

- P0/P1 always block;
- P2 blocks only for authority, false-green, approval gates, security,
  source-authority, evidence integrity, or validator failure;
- ordinary documentation-consistency P2 may be auto-corrected or accepted with
  concerns;
- P3 never blocks.

Root-cause progress is measured by remaining count and severity. Two consecutive
rounds without material reduction return `BLOCKED`; a single unsuccessful round
does not. Review scope expansion, authority expansion, or a local counter limit
returns `HANDOFF_READY` or `HUMAN_DECISION_REQUIRED` as appropriate.

## 10. Continuity Protocol

The local checkpoint is:

```text
.sagekit/runtime/CURRENT_RUN.json
```

It is ignored by `.gitignore`, must not be tracked, and contains no chat
transcript, credential, secret, or unbounded command output. The schema contains:

```yaml
schema_version:
run_id:
goal:
repository_root:
branch:
base_sha:
head_sha:
authority:
change_class:
completed_work:
open_findings:
evidence_references:
invalidated_evidence:
execution_counters:
next_action:
allowed_paths:
stop_conditions:
created_at:
updated_at:
```

`authority` contains an identifier, version, bounded summary, an internal payload
SHA-256 digest, and optional repository-relative file references with SHA-256
digests. Resume recomputes the payload digest and all available reference
digests. Evidence references contain compact fingerprints or
repository-relative references, never copied logs.

Resume:

1. find and parse the checkpoint;
2. validate schema and field bounds;
3. verify canonical repository root, branch, and exact HEAD;
4. verify authority reference hashes and version;
5. verify referenced evidence fingerprints;
6. return only the compact completed work, open findings, evidence status, and
   `next_action`.

All mismatches are returned in one aggregate. Resume fails closed and performs no
work when any mismatch exists. Missing and corrupt checkpoints use distinct
errors. Clearing removes only the validated checkpoint path.

CLI:

```text
sagekit checkpoint create
sagekit checkpoint status
sagekit resume
sagekit checkpoint clear
```

`resume` validates and emits the next-action packet; it does not execute arbitrary
shell commands. The SAGE-Kit skill can use that packet to continue a new
session without asking the user to copy prior chat history.

## 11. Validation Contract Compatibility

Compatibility is isolated from checkpoint, counters, and reviewer state.

### 11.1 Contract selection

The selector examines the task/evidence pair before validation:

| Record state | Selection |
| --- | --- |
| Both records explicitly declare current v2 metadata and active scope. | Validate strictly with v2. |
| Both records are terminal closed/verified legacy records with no version metadata. | Validate with frozen v1. |
| Both records explicitly declare the same supported frozen version and matching snapshot. | Validate with that frozen version. |
| One record declares metadata and the other does not; versions/scopes differ; active work requests v1; terminal state disagrees; metadata is incomplete. | Fail closed as ambiguous/mixed. |

Once v2 is selected, v2 validation failure is final. The selector never retries
v1. Contract selection is emitted as an auditable finding.

### 11.2 Contract metadata and anti-tamper

Current task and evidence templates declare:

```yaml
validation_contract:
  version: 2
  policy_id: sagekit-task-dispatch-v2
  policy_sha256: 64-lowercase-hex digest declared by the packaged v2 policy
  scope: active
```

Both sides must match each other and the packaged policy. Any changed version,
policy ID, digest, or scope fails before record validation. The v1 policy and
schemas are packaged under a separate immutable resource directory. The current
v2 schemas remain the adopted-project schema surface.

Implicit closed legacy records use the packaged v1 policy identity in the
selection result without rewriting their source files.

### 11.3 Active reconciliation isolation

Closed history is validated as history and then excluded from active duplicate,
lease, lock, and dispatch-board reconciliation. Active records still reconcile
strictly with each other. This prevents a historical lock or duplicate ID from
creating a current false failure while preserving pair-level legacy validation.

### 11.4 Bounded findings

Validators return complete in-memory findings. Presentation applies a fixed
sample limit while preserving:

- total finding count;
- displayed finding count;
- truncated count;
- exact counts by level;
- `path`, `rule`, and `message` for every displayed sample;
- stable JSON key and finding order.

Exit status uses all findings, not only the displayed sample. Truncation can
never hide a failure from the process status.

## 12. Module Boundaries

Planned runtime modules:

| Module | Responsibility |
| --- | --- |
| `sagekit/pathing.py` | Canonical cross-platform repository path and containment operations. |
| `sagekit/change_control.py` | Change classes, corrective envelopes, authority decisions, aggregated deltas, and state outcomes. |
| `sagekit/evidence.py` | Evidence fingerprints, change events, invalidation, and reuse decisions. |
| `sagekit/execution_limits.py` | Deterministic limits, counters, progress tracking, and handoff decisions. |
| `sagekit/review.py` | Topology selection, shared-file density, finding severity, first-report and corrective re-review convergence. |
| `sagekit/continuity.py` | Checkpoint model, bounded JSON persistence, Git/authority/evidence validation, status, resume, and clear. |
| `sagekit/validation_contracts/v1.py` | Frozen legacy policy adapter. |
| `sagekit/validation_contracts/v2.py` | Current contract metadata and strict validation adapter. |
| `sagekit/compatibility.py` | Pair classification, fail-closed contract selection, and active/history partitioning. |
| `sagekit/reporting.py` | Stable bounded human/JSON reports and exact totals. |
| `sagekit/cli.py` | Thin command parsing and delegation only. |

The existing Task Dispatch validator remains the procedural legacy validation
core. It is not given checkpoint, counter, or reviewer responsibilities.
Compatibility chooses a contract before calling it. The adopted-project check
uses the compatibility result to separate historical and active reconciliation.

Packaged resources:

```text
sagekit/resources/contracts/v1/
  policy.json
  task.schema.json
  evidence.schema.json
sagekit/resources/contracts/v2/
  policy.json
```

The v1 schemas are frozen copies of the accepted baseline contract. The v2 policy
digest is referenced by current templates and schemas. Package discovery uses
`importlib.resources`.

## 13. CLI UX and Exit Codes

Existing `check`, `doctor`, and `init` behavior remains compatible. `check` and
`doctor` gain bounded reporting with a documented default and optional
`--max-findings`.

Checkpoint commands accept `--target`; create also accepts goal, authority ID
and version, change class, next action, allowed paths, stop conditions, authority
references, and evidence references. Repeated arguments collect lists.

Exit codes:

- `0`: success/valid/resumable;
- `1`: validation failure, checkpoint mismatch, missing/corrupt checkpoint, or
  human decision required;
- `2`: CLI usage error;
- `3`: unexpected internal error.

Human output is concise. JSON output is deterministic and includes a summary.
No command prints secrets or full checkpoint content by default.

## 14. Failure Handling

- Missing/corrupt checkpoint: fail with a specific rule and remediation.
- Repo/branch/HEAD drift: fail closed with one mismatch packet.
- Authority/evidence hash drift: fail closed and list every mismatch once.
- Runtime content tracked by Git: `FAIL` with rule
  `source-tracked-runtime`.
- C1 outside file scope: one `AUTHORITY_DELTA`.
- C2 without authority or any C3: one decision packet.
- Contract ambiguity/tamper: fail before substantive validation.
- v2 validation failure: return v2 findings without fallback.
- Output overflow: truncate display only; totals and exit status remain exact.
- Counter exhaustion: checkpoint and `HANDOFF_READY`.
- Immediate destructive risk: `STOP`.

## 15. Migration and Backward Compatibility

1. Ship frozen v1 policy/resources and the selector first.
2. Update current source templates and schemas to explicit v2 metadata.
3. Treat unversioned active records as ambiguous and fail closed with a migration
   message.
4. Continue accepting unversioned terminal closed legacy records under v1.
5. Do not edit or synthesize version fields in accepted history.
6. Existing public validator functions remain callable for direct legacy tests;
   the high-level project check uses compatibility selection.
7. Existing CLI commands and exit codes retain their meanings, with additive
   summary fields in JSON.

## 16. Documentation and Skill Guidance

Canonical product guidance will be split into:

- execution economy and authority;
- continuity/checkpoint;
- validation contract compatibility.

The core and skill will route to these documents rather than duplicate every
rule. Status-only C0 maintenance is explicitly record ownership work, not
implementation work. Superpowers capabilities remain individually selectable
adapters rather than a mandatory combined workflow.

### Bootstrap Maintainer Policy

SAGE-Kit does not require its own repository maintainers to govern SAGE-Kit
development with an instantiated SAGE-Kit milestone/phase/ledger workflow.
Source-repository dogfood is a validation mode, not a mandatory control mode.
Maintainers may use a lightweight ordinary engineering workflow to avoid
recursive governance and bootstrap cost.

This exception applies only to maintenance of the SAGE-Kit source repository.
It does not weaken or bypass the governance contract adopted by a target
project, and it cannot be cited by a target project to ignore its own authority,
scope, gate, lock, evidence, or approval rules.

## 17. Tests

Focused unit tests cover:

- C0 does not request implementation verification;
- C1 inside the envelope auto-corrects;
- uncovered C1 paths produce one authority delta;
- C2 invalidates semantic evidence;
- C3 requires a human decision;
- unrelated evidence is reused and relevant diffs invalidate it;
- unrelated P2/P3 findings enter the backlog;
- two no-progress rounds block;
- matching checkpoint resumes and HEAD drift fails closed;
- missing/corrupt checkpoints are clear errors;
- runtime checkpoint paths are ignored and tracked runtime fails source hygiene;
- Windows case normalization and symlink/reparse containment;
- closed legacy selects v1;
- active selects v2;
- mixed records fail closed;
- v2 failure does not fall back;
- policy snapshot tamper fails;
- closed history does not affect active duplicate/lock reconciliation;
- output is bounded while totals stay exact;
- wheel-installed policy/schema resources are discoverable;
- all syntax remains Python 3.10 compatible.

Stable-candidate verification runs exactly one full unit suite after baseline,
one source-repository check, one wheel build/install/outside-source smoke, one
CLI smoke, one synthetic legacy/active/mixed scenario, `git diff --check`, a
tracked-runtime scan, and a project-specific-name leakage scan.

## 18. Rollout

Phase A introduces execution economy, continuity, documentation, skill routing,
and focused tests. Phase B introduces frozen/current validation contracts,
compatibility selection, bounded reporting, resources, CLI integration, and
focused tests. Both phases stay on one branch.

After a stable candidate, two read-only reviewers run once in parallel:

- authority/state/false-green/compatibility/checkpoint/governance;
- tests/CLI/package/cross-platform/performance/bounded-output/docs consistency.

P0/P1 and authority/false-green/validator P2 findings are corrected. Ordinary
documentation P2 findings may be corrected in one batch; P3 is recorded. Only
targeted invalidated verification is rerun, and no second full review wave is
started.
