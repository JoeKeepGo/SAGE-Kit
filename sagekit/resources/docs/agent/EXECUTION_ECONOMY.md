# Execution Economy

This document is the normative SAGE-Kit policy for change classification,
corrective authority, evidence reuse, verification depth, review convergence,
execution limits, and handoff states. When older generic controller or
corrective text would require broader repeated work, this document controls.
Approval gates, security boundaries, and explicit project authority still
control over this policy.

## Change Classification

| Class | Meaning | Normal action |
| --- | --- | --- |
| C0 Record-only | Status, ledger, evidence index, spelling, or current-truth synchronization that does not change contract semantics. | Auto-correct with targeted record consistency verification. |
| C1 Bounded corrective | A local reversible repair required to satisfy an already-approved acceptance criterion. | Auto-correct only inside Bounded Corrective Authority. |
| C2 Contract-affecting | API, schema, permission, state machine, source authority, information architecture, or acceptance semantics. | Require matching authority and the affected semantic review lanes. |
| C3 External/destructive | Deployment, migration, credentials, paid operations, external writes, or irreversible behavior. | Require a human decision; stop immediately only for active safety risk. |

Classification is explicit. A path or extension alone cannot prove C0 or C1.
Ambiguous classification is treated as C2 until resolved.

## Bounded Corrective Authority

C1 is automatically authorized only when all of these predicates are true:

- the change serves an already-approved acceptance criterion;
- it adds no product feature;
- it changes no external API, security policy, or deployment target;
- every changed path is inside a predeclared corrective file scope;
- it is reversible;
- it names focused verification;
- it does not open a closed approval gate.

When only file coverage is missing, return one `AUTHORITY_DELTA`. It lists all
required paths, each purpose, and a recommended common approval boundary. Do not
stop once per file. After approval, reuse all evidence not invalidated by the
approved diff.

C0 is record ownership work, not implementation work. The current record owner
may update it under matching write ownership. Run targeted record consistency
verification against the changed status and its direct authority references.
Do not reload the milestone, rerun implementation tests, rerun review lanes, or
rehash unrelated protected files.

## One Review Topology

Every execution unit chooses one primary review topology:

- `Light`: focused verification; no independent reviewer by default.
- `Standard`: implementation review and affected-lane verification.
- `Heavy`: wave/lane review and one final integration review.

Do not stack per-task, per-worker, corrective, lane, and final reviewers by
default. Add independent review only for P0/P1, security, authority,
cross-contract, or destructive risk, and record the reason.

If planned writers share files or overlapping paths, a finding changes another
task's assumptions, or workers would wait and replay patches, use one integration
writer. Other agents are read-only investigators or reviewers.

## Verification Ladder

Use exactly this ladder:

```text
focused verification
-> affected-lane verification
-> final integration verification
```

A single finding runs only its minimum reproduction and directly affected
focused tests. A lane gate runs only that lane's affected suite. After a
corrective batch, run only targeted verification and targeted re-review for the
affected finding and direct regressions. The required order is implementation,
focused verification, independent review, one corrective batch, targeted
verification, review/corrective closure, stable candidate freeze, and then final
integration verification.

Managed expensive verification is eligible only for a frozen candidate whose
fingerprint matches current inputs. Before candidate freeze, the managed
lifecycle prohibits full suite, retained regression suite, wheel/install,
outside-source or package smoke, and full integration re-review. The fact that
legacy preliminary counters do not consume final-candidate capacity never
authorizes an early run. Harness or teardown failure must first be reduced to a
minimum reproduction; do not rerun the complete suite to diagnose it.

Full suite, retained regression, wheel/install, outside-source/package smoke,
and full integration re-review run once for each matching frozen stable
candidate. Evidence for an existing fingerprint must be reused while its inputs
remain unchanged. A new session does not invalidate evidence. A record-only
change does not invalidate implementation evidence.

Workers have no full-suite authority and reviewers cannot expand verification
authority. A Lane Controller owns only affected-lane verification. The Root or
Final Controller exclusively owns final full-suite authority.

### Verification Attempt Lifecycle

Every admitted final full-suite or wheel/install attempt follows:

```text
PREFLIGHT -> READY -> STARTED -> PASSED | FAILED | ABORTED
```

