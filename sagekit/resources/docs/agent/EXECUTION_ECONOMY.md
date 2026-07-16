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

A local edit runs focused verification. A lane gate runs only that lane's suite.
The required order is implementation, focused verification, independent review,
one corrective batch, targeted verification, review/corrective closure, stable
candidate freeze, and then final integration verification.

A full suite or wheel/install run before review and corrective closure is
`preliminary`. It may provide development feedback, but it does not consume a
final-candidate budget and is never merge-gate evidence. Full suite,
wheel/install, package discovery, and outside-source smoke run once for each
matching frozen stable candidate. A new session does not invalidate evidence.
A record-only change does not invalidate implementation evidence.

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
  fingerprint:
```

Final verification is authorized only when review and the corrective batch are
closed, the candidate fingerprint matches the current HEAD, diff, contracts,
and dependencies, and the worktree has no unexpected changes. A mismatch fails
closed with exact differences and does not consume a run.

One approved corrective batch may invalidate an unverified candidate and
automatically create its successor without human budget approval. Candidate
generation is bounded: a second regeneration, or any change after final
verification, returns `HANDOFF_READY`. It never starts an automatic full-suite
loop.

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
separate decision and never rewrites history.

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
  preliminary:
    purpose: development feedback
    consumes_final_candidate_budget: false
  final_candidate:
    requires_review_closed: true
    requires_corrective_batch_closed: true
    requires_candidate_fingerprint: true
    max_runs_per_candidate: 1
```

Preliminary runs never decrement or exhaust final-candidate capacity. A
successor candidate created by the one approved corrective batch has its own
single final budget and does not require manual relaxation.

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
