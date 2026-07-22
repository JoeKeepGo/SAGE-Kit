# Final Review Packet Template

Use this packet from Final Review Controller to Project Manager Controller.

Role and review/corrective separation are canonical at
`docs/agent/GOVERNANCE_LEVELS.md#sage-auth-005` and
`docs/agent/GOVERNANCE_LEVELS.md#sage-auth-006`. This packet retains the
read-only verdict, corrective delegation, closure, and Project Manager decision
inputs.

```markdown
Initial Verdict: `ACCEPTABLE`, `ACCEPTABLE_WITH_CONCERNS`, `NEEDS_CORRECTION`, or `BLOCKED`

Current Final Verdict: `ACCEPTABLE`, `ACCEPTABLE_WITH_CONCERNS`, `NEEDS_CORRECTION`, or `BLOCKED`

Verdict Finalization Status: `NOT_APPLICABLE`, `PENDING_CORRECTION`,
`VERDICT_FINALIZED_FROM_RECEIPT`, or `FINALIZED_BY_REVIEW`

Milestone:

Review Packet Owner: `Final Review Controller` or `<named author>`

Primary Capability:

Coder Packet Ref:

Review Scope:

Governance Review:
- Controller level reviewed:
- Worker levels reviewed:
- Heavy controls enabled only when triggered:
- Over-governance found:
- Under-governance found:

Permission Review:
- Final Review mode: `READ_ONLY_REVIEW`
- Final Review corrective orchestration authorized: `<yes/no; delegates only to
  separately CORRECTIVE_AUTHORIZED workers and does not grant controller writes>`
- Mode allowed by execution packet:
- Write/corrective authority preserved:
- Submit/cleanup authority preserved:
- Permission overreach found:
- Permission underreach found:

Capability Discovery Used:
- Capability registry checked:
- SAGE-Kit boundary preserved:
- Skills used:
- superpowers skills used:
- superpowers boundary violations:
- Plugins/connectors used:
- Tools used:
- Capability adapters reviewed:
- Adapter authorization/fallback reviewed:
- External capability evidence verified:
- External planning output mapped to SAGE-Kit docs:
- Missing capabilities and fallback:

Review Delegation Plan:
- Controller role:
- Review workers:
- Validation lanes:
- Parallel checks allowed:
- Files or evidence to inspect:
- Stop conditions:

Review Workers:

| Worker | Focus | Status | Evidence | Findings |
|---|---|---|---|---|
| `<worker>` | `<phase/contract/runtime/security/etc>` | `<status>` | `<evidence>` | `<findings>` |

Worker Governance Findings:

| Worker | Governance Level | Permission Mode | Appropriate | Finding |
|---|---|---|---|---|
| `<worker>` | `Light, Standard, or Heavy` | `<mode>` | `<yes/no>` | `<finding or none>` |

Independent Checks:

Parallelism Reassessment:
- Execution shape reviewed: `SERIAL`, `PARALLEL_WITH_WAVES`, `PARALLEL_PHASES`, or `STOP_FOR_PM`
- Wave readiness reviewed:
- Cosmetic wave plan found:
- Safe as executed: `<yes/no/blocked>`
- Serial gates protected:
- Unsafe parallelism found:
- Recommended future execution shape:

Coder Execution Mode Review:
- Coder self-executed: `<yes/no>`
- Self-execution allowed by packet: `<yes/no/n/a>`
- Self-execution stayed narrow: `<yes/no/n/a>`
- Worker dispatch should have been used: `<yes/no>`
- Additional review risk:

Worktree Review:
- Worktree isolation authorized: `<yes/no/n/a>`
- Worktree map reviewed:
- File boundaries preserved:
- Runtime or dependency conflicts:
- Integration evidence:
- Stale worktrees:
- Submit authority preserved:
- Cleanup authority preserved:
- Submit recommendation:
- Cleanup recommendation:

Task Dispatch Review:
- Task Dispatch active: `<yes/no>`
- Task/evidence records reviewed:
- Validator command:
- Validator result:
- L0-L4 evidence gaps:
- Resource lock or lease gaps:
- Mock or fallback concerns:
- Orphan task/evidence records:
- Cross-task exclusive-lock conflicts:
- Records needing Project Manager decision:

State Truth Reconciliation Gate:
- Applicable / `N/A` reason:
- Profile reference: `docs/profiles/task-dispatch/DISPATCH_PROFILE.md`
- Owners and mutation authority checked:
- Mismatches or corrective/handoff reference:
- Result: `PASS`, `BLOCKED`, or `N/A`

Phase Findings:

| Phase | Verdict | Findings | Required Corrections |
|---|---|---|---|
| `<phase>` | `<verdict>` | `<findings>` | `<corrections or none>` |

Finding Classification:

| Finding ID | Severity | Classification | Corrective Allowed | Required Packet / Decision | Verification | Re-Review |
|---|---|---|---|---|---|---|
| `<id>` | `<P0/P1/P2/P3>` | `AUTO_CORRECTIVE`, `PM_DECISION`, `BLOCKED`, or `DEFER` | `<yes/no>` | `<packet/ref/decision/blocker>` | `<commands/evidence>` | `<yes/no>` |

Severity Acceptance Gate:
- P0/P1 open findings: `<none/list>`
- P2 findings that block acceptance because they affect authority, false-green,
  approval gates, security boundaries, validator/gate-ready requirements,
  source authority, or evidence integrity: `<none/list>`
- Ordinary documentation consistency P2 findings accepted with concerns or
  auto-corrected: `<none/list>`
- P3 follow-up findings: `<none/list>`
- Acceptance blocked by severity gate: `<yes/no>`

Contract Findings:

Runtime Findings:

Security / Data Hygiene Findings:

Approval Gate Findings:

Memory / Ledger / Closeout Findings:

Corrective Packet Required: `<yes/no>`

Corrective Packet:
- `<path or inline summary>`

Reviewer-Authored Deterministic Closure Predicates (optional; record before
corrective editing):

| Finding ID | Finding Classification | Closure Eligibility Class | Exact Files And Fields | Authoritative Value And Source Ref | Allowed Diff | Closure Commands | Out-Of-Scope Protected Hashes | Precommitted Final Verdict | Closure Receipt Owner | Closure Receipt Destination |
|---|---|---|---|---|---|---|---|---|---|---|
| `<id>` | `AUTO_CORRECTIVE` | `MECHANICAL_STATUS` | `<files/fields>` | `<value/ref>` | `<exact diff>` | `<commands>` | `<out-of-scope hashes>` | `ACCEPTABLE` or `ACCEPTABLE_WITH_CONCERNS` | `<original Final Review Controller/named packet author; not fixer>` | `<this review packet/output>` |

Do not add or broaden a predicate after corrective editing begins.

Corrective Closure:
- Closure mode: `NONE`, `READ_ONLY_PACKET_ONLY`, `AUTO_OPEN_AUTHORIZED`,
  `AUTO_CONTINUE_CONVERGING`, `DETERMINISTIC_PREDICATE`,
  `PM_DECISION_REQUIRED`, or `BLOCKED`
- If required, packet/handoff/blocker provided: `<yes/no/n/a>`
- Auto-open authorized by execution packet: `<yes/no/n/a>`
- Corrective round / convergence budget:
- Authorized corrective packet or boundary:
- Findings trend: `<decreasing/same/increasing>`
- Severity trend: `<decreasing/same/increasing>`
- Same root cause stalled for two consecutive rounds: `<yes/no>`
- Scope expanded: `<yes/no>`
- New authority, false-green, approval-gate, security, validator/gate-ready,
  source-authority, or evidence-integrity risk: `<yes/no>`
- Continue automatically under convergence rule inside authorized boundary:
  `<yes/no>`
- Re-review owner:
- Re-review status: `NOT_STARTED`, `IN_REVIEW`, `PASSED`, `FAILED`, or `NOT_REQUIRED_DETERMINISTIC`
- Deterministic rule: use `NOT_REQUIRED_DETERMINISTIC`; never record deterministic closure as `PASSED` re-review
- Re-review evidence:
- Affected review workers/subagents/lanes rerun: `<yes/no/n/a>`
- If not rerun, narrow diff review rationale:
- If no review invocation, use the Deterministic Verdict Finalization fields
  below; do not create a second closure or re-review status.
- "Corrective required: yes" without packet/handoff/blocker: `<yes/no>`

Review Scope Selection:
- Selected re-review scope: `deterministic closure (no review invocation)`,
  `targeted status/evidence lanes`,
  `Final Review narrow diff (targeted submode)`, `full affected lanes`, or
  `full A-E/project review`
- Reason targeted review is enough:
- Reason full review is required:
- Ledger/evidence/status-only change: `<yes/no>`
- Semantic, permission, source authority, information architecture, contract,
  runtime, security, approval gate, or validator meaning changed: `<yes/no>`
- Reviewer-authored mechanical predicate existed before fix: `<yes/no>`
- Predicate matched exactly and closure receipt recorded: `<yes/no/n/a>`

Deterministic Verdict Finalization (only after an initial `NEEDS_CORRECTION`):
- Finding closure status: `AUTO_CLOSED_BY_PREDICATE`
- All blocking findings closed: `<yes/no>`
- Precommitted Final Verdict: `ACCEPTABLE` or `ACCEPTABLE_WITH_CONCERNS`
- Closure Receipt Owner:
- Closure Receipt Ref:
- Closure Receipt Destination:
- Finalized by original Final Review Controller or named review packet author:
  `<yes/no>`
- Verdict finalization status: `VERDICT_FINALIZED_FROM_RECEIPT`
- Finalized verdict:
- Mechanical finalization does not re-review files, start a reviewer, or create
  a new Final Review pass: `<confirmed/not confirmed>`
- Project Manager acceptance remains pending: `<yes/no>`

Corrective Delegation:
- Allowed executor: `Coder Controller`, `Corrective Worker`, or `Project Manager decision required`
- Allowed capabilities:
- Capability adapter boundaries:
- SAGE-Kit boundary for external capabilities:
- Stop conditions:

Residual Risks:

Recommended Project Manager Decision:

Re-Review Required: `<yes/no; no only with NOT_REQUIRED_DETERMINISTIC>`
```

The recommendation and decision fields instantiate
`docs/agent/GOVERNANCE_LEVELS.md#sage-auth-005`.