An ineligible request before candidate freeze is denied before attempt creation,
cannot enter `STARTED`, and increments no counter.
Capability or preflight failures do not consume a candidate verification run.
This applies to preflight for an eligible frozen candidate; it is not an
exception to admission.
A run is consumed atomically when candidate execution starts.
`PREFLIGHT` and `READY`
therefore do not increment counters. Transitioning to `STARTED` increments the
matching final counter exactly once; `PASSED`, `FAILED`, and `ABORTED` after
start remain counted.

Preflight readiness is structured evidence: an attempt id, the candidate
fingerprint when applicable, and named boolean checks. A message alone cannot
authorize `STARTED`. Reusing an attempt id with the same identity is idempotent
and never consumes twice; reusing it for a different identity is rejected.
Candidate mismatch prevents `STARTED`.

Started attempts are checkpointed with their attempt id, kind, stage, candidate,
preflight checks, and lifecycle state so resume cannot consume the same run
again.

### Verification Dependencies

Each verification node declares either no dependencies (`independent`) or a
bounded `depends_on` list. Failure of one verification node skips only dependent successors; independent verification nodes continue and report their own results.
A skipped successor reports `skipped_due_to_dependency`; a node whose
dependencies passed reports `executed`.

This dependency decision is not a general scheduler. Callers retain ownership
of command execution, evidence capture, and candidate lifecycle transitions.

## Stable Candidate

A frozen candidate binds:

```yaml
candidate:
  head_sha:
  diff_hash:
  contract_digest:
  dependency_digest:
  review_closed:
  corrective_batch_closed:
  generation:
  predecessor_digest:
  corrective_batch_id:
  authority_anchor:
  root_cause_id:
  open_findings_count:
  no_progress_rounds:
  convergence_authority_digest:
  convergence_authority_id:
  execution_scope:
  root_cause_family:
  convergence_allowed_paths:
  convergence_invariant:
  finding_severity:
  targeted_review_closed:
  finding_trend:
  fingerprint:
```

Final verification is authorized only when review and the corrective batch are
closed, the candidate fingerprint matches the current HEAD, diff, contracts,
and dependencies, and the worktree has no unexpected changes. A mismatch fails
closed with exact differences and does not consume a run.

One approved corrective batch may invalidate an unverified candidate and
automatically create one successor without human budget approval. The batch id
is bound to the successor, so the same batch cannot create another automatic
candidate. Any change after final verification first returns `HANDOFF_READY`
and persists state and evidence.

When final verification finds a problem, diagnose and fix it with focused tests
and close only the targeted re-review. Any code change requires a successor
candidate; after that successor is frozen, it receives its one new final
verification run.

A later human-approved handoff corrective may create the next generation only
when it binds a non-empty authority anchor, root-cause id, and current finding
count. This is a new authority event, not automatic budget relaxation.
Generation numbers are audit data, not a permanent ceiling. Two approved
rounds with the same root cause and no finding reduction return `BLOCKED`;
finding reduction resets that no-progress count. The system never starts an
automatic candidate or full-suite loop.

### Preauthorized Convergence Window

A Preauthorized Convergence Window is an explicit, opt-in authority contract
for deterministic corrective work in one stable execution unit. Without it,
the existing single automatic successor rule above is unchanged. With it, a
converging sequence may create additional successor candidates without a new
handoff merely because another remote environment layer became visible.

The serialized authority names a stable authority id, execution scope,
root-cause family, component-aware allowed paths, approved invariant,
`implementation-preserving-only` policy, targeted-review requirement, stop
conditions, approver role, and approval reference. It has canonical JSON and a
stable SHA-256 digest. Absolute paths, parent traversal, malformed authority,
or replacement of the authority digest fail closed. The runtime derives
changed paths from Git and checks canonical containment; sibling prefixes,
symlink escape, and implicit expansion into shared, package, or docs paths are
not authorized.

A semantic-preserving implementation corrective changes how an already
approved contract is implemented without changing its invariant. Examples
include cross-platform path representation, a missing test import, shell
quoting, package resource inclusion under the same resource contract, and a
deterministic test harness repair. Touching authority, security, containment,
validator, package, or release-gate implementation does not by itself make the
change policy-changing, but it requires closed targeted review when the
authority says so.

A policy-changing semantic change alters the approved invariant or public
boundary: repository containment, symlink policy, allowed directories,
contract selection, approval authority, required evidence, public behavior,
or a security boundary. It returns `HANDOFF_READY`; the window cannot approve
it automatically. Scope expansion, a new gate or permission, consumer
mutation, test/gate weakening, or unrelated root-cause family also hand off.

Finding-count or severity reduction resets consecutive no-progress rounds. A
structured, targeted-reviewed finding increase may continue only when the
previous fix exposed the next deterministic layer in the same family. The
first unchanged same-root round is recorded; the second returns `BLOCKED`.
Candidate generation is audit data and never a fixed blocking ceiling.

Every successor gets a new fingerprint and predecessor digest while retaining
the authority digest and family. Final full-suite and wheel counters remain
per-candidate, and each candidate can start each final verification kind only
once. The window is not an unlimited retry mechanism. A transient rerun and a
code corrective are different actions; deterministic failures must not be
rerun in the hope of a different result.

## Evidence Fingerprint

Reusable evidence records:

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
candidate_fingerprint:
```

Invalidation rules:

- C0 invalidates only overlapping record consistency evidence.
- C1 invalidates overlapping focused evidence and its directly affected lane.
- C2 invalidates evidence for the changed contract, authority, or semantic lane.
- Build, dependency, or package changes invalidate relevant build, platform,
  package, and integration evidence.
- A different candidate fingerprint invalidates final integration, build,
  platform, and package evidence.
- Unrelated unchanged surfaces remain valid.

Evidence remains an immutable observation at its original HEAD. Reuse is a
separate decision and never rewrites history. Evidence whose fingerprint and
inputs still match must be reused rather than regenerated.

## Deterministic Limits

Limits count visible work events, never model tokens, quotas, or elapsed
subscription budget:

```yaml
implementation_workers: 1
read_only_review_agents: 2
parallel_agent_waves: 1
corrective_re_review_rounds: 1
reviewer_reports_per_scope: 1
repeated_root_cause_without_progress: 2
max_full_suite_runs_per_candidate: 1
max_wheel_install_runs_per_candidate: 1
```

Before an event exceeds its limit, create or refresh the continuity checkpoint
and return `HANDOFF_READY`. Do not return `STOP` merely because a local count was
reached.

```yaml
verification_runs:
  candidate_ineligible:
    allowed_to_run: false
    counter_increment: false
  final_candidate:
    requires_review_closed: true
    requires_corrective_batch_closed: true
    requires_candidate_fingerprint: true
    max_runs_per_candidate: 1
```

Legacy preliminary counters remain readable for checkpoint compatibility but
do not authorize new attempts. A successor candidate created by the one
approved corrective batch has its own single final budget and does not require
manual relaxation.

## Review Convergence Contract

The first reviewer report for a scope must batch all findings and classify them
P0-P3. A corrective re-review checks only closure of original findings, direct
regressions, new P0/P1, and authority or false-green P2.

New ordinary P2/P3 outside direct regression enters backlog instead of expanding
the active scope.

- P0/P1 blocks.
- P2 blocks only for authority, false-green, approval gates, security, source
  authority, evidence integrity, or validator failure.
- Ordinary documentation consistency P2 may be auto-corrected or accepted with
  concerns.
- P3 does not block.

The same root cause with no material reduction for two consecutive rounds is
`BLOCKED`. A fixed round count alone is not a blocker; reaching a local review
limit is `HANDOFF_READY`.

## Runtime Outcomes

- `CONTINUE`: authorized ordinary execution.
- `AUTO_CORRECT`: C0 or C1 inside its corrective envelope.
- `HANDOFF_READY`: resumable state with no product decision.
- `HUMAN_DECISION_REQUIRED`: product, authority, security, or destructive
  decision; aggregate all decisions into one packet.
- `BLOCKED`: unavailable external dependency or two no-progress rounds for the
  same root cause.
- `STOP`: immediate safety or destructive risk only.

Use `docs/agent/CONTINUITY_PROTOCOL.md` for automatic checkpoint and resume.
